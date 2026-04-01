# Macrova (nutrition-agent)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests/)

**Version: v0.1.0**

A meal planner that generates **single- or multi-day meal plans** (breakfast, lunch, dinner, plus additional slots) from your schedule and nutrition goals. The current implementation uses a **spec-aligned, phase-based planner** with deterministic backtracking search, **rule-based recipe scoring**, and **structured nutrition calculations** (macros + tracked micronutrients). LLM integration is coming soon.

---

## Getting started

### Install

```bash
git clone <repository-url>
cd nutrition-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Replace `<repository-url>` with your clone URL (e.g. from GitHub). The folder name after clone is `nutrition-agent`.

### Quick run (local mode)

After copying the example config and data files (see below), run:

```bash
python3 plan_meals.py
```

This uses the bundled ingredient database (no API key). For USDA API mode, see [USAGE.md](USAGE.md#api-mode-setup).

### Configure and run

1. **Copy example config and data** (recipe/ingredient data are not in the repo):
   ```bash
   cp config/user_profile.yaml.example config/user_profile.yaml
   cp data/recipes/recipes.json.example data/recipes/recipes.json
   cp data/ingredients/custom_ingredients.json.example data/ingredients/custom_ingredients.json
   ```
2. Edit `config/user_profile.yaml` with your goals, schedule, and preferences.
3. **Run the planner:**
   ```bash
   python3 plan_meals.py
   ```
   Output is Markdown by default. Use `--output json` for JSON, or see below for more options.

**More detail:** [QUICK_START.md](QUICK_START.md) for a short run-through; [USAGE.md](USAGE.md) for all CLI options, API mode, and the REST API.

### Run tests

```bash
pytest tests/
```

No API key or network access is required; USDA-dependent tests use mocks.

**Environment variables:** None for local mode. For USDA API mode, copy `.env.example` to `.env` and set `USDA_API_KEY`; see [USAGE.md](USAGE.md#api-mode-setup).

---

## Current state

The planner recommends meals over a **planning horizon of 1–7 days** from your recipe list. Ingredient nutrition is provided by a **provider abstraction** (local JSON or USDA API), and a phase-based planner enforces macro and micronutrient constraints. In practice:

- **User profile:** Daily calories, protein, fat range, carbs, schedule (per-day `MealSlot` lists), activity context, excluded ingredients, pinned assignments, optional `max_daily_calories`, and optional micronutrient targets / upper limits.
- **Recipe scoring:** Nutrition fit, cooking time vs schedule, preferences (likes/dislikes/allergies via exclusions), and micronutrient contribution, via a composite score and deterministic ordering.
- **Ingredient nutrition:** Either a **local JSON** ingredient DB (default) or the **USDA FoodData Central API** (optional, `--ingredient-source api` and `USDA_API_KEY`), funneled through a caching and normalization pipeline into internal `NutritionProfile` objects (macros + `MicronutrientProfile`).
- **Planner engine:** Phase 0–7 pipeline under `src/planning/`, with hard constraints, forward-check constraints, multi-day feasibility checks, and backtracking search (`plan_meals` / `run_meal_plan_search`).
- **Output:** Structured daily and (when D > 1) weekly view with per-meal, per-day, and cross-day nutrition, adherence to goals, and warnings/failure modes.

For a deeper architectural overview, see **`docs/planner_architecture.md`** and **`docs/MEALPLAN_SPECIFICATION_v1.md`**.

**Interfaces:** CLI (`plan_meals.py` / `python3 -m src.cli`), an optional **REST API** (FastAPI server in `src/api/server.py`), and a **Flutter frontend** (`frontend/`) that integrates async grocery cart optimization.

### Async Grocery Cart Optimization (Macrova frontend + FastAPI + TinyFish)

The project includes an end-to-end **async grocery cart optimizer** that takes a generated meal plan, calls a Node-based optimizer backed by TinyFish product search, and returns a **multi-store shopping cart** with progress updates.

- **Frontend (Flutter, `frontend/`)**
  - `MealPlanViewScreen` exposes an **“Optimize Grocery Cart”** button.
  - Tapping the button:
    - Builds a `GroceryOptimizeRequest` JSON body from the current meal plan.
    - Calls `POST /api/v1/grocery/meal-plan-snapshot` to register the plan.
    - Calls `POST /api/v1/grocery/optimize-cart` to start an async job and receive a `jobId`.
    - Starts polling `GET /api/v1/grocery/optimize-cart/{jobId}` every 2–4 seconds via `OptimizationJobProvider`.
  - While the job runs:
    - `OptimizationProgress` shows a **progress bar**, stage text, and elapsed time.
  - When the job completes:
    - A “Cart ready” panel appears with latency/cache stats.
    - A **cart dialog** shows:
      - Estimated total cost.
      - Total cart line count.
      - **Per-store sections** (e.g. Target) with product-level rows (name, pack count, price).
    - If the job fails, a failure card is shown with the error message and an always-available **Retry** button that re-submits the same snapshot as a new job.

- **Backend API (FastAPI, `src/api/server.py` + `src/routes/grocery.py`)**
  - Synchronous optimizer:
    - `POST /api/v1/grocery/optimize` — runs the Node CLI inline and returns a `GroceryOptimizeResponse` (JSON) for blocking flows.
  - Async cart optimization:
    - `POST /api/v1/grocery/meal-plan-snapshot`
      - Accepts a `GroceryOptimizeRequest` body and stores a **snapshot** (meal plan + stores) in a short-lived in-memory store.
      - Returns `{ "mealPlanId": "..." }` for subsequent async jobs.
    - `POST /api/v1/grocery/optimize-cart`
      - Body:
        - `mealPlanId: string` (must match a registered snapshot).
        - `preferences: { mode: "balanced" | "min_cost" | "min_waste", maxStores: number }`.
      - Requires an identity header: **`X-User-Id`**.
      - Enforces **rate limits** via:
        - A global max queue depth.
        - A per-user cap on active (queued + running) jobs.
      - On success, enqueues a job and returns `202 Accepted` with `{ "jobId": "..." }`.
    - `GET /api/v1/grocery/optimize-cart/{jobId}`
      - Returns the async job status:
        - `status: "queued" | "running" | "completed" | "failed"`
        - `progress: 0–100`
        - `stage: string` (human-readable pipeline stage)
        - `result: OptimizationResult | null` (cart + per-store breakdown) when completed
        - `error: { message, code?, retryable? } | null` on failure
        - `stats: { runId, totalLatency, searchLatency, failedQueries, cacheHits }` when available
      - Also requires the same `X-User-Id` header and **enforces ownership**:
        - Unknown/expired job → `404 JOB_NOT_FOUND`.
        - Job belongs to a different user → `403 FORBIDDEN`.

- **Job system and worker (Python, `src/jobs/`, `src/pipeline/`)**
  - `OptimizationJobRecord` tracks:
    - `id`, `meal_plan_id`, `user_id`, `status`, `progress`, `stage`,
    - timestamps, attempts, `result`, `error`, and `stats`.
  - `InMemoryJobStore`:
    - Thread-safe in-memory dictionary of jobs with a **post-completion TTL** to bound memory.
    - Supports listing stuck jobs and counting active jobs per user for rate limiting.
  - `InMemoryJobQueue`:
    - `asyncio.Queue` of job IDs with admission checks:
      - Rejects when the queue is full (returns `429 QUEUE_FULL`).
      - Rejects when a user exceeds the active job cap (returns `429 CONCURRENCY_LIMIT`).
  - Worker lifecycle:
    - On API startup, the server creates the store, queue, and a `MealPlanSnapshotStore`, then launches a **supervised background worker**:
      - `job_worker_loop(app)` pulls job IDs, resolves the snapshot, and calls `run_optimization_job`.
      - `supervised_job_worker_loop(app)` restarts the worker after crashes with a small backoff, so a single bad job cannot permanently kill async processing.
  - `run_optimization_job`:
    - Wraps the existing Node optimizer (`run_grocery_optimizer`) and:
      - Builds the Node request payload from the saved snapshot and preferences.
      - Updates `progress`/`stage` at key milestones:
        - e.g. “aggregating ingredients”, “preparing product search”, “searching products (attempt i/n)”, “processing optimizer output”, “finalizing results”.
      - Enforces a **hard per-job timeout** (~5 minutes by default).
      - Performs **bounded retries** for transient TinyFish/Node failures, with exponential backoff.
      - Applies a **partial result policy**: jobs can succeed with warnings when a high-enough fraction of ingredients are covered.
      - Computes and stores metrics (`JobStats`) from the Node pipeline trace:
        - `totalLatency`, `searchLatency`, `failedQueries`, `cacheHits`, etc.
      - Guarantees **monotonic progress**: progress values never decrease, even across retries, to avoid jarring UX regressions.

- **TinyFish integration (Node, `packages/grocery-optimizer/`)**
  - `grocery_pipeline.ts` orchestrates:
    - Ingredient aggregation and normalization.
    - Bounded-concurrency TinyFish search (configurable, default 3 in-flight searches).
    - Query/result caching for product search and parsed prices.
    - Heuristic skipping of low-value ingredients (e.g. salt, water).
    - Multi-store cart optimization with waste and cost trade-offs.
  - `TinyFishAdapter` implements:
    - Retries with backoff for transient errors.
    - Abort signals and progress callbacks for streaming searches.

To use the async grocery cart feature locally:

1. Run the FastAPI server (after building the Node `grocery-optimizer` package):
   ```bash
   uvicorn src.api.server:app --reload
   ```
2. Run the Flutter app in `frontend/` pointing at the API (set `API_BASE_URL` if not `http://localhost:8000`).
3. Generate a meal plan, then tap **“Optimize Grocery Cart”** on the Meal Plan screen.

