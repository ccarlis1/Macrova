/* global React, cx, Icon, TopBar, Section, StickyCTA */
const Dp = window.MACROVA_DATA;

function PantryScreen({ onFlow }) {
  const [tab, setTab] = React.useState("review");
  const pantry = Dp.pantry;
  const tabs = [["review", `Needs review · ${pantry.needsReview.length}`], ["custom", "Custom"], ["recent", "Recent"], ["usda", "USDA"]];

  return (
    <>
      <TopBar title="Pantry" action={
        <button className="icon-btn" aria-label="Create" onClick={() => onFlow("ingredient")}><Icon name="plus" size={16}/></button>
      }/>

      <section className="section" style={{ paddingBottom: 0 }}>
        <div className="search-bar">
          <Icon name="search" size={16}/>
          <span>Search {pantry.counts.resolved.toLocaleString()} USDA + custom items</span>
          <span className="kbd">⌘K</span>
        </div>
        <p className="muted" style={{ fontSize: 13, margin: "10px 2px 0" }}>
          {pantry.counts.resolved} resolved · <b style={{ color: "var(--accent-deep)" }}>{pantry.counts.unresolved} unresolved</b> · {pantry.counts.custom} custom
        </p>
      </section>

      <div style={{ marginTop: 16, marginBottom: 4 }}>
        <div className="scroll-row">
          {tabs.map(([k, l]) => (
            <button key={k} className={cx("pill", tab === k && "on")} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      {tab === "review" && (
        <Section title="Needs review" sub="Agent-matched against USDA — confirm or override">
          {pantry.needsReview.map(u => {
            const confCls = u.conf >= 0.85 ? "hi" : u.conf > 0 ? "mid" : "none";
            return (
              <div className="resolve-card" key={u.id}>
                <div className="rc-head">
                  <Icon name="warning" size={18} sw={1.8}/>
                  <span className="rc-q">{u.query}</span>
                  <span className={cx("conf", confCls)}>{u.conf > 0 ? Math.round(u.conf * 100) + "%" : "no match"}</span>
                </div>
                <div className="rc-match">{u.match || "No USDA match found — create a custom ingredient with your own macros."}</div>
                {u.kcal != null && (
                  <div className="row gap-sm" style={{ marginBottom: 12, flexWrap: "wrap" }}>
                    <span className="tag">{u.kcal} kcal/100g</span>
                    <span className="tag">{u.p}g P</span>
                    <span className="tag">{u.c}g C</span>
                    <span className="tag">{u.f}g F</span>
                  </div>
                )}
                <div className="rc-actions">
                  {u.conf > 0
                    ? <><button className="btn btn-primary btn-sm">Accept match</button><button className="btn btn-sm">Override</button></>
                    : <><button className="btn btn-primary btn-sm" onClick={() => onFlow("ingredient")}>+ Create custom</button><button className="btn btn-sm">Skip</button></>}
                </div>
              </div>
            );
          })}
        </Section>
      )}

      {tab === "custom" && (
        <Section title="Custom ingredients" sub={`${pantry.custom.length} of ${pantry.counts.custom} · your own & branded items`}>
          <div className="custom-list">
            {pantry.custom.map(it => (
              <div className="ci" key={it.id}>
                <div className="av"><Icon name="pantry" size={18}/></div>
                <div style={{ flex: 1 }}><div className="nm">{it.name}</div><div className="mt">{it.kcal} kcal · {it.p}g P · {it.c}g C · {it.f}g F · per 100g</div></div>
                <span className="tag">{it.src}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {tab === "recent" && (
        <Section title="Recently used" sub="Pulled into recent recipes & plans">
          <div className="row gap-sm" style={{ flexWrap: "wrap" }}>
            {pantry.recent.map(n => <span key={n} className="tag">{n}</span>)}
          </div>
        </Section>
      )}

      {tab === "usda" && (
        <Section title="USDA FoodData Central" sub="Search remote · resolves to per-100g macros + micros">
          <div className="card" style={{ padding: 18, textAlign: "center" }}>
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: "var(--bg-soft)", color: "var(--ink-3)", display: "grid", placeItems: "center", margin: "0 auto 12px" }}><Icon name="cloud" size={22}/></div>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Type a food name to search USDA</div>
            <div className="muted" style={{ fontSize: 13, lineHeight: 1.5 }}>All FDC types: SR Legacy, Foundation, Survey, Branded. Tap a result to resolve & save into your pantry.</div>
            <div className="row gap-sm" style={{ justifyContent: "center", marginTop: 14, flexWrap: "wrap" }}>
              <span className="tag">SR Legacy only</span>
              <span className="mock-tag">live search wires to /api/ingredients</span>
            </div>
          </div>
        </Section>
      )}

      <StickyCTA label="Can't find something?" sub="Add a custom ingredient">
        <button className="btn btn-primary" onClick={() => onFlow("ingredient")}>+ Custom</button>
      </StickyCTA>
    </>
  );
}

window.PantryScreen = PantryScreen;
