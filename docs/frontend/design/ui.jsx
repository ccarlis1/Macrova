/* global React */
// Shared UI primitives for the combined Macrova prototype.
const { useState, useEffect, useRef } = React;
const D = window.MACROVA_DATA;

function cx(...x) { return x.filter(Boolean).join(" "); }

const IMG_MAP = {
  recipe_001: "warm", recipe_002: "warm", recipe_003: "cool",
  recipe_004: "warm", recipe_005: "warm", recipe_006: "berry",
  recipe_007: "salmon", recipe_008: "warm", recipe_009: "greens",
  recipe_010: "cream", recipe_011: "greens", recipe_012: "warm",
  recipe_013: "greens", recipe_014: "warm", recipe_015: "greens",
  recipe_016: "warm",
};
const recipeImg = (id) => IMG_MAP[id] || "warm";
const RECIPE_BY = (id) => D.recipes.find(r => r.id === id);
const THEME = {
  salmon: { a: "#f0a890", b: "#d77c5e", c: "#a85539" },
  bowl:   { a: "#d4c89a", b: "#b8a868", c: "#8a7a3e" },
  greens: { a: "#b8d4a8", b: "#88a872", c: "#58783e" },
  warm:   { a: "#f4c89a", b: "#d8985e", c: "#a06030" },
  cool:   { a: "#c8d8e0", b: "#88a8b8", c: "#506878" },
  cream:  { a: "#efe6d4", b: "#c8b890", c: "#968558" },
  berry:  { a: "#d8a8c0", b: "#a87090", c: "#785068" },
};
const themeColors = (id) => THEME[recipeImg(id)] || THEME.warm;
function gradFor(id) {
  const t = themeColors(id);
  return `linear-gradient(135deg, ${t.a}, ${t.b} 60%, ${t.c})`;
}

// ---------- Icons ----------
function Icon({ name, size = 20, sw = 1.8 }) {
  const p = {
    today: <circle cx="12" cy="12" r="9"/>,
    plan: <><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/></>,
    recipes: <><path d="M5 4h14v6a7 7 0 0 1-14 0V4z"/><path d="M5 20h14"/></>,
    pantry: <><path d="M4 7h16M5 7l1 13h12l1-13M9 7V4h6v3M10 11v6M14 11v6"/></>,
    you: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    back: <path d="M15 18l-6-6 6-6"/>,
    search: <><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></>,
    chevron: <path d="M9 6l6 6-6 6"/>,
    chevronDown: <polyline points="6 9 12 15 18 9"/>,
    close: <path d="M18 6L6 18M6 6l12 12"/>,
    check: <polyline points="4 12 10 18 20 6"/>,
    sparkle: <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z"/>,
    workout: <path d="M6 7v10M18 7v10M3 10v4M21 10v4M6 12h12"/>,
    refresh: <path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/>,
    edit: <path d="M3 21l4-1 11-11-3-3L4 17l-1 4zM14 6l3 3"/>,
    trash: <><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    warning: <path d="M12 3l9 16H3L12 3zM12 9v5M12 17v.5"/>,
    mic: <><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></>,
    cloud: <path d="M7 18a4 4 0 0 1 0-8 6 6 0 0 1 11-2 4 4 0 0 1 0 8"/>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0 }}>
      {p[name]}
    </svg>
  );
}

// ---------- Top bar ----------
function TopBar({ title, action }) {
  return (
    <div className="topbar">
      {title
        ? <div style={{ fontWeight: 600, fontSize: 17, letterSpacing: "-0.01em" }}>{title}</div>
        : <div className="brand"><span className="brand-mark"/>Macrova</div>}
      {action !== undefined
        ? action
        : <button className="icon-btn" aria-label="Settings">⚙</button>}
    </div>
  );
}

// ---------- Tab bar ----------
function TabBar({ active, onChange }) {
  const tabs = [
    { id: "today", label: "Today" },
    { id: "plan", label: "Plan" },
    { id: "recipes", label: "Recipes" },
    { id: "pantry", label: "Pantry" },
    { id: "you", label: "You" },
  ];
  return (
    <nav className="tabbar" role="tablist">
      {tabs.map(t => (
        <button key={t.id} className={cx("tab", active === t.id && "on")} onClick={() => onChange(t.id)}>
          <Icon name={t.id} size={22} sw={active === t.id ? 2.2 : 1.7}/>
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  );
}

// ---------- Section header ----------
function Section({ title, sub, link, onLink, children, style }) {
  return (
    <section className="section" style={style}>
      <div className="section-head">
        <div>
          <h2 className="section-title">{title}</h2>
          {sub && <p className="section-sub">{sub}</p>}
        </div>
        {link && <button className="section-link" onClick={onLink}>{link}</button>}
      </div>
      {children}
    </section>
  );
}

// ---------- Recipe image block ----------
function RecipeImg({ id, className, children, style }) {
  return (
    <div className={cx("img", recipeImg(id), "img-grain", className)}
      style={{ background: gradFor(id), ...style }}>
      {children}
    </div>
  );
}

// ---------- Macro split bar ----------
function MacroSplit({ p, c, f }) {
  const pk = p * 4, ck = c * 4, fk = f * 9;
  const sum = pk + ck + fk || 1;
  const pp = Math.round(pk / sum * 100), cp = Math.round(ck / sum * 100), fp = 100 - pp - cp;
  return (
    <>
      <div className="macro-split">
        <span className="seg pro" style={{ width: pp + "%" }}/>
        <span className="seg carb" style={{ width: cp + "%" }}/>
        <span className="seg fat" style={{ width: fp + "%" }}/>
      </div>
      <div className="split-legend">
        <span><i className="pro"/> Protein {pp}%</span>
        <span><i className="carb"/> Carbs {cp}%</span>
        <span><i className="fat"/> Fat {fp}%</span>
      </div>
    </>
  );
}

// ---------- Micronutrient bar rows (grouped) ----------
function MicroRows({ micros, scale = 1 }) {
  const groups = {};
  micros.forEach(m => { (groups[m.group] = groups[m.group] || []).push(m); });
  return (
    <div className="micro-list">
      {Object.entries(groups).map(([g, items]) => (
        <React.Fragment key={g}>
          <div className="micro-grp-title">{g}</div>
          {items.map(m => {
            const v = m.val * scale;
            const pct = Math.round(v / m.target * 100);
            const cls = pct < 25 ? "low" : pct > 110 ? "over" : "";
            const vs = v < 10 ? v.toFixed(1) : Math.round(v);
            return (
              <div className="micro-r" key={m.name}>
                <span className="nm">{m.name}</span>
                <span className="bar"><span className={cls} style={{ width: Math.min(100, pct) + "%" }}/></span>
                <span className="pct">{pct}%</span>
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}

// ---------- Sticky CTA ----------
function StickyCTA({ label, sub, children }) {
  return (
    <div className="sticky-cta">
      <div className="label">{label}<b>{sub}</b></div>
      {children}
    </div>
  );
}

Object.assign(window, {
  cx, recipeImg, RECIPE_BY, themeColors, gradFor,
  Icon, TopBar, TabBar, Section, RecipeImg, MacroSplit, MicroRows, StickyCTA,
});