The system will:

- Register the current plan snapshot.
- Start an async job tied to your `X-User-Id`.
- Stream progress via polling until the job completes or fails.
- Render a **per-store cart summary** with product-level details and a clear retry path on failures.

### End Game Vision
The ultimate goal is to create an **all-purpose nutritious meals generator** that combines:
- **LLM Creativity**: Leveraging AI to understand natural language queries and user preferences
- **Technical Precision**: Accurate nutrition calculations and meal balancing
- **Cultural Diversity**: Recipes from different cultures that taste good and meet nutrition goals
- **Advanced Customization**: Complex meal planning with constraints like meal prep, specific ingredients, and flexible scheduling

**Example End Game Query:**
> "I want a set of meals generated for the week. I want salmon 2 of these days, and I want to make 4 servings my weekly meal prep chili recipe. I also want sunday to be a more flexible day so don't plan out lunch and dinner, just plan out one meal for sunday."

The system will intelligently parse this request, account for the chili's nutrition across the week, ensure salmon appears twice, and provide flexible Sunday planning - all while maintaining optimal nutrition balance.

## Goals

### Current MVP Goals
- Recommend recipes based on user preferences and goals
- Calculate and display accurate nutrition for selected recipes
- Ensure multiple meals fit principles of a balanced diet
- Be deployable locally for personal use
- **Foundation Priority**: Accurate nutrition calculations and meal balancing above all else

