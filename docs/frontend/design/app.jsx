/* global React, ReactDOM, RECIPE_BY, TabBar,
   TodayScreen, PlanScreen, RecipesScreen, YouScreen, PantryScreen,
   PlannerConfigFlow, RecipeBuilderFlow, AgentFlow, FailureFlow, DetailSheet */

function App() {
  const [tab, setTab] = React.useState("today");
  const [openRecipe, setOpenRecipe] = React.useState(null);
  const [openMeal, setOpenMeal] = React.useState(null);
  const [flow, setFlow] = React.useState(null); // config | builder | agent | failure | ingredient

  const openMealHandler = (meal) => {
    const r = RECIPE_BY(meal.recipeId);
    if (!r) return;
    setOpenMeal(meal); setOpenRecipe(r);
  };
  const closeDetail = () => { setOpenRecipe(null); setOpenMeal(null); };
  const pin = () => { if (openMeal) setOpenMeal({ ...openMeal, pinned: !openMeal.pinned }); };

  const onFlow = (name) => setFlow(name);
  const closeFlow = () => setFlow(null);
  const generate = () => { setFlow(null); setTab("plan"); };

  const anySheet = openRecipe || flow;

  return (
    <>
      <aside className="readiness-key">
        <h5>Mock UI · readiness</h5>
        <div className="item"><span className="ready wire">Wire</span><span>Backed by existing model + endpoint</span></div>
        <div className="item"><span className="ready part">Partial</span><span>Model exists, write path TBD</span></div>
        <div className="item"><span className="ready mock">Mock</span><span>Visual only, no backend</span></div>
        <div style={{ borderTop: "1px solid var(--line)", marginTop: 10, paddingTop: 10, color: "var(--ink-3)", fontSize: 11, lineHeight: 1.5 }}>
          UI-direction visual system applied to the full functional surface: planner config, builder, pantry resolution, agent and infeasibility handling.
        </div>
      </aside>

      <div className="preview-frame">
        <div className="app" data-screen-label={tab}>
          {tab === "today" && <TodayScreen onOpenRecipe={setOpenRecipe} onOpenMeal={openMealHandler} onFlow={onFlow}/>}
          {tab === "plan" && <PlanScreen onOpenMeal={openMealHandler} onFlow={onFlow}/>}
          {tab === "recipes" && <RecipesScreen onOpenRecipe={setOpenRecipe} onFlow={onFlow}/>}
          {tab === "pantry" && <PantryScreen onFlow={onFlow}/>}
          {tab === "you" && <YouScreen onFlow={onFlow}/>}

          {!anySheet && <TabBar active={tab} onChange={setTab}/>}
        </div>
      </div>

      {openRecipe && <DetailSheet recipe={openRecipe} meal={openMeal} onClose={closeDetail} onPin={pin} onEdit={() => { closeDetail(); setFlow("builder"); }}/>}

      {flow === "config" && <PlannerConfigFlow onClose={closeFlow} onGenerate={generate}/>}
      {(flow === "builder" || flow === "ingredient") && <RecipeBuilderFlow onClose={closeFlow}/>}
      {flow === "agent" && <AgentFlow onClose={closeFlow} onApply={generate}/>}
      {flow === "failure" && <FailureFlow onClose={closeFlow}/>}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
