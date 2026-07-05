// Macrova mock data — derived from frontend/lib/models + assets/dev/server_recipes.json

window.MACROVA_DATA = (function() {
  const recipes = [
    { id: "recipe_001", name: "Carb Heavy Bowl", time: 15, kcal: 612, p: 22, c: 110, f: 12, tags: ["asian", "vegetarian", "quick"], full: true, desc: "Jasmine rice and edamame with sesame oil and soy sauce." },
    { id: "recipe_002", name: "Spaghetti Squash & Beef", time: 45, kcal: 480, p: 38, c: 28, f: 22, tags: ["italian", "low-carb", "high-protein"], full: true, desc: "Baked spaghetti squash with tomato meat sauce and parmesan." },
    { id: "recipe_003", name: "Tuna Poke Bowl", time: 25, kcal: 720, p: 48, c: 78, f: 18, tags: ["asian", "high-protein", "fish"], full: true, desc: "Hawaiian-style with tuna sashimi, jasmine rice, edamame, tofu." },
    { id: "recipe_004", name: "Bolognese", time: 40, kcal: 690, p: 42, c: 70, f: 22, tags: ["italian", "high-protein"], full: true, desc: "Classic meat sauce over pasta with parmesan and spinach." },
    { id: "recipe_005", name: "Beef & Egg Fried Rice", time: 25, kcal: 640, p: 40, c: 72, f: 18, tags: ["asian", "high-protein", "quick"], full: true, desc: "Ground beef, scrambled eggs, jasmine rice, black beans, spinach." },
    { id: "recipe_006", name: "Greek Yogurt Parfait", time: 5, kcal: 320, p: 28, c: 38, f: 6, tags: ["breakfast", "high-protein", "no-cook"], full: true, desc: "Yogurt, berries, granola, honey." },
    { id: "recipe_007", name: "Salmon & Sweet Potato", time: 35, kcal: 580, p: 38, c: 48, f: 24, tags: ["fish", "high-protein", "gluten-free"], full: true, desc: "Roasted salmon with sweet potato wedges and asparagus." },
    { id: "recipe_008", name: "Chickpea Tagine", time: 40, kcal: 460, p: 18, c: 70, f: 12, tags: ["vegan", "moroccan", "fiber-rich"], full: true, desc: "Slow-cooked chickpeas with apricots, cumin, couscous." },
    { id: "recipe_009", name: "Chicken Caesar Wrap", time: 15, kcal: 540, p: 42, c: 38, f: 22, tags: ["lunch", "quick"], full: false, desc: null },
    { id: "recipe_010", name: "Overnight Oats", time: 5, kcal: 380, p: 18, c: 52, f: 10, tags: ["breakfast", "no-cook", "vegan"], full: true, desc: "Rolled oats, almond milk, chia, banana, peanut butter." },
    { id: "recipe_011", name: "Thai Peanut Tofu", time: 30, kcal: 520, p: 28, c: 48, f: 22, tags: ["asian", "vegetarian", "spicy"], full: false, desc: null },
    { id: "recipe_012", name: "Turkey Chili", time: 50, kcal: 480, p: 38, c: 42, f: 14, tags: ["batch", "high-protein", "freezer"], full: true, desc: "Lean turkey, three beans, tomato, smoky paprika." },
    { id: "recipe_013", name: "Egg White Scramble", time: 10, kcal: 280, p: 32, c: 18, f: 8, tags: ["breakfast", "high-protein", "low-carb"], full: true, desc: "Egg whites, spinach, cherry tomato, feta." },
    { id: "recipe_014", name: "Lentil Soup", time: 35, kcal: 360, p: 22, c: 48, f: 6, tags: ["vegan", "fiber-rich", "batch"], full: true, desc: "Red lentils, carrot, celery, cumin, lemon." },
    { id: "recipe_015", name: "Steak Salad", time: 20, kcal: 540, p: 44, c: 18, f: 30, tags: ["low-carb", "high-protein", "gluten-free"], full: false, desc: null },
    { id: "recipe_016", name: "Black Bean Tacos", time: 20, kcal: 510, p: 20, c: 62, f: 16, tags: ["vegetarian", "mexican", "quick"], full: true, desc: "Black beans, slaw, avocado, lime, corn tortillas." },
  ];

  // 7-day plan; some pinned, some flexible, some empty/failed
  const plan = {
    days: 7,
    daysOfWeek: ["MON","TUE","WED","THU","FRI","SAT","SUN"],
    target: { kcal: 2200, p: 165, c: 220, fMin: 65, fMax: 80 },
    schedule: [
      { dayIndex: 1, meals: [
          { idx: 1, recipeId: "recipe_006", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_009", busyness: 2, tags: ["lunch"], pinned: false, state: "ok" },
          { idx: 3, recipeId: "recipe_004", busyness: 3, tags: ["dinner"], pinned: false, state: "ok" }
        ], workouts: [{ after: 2, type: "PM", intensity: "high" }] },
      { dayIndex: 2, meals: [
          { idx: 1, recipeId: "recipe_013", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_015", busyness: 2, tags: ["lunch"], pinned: false, state: "ok" },
          { idx: 3, recipeId: "recipe_007", busyness: 3, tags: ["dinner"], pinned: true, state: "ok", note: "Date night" }
        ], workouts: [{ after: 1, type: "AM", intensity: "med" }] },
      { dayIndex: 3, meals: [
          { idx: 1, recipeId: "recipe_010", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_012", busyness: 2, tags: ["lunch","leftovers"], pinned: true, state: "ok" },
          { idx: 3, recipeId: "recipe_002", busyness: 3, tags: ["dinner"], pinned: false, state: "ok" }
        ], workouts: [] },
      { dayIndex: 4, meals: [
          { idx: 1, recipeId: "recipe_006", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: null, busyness: 2, tags: ["lunch"], pinned: false, state: "empty" },
          { idx: 3, recipeId: "recipe_005", busyness: 3, tags: ["dinner"], pinned: false, state: "ok" }
        ], workouts: [{ after: 2, type: "PM", intensity: "high" }] },
      { dayIndex: 5, meals: [
          { idx: 1, recipeId: "recipe_013", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_012", busyness: 2, tags: ["lunch","leftovers"], pinned: true, state: "ok" },
          { idx: 3, recipeId: "recipe_003", busyness: 3, tags: ["dinner"], pinned: false, state: "warn", note: "Sodium high" }
        ], workouts: [] },
      { dayIndex: 6, meals: [
          { idx: 1, recipeId: "recipe_010", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_001", busyness: 2, tags: ["lunch"], pinned: false, state: "ok" },
          { idx: 3, recipeId: "recipe_008", busyness: 4, tags: ["dinner"], pinned: false, state: "ok" }
        ], workouts: [{ after: 1, type: "AM", intensity: "low" }] },
      { dayIndex: 7, meals: [
          { idx: 1, recipeId: "recipe_006", busyness: 1, tags: ["breakfast"], pinned: false, state: "ok" },
          { idx: 2, recipeId: "recipe_014", busyness: 2, tags: ["lunch"], pinned: false, state: "ok" },
          { idx: 3, recipeId: "recipe_016", busyness: 3, tags: ["dinner"], pinned: false, state: "ok" }
        ], workouts: [] },
    ],
    weeklyTotals: { kcal: 15240, p: 1140, c: 1520, f: 510, sodium: 14800, sodiumMax: 16100 },
    micros: [
      { key: "fiber",    label: "Fiber",      val: 198, target: 245, unit: "g" },
      { key: "iron",     label: "Iron",       val: 122, target: 126, unit: "mg" },
      { key: "calcium",  label: "Calcium",    val: 6800, target: 7000, unit: "mg" },
      { key: "vit_d",    label: "Vitamin D",  val: 3800, target: 4200, unit: "IU" },
      { key: "vit_c",    label: "Vitamin C",  val: 690, target: 630, unit: "mg" },
      { key: "potass",   label: "Potassium",  val: 23500, target: 24500, unit: "mg" },
      { key: "magn",     label: "Magnesium",  val: 2900, target: 2940, unit: "mg" },
      { key: "omega3",   label: "Omega-3",    val: 9.2, target: 11.2, unit: "g" },
    ],
    warnings: [
      { type: "sodium", level: "warn", text: "Weekly sodium ~14,800 mg vs recommended 16,100 mg max (0.92×). Within target." },
      { type: "micro",  level: "info", text: "Vitamin D between τ-floor and full weekly RDI (3800/4200 IU, 90%)." },
    ]
  };

  const profile = {
    name: "Sam Carter",
    demographic: "adult-male-30",
    targetKcal: 2200, targetP: 165, targetC: 220, fatMin: 65, fatMax: 80,
    proteinPct: 30, carbPct: 40, fatPct: 30,
    deficit: false, tau: 1.0,
    allergies: ["peanuts", "shellfish"],
    likes: ["salmon", "yogurt", "rice"],
    dislikes: ["liver", "olives"],
    planningMode: "assisted_cached",
    ingredientSource: "local",
    llmValidated: true,
  };

  // Default weekly rhythm — drives the planner schedule editor
  const scheduleTemplate = [
    { slot: "Breakfast", time: "8:00", busyness: 1, note: "Quick · low effort" },
    { slot: "Lunch", time: "13:00", busyness: 2, note: "Portable · ~30 min" },
    { slot: "Dinner", time: "19:00", busyness: 3, note: "Cooked · 30–60 min" },
  ];

  // Planner config working state (mirrors POST /api/v1/plan request)
  const plannerConfig = {
    days: 7,
    planningMode: "assisted_cached",
    ingredientSource: "local",
    poolSelectedIds: ["recipe_001","recipe_002","recipe_003","recipe_004","recipe_005","recipe_006","recipe_007","recipe_010","recipe_012","recipe_013","recipe_014","recipe_016"],
    perDay: [
      { day: 1, meals: [1,2,3], workouts: [2] },
      { day: 2, meals: [1,2,3], workouts: [1] },
      { day: 3, meals: [1,2,3,4], workouts: [] },
    ],
  };

  // Recipe Builder draft (per-100g base values, mirrors NutritionSummary contract)
  const builder = {
    name: "Spaghetti Squash & Lean Beef Bolognese",
    servings: 2,
    cookTime: 45,
    ingredients: [
      { id: "i1", name: "Spaghetti squash",    qty: 350, unit: "g", kcal: 34,  p: 0.6, c: 8,  f: 0.3, src: "USDA · Foundation" },
      { id: "i2", name: "Tomato",               qty: 350, unit: "g", kcal: 18,  p: 0.9, c: 4,  f: 0.2, src: "USDA · SR Legacy" },
      { id: "i3", name: "Lean ground beef 95%", qty: 280, unit: "g", kcal: 140, p: 22,  c: 0,  f: 5,   src: "USDA · Foundation" },
      { id: "i4", name: "Parmesan cheese",      qty: 50,  unit: "g", kcal: 392, p: 36,  c: 4,  f: 26,  src: "Custom" },
      { id: "i5", name: "Fresh parsley",        qty: 10,  unit: "g", kcal: 36,  p: 3,   c: 6,  f: 0.8, src: "USDA · SR Legacy" },
    ],
    steps: [
      "Halve the spaghetti squash; roast cut-side down at 400°F for 35 minutes until tender.",
      "While the squash roasts, brown the lean beef in a wide pan over medium-high heat.",
      "Add tomato to the beef; simmer 10 minutes to thicken into a quick sauce.",
      "Scrape the cooked squash flesh into long strands.",
      "Top squash with the meat sauce, fresh parsley, and grated parmesan.",
    ],
    // per-serving micronutrients, grouped — mirrors micronutrientsPer100g schema
    micros: [
      { name: "Fiber",         val: 6.4,  unit: "g",  target: 35,   group: "Fiber & fats" },
      { name: "Saturated fat", val: 4.8,  unit: "g",  target: 22,   group: "Fiber & fats" },
      { name: "Omega-3",       val: 0.42, unit: "g",  target: 1.6,  group: "Fiber & fats" },
      { name: "Vitamin A",     val: 720,  unit: "IU", target: 3000, group: "Vitamins" },
      { name: "Vitamin C",     val: 38,   unit: "mg", target: 90,   group: "Vitamins" },
      { name: "Vitamin B12",   val: 2.4,  unit: "µg", target: 2.4,  group: "Vitamins" },
      { name: "Folate",        val: 86,   unit: "µg", target: 400,  group: "Vitamins" },
      { name: "Iron",          val: 4.6,  unit: "mg", target: 18,   group: "Minerals" },
      { name: "Calcium",       val: 280,  unit: "mg", target: 1000, group: "Minerals" },
      { name: "Magnesium",     val: 92,   unit: "mg", target: 420,  group: "Minerals" },
      { name: "Potassium",     val: 1180, unit: "mg", target: 3500, group: "Minerals" },
      { name: "Sodium",        val: 540,  unit: "mg", target: 2300, group: "Minerals" },
    ],
    units: ["g","tbsp","cup","oz","piece"],
  };

  // Pantry / ingredient hub
  const pantry = {
    needsReview: [
      { id: "n1", query: "whole-milk greek yogurt", match: "USDA 173430 · plain whole-milk yogurt", conf: 0.92, kcal: 61, p: 3.5, c: 4.7, f: 3.3 },
      { id: "n2", query: "shirataki noodles", match: null, conf: 0, kcal: null, p: null, c: null, f: null },
      { id: "n3", query: "calabrian chili paste", match: "USDA 1100 · chili sauce, hot", conf: 0.74, kcal: 29, p: 1.2, c: 6.4, f: 0.3 },
    ],
    custom: [
      { id: "c1", name: "House granola", kcal: 118, p: 4, c: 16, f: 5, src: "self" },
      { id: "c2", name: "Nonna's tomato sauce", kcal: 32, p: 1, c: 6, f: 0.5, src: "self" },
      { id: "c3", name: "Whey isolate (vanilla)", kcal: 110, p: 24, c: 2, f: 1, src: "brand" },
    ],
    recent: ["Salmon, atlantic", "Greek yogurt 0%", "Jasmine rice", "Chickpeas, canned", "Spinach, raw", "Olive oil"],
    counts: { resolved: 142, unresolved: 3, custom: 14 },
  };

  // Agent plan-from-text
  const agent = {
    prompt: "Plan me 3 days, high-protein, mostly Mediterranean, ≤ 30 min on weekdays, no peanuts.",
    parsed: [
      { label: "Horizon", value: "3 days", ok: true },
      { label: "Protein floor", value: "160 g/day", ok: true },
      { label: "Cuisine", value: "Mediterranean", ok: true },
      { label: "Time", value: "≤ 30 min weekday", ok: true },
      { label: "Excludes", value: "peanuts", ok: false },
    ],
    conf: 0.94,
    matches: [
      { id: "recipe_007", score: 0.93 },
      { id: "recipe_003", score: 0.88 },
      { id: "recipe_014", score: 0.81 },
      { id: "recipe_011", score: 0.62 },
    ],
    generate: [
      { name: "White-bean tuna salad", state: "done", meta: "420 kcal · 38g P · 12 min" },
      { name: "Lamb gyro plate", state: "running", meta: "step 2 of 3 · ~6s" },
      { name: "Herbed chickpea bowl", state: "queued", meta: "queued" },
    ],
  };

  return { recipes, plan, profile, scheduleTemplate, plannerConfig, builder, pantry, agent };
})();