### End Game Goals
- **LLM-Powered Creativity**: Combine technical nutrition precision with AI creativity for meal selection
- **Multi-Cultural Recipe Database**: Incorporate recipes from different cultures while maintaining nutrition goals
- **Natural Language Interface**: Accept complex, natural language meal planning requests
- **Advanced Meal Prep Integration**: Plan meals around pre-made components and batch cooking
- **Flexible Scheduling**: Handle complex scheduling constraints and preferences
- **Specialized Agent Training**: Train on recipe databases and up-to-date nutrition principles

## Example: Full Day of Meals

### **Output**
- **Meal 1:** Preworkout Meal
	- Given that you train 2 hours after waking up, this is a meal that is quick to make but will still give you enough carbs for your workout
	- 200g cream of rice
	- 1 scoop whey protein powder
	- 1 tsp almond butter
	- 50g blueberries
	- *Meal instructions*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- **Meal 2:** Mexican-Style Breakfast Scramble
	- This meal will take less than 30 minutes to make, is highly satiating with fiber and protein, packed with micronutrients, and incredibly tasty!
	- 5 large eggs
	- 175g potatoes
	- 50g red peppers
	- 40g raw spinach
	- 1oz sharp cheddar cheese
	- 3oz lean turkey sausage
	- 50g pinto
	- 2 tsp olive oil
	- Salsa and green onion to taste
	- *Meal Instructions go here*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- **Meal 3:** Hot Honey Salmon with rice
	- This meal will take less than 30 minutes to make, and will cover the majority of the rest of your nutrition needs!
	- 4 oz salmon
	- 1 cup jasmine rice
	- 1 tbsp honey
	- 1 tsp chili crisp
	- *Meal Instructions go here*
	- Nutrition Breakdown: *full micro/macro calculation goes here*
