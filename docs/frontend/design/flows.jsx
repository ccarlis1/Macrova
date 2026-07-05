/* global React, cx, Icon, RECIPE_BY, gradFor, MacroSplit */
const Df = window.MACROVA_DATA;

// ============================================================ PLANNER CONFIG
function PlannerConfigFlow({ onClose, onGenerate }) {
  const p = Df.profile;
  const cfg = Df.plannerConfig;
  const [days, setDays] = React.useState(3);
  const [mode, setMode] = React.useState(cfg.planningMode);
  const [source, setSource] = React.useState(cfg.ingredientSource);
  const [deficit, setDeficit] = React.useState(false);
  const [perDay, setPerDay] = React.useState(cfg.perDay.map(d => ({ ...d, meals: [...d.meals], workouts: [...d.workouts] })));
  const [pool, setPool] = React.useState(new Set(cfg.poolSelectedIds));

  // keep perDay length in sync with days
  React.useEffect(() => {
    setPerDay(prev => {
      const next = [...prev];
      while (next.length < days) next.push({ day: next.length + 1, meals: [1, 2, 3], workouts: [] });
      return next.slice(0, days);
    });
  }, [days]);

  const setMealCount = (di, n) => setPerDay(prev => prev.map((d, i) => i === di ? { ...d, meals: Array.from({ length: n }, (_, k) => (d.meals[k] || 2)), workouts: d.workouts.filter(w => w < n) } : d));
  const setBusy = (di, mi, b) => setPerDay(prev => prev.map((d, i) => i === di ? { ...d, meals: d.meals.map((m, j) => j === mi ? b : m) } : d));
  const toggleWorkout = (di, gap) => setPerDay(prev => prev.map((d, i) => {
    if (i !== di) return d;
    const has = d.workouts.includes(gap);
    if (has) return { ...d, workouts: d.workouts.filter(w => w !== gap) };
    if (d.workouts.length >= 2) return d;
    return { ...d, workouts: [...d.workouts, gap].sort() };
  }));
  const togglePool = (id) => setPool(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const modeOpts = [["deterministic", "Deterministic"], ["assisted_cached", "Assisted (cache)"], ["assisted_live", "Assisted (live)"]];

  return (
    <>
      <div className="scrim" onClick={onClose}/>
      <div className="sheet">
        <div className="flow-head">
          <button className="back" onClick={onClose}><Icon name="back" size={18}/></button>
          <div className="ttl">New plan<small>Configure horizon, schedule & pool</small></div>
        </div>
        <div className="steps-prog"><span className="on"/><span className="on"/><span className="on"/><span/><span/></div>

        <div className="flow-body">
          {/* 01 Targets */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>01 · Targets</h2><p className="section-sub">Pulled from your profile</p></div></div>
            <div className="card" style={{ padding: 18 }}>
              <div className="row between" style={{ alignItems: "baseline" }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                  <span style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em" }}>{(deficit ? Math.round(p.targetKcal * 0.85) : p.targetKcal).toLocaleString()}</span>
                  <span className="muted" style={{ fontSize: 14 }}>kcal/day</span>
                </div>
                <span className="tag">{p.targetP}g P · {p.targetC}g C · {p.fatMin}–{p.fatMax}g F</span>
              </div>
              <div className="row between" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
                <div><div style={{ fontWeight: 600, fontSize: 14 }}>Calorie deficit mode</div><div className="muted" style={{ fontSize: 12.5 }}>Auto-reduce target by 15%</div></div>
                <div className="segmented" style={{ width: 110 }}>
                  <button className={!deficit ? "on" : ""} onClick={() => setDeficit(false)}>Off</button>
                  <button className={deficit ? "on" : ""} onClick={() => setDeficit(true)}>On</button>
                </div>
              </div>
            </div>
          </section>

          {/* 02 Horizon */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>02 · Horizon</h2><p className="section-sub">How many days to plan</p></div></div>
            <div className="card" style={{ padding: 18 }}>
              <div className="chip-row">
                {[1, 2, 3, 4, 5, 6, 7].map(n => (
                  <button key={n} className={cx("chip-pick", days === n && "on")} onClick={() => setDays(n)}>{n}</button>
                ))}
              </div>
            </div>
          </section>

          {/* 03 Engine */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>03 · Engine</h2><p className="section-sub">Planning mode & nutrition source</p></div></div>
            <div className="card" style={{ padding: 18 }}>
              <div className="f-label">Planning mode</div>
              <div className="segmented" style={{ marginBottom: 6 }}>
                {modeOpts.map(([k, l]) => <button key={k} className={mode === k ? "on" : ""} onClick={() => setMode(k)}>{l}</button>)}
              </div>
              <p className="field-help">{mode === "deterministic" ? "Solver-only, no LLM. Fast and fully reproducible." : "Uses the server LLM. " + (mode === "assisted_cached" ? "Cache-strict — falls back if a slot misses." : "Live — can synthesize missing slots on demand.")}</p>
              {mode !== "deterministic" && (
                <div className="row gap-sm" style={{ marginTop: 8 }}><span className="tag accent"><Icon name="check" size={12}/> LLM validated</span></div>
              )}
              <div className="f-label" style={{ marginTop: 18 }}>Ingredient source</div>
              <div className="segmented">
                <button className={source === "local" ? "on" : ""} onClick={() => setSource("local")}>Local JSON</button>
                <button className={source === "api" ? "on" : ""} onClick={() => setSource("api")}>USDA API</button>
              </div>
              <p className="field-help">{source === "local" ? "Resolves recipe nutrition from custom_ingredients.json on the server." : "Resolves via USDA FoodData Central. Requires USDA_API_KEY on the API server."}</p>
            </div>
          </section>

          {/* 04 Schedule */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>04 · Schedule</h2><p className="section-sub">Meals, busyness band & workouts per day</p></div></div>
            {perDay.map((d, di) => {
              const n = d.meals.length;
              const gaps = n >= 2 ? Array.from({ length: n - 1 }, (_, i) => i + 1) : [];
              return (
                <div className="day-config" key={di}>
                  <div className="dc-head"><span className="t">Day {di + 1}</span><span className="m">{n} meals · {d.workouts.length} workout</span></div>
                  <div className="f-label">Meals per day</div>
                  <div className="chip-row" style={{ marginBottom: 16 }}>
                    {[1, 2, 3, 4, 5, 6].map(c => <button key={c} className={cx("chip-pick", n === c && "on")} onClick={() => setMealCount(di, c)} style={{ minWidth: 36, height: 36 }}>{c}</button>)}
                  </div>
                  <div className="f-group" style={{ marginBottom: 16 }}>
                    {d.meals.map((b, mi) => (
                      <div className="busy-row" key={mi}>
                        <span className="bl">Meal {mi + 1}</span>
                        <div className="busy-seg">
                          {[1, 2, 3, 4].map(lvl => <button key={lvl} className={b === lvl ? "on" : ""} onClick={() => setBusy(di, mi, lvl)}>{lvl}</button>)}
                        </div>
                      </div>
                    ))}
                  </div>
                  {gaps.length > 0 && (
                    <>
                      <div className="f-label">Workouts (between meals)</div>
                      <div className="wo-chips">
                        {gaps.map(g => {
                          const on = d.workouts.includes(g);
                          return (
                            <button key={g} className={cx("wo-chip", on ? "on" : "add")} onClick={() => toggleWorkout(di, g)}>
                              {on ? <><Icon name="workout" size={13}/> After meal {g} <span className="x">×</span></> : <>+ After meal {g}</>}
                            </button>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
            <p className="field-help">Busyness 1 (5 min snack) → 4 (45+ min cook). The solver matches recipes to each band.</p>
          </section>

          {/* 05 Pool */}
          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>05 · Recipe pool</h2><p className="section-sub">{pool.size} of {Df.recipes.length} selected</p></div></div>
            {Df.recipes.slice(0, 8).map(r => {
              const on = pool.has(r.id);
              return (
                <div key={r.id} className={cx("pool-row", on && "on")} onClick={() => togglePool(r.id)}>
                  <div className="pool-check"><Icon name="check" size={14} sw={2.4}/></div>
                  <div className="pr-thumb" style={{ background: gradFor(r.id) }}/>
                  <div className="pr-info"><div className="n">{r.name}</div><div className="s">{r.kcal} kcal · {r.p}g P · {r.time} min</div></div>
                </div>
              );
            })}
            <p className="field-help">Only server-synced recipes are used by the planner. Selecting more gives the solver room to hit every target.</p>
          </section>
        </div>

        <div className="sticky-cta">
          <div className="label">{days}-day plan<b>{pool.size} recipes in pool</b></div>
          <button className="btn btn-primary" onClick={onGenerate}><Icon name="sparkle" size={15}/> Generate</button>
        </div>
      </div>
    </>
  );
}

// ============================================================ AGENT
function AgentFlow({ onClose, onApply }) {
  const a = Df.agent;
  return (
    <>
      <div className="scrim" onClick={onClose}/>
      <div className="sheet">
        <div className="flow-head">
          <button className="back" onClick={onClose}><Icon name="back" size={18}/></button>
          <div className="ttl">Plan from text<small>Agent · parse → match → generate</small></div>
        </div>
        <div className="flow-body">
          <section className="section" style={{ paddingTop: 18 }}>
            <div className="agent-prompt">
              <div className="ap-k">You said</div>
              <p className="ap-q">“{a.prompt}”</p>
              <div className="row gap-sm" style={{ marginTop: 14 }}>
                <button className="btn btn-sm"><Icon name="edit" size={14}/> Edit</button>
                <button className="btn btn-sm"><Icon name="mic" size={14}/> Re-record</button>
              </div>
            </div>
          </section>

          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Parsed</h2><p className="section-sub">Server · plan-from-text · conf {a.conf.toFixed(2)}</p></div></div>
            <div className="card" style={{ padding: "6px 18px 14px" }}>
              {a.parsed.map(row => (
                <div className="parse-row" key={row.label}>
                  <span className="pk">{row.label}</span>
                  <span className={cx("tag", row.ok ? "" : "accent")} style={{ textTransform: "capitalize" }}>{row.value}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Matched</h2><p className="section-sub">{a.matches.length} of {a.matches.length + a.generate.length} slots from your library</p></div></div>
            {a.matches.map(m => {
              const r = RECIPE_BY(m.id);
              const hi = m.score >= 0.8;
              return (
                <div className="match-card" key={m.id}>
                  <div className="mc-thumb" style={{ background: gradFor(m.id) }}/>
                  <div className="mc-info"><div className="n">{r?.name}</div><div className="s">match · {m.score.toFixed(2)} · {r?.kcal} kcal · {r?.p}g P</div></div>
                  <div className={cx("mc-badge", hi ? "hi" : "mid")}><Icon name="check" size={15} sw={2.4}/></div>
                </div>
              );
            })}
          </section>

          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Generating gaps</h2><p className="section-sub">LLM synthesizes the {a.generate.length} missing slots</p></div></div>
            {a.generate.map((g, i) => (
              <div className={cx("gen-row", g.state === "queued" && "pending")} key={i}>
                {g.state === "running"
                  ? <div className="spinner"/>
                  : <div className={cx("gen-badge", g.state === "done" && "done")}>{g.state === "done" ? <Icon name="check" size={13} sw={2.6}/> : null}</div>}
                <div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 600 }}>{g.name}</div><div className="muted" style={{ fontSize: 12, marginTop: 1 }}>{g.meta}</div></div>
                {g.state === "running" && <button className="btn btn-sm">Cancel</button>}
              </div>
            ))}
          </section>
        </div>

        <div className="sticky-cta">
          <div className="label">{a.matches.length} matched · {a.generate.length} generating<b>Apply to a new 3-day plan</b></div>
          <button className="btn btn-primary" onClick={onApply}><Icon name="sparkle" size={15}/> Apply</button>
        </div>
      </div>
    </>
  );
}

// ============================================================ FAILURE
function FailureFlow({ onClose }) {
  const [traceOpen, setTraceOpen] = React.useState(false);
  const fixes = [
    { ic: "plus", t: "Add 3+ high-protein recipes", d: "Library has 9 candidates ≥ 35g protein." },
    { ic: "edit", t: "Lower protein to 145g", d: "Stays inside 0.8g/lb floor for your weight." },
    { ic: "refresh", t: "Switch to assisted (live)", d: "Server LLM can synthesize a missing slot." },
  ];
  return (
    <>
      <div className="scrim" onClick={onClose}/>
      <div className="sheet">
        <div className="flow-head">
          <button className="back" onClick={onClose}><Icon name="back" size={18}/></button>
          <div className="ttl">Couldn't plan<small>Infeasibility diagnosis</small></div>
        </div>
        <div className="flow-body">
          <section className="section" style={{ paddingTop: 18 }}>
            <div className="fail-hero">
              <div className="fk"><Icon name="warning" size={14}/> Infeasible</div>
              <p className="ft">Your protein target of <em>160g/day</em> can't be reached with the 12 selected recipes.</p>
            </div>
          </section>

          <section className="section">
            <div className="card" style={{ padding: 18 }}>
              <div className="row between" style={{ alignItems: "flex-start" }}>
                <div><div className="f-label" style={{ marginBottom: 4 }}>Hardest constraint</div><div style={{ fontSize: 15, fontWeight: 600 }}>Protein floor</div></div>
                <span style={{ fontWeight: 600, color: "var(--accent-deep)", fontVariantNumeric: "tabular-nums" }}>−24g</span>
              </div>
              <div className="macro-cell bar" style={{ background: "var(--line)", height: 6, borderRadius: 999, marginTop: 12, overflow: "hidden" }}><span style={{ display: "block", height: "100%", width: "85%", background: "var(--m-carb)", borderRadius: 999 }}/></div>
            </div>
          </section>

          <section className="section">
            <div className="section-head"><div><h2 className="section-title" style={{ fontSize: 18 }}>Suggested fixes</h2></div></div>
            <div className="card" style={{ padding: "4px 18px" }}>
              {fixes.map((f, i) => (
                <div className="fix-row" key={i}>
                  <div className="fi"><Icon name={f.ic} size={16}/></div>
                  <div style={{ flex: 1 }}><div className="ft2">{f.t}</div><div className="fd">{f.d}</div></div>
                  <Icon name="chevron" size={16}/>
                </div>
              ))}
            </div>
          </section>

          <section className="section">
            <div className="disclose" onClick={() => setTraceOpen(o => !o)} style={{ cursor: "pointer" }}>
              <div className="disclose summary" style={{ padding: "14px 16px", fontWeight: 600, fontSize: 15, display: "flex", justifyContent: "space-between" }}>
                <span>Solver trace</span>
                <span style={{ transform: traceOpen ? "rotate(90deg)" : "none", transition: "transform .18s", color: "var(--ink-3)" }}>›</span>
              </div>
              {traceOpen && (
                <div style={{ padding: "0 16px 16px" }}>
                  <pre className="trace">{`infeasible: protein floor 160g ↔ pool max 136g
  · 12 recipes, ⌀ 28.4g protein/serving
  · binding: Σ protein < 7 × 160
  · suggested: pool ≥ 14 with σ ≥ 32g`}</pre>
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="sticky-cta">
          <div className="label">Generation halted<b>Adjust pool or targets</b></div>
          <button className="btn btn-primary" onClick={onClose}>Edit plan</button>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { PlannerConfigFlow, AgentFlow, FailureFlow });
