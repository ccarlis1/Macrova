/* global React, cx, Icon, MacroSplit, MicroRows */
const Db = window.MACROVA_DATA;

function RecipeBuilderFlow({ onClose }) {
  const base = Db.builder;
  const [ings, setIngs] = React.useState(base.ingredients.map(i => ({ ...i })));
  const [steps, setSteps] = React.useState([...base.steps]);
  const [servings, setServings] = React.useState(base.servings);
  const [mode, setMode] = React.useState("serving"); // serving | total
  const [microOpen, setMicroOpen] = React.useState(false);

  // totals from per-100g values
  const totals = ings.reduce((a, i) => {
    const k = i.qty / 100;
    return { kcal: a.kcal + i.kcal * k, p: a.p + i.p * k, c: a.c + i.c * k, f: a.f + i.f * k };
  }, { kcal: 0, p: 0, c: 0, f: 0 });
  const div = mode === "serving" ? servings : 1;
  const show = { kcal: totals.kcal / div, p: totals.p / div, c: totals.c / div, f: totals.f / div };
  const microScale = mode === "serving" ? 1 : servings;

  const setQty = (id, qty) => setIngs(prev => prev.map(i => i.id === id ? { ...i, qty: Math.max(0, qty) } : i));
  const setUnit = (id, unit) => setIngs(prev => prev.map(i => i.id === id ? { ...i, unit } : i));
  const removeIng = (id) => setIngs(prev => prev.filter(i => i.id !== id));
  const addIng = () => setIngs(prev => [...prev, { id: "i" + Date.now(), name: "New ingredient", qty: 100, unit: "g", kcal: 100, p: 5, c: 10, f: 5, src: "Custom" }]);
  const setStep = (i, v) => setSteps(prev => prev.map((s, j) => j === i ? v : s));
  const addStep = () => setSteps(prev => [...prev, ""]);
  const removeStep = (i) => setSteps(prev => prev.filter((_, j) => j !== i));

  const dailyKcal = Db.profile.targetKcal;

  return (
    <>
      <div className="scrim" onClick={onClose}/>
      <div className="sheet">
        <div className="flow-head">
          <button className="back" onClick={onClose}><Icon name="back" size={18}/></button>
          <div className="ttl">Edit recipe<small>Live nutrition · server-calculated</small></div>
          <div className="right"><button className="btn btn-primary btn-sm">Update</button></div>
        </div>

        <div className="flow-body">
          {/* Name + meta */}
          <section className="section" style={{ paddingTop: 18 }}>
            <div className="card" style={{ padding: 18 }}>
              <div className="field" style={{ marginBottom: 16 }}>
                <label className="f-label" style={{ marginBottom: 6 }}>Recipe name</label>
                <input className="input lg" defaultValue={base.name} style={{ width: "100%", border: "1px solid var(--line-strong, #ddd)", borderRadius: "var(--r-1)", padding: "13px 15px", font: "inherit", fontSize: 17, fontWeight: 600 }}/>
              </div>
              <div className="row gap-md">
                <div style={{ flex: 1 }}>
                  <label className="f-label" style={{ marginBottom: 6, display: "block" }}>Servings</label>
                  <div className="num-pill">
                    <button onClick={() => setServings(s => Math.max(1, s - 1))}>−</button>
                    <span className="val">{servings}</span>
                    <button onClick={() => setServings(s => s + 1)}>+</button>
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <label className="f-label" style={{ marginBottom: 6, display: "block" }}>Cook time</label>
                  <div className="qty-input">
                    <input type="number" defaultValue={base.cookTime}/>
                    <select><option>min</option></select>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Live nutrition card */}
          <section className="section">
            <div className="card nutri-card" style={{ padding: 22 }}>
              <div className="live-nutri-head">
                <h3 style={{ fontSize: 17, fontWeight: 600, margin: 0, letterSpacing: "-0.01em" }}>Nutrition</h3>
                <div className="segmented" style={{ width: 168 }}>
                  <button className={mode === "serving" ? "on" : ""} onClick={() => setMode("serving")}>Per serving</button>
                  <button className={mode === "total" ? "on" : ""} onClick={() => setMode("total")}>Total</button>
                </div>
              </div>
              <div className="live-source"><span className="dot"/>Server-calculated · {mode === "serving" ? `${servings} servings` : "whole recipe"}</div>

              <div className="macros-primary" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="macro-tile cal" style={{ gridColumn: "span 2", background: "var(--ink-1)", color: "#fff", borderRadius: "var(--r-2)", padding: "14px 16px" }}>
                  <div className="label" style={{ color: "rgba(255,255,255,0.65)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>Calories</div>
                  <div className="val" style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em" }}>{Math.round(show.kcal)}<span style={{ fontSize: 13, fontWeight: 500, color: "rgba(255,255,255,0.65)", marginLeft: 3 }}>kcal</span></div>
                  <div style={{ fontSize: 11, color: "rgba(255,255,255,0.55)", marginTop: 4 }}>≈ {Math.round(show.kcal / dailyKcal * 100)}% of {dailyKcal.toLocaleString()} daily</div>
                </div>
                {[["Protein", show.p, "var(--m-pro)", Db.profile.targetP], ["Carbs", show.c, "var(--m-carb)", Db.profile.targetC], ["Fat", show.f, "var(--m-fat)", null]].map(([l, v, color, tgt], idx) => (
                  <div className="macro-tile" key={l} style={{ background: "var(--bg-tint)", borderRadius: "var(--r-2)", padding: "14px 16px", gridColumn: idx === 2 ? "span 2" : "auto" }}>
                    <div className="label" style={{ color, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, marginBottom: 4 }}>{l}</div>
                    <div className="val" style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>{Math.round(v)}<span style={{ fontSize: 13, fontWeight: 500, color: "var(--ink-3)", marginLeft: 3 }}>g</span></div>
                    <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>{tgt ? `${Math.round(v / tgt * 100)}% of ${tgt}g daily` : `Within ${Db.profile.fatMin}–${Db.profile.fatMax}g target`}</div>
                  </div>
                ))}
              </div>

              <MacroSplit p={show.p} c={show.c} f={show.f}/>

              <div className="micro-disclose" style={{ marginTop: 22, borderTop: "1px solid var(--line)", paddingTop: 18 }}>
                <button className={cx("micro-toggle", microOpen && "open")} onClick={() => setMicroOpen(o => !o)} style={{ width: "100%", background: "transparent", border: 0, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0", fontSize: 14, fontWeight: 500 }}>
                  <span className="left" style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                    <span>{microOpen ? "Hide micronutrients" : "View micronutrients"}</span>
                    <span className="count" style={{ fontSize: 12, color: "var(--ink-3)", fontWeight: 400 }}>{base.micros.length} tracked</span>
                  </span>
                  <span style={{ transition: "transform .2s", transform: microOpen ? "rotate(180deg)" : "none", color: "var(--ink-3)", display: "inline-flex" }}><Icon name="chevronDown" size={16}/></span>
                </button>
                {microOpen && (
                  <div style={{ marginTop: 16 }}>
                    <MicroRows micros={base.micros} scale={microScale}/>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Ingredients editor */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Ingredients</h2><p className="section-sub">Quantities update nutrition automatically · {ings.length} items</p></div></div>
            {ings.map(i => {
              const calc = Math.round(i.kcal * i.qty / 100);
              return (
                <div className="ing-edit" key={i.id}>
                  <div className="ie-top">
                    <div style={{ minWidth: 0 }}>
                      <div className="ie-name">{i.name}</div>
                      <div className="ie-src">{i.src} · {i.kcal} kcal/100g</div>
                    </div>
                    <div className="ie-kcal">{calc} kcal</div>
                  </div>
                  <div className="ie-controls">
                    <div className="qty-input">
                      <input type="number" value={i.qty} min="0" step="5" onChange={e => setQty(i.id, parseFloat(e.target.value) || 0)}/>
                      <select value={i.unit} onChange={e => setUnit(i.id, e.target.value)}>
                        {base.units.map(u => <option key={u} value={u}>{u}</option>)}
                      </select>
                    </div>
                    <button className="delete-btn" onClick={() => removeIng(i.id)} aria-label="Remove"><Icon name="trash" size={16}/></button>
                  </div>
                </div>
              );
            })}
            <button className="ing-add" onClick={addIng}><Icon name="plus" size={16}/> Add ingredient</button>
          </section>

          {/* Steps editor */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Instructions</h2><p className="section-sub">One step at a time · clear, short directions</p></div></div>
            {steps.map((s, i) => (
              <div className="step-edit" key={i}>
                <div className="num">{i + 1}</div>
                <textarea value={s} onChange={e => setStep(i, e.target.value)} rows={2}/>
                <button className="delete-btn" onClick={() => removeStep(i)} aria-label="Remove step"><Icon name="close" size={16}/></button>
              </div>
            ))}
            <button className="ing-add" onClick={addStep}><Icon name="plus" size={14}/> Add step</button>
          </section>

          <section className="section">
            <div className="card card-hover" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, cursor: "pointer", background: "var(--accent-soft)", borderColor: "transparent" }}>
              <div style={{ width: 38, height: 38, borderRadius: "50%", background: "#fff", color: "var(--accent-deep)", display: "grid", placeItems: "center", flex: "0 0 auto" }}><Icon name="sparkle" size={18}/></div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14.5, color: "var(--accent-deep)" }}>Generate variations on the server</div>
                <div style={{ fontSize: 12.5, color: "var(--accent-deep)", opacity: 0.8 }}>LLM drafts validated recipes from this theme</div>
              </div>
            </div>
          </section>
        </div>

        <div className="sticky-cta">
          <div className="label">{ings.length} ingredients · {steps.length} steps<b>{Math.round(totals.kcal / servings)} kcal / serving</b></div>
          <button className="btn" onClick={onClose}>Discard</button>
          <button className="btn btn-primary" onClick={onClose}>Save recipe</button>
        </div>
      </div>
    </>
  );
}

window.RecipeBuilderFlow = RecipeBuilderFlow;