- *Micronutrient Breakdown*


## Functional Requirements

- Must parse a list of ingredients
    
- Must retrieve relevant recipes
    
- Must compute or retrieve nutrition values
    
- Must score recipes based on nutrition goals
    
- Must return structured output
    

## Non-Functional Requirements

- Runs locally or within low-latency API
    
- Easy to update recipes/preferences
    
- Minimal dependencies


## Project structure

```
config/          # User profile (YAML); copy from .example
data/            # Recipes and ingredients JSON; copy from .example
src/
  cli.py         # CLI entrypoint
  api/           # Optional REST API (FastAPI)
  providers/     # Ingredient data (local JSON or USDA API)
  nutrition/     # Nutrition calculator and aggregation
  planning/      # Meal planner
  scoring/       # Recipe scorer
  ingestion/     # Recipe retrieval, USDA client, ingredient cache
  data_layer/    # Models, recipe/ingredient DBs, user profile loader
  output/        # Markdown/JSON formatters
tests/           # Pytest suite (no network required)
```

## Development roadmap

### Phase 1–4: MVP foundation (current)
- ✅ Accurate nutrition calculations and meal balancing
- ✅ Rule-based recipe scoring and selection
- ✅ Local ingredient database (JSON)
- ✅ Optional USDA API ingredient source (`--ingredient-source api`; requires `USDA_API_KEY`)
- ✅ User profile, schedule, and preferences (likes, dislikes, allergies)
- ✅ CLI and optional REST API

### Phase 5+: LLM Integration & Creativity
- **LLM-Enhanced Reasoning**: Replace rule-based scoring with intelligent AI reasoning
- **Natural Language Queries**: Accept complex meal planning requests in natural language
- **Recipe Creativity**: AI-generated recipe variations and cultural fusion
- **Specialized Training**: Train agent on comprehensive recipe databases and nutrition science

### Future Extensions
- **Multi-User Support**: Expand beyond personal use
- **Advanced Interfaces**: GUI for meal selection, scheduling, and preferences
- **Recipe Database Expansion**: Incorporate diverse cultural recipes
- **Maintenance Calorie Calculator**: Automated TDEE calculation
- **Dynamic RDI Calculation**: Personalized micronutrient targets based on individual needs

### Interface Evolution Options
The final product may feature:
- Natural language prompts for complex meal planning
- GUI with drag-and-drop meal scheduling
- Hybrid approach combining structured inputs with AI flexibility

**Current priority:** Nail the foundational nutrition logic and meal balancing before adding creative AI features.

---

## License

This project is licensed under the MIT License—see [LICENSE](LICENSE).
