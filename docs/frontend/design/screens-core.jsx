/* global React, cx, recipeImg, RECIPE_BY, Icon, TopBar, Section, RecipeImg, MacroSplit, MicroRows, StickyCTA, gradFor */
const D = window.MACROVA_DATA;

// ============================================================ TODAY
function TodayScreen({ onOpenRecipe, onOpenMeal, onFlow }) {
  const today = D.plan.schedule[2];
  const upNext = today.meals.find(m => m.idx === 3);
  const upNextRecipe = upNext ? RECIPE_BY(upNext.recipeId) : null;
  const suggested = D.recipes.slice(2, 7);

  return (
    <>
      <TopBar/>
      <div className="greet">
        <div className="hello">Wednesday, May 8</div>
        <h1 className="name">Good evening, Sam.</h1>
      </div>

      <div className="banner">
        <h2>Almost there</h2>
        <p>You've eaten 1,490 of 2,200 kcal so far. Dinner takes you home.</p>
        <div className="stats">
          <div className="stat"><div className="l">Protein</div><div className="v">112<span className="u">/165 g</span></div></div>
          <div className="stat"><div className="l">Calories</div><div className="v">1,490<span className="u">/2,200</span></div></div>
          <div className="stat"><div className="l">Workouts</div><div className="v">1<span className="u">/1 today</span></div></div>
        </div>
      </div>

      {/* Agent entry */}
      <Section title="Plan with words" sub="Describe what you want — Macrova drafts it">
        <div className="card card-hover" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }} onClick={() => onFlow("agent")}>
          <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--accent-soft)", color: "var(--accent-deep)", display: "grid", placeItems: "center", flex: "0 0 auto" }}>
            <Icon name="sparkle" size={20}/>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>“High-protein, ≤30 min, no peanuts…”</div>
            <div className="muted" style={{ fontSize: 13 }}>Parse → match → generate the gaps</div>
          </div>
          <Icon name="chevron" size={18}/>
        </div>
      </Section>

      <Section title="Up next, dinner" sub="Generated for tonight at 7:00 PM">
        {upNextRecipe && (
          <div className="recipe-hero card-hover" onClick={() => onOpenRecipe(upNextRecipe)}>
            <RecipeImg id={upNextRecipe.id}>
              <span className="badge dot">Generated</span>
              <button className="heart" aria-label="Pin">♡</button>
            </RecipeImg>
            <div className="body">
              <div className="meta-row"><span>{upNextRecipe.time} min</span><span className="dot"/><span>1 serving</span><span className="dot"/><span>Italian</span></div>
              <h3>{upNextRecipe.name}</h3>
              <p className="desc">{upNextRecipe.desc}</p>
              <div className="macros">
                <span className="m"><b>{upNextRecipe.kcal}</b>kcal</span>
                <span className="m"><b>{upNextRecipe.p}</b>g protein</span>
                <span className="m"><b>{upNextRecipe.c}</b>g carbs</span>
                <span className="m"><b>{upNextRecipe.f}</b>g fat</span>
              </div>
            </div>
          </div>
        )}
      </Section>

      <Section title="Today's plan" sub="3 meals · 1 batch from Sunday" link="Edit" onLink={() => onFlow("config")}>
        <div className="day-card">
          <div className="day-meals">
            {today.meals.map(m => {
              const r = RECIPE_BY(m.recipeId);
              const time = m.idx === 1 ? "8:00" : m.idx === 2 ? "13:00" : "19:00";
              if (!r) return null;
              return (
                <div key={m.idx} className={cx("meal-slot", m.pinned && "pinned")} onClick={() => onOpenMeal({ ...m, dayIndex: today.dayIndex })}>
                  <div className="time">{time}</div>
                  <div className="thumb" style={{ background: gradFor(r.id) }}/>
                  <div className="info"><div className="name">{r.name}</div><div className="sub">{r.kcal} kcal · {r.p}g protein · {r.time}m</div></div>
                  {m.pinned && <span className="pin">●</span>}
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      <Section title="Suggested for tomorrow" sub="From your library, fits your remaining macros"/>
      <div className="carousel">
        {suggested.map(r => (
          <div key={r.id} className="recipe-mini" onClick={() => onOpenRecipe(r)}>
            <RecipeImg id={r.id}/>
            <div className="name">{r.name}</div>
            <div className="sub">{r.kcal} kcal · {r.time} min</div>
          </div>
        ))}
      </div>

      <StickyCTA label="Plan ready" sub="7 days · 21 meals">
        <button className="btn btn-primary" onClick={() => onFlow("config")}>Re-generate</button>
      </StickyCTA>
    </>
  );
}

// ============================================================ PLAN
function PlanScreen({ onOpenMeal, onFlow }) {
  const [openDay, setOpenDay] = React.useState(3);
  const wt = D.plan.weeklyTotals;
  return (
    <>
      <TopBar title="This week" action={
        <button className="icon-btn" aria-label="Regenerate" onClick={() => onFlow("config")}><Icon name="refresh" size={16}/></button>
      }/>

      <Section title="May 6 – May 12" sub="7 days · 99% on calories · 99% on protein" style={{ paddingBottom: 0 }}/>
      <section className="section" style={{ paddingTop: 12 }}>
        <div className="row gap-sm" style={{ flexWrap: "wrap" }}>
          <span className="tag accent">● 18 generated</span>
          <span className="tag" style={{ background: "var(--pinned-soft)", color: "var(--pinned)", borderColor: "transparent" }}>● 3 pinned</span>
          <span className="tag">● 1 leftover batch</span>
        </div>
      </section>

      <section className="section">
        {D.plan.schedule.map(day => {
          const dow = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][day.dayIndex - 1];
          const isOpen = openDay === day.dayIndex;
          const cal = day.meals.reduce((s, m) => s + (RECIPE_BY(m.recipeId)?.kcal || 0), 0);
          const prot = day.meals.reduce((s, m) => s + (RECIPE_BY(m.recipeId)?.p || 0), 0);
          const hasIssue = day.meals.some(m => m.state === "warn" || m.state === "empty");
          return (
            <div key={day.dayIndex} className="day-card">
              <div className="day-head" onClick={() => setOpenDay(isOpen ? null : day.dayIndex)}>
                <div className="left">
                  <h4>{dow} · May {day.dayIndex + 5}</h4>
                  <div className="sub">{day.meals.filter(m => m.recipeId).length} meals{day.workouts.length ? ` · ${day.workouts.length} workout` : ""}{hasIssue ? " · needs attention" : ""}</div>
                </div>
                <div className="right"><b>{cal.toLocaleString()} kcal</b><span>{prot}g protein</span></div>
              </div>
              {isOpen && (
                <div className="day-meals">
                  {day.meals.map(m => {
                    const r = RECIPE_BY(m.recipeId);
                    const time = m.idx === 1 ? "8:00" : m.idx === 2 ? "13:00" : "19:00";
                    if (!r) return (
                      <div key={m.idx} className="meal-slot empty" onClick={() => onFlow("config")}>+ Add recipe to slot {m.idx} ({time})</div>
                    );
                    return (
                      <div key={m.idx} className={cx("meal-slot", m.pinned && "pinned")} onClick={() => onOpenMeal({ ...m, dayIndex: day.dayIndex })}>
                        <div className="time">{time}</div>
                        <div className="thumb" style={{ background: gradFor(r.id) }}/>
                        <div className="info">
                          <div className="name">{r.name}</div>
                          <div className="sub">{r.kcal} kcal · {r.p}g P · {r.time}m{m.state === "warn" ? " · ⚠ " + (m.note || "") : ""}</div>
                        </div>
                        {m.pinned && <span className="pin">●</span>}
                      </div>
                    );
                  })}
                  {day.workouts.map((w, i) => (
                    <div key={"w" + i} className="meal-slot" style={{ background: "transparent", border: "1.5px dashed var(--line)" }}>
                      <div className="time">PM</div>
                      <div className="thumb" style={{ background: "var(--bg-soft)", display: "grid", placeItems: "center", color: "var(--ink-3)" }}><Icon name="workout" size={18}/></div>
                      <div className="info"><div className="name">Workout · {w.intensity} intensity</div><div className="sub">After meal {w.after}</div></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </section>

      <Section title="Plan summary" sub="Weekly totals vs targets">
        <div className="card" style={{ padding: 18 }}>
          <div className="macro-grid">
            <div className="macro-cell"><div className="l">Calories</div><div className="v">{wt.kcal.toLocaleString()}<span className="u">/15,400</span></div><div className="bar"><span style={{ width: "99%" }}/></div></div>
            <div className="macro-cell"><div className="l">Protein</div><div className="v">{wt.p}<span className="u">/1,155 g</span></div><div className="bar"><span className="pro" style={{ width: "99%" }}/></div></div>
            <div className="macro-cell"><div className="l">Carbs</div><div className="v">{wt.c}<span className="u">/1,540 g</span></div><div className="bar"><span className="carb" style={{ width: "99%" }}/></div></div>
            <div className="macro-cell"><div className="l">Fat</div><div className="v">{wt.f}<span className="u">/510 g</span></div><div className="bar"><span className="fat" style={{ width: "100%" }}/></div></div>
          </div>
        </div>
      </Section>

      <Section title="Micronutrients" sub="Weekly totals vs RDI × 7 days">
        <div className="card" style={{ padding: 18 }}>
          <div className="plan-micro">
            {D.plan.micros.map(m => {
              const pct = Math.round(m.val / m.target * 100);
              const cls = pct < 80 ? "low" : pct > 110 ? "over" : "";
              return (
                <div className="pm" key={m.key}>
                  <div className="top"><span className="nm">{m.label}</span><span className="vv">{pct}%</span></div>
                  <div className="bar"><span className={cls} style={{ width: Math.min(100, pct) + "%" }}/></div>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      <Section title="Things to know">
        {D.plan.warnings.map((w, i) => (
          <div className="card" style={{ padding: 0, marginBottom: 10 }} key={i}>
            <div className="advisory">
              <div className={cx("ai", w.level === "warn" ? "warn" : "info")}>{w.level === "warn" ? "!" : "i"}</div>
              <div style={{ flex: 1 }}>
                <div className="at">{w.type === "sodium" ? "Sodium near weekly cap" : "Vitamin D at 90% of weekly target"}</div>
                <div className="ad">{w.text}</div>
              </div>
            </div>
          </div>
        ))}
        <div className="card card-hover" style={{ padding: 16, cursor: "pointer", display: "flex", alignItems: "center", gap: 12 }} onClick={() => onFlow("failure")}>
          <div className="ai warn" style={{ width: 36, height: 36, borderRadius: "50%", display: "grid", placeItems: "center", background: "var(--accent-soft)", color: "var(--accent-deep)", fontWeight: 700 }}>?</div>
          <div style={{ flex: 1 }}>
            <div className="at" style={{ fontWeight: 600, fontSize: 14.5 }}>Last generation hit a snag</div>
            <div className="ad muted" style={{ fontSize: 13 }}>See why a high-protein day was infeasible →</div>
          </div>
        </div>
      </Section>

      <StickyCTA label="Generated 12m ago" sub="Re-generate from scratch">
        <button className="btn" onClick={() => onFlow("config")}>Edit pool</button>
        <button className="btn btn-primary" onClick={() => onFlow("config")}>Generate</button>
      </StickyCTA>
    </>
  );
}

// ============================================================ RECIPES
function RecipesScreen({ onOpenRecipe, onFlow }) {
  const [filter, setFilter] = React.useState("all");
  const featured = D.recipes[6];
  const groups = [
    { title: "Quick weeknight", sub: "Under 25 minutes", ids: ["recipe_001","recipe_005","recipe_006","recipe_009","recipe_013","recipe_016"] },
    { title: "High protein", sub: "≥ 35g per serving", ids: ["recipe_003","recipe_004","recipe_007","recipe_012","recipe_015"] },
    { title: "Batch & freezer", sub: "Cook once, eat four times", ids: ["recipe_012","recipe_014","recipe_008"] },
    { title: "Vegetarian", sub: "Plant-forward favorites", ids: ["recipe_001","recipe_008","recipe_010","recipe_011","recipe_014","recipe_016"] },
  ];
  return (
    <>
      <TopBar title="Recipes" action={
        <button className="icon-btn" aria-label="New recipe" onClick={() => onFlow("builder")}><Icon name="plus" size={16}/></button>
      }/>

      <Section title="Featured this week" sub="Hand-picked from your library">
        <div className="recipe-hero card-hover" onClick={() => onOpenRecipe(featured)}>
          <RecipeImg id={featured.id}>
            <span className="badge">Top match · 96%</span>
            <button className="heart">♡</button>
          </RecipeImg>
          <div className="body">
            <div className="meta-row"><span>{featured.time} min</span><span className="dot"/><span>High protein</span><span className="dot"/><span>Gluten-free</span></div>
            <h3>{featured.name}</h3>
            <p className="desc">{featured.desc}</p>
            <div className="macros">
              <span className="m"><b>{featured.kcal}</b>kcal</span>
              <span className="m"><b>{featured.p}</b>g protein</span>
              <span className="m"><b>{featured.f}</b>g fat</span>
            </div>
          </div>
        </div>
      </Section>

      <div style={{ marginTop: 18, marginBottom: 4 }}>
        <div className="scroll-row">
          {[["all","All recipes"],["quick","Quick"],["highp","High protein"],["veg","Vegetarian"],["batch","Batch"],["asian","Asian"],["italian","Italian"],["lowcarb","Low-carb"]].map(([k, l]) => (
            <button key={k} className={cx("pill", filter === k && "on")} onClick={() => setFilter(k)}>{l}</button>
          ))}
        </div>
      </div>

      {groups.map(g => (
        <Section key={g.title} title={g.title} sub={g.sub} link="See all">
          <div className="carousel" style={{ paddingLeft: 0, paddingRight: 0, marginLeft: -20, marginRight: -20 }}>
            {g.ids.slice(0, 6).map(id => {
              const r = RECIPE_BY(id);
              if (!r) return null;
              return (
                <div key={id} className="recipe-mini" onClick={() => onOpenRecipe(r)}>
                  <RecipeImg id={r.id}/>
                  <div className="name">{r.name}</div>
                  <div className="sub">{r.kcal} kcal · {r.time} min</div>
                </div>
              );
            })}
          </div>
        </Section>
      ))}

      <Section title="All recipes" sub={`${D.recipes.length} in your library`}>
        {D.recipes.map(r => (
          <div key={r.id} className="recipe-row" onClick={() => onOpenRecipe(r)}>
            <div className="thumb" style={{ background: gradFor(r.id) }}/>
            <div className="info"><div className="name">{r.name}</div><div className="sub">{r.tags.slice(0, 2).join(" · ")} · {r.time} min</div></div>
            <div className="end"><b>{r.kcal}</b><span>{r.p}g P</span></div>
          </div>
        ))}
      </Section>

      <StickyCTA label="Have a recipe in mind?" sub="Add to library">
        <button className="btn btn-primary" onClick={() => onFlow("builder")}>+ New recipe</button>
      </StickyCTA>
    </>
  );
}

// ============================================================ YOU
function YouScreen({ onFlow }) {
  const p = D.profile;
  return (
    <>
      <TopBar title="You"/>

      <section className="section">
        <div className="card" style={{ padding: 18, display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 56, height: 56, borderRadius: "50%", background: "linear-gradient(135deg, #f0a890, #c46c4e)", display: "grid", placeItems: "center", color: "#fff", fontWeight: 600, fontSize: 22, flex: "0 0 auto" }}>SC</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>{p.name}</div>
            <div className="muted" style={{ fontSize: 13 }}>Adult male, 19–30 · {p.targetKcal.toLocaleString()} kcal/day</div>
          </div>
          <button className="btn btn-sm">Edit</button>
        </div>
      </section>

      <Section title="Daily targets" sub="What you're aiming for each day">
        <div className="card" style={{ padding: 18 }}>
          <div className="macro-grid">
            <div className="macro-cell"><div className="l">Calories</div><div className="v">{p.targetKcal.toLocaleString()}<span className="u"> kcal</span></div></div>
            <div className="macro-cell"><div className="l">Protein</div><div className="v">{p.targetP}<span className="u"> g · {p.proteinPct}%</span></div></div>
            <div className="macro-cell"><div className="l">Carbs</div><div className="v">{p.targetC}<span className="u"> g · {p.carbPct}%</span></div></div>
            <div className="macro-cell"><div className="l">Fat</div><div className="v">{p.fatMin}–{p.fatMax}<span className="u"> g · {p.fatPct}%</span></div></div>
          </div>
          <div className="row between" style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
            <div><div style={{ fontWeight: 600, fontSize: 14 }}>Calorie deficit mode</div><div className="muted" style={{ fontSize: 12.5 }}>Auto-reduce target by 15%</div></div>
            <div className={cx("segmented")} style={{ width: 120 }}>
              <button className={!p.deficit ? "on" : ""}>Off</button>
              <button className={p.deficit ? "on" : ""}>On</button>
            </div>
          </div>
        </div>
      </Section>

      <Section title="Schedule template" sub="Your default weekly rhythm" link="Edit" onLink={() => onFlow("config")}>
        <div className="card">
          <div className="day-meals" style={{ padding: 14 }}>
            {D.scheduleTemplate.map(s => (
              <div key={s.time} className="meal-slot">
                <div className="time">{s.time}</div>
                <div className="thumb" style={{ background: "var(--accent-soft)", display: "grid", placeItems: "center", color: "var(--accent-deep)", fontWeight: 600 }}>{s.slot[0]}</div>
                <div className="info"><div className="name">{s.slot}</div><div className="sub">{s.note} · busyness {s.busyness}/4</div></div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Allergies & preferences" sub="Hard-blocks and gentle nudges for the planner">
        <div className="card" style={{ padding: 18 }}>
          <div className="f-label">Allergies</div>
          <div className="row gap-sm" style={{ flexWrap: "wrap", marginBottom: 16 }}>
            {p.allergies.map(a => <span key={a} className="tag accent" style={{ textTransform: "capitalize" }}>{a}</span>)}
            <button className="tag" style={{ borderStyle: "dashed", cursor: "pointer" }}>+ Add</button>
          </div>
          <div className="f-label">Likes</div>
          <div className="row gap-sm" style={{ flexWrap: "wrap", marginBottom: 16 }}>
            {p.likes.map(a => <span key={a} className="tag" style={{ textTransform: "capitalize" }}>{a}</span>)}
          </div>
          <div className="f-label">Dislikes</div>
          <div className="row gap-sm" style={{ flexWrap: "wrap" }}>
            {p.dislikes.map(a => <span key={a} className="tag" style={{ textTransform: "capitalize" }}>{a}</span>)}
          </div>
        </div>
      </Section>

      <Section title="Planner engine" sub="How plans get generated">
        <div className="settings-list">
          {[
            ["Planning mode", "Assisted · cache strict"],
            ["Ingredient source", "Local JSON + USDA"],
            ["LLM credentials", p.llmValidated ? "Validated ✓" : "Not set"],
            ["Micronutrient targets", "Full RDI · weekly τ = 1.0"],
          ].map(([l, v]) => (
            <div key={l} className="row"><div className="l flex-1" style={{ padding: "14px 16px", borderBottom: "1px solid var(--line-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}><span>{l}</span><span className="muted" style={{ fontSize: 13 }}>{v} ›</span></div></div>
          ))}
        </div>
      </Section>

      <Section title="Coming soon" sub="Visualized in this design but not yet wired">
        <div className="card" style={{ padding: 18 }}>
          {[
            ["Pinned meals", "Lock specific meals so the planner schedules around them"],
            ["Meal-prep batches", "Cook once Sunday, fill the week"],
            ["Recipe discovery", "Suggestions to fill nutrient gaps"],
          ].map(([t, d]) => (
            <div key={t} className="row" style={{ padding: "10px 0", borderBottom: "1px solid var(--line-soft)" }}>
              <div style={{ flex: 1 }}><div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{t}</div><div className="muted" style={{ fontSize: 13 }}>{d}</div></div>
              <span className="mock-tag">Concept</span>
            </div>
          ))}
        </div>
      </Section>

      <div style={{ height: 110 }}/>
    </>
  );
}

Object.assign(window, { TodayScreen, PlanScreen, RecipesScreen, YouScreen });
