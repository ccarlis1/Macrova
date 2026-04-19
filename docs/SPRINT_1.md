# Sprint 1 — Tagging v2, Meal Prep, Planner Intelligence, UI Revamp

**Owner:** You  ·  **Duration:** Week 1 (5 working days) + Week 2 buffer  ·  **Status:** Ready to build

> Per-task stubs live in `[docs/sprint1/](./sprint1/README.md)`.

---

# 1. Product Requirements Document

## 1.1 Problem Definition

Core problems, tied to user behavior:


| #   | Problem                                                                                                                               | User behavior evidence                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| P1  | **Planner cannot express real-world meal slot intent.** A slot is not "breakfast" — it's "portable, no-kitchen, must be kiwis + bar." | User manually overrides output; plan fights reality.                                      |
| P2  | **Recipes cannot be reliably reused across busy schedules.** Meal prep exists in the user's head, not the system.                     | User cooks one batch Sunday → eats it Mon/Tue/Wed but planner re-picks different lunches. |
| P3  | **Tagging is nominal, not functional.** Tags exist on the model but are not normalized and don't drive selection.                     | User cannot filter planner to a tag; LLM tags are free-form noise.                        |
| P4  | **UI feels like a spreadsheet.** High cognitive load to read or rearrange a day.                                                      | User reads CLI markdown output instead of using the Flutter screens.                      |
| P5  | **LLM recipe generation is a blind fire-and-forget.** User cannot preview before paying full generation cost + USDA lookups.          | User distrusts auto-generated recipes; manually edits after.                              |


## 1.2 Goals & Success Metrics


| Goal | Metric                                                     | Target                                                          |
| ---- | ---------------------------------------------------------- | --------------------------------------------------------------- |
| G1   | Time to generate a full 7-day plan from a clean profile    | < 120 s end-to-end (90 s planner + 30 s user confirms)          |
| G2   | Time to add a meal-prep batch and have it populate 3 slots | < 30 s, ≤ 4 taps                                                |
| G3   | Planner respects hard tag constraints                      | 100 % of slots with a required tag match it (enforced in tests) |
| G4   | LLM-generated recipes are schema-valid and USDA-grounded   | 100 % pass `RecipeValidator`; 0 hallucinated nutrient values    |
| G5   | User reuses recipes instead of re-picking                  | ≥ 60 % of lunches in a week come from a `meal_prep` batch       |
| G6   | Tag coverage of recipe corpus                              | ≥ 95 % of recipes carry ≥ 1 `context` tag                       |
| G7   | Planner determinism parity (CLI vs Flutter)                | Same `recipe_ids_sha256` + same plan for same seed              |


## 1.3 Core Features

### Must-have (Sprint 1)

#### F1. Tagging System v2

- **Description:** Typed, normalized tags (`context`, `time`, `nutrition`, `constraint`) attached to every recipe, editable in UI, readable by planner + LLM.
- **Why:** Prerequisite for P1, P3, P5. Nothing else works without it.
- **Edge cases:**
  - Recipe with zero tags → treated as `context:unspecified` (surfaced with a warning badge in UI, **not** silently pickable by the planner for a tag-constrained slot).
  - Conflicting tags (`time:instant` + `time:long`) → reject at save-time with inline error.
  - User renames a tag → migrate via canonical slug, not display name.
- **Dependencies:** Migration of existing `recipes.json`. New `tags` column on `Recipe`. Planner tag filter reads typed tags.

#### F2. Meal Prep Batches

- **Description:** A recipe can be "started" as a meal prep batch: user picks servings count (N) and which slots (across days) the servings should auto-fill. Batch is a first-class entity that owns its slot assignments.
- **Why:** P2. Matches how user actually eats Mon–Wed.
- **Edge cases:**
  - N servings > assigned slots → remaining servings stored as "leftovers" (surfaced but not auto-planned).
  - Assigned slot already has a meal → prompt: **Replace / Skip / Cancel batch**.
  - User deletes recipe that has an active batch → batch enters `orphaned` state; slots show warning; no silent data loss.
  - Partial-eaten batch across reschedules → servings_remaining decrements per consumed slot.
- **Dependencies:** F1 (needs `context:meal_prep` tag), new `MealPrepBatch` entity, planner must honor pre-filled slots as hard constraints.

#### F3. Planner Tag-Constrained Selection

- **Description:** Each meal slot in the user profile can declare **required tags** and **preferred tags**. Planner treats required tags as hard constraints (slot must pick a recipe carrying all required tags); preferred as scoring boosts.
- **Why:** P1. Replaces the ad-hoc "busyness + meal_type" pairing.
- **Edge cases:**
  - Required tag has 0 recipes → planner fails fast with `FM-TAG-EMPTY` (not a silent substitution).
  - Required tag has exactly 1 recipe → equivalent to "force select" (covers the trivial forced-recipe case).
  - Slot has both required tag and a pre-filled meal_prep serving → meal_prep wins; tag still validated (warn if the batched recipe lacks it).
- **Dependencies:** F1. `phase3_feasibility` + `phase6_candidates` updated to read typed tags.

#### F4. LLM Recipe Suggestion → Approval → Generation

- **Description:** Two-stage flow. Stage A: given a query (e.g. "high-protein shrimp, <20 min"), LLM returns a **shortlist** of 3–5 candidates (name + 1-line summary + optional image). User picks one. Stage B: full recipe generation, USDA grounding, auto-tagging, save to bank.
- **Why:** P5 + G4. Prevents wasted generation and hallucinated nutrition.
- **Edge cases:**
  - LLM returns a candidate whose ingredients cannot all be resolved in USDA → reject; surface which ingredient failed; offer substitution.
  - User rejects all candidates → one retry with refined query; then stop (no infinite spend).
  - Duplicate of existing recipe (fuzzy name match ≥ 0.85) → surface as "already in bank" instead of regenerating.
- **Dependencies:** Existing `src/llm/pipeline.py`, `recipe_validator.py`, `ingredient_matcher.py`. New suggestion endpoint. F1 for auto-tagging output.

#### F5. UI Revamp (Cards, Drag-and-Drop, Visual Tags)

- **Description:** Flutter rebuild of Planner + Recipe Builder screens with a card-based layout, colored tag chips, drag-and-drop to move meals between slots.
- **Why:** P4. User won't adopt a spreadsheet.
- **Edge cases:**
  - Drag a meal-prep serving out of its batch → show dialog: "This is serving 2/5 of batch X. Detach?"
  - Narrow viewport / mobile web → cards stack vertically, DnD degrades to long-press + select-target.
- **Dependencies:** F1, F2, F3.

### Nice-to-have (Future / Week 2+)

- Smart suggestions ("Your Tue dinner slot is usually empty on workout weeks — add one?").
- Nutrition heat-map across the week.
- Grocery list diff when a batch is added.
- LLM-driven "rescue this plan" when feasibility fails.
- Shared recipe import from URL.

---

# 2. System Design (High Level)

## 2.1 Core Entities

```
UserProfile ──< MealSlot (per day type)
                    │
                    ├─ required_tags: [Tag]
                    └─ preferred_tags: [Tag]

Recipe ──< RecipeTag >── Tag
  │
  └─< MealPrepBatch ──< BatchAssignment ──> MealSlot(on a specific day)

MealPlanDay ──< PlannedMeal ──> Recipe
                   │
                   └─ source: {planner | meal_prep_batch | user_override}
```

### Entity detail

**Recipe** (extends existing `src/data_layer/models.py::Recipe`)

- `id: str`
- `name: str`
- `ingredients: List[Ingredient]`
- `cooking_time_minutes: int`
- `instructions: List[str]`
- `**tags: List[Tag]`** ← NEW, replaces the TODO comment
- `**is_meal_prep_capable: bool**` ← NEW, derived from `context:meal_prep` tag
- `**default_servings: int**` ← NEW (default 1; batches require ≥ 2)

**Tag** (new)

- `slug: str` — canonical, lowercase, hyphenated (`high-protein`, `no-kitchen`)
- `display: str`
- `type: Literal["context", "time", "nutrition", "constraint"]`
- `source: Literal["user", "llm", "system"]`
- `created_at: datetime`

**MealSlot** (meal-only; extends existing schedule model)

- `slot_id: str` (stable per day type, e.g. `workout_day.meal_2`)
- `day_type: Literal["workout", "golf", "rest"]` (extensible)
- `ordinal: int`
- `required_tags: List[str]` (tag slugs)
- `preferred_tags: List[str]`
- `busyness_max: int` (1–4; see §2.4)

**WorkoutSlot** (new; non-meal context slot)

- `slot_id: str` (stable per day type, e.g. `workout_day.workout_1`)
- `day_type: Literal["workout", "golf", "rest"]` (extensible)
- `ordinal: int`
- `workout_type: Optional[str]`
- `relative_to_meal_index: Optional[int]` (for pre/post-workout reasoning)

**MealPlanDay**

- `date: str` (ISO)
- `day_type: str`
- `meals: List[PlannedMeal]`
- `totals: NutritionProfile`
- `meets_goals: bool`

**PlannedMeal**

- `slot_id: str`
- `recipe_id: str`
- `servings: float` (1.0 for single, fractional for scaled)
- `source: Literal["planner", "meal_prep_batch", "user_override"]`
- `batch_id: Optional[str]`

**MealPrepBatch** (new, first-class)

- `id: str`
- `recipe_id: str`
- `total_servings: int`
- `cook_date: str`
- `assignments: List[BatchAssignment]` — each (date, slot_id, servings)
- `status: Literal["planned", "active", "consumed", "orphaned"]`

**UserProfile** — already present. Sprint 1 adds:

- `day_type_schedules: Dict[str, List[MealSlot]]` (replaces the loose `schedule: Dict[str, int]`; keep back-compat shim)
- `week_template: List[str]` (e.g. `["workout","workout","golf","rest","workout","workout","rest"]`)

## 2.2 Tagging System Redesign

### Tag types


| Type           | Purpose                              | Examples                                                                                | Required on recipe?                                                    |
| -------------- | ------------------------------------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **context**    | Where/when this recipe fits in a day | `meal-prep`, `instant-snack`, `pre-workout`, `portable`, `no-kitchen`                   | **Yes, ≥ 1**                                                           |
| **time**       | Prep + cook time bucket (meal recipes only)   | `time-0` (instant/no-prep), `time-1` (1–5m), `time-2` (6–15m), `time-3` (16–30m), `time-4` (30m+) | **Yes, exactly 1** (computed from `cooking_time_minutes`; overridable) |
| **nutrition**  | Macro/ingredient emphasis            | `high-protein`, `high-carb`, `low-fat`, `shrimp`, `egg-based`                           | Optional                                                               |
| **constraint** | Hard exclusions                      | `no-dairy`, `no-kitchen`, `nut-free`                                                    | Optional                                                               |


**[DECISION]** `context` + `time` are required on every recipe (system enforces on save). `nutrition` and `constraint` are optional and additive. This is the minimum needed to make the planner's hard constraints usable without letting tags explode.

**[DECISION]** `time` tags are a 5-bucket **meal recipe** scale. Legacy `busyness_level` in meal slots remaps to `time-1..time-4`; `time-0` is for instant/no-prep recipes and is **not** derived from schedule `busyness=0`. See §2.4.

### How the planner consumes tags

1. For each slot, load `required_tags` (set R) and `preferred_tags` (set P).
2. Filter recipe pool to recipes whose tag set ⊇ R. This is the **hard constraint**.
3. Score remaining candidates; +ε boost per tag in P the recipe carries.
4. Apply existing macro/variety scoring on top.

### Canonical slug + aliases

- Tag service exposes `resolve(slug_or_display) -> Tag`.
- Aliases table (`high_protein` → `high-protein`, `Meal Prep` → `meal-prep`) lives in `data/tags/aliases.json`, LLM-writable via a tool call, user-confirmable.

## 2.3 Meal Prep System

### What makes a recipe "meal prep"

A recipe is meal-prep-capable when **both**:

1. It carries the `context:meal-prep` tag.
2. `default_servings ≥ 2`.

No other heuristic. Explicit, not inferred.

### Serving distribution logic

```
batch = MealPrepBatch(recipe, total_servings=N, cook_date=D)
user picks slots: [(date_i, slot_id_i)] with length K

if K > N:
    error("Not enough servings")
if K < N:
    batch.leftover_servings = N - K  # surfaced, not auto-planned
```

Each assignment consumes 1.0 serving (Sprint 1 constraint — fractional servings are Week 2+).

### How servings map to meal slots

- When the planner runs, it **reads active batches first** and pre-fills those slots with `source="meal_prep_batch"`, before any tag-based selection runs.
- Pre-filled slots are **locked** from the planner's perspective (treated like `user_override`).
- Tag validation still runs on locked slots, producing a **warning** (not an error) if the batched recipe lacks a slot's required tag. Rationale: user-intent beats system-purity for this feature.

### UI + backend interaction

- Backend exposes `POST /api/v1/meal_prep_batches`, `GET /api/v1/meal_prep_batches?active=true`, `DELETE /api/v1/meal_prep_batches/{id}`.
- Planner's `PlanRequest` gains `active_batches: List[MealPrepBatch]` (derived server-side; clients don't have to populate).
- Flutter "Meal Prep Tray" panel on the planner screen lists active batches with a servings counter. Dragging a batch card onto a slot creates an assignment.

## 2.4 Busyness scale reconciliation (+ workout-slot handling)

**[DECISION]** preserve current profile semantics where `busyness=0` means a **workout slot**, not a meal slot. Busyness revamp only applies to meal slots.

| Legacy schedule value | Meaning in Sprint 1 | Planner behavior |
| -------- | ------- | ------------------ |
| `0` | Workout slot (`WorkoutSlot`) | Excluded from meal candidate selection; used as timing context (pre/post-workout tags and slot scoring). |
| `1` | Meal slot, <= 5 min | Maps to `time-1` |
| `2` | Meal slot, 6–15 min | Maps to `time-2` |
| `3` | Meal slot, 16–30 min | Maps to `time-3` |
| `4` | Meal slot, >30 min | Maps to `time-4` |

`time-0` remains valid for **instant/no-prep recipes** (e.g., portable snack recipes) but is independent of schedule `busyness=0`.

Migration rules:

1. Legacy `schedule` entries with `0` are migrated into `WorkoutSlot`s (or `schedule_days.workouts`), not `MealSlot`s.
2. Legacy `schedule` entries with `1..4` become `MealSlot`s with `busyness_max=1..4`.
3. Recipe time-tag migration maps by `cooking_time_minutes` only:
   - `0` → `time-0`
   - `1..5` → `time-1`
   - `6..15` → `time-2`
   - `16..30` → `time-3`
   - `31+` → `time-4`

---

# 3. Planner Logic (Critical)

## 3.1 Inputs

```
plan(
    profile: UserProfile,
    week_template: List[DayType],       # e.g. [workout, workout, golf, rest, ...]
    recipe_pool: List[Recipe],          # filtered to user's bank
    active_batches: List[MealPrepBatch],
    seed: Optional[int] = None,         # determinism
) -> MealPlan
```

## 3.2 Output

```
MealPlan {
    days: List[MealPlanDay],
    termination_code: "OK" | "FM-TAG-EMPTY" | "FM-MACRO-INFEASIBLE" | "FM-BATCH-CONFLICT",
    report: { per-day stats, unmet tags, macro deltas }
}
```

## 3.3 Algorithm (pseudocode)

```
function plan(profile, week_template, recipe_pool, active_batches, seed):
    rng = Random(seed or default_seed())
    days = []

    # -- Phase A: resolve day slots from profile + template
    for date, day_type in zip(calendar_dates, week_template):
        slots = profile.day_type_schedules[day_type]   # ordered MealSlot list
        day = MealPlanDay(date=date, day_type=day_type, meals=[])

        # -- Phase B: pre-fill from active meal-prep batches
        for batch in active_batches:
            for assignment in batch.assignments_for(date):
                slot = slots.by_id(assignment.slot_id)
                day.meals.append(PlannedMeal(
                    slot_id=slot.slot_id,
                    recipe_id=batch.recipe_id,
                    servings=1.0,
                    source="meal_prep_batch",
                    batch_id=batch.id,
                ))
                slot.locked = True
                # Soft check: warn if required_tags not met, don't fail

        # -- Phase C: fill remaining slots under hard tag constraints
        for slot in slots.where(locked=False):
            candidates = [r for r in recipe_pool
                          if set(slot.required_tags).issubset(r.tag_slugs)
                          and not violates_constraints(r, profile)]
            if not candidates:
                return fail("FM-TAG-EMPTY", slot=slot.slot_id)

            # -- soft scoring
            scored = []
            for r in candidates:
                score = 0.0
                score += 1.0 * count_preferred_tag_matches(r, slot)
                score -= variety_penalty(r, day, last_n_days=3)   # avoid repeats
                score += macro_fit_score(r, day.remaining_targets(profile))
                score += time_fit_score(r, slot.busyness_max)
                scored.append((score, r))

            scored.sort(key=lambda x: x[0], reverse=True)
            # deterministic tie-break by recipe_id, then rng if still tied
            chosen = tie_break(scored, rng)

            day.meals.append(PlannedMeal(
                slot_id=slot.slot_id,
                recipe_id=chosen.id,
                servings=1.0,
                source="planner",
            ))

        # -- Phase D: validate day macros
        day.totals = aggregate_nutrition(day.meals)
        day.meets_goals = within_tolerance(day.totals, profile.goals)
        days.append(day)

    # -- Phase E: final feasibility report
    report = build_report(days, profile)
    if any_day_grossly_infeasible(days, profile):
        return fail("FM-MACRO-INFEASIBLE", report=report)
    return MealPlan(days=days, termination_code="OK", report=report)
```

## 3.4 Constraints

**Hard (must hold; violation → plan fails):**

- `slot.required_tags ⊆ recipe.tag_slugs`
- `recipe` does not contain any ingredient in `profile.allergies`
- `recipe` does not carry a `constraint:`* tag the user has excluded
- Meal-prep assignments are honored verbatim
- Day macros within ±20 % of targets (tunable) — otherwise report `FM-MACRO-INFEASIBLE` with a partial plan

**Soft (optimize):**

- Preferred tag matches (+)
- Macro fit to remaining daily targets (+)
- Variety across last 3 days (−penalty for repeats, except meal-prep batch)
- Time fit to slot busyness (+)
- User liked_foods containment (+), disliked_foods containment (−)

## 3.5 Forced-recipe selection

**[DECISION]** no separate "force this recipe" control in Sprint 1. The tagging system subsumes it: create a tag with a single recipe in it, set it as a slot's `required_tag`. This keeps one mental model. Exception: meal-prep batches, which are effectively forced and need their own UI.

---

# 4. LLM Integration Design

## 4.1 Recipe Generation Flow

```
[User query]
   │  POST /api/v1/llm/suggest  { query, k=5 }
   ▼
[Stage A — suggest]
   LLM returns: [{name, one_liner, thumbnail_url?, est_macros, reason_match}]
   │
   ▼
[User picks one candidate]
   │  POST /api/v1/llm/generate { suggestion_id }
   ▼
[Stage B — generate]
   1. LLM drafts full ingredient list + instructions (structured output only)
   2. IngredientMatcher resolves each ingredient against USDA (existing)
   3. RecipeValidator enforces schema + nutrition sanity (existing)
   4. RecipeTagger emits typed tags, normalized via Tag service (new)
   5. Duplicate check (fuzzy name match vs recipe bank)
   6. Save → return Recipe + warnings
```

Every stage produces a structured JSON the UI can render as a review screen before the next stage runs.

## 4.2 Tagging Loop

```
recipe_draft -> LLM.suggest_tags(recipe_draft)
            -> returns {context: [...], time: [...], nutrition: [...], constraint: [...]}
            -> TagService.normalize(tag)  # alias resolution, slug creation
            -> recipe.tags = normalized
            -> if any new slug not in TagRegistry:
                 register with source="llm", surface for user confirmation on next view
```

LLM **cannot** write raw nutrition. Nutrition is always computed from resolved USDA ingredients via `src/nutrition/aggregator.py`. This is enforced by:

- `RecipeValidator` rejects any LLM output that contains a `nutrition` block.
- The generation prompt template forbids nutrition fields in the output schema.

## 4.3 Guardrails


| Guardrail                                | Mechanism                                                                                                                         |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| No hallucinated nutrition                | Structured output schema omits nutrition; recomputed from USDA post-generation                                                    |
| No hallucinated ingredients              | Every ingredient must resolve via `IngredientMatcher`; unresolved → reject with `INGREDIENT_UNRESOLVED` error naming the offender |
| No tag explosion                         | `RecipeTagger` capped at ≤ 2 `context`, 1 `time`, ≤ 4 `nutrition`, ≤ 3 `constraint` tags                                          |
| No infinite retry                        | Suggestion stage: max 2 refinements; Generation stage: max 1 retry on validation failure                                          |
| No silent schema drift                   | All LLM calls use Pydantic models from `src/llm/schemas.py`; invalid JSON → hard fail, not repair                                 |
| Deterministic output for same query+seed | Pass `seed` and `temperature=0.2`; cache by hash of (query, seed, model)                                                          |


---

# 5. UX / UI Spec

## 5.1 Principles

- **Card-based, not grid-based.** A day is a column of meal cards, not a row of cells.
- **Drag-and-drop is the primary rearrange gesture.** Tap-to-edit is secondary.
- **Tags are visual chips**, colored per type (context=blue, time=amber, nutrition=green, constraint=red).
- **Meal prep is always visible** as a tray/panel on the planner, never buried in a submenu.
- **Progressive disclosure.** Macros, nutrition detail, and instructions live one tap away — never on the primary card.
- **No spreadsheet vibes.** No fixed-width columns, no row numbers, no "edit cell" affordance.

## 5.2 Key Screens

### 5.2.1 Planner Screen

```
┌─────────────────────────────────────────────────────────────────┐
│ [Week of Apr 20] [◀ prev] [next ▶]          [Generate Plan] ⚙   │
├─────────────────────────────────────────────────────────────────┤
│ MEAL PREP TRAY                                                   │
│ ┌───────────┐ ┌───────────┐  + New batch                         │
│ │ Chicken   │ │ Turkey    │                                      │
│ │ Rice Bowl │ │ Chili     │                                      │
│ │ 3 / 5 left│ │ 2 / 4 left│                                      │
│ └───────────┘ └───────────┘                                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ MON      │ TUE      │ WED      │ THU      │ FRI      │ SAT      │
│ workout  │ workout  │ golf     │ rest     │ workout  │ rest     │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ ▣ Meal 1 │ ▣ Meal 1 │ ...      │          │          │          │
│ Kiwi+Bar │ Kiwi+Bar │                                            │
│ [instant]│ [instant]│                                            │
│ ─────    │ ─────    │                                            │
│ ◆ Meal 2 │ ◆ Meal 2 │  ← ◆ = meal prep, ▣ = required tag lock    │
│ Chicken  │ Chicken  │                                            │
│ Rice(1/5)│ Rice(2/5)│                                            │
│ ...                                                               │
└─────────────────────────────────────────────────────────────────┘
```

Interactions:

- Drag a Meal Prep Tray card onto a slot → creates a `BatchAssignment`.
- Drag a meal card between slots (same or different day) → updates plan; if dragged card is a batch serving, prompt detach/move-serving.
- Tap a card → bottom sheet with macros, ingredients, instructions, **[Swap]** button (opens tag-filtered candidate list).
- Tap **[Swap]** → shows candidates matching slot's required tags, ranked by same scorer the planner uses.

### 5.2.2 Recipe Builder

Single screen, three collapsible sections:

1. **Basics** — name, cooking time, default servings, **"Meal-prep capable"** switch (toggling this adds/removes `context:meal-prep` tag and makes `default_servings` min = 2).
2. **Ingredients** — autocomplete against USDA + local DB. Inline resolve status (✓ / ⚠ / ✗).
3. **Tags** — 4 chip rows, one per tag type. `context` and `time` rows have a **required** indicator; saving is blocked until each has ≥ 1.

A sticky "LLM assist" button at the top: opens a side sheet to run the suggestion flow and pre-fill the form.

### 5.2.3 Meal Prep Flow

Triggered from (a) Recipe card's "Start a batch" CTA, or (b) Planner's Meal Prep Tray **+ New batch**.

Steps:

1. Pick recipe (filtered to `is_meal_prep_capable`).
2. Pick total servings (N) and cook date.
3. Pick target slots across the week (multi-select on a mini-week view).
4. Confirm. Backend creates `MealPrepBatch`; planner refreshes; tray updates.

No separate top-level menu. The feature lives where the user needs it: inside the recipe and inside the planner. This directly resolves the notes' tension about a separate menu vs integrated flow.

### 5.2.4 Tag Management

Settings → Tags. Two tabs:

- **By type** — lists `context`, `time`, `nutrition`, `constraint` with recipe counts per tag.
- **Aliases** — merge duplicates; rename (canonical slug stays, display changes).

LLM-created tags show a **"Suggested by LLM"** badge until confirmed by the user.

## 5.3 Critical UX Decisions


| Question                                         | Decision                                                                                                                                                                 | Rationale                                                                           |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| How does user "force" a specific meal in a slot? | Create a tag with one recipe; assign it as `required_tag` on the slot. OR use meal-prep batch. No dedicated "force" control.                                             | One mental model (tags). Keeps the planner's contract clean.                        |
| How are tags selected on a slot?                 | Multi-select chip picker, grouped by type. Required tags live on the slot definition (in profile), not per-day.                                                          | Per-day required tags = spreadsheet energy. Day-type templates scale.               |
| Is meal prep visible or hidden?                  | Always visible as a tray on the planner + inline CTA on every recipe. Never a separate top-level menu.                                                                   | Notes explicitly flagged the discoverability risk of a hidden menu. Tray solves it. |
| What does a planner failure look like?           | Card for the failing slot shows a red banner with `FM-`* code + one-line fix ("No recipes match tag `pre-workout`. Add one or relax constraints.") + CTA to LLM suggest. | Turns failures into actionable recovery, not dead ends.                             |


---

# 6. Engineering Task Breakdown — Week 1

Complexity: **S** ≤ 0.5 day, **M** 0.5–1.5 days, **L** 1.5–3 days.

Per-task stubs live in `[docs/sprint1/](./sprint1/README.md)`.

## Data Model


| #                                                 | Title                                              | Description                                                                                                                      | Acceptance                                                                          | C   |
| ------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | --- |
| [DM-1](./sprint1/DM-1-tag-model-registry.md)      | Add `Tag` model + registry                         | New `src/data_layer/tags.py` with `Tag`, `TagType`, `TagRegistry`. JSON-backed at `data/tags/registry.json`.                     | Unit tests: slug normalization, alias resolution, type validation.                  | M   |
| [DM-2](./sprint1/DM-2-recipe-tags-extension.md)   | Extend `Recipe` with `tags`                        | Add `tags: List[Tag]`, `default_servings: int`, derived `is_meal_prep_capable`. Update `recipes.json` schema + migration script. | All existing recipes load post-migration; `is_meal_prep_capable` correctly derived. | M   |
| [DM-3](./sprint1/DM-3-meal-prep-batch-entity.md)  | `MealPrepBatch` entity + store                     | New model + JSON store at `data/meal_prep/batches.json`. CRUD through repository.                                                | Round-trip tests; orphan detection on recipe delete.                                | M   |
| [DM-4](./sprint1/DM-4-userprofile-slots.md)       | `MealSlot` + `day_type_schedules` in `UserProfile` | Add typed slots with `required_tags`, `preferred_tags`, `busyness_max`. Back-compat shim for current `schedule: Dict[str, int]`. | Old profile YAMLs still load; new profiles expose typed slots.                      | M   |
| [DM-5](./sprint1/DM-5-busyness-time-migration.md) | Busyness → `time-`* tag migration                  | One-shot script.                                                                                                                 | Every existing recipe has exactly 1 `time-*` tag after run.                         | S   |


## Backend


| #                                               | Title                                  | Description                                                                                                   | Acceptance                                                                    | C   |
| ----------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --- |
| [BE-1](./sprint1/BE-1-tag-service.md)           | `TagService` (CRUD + normalize)        | Create, resolve, alias, merge. Exposed on FastAPI.                                                            | `POST/GET/PATCH /api/v1/tags` covered by tests.                               | M   |
| [BE-2](./sprint1/BE-2-planner-batch-prefill.md) | Planner Phase-B pre-fill from batches  | Extend `src/planning/phase3_feasibility.py` + `phase6_candidates.py` to read `active_batches` and lock slots. | Plan with a batch produces identical batched meals in all assigned slots.     | M   |
| [BE-3](./sprint1/BE-3-hard-tag-filter.md)       | Hard tag-constraint filter             | Replace current tag filter with typed logic: `required_tags ⊆ recipe.tags`.                                   | Tests: empty-result → `FM-TAG-EMPTY`; single-recipe-tag acts as force-select. | M   |
| [BE-4](./sprint1/BE-4-soft-scoring-tags.md)     | Soft scoring: preferred tags + variety | Add to `phase4_scoring.py`.                                                                                   | Plans with preferred tags pick them > 80 % when feasible (regression test).   | S   |
| [BE-5](./sprint1/BE-5-meal-prep-endpoints.md)   | Meal-prep endpoints                    | `POST/GET/DELETE /api/v1/meal_prep_batches`. Include orphan cleanup.                                          | Integration tests; OpenAPI updated.                                           | M   |
| [BE-6](./sprint1/BE-6-plan-request-wiring.md)   | Planner request wiring                 | `PlanRequest` includes `active_batches` (server-populated).                                                   | CLI + Flutter produce the same plan given same profile (parity test).         | S   |
| [BE-7](./sprint1/BE-7-failure-codes.md)         | Failure-code surfacing                 | Return `FM-TAG-EMPTY` with offending slot + tag; `FM-BATCH-CONFLICT` on assignment overlaps.                  | Error JSON schema tested.                                                     | S   |


## AI / LLM


| #                                              | Title                              | Description                                                                                                          | Acceptance                                                                 | C   |
| ---------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --- |
| [AI-1](./sprint1/AI-1-llm-suggest.md)          | `LLM.suggest_recipes(query, k)`    | New endpoint + pipeline stage returning shortlist with `one_liner`, `est_macros`, `reason_match`. Structured output. | Returns k candidates within 10 s; 100 % schema-valid.                      | M   |
| [AI-2](./sprint1/AI-2-two-stage-generation.md) | Two-stage generation wiring        | Split current `pipeline.py` into `suggest` + `generate`. `generate` keyed by a `suggestion_id` to prevent drift.     | E2E test: query → suggest → generate → recipe saved.                       | M   |
| [AI-3](./sprint1/AI-3-recipe-tagger-v2.md)     | `RecipeTagger` v2 emits typed tags | Update `src/llm/recipe_tagger.py` to output `{context, time, nutrition, constraint}` and normalize via `TagService`. | Tagger test corpus: ≥ 95 % recipes get ≥ 1 `context`, exactly 1 `time`.    | M   |
| [AI-4](./sprint1/AI-4-nutrition-guardrail.md)  | Nutrition hallucination guardrail  | Remove nutrition from LLM output schema; `RecipeValidator` rejects any LLM-sourced nutrition field.                  | Regression test with a prompt trying to inject nutrition → rejected.       | S   |
| [AI-5](./sprint1/AI-5-duplicate-detection.md)  | Duplicate detection                | Fuzzy match (token-sort ratio) ≥ 0.85 against existing bank on generate.                                             | Generating a near-duplicate returns the existing recipe id with a warning. | S   |


## Frontend (Flutter)


| #                                               | Title                             | Description                                                                            | Acceptance                                              | C   |
| ----------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------- | --- |
| [FE-1](./sprint1/FE-1-planner-card-rebuild.md)  | Planner screen card-based rebuild | New widgets: `DayColumn`, `MealCard`, `TagChip`. Remove grid layout.                   | Matches §5.2.1 wireframe; passes widget tests.          | L   |
| [FE-2](./sprint1/FE-2-drag-and-drop.md)         | Drag-and-drop between slots       | Use `Draggable` + `DragTarget`; detach-prompt on batch serving.                        | Manual QA + widget tests for the detach dialog.         | M   |
| [FE-3](./sprint1/FE-3-meal-prep-tray.md)        | Meal Prep Tray panel              | Persistent panel; drag source for batch cards; shows remaining servings.               | Dragging a card onto a slot creates assignment via API. | M   |
| [FE-4](./sprint1/FE-4-recipe-builder-revamp.md) | Recipe Builder revamp             | Three sections per §5.2.2; inline ingredient resolution status.                        | Required-tag guard blocks save with inline error.       | L   |
| [FE-5](./sprint1/FE-5-tag-chip-picker.md)       | Tag chip picker                   | Grouped by type, colored. Reused across Recipe Builder and slot config.                | Widget test; color-contrast a11y check.                 | S   |
| [FE-6](./sprint1/FE-6-llm-suggest-flow.md)      | LLM suggest → approve flow        | Side sheet with candidate cards; approve routes to generation; loading + error states. | E2E happy path + reject-all path.                       | M   |
| [FE-7](./sprint1/FE-7-meal-prep-wizard.md)      | Meal-prep creation wizard         | 4-step modal per §5.2.3.                                                               | Creates a batch, planner refresh shows pre-fills.       | M   |
| [FE-8](./sprint1/FE-8-slot-config.md)           | Slot config in Profile            | UI to edit required/preferred tags per day-type slot.                                  | Persists to profile YAML via API.                       | M   |
| [FE-9](./sprint1/FE-9-failure-surfaces.md)      | Failure-state surfaces            | Red banner + "Fix with LLM" CTA for `FM-*`.                                            | Triggered in a feasibility-fail test.                   | S   |


**Rough total:** ~18–22 engineering-days of work. Single dev across Week 1 + Week 2 is realistic if Week 1 focuses on DM + BE + FE-1/FE-3/FE-5 (the critical path), deferring AI-1..AI-5 and the LLM side-sheet to Week 2.

---

# 7. Risks & Design Decisions

### R1. Tagging vs direct selection

- **Risk:** Tagging adds ceremony. A user who just wants "always scrambled eggs Monday breakfast" now has to create a tag and pin it.
- **Decision:** Accept the ceremony. The alternative (dual system: tags + force-select) doubles planner complexity and UI surface. Mitigation: a recipe's own name becomes its tag slug automatically when the user clicks **"Always use this for this slot"** in the Recipe card — sugar over the tag system, not a parallel one.

### R2. Meal prep visibility vs minimalism

- **Risk:** A persistent tray clutters the planner for users who don't meal prep.
- **Decision:** Tray is collapsible and auto-hides when there are 0 active batches. First-time discovery handled by an inline "Meal prep saves time across the week" empty-state card with a **+ New batch** CTA. This resolves the notes' stated tension explicitly.

### R3. LLM optional vs integrated

- **Risk:** Deep LLM integration increases cost, latency, and failure surface. Opt-in keeps the app reliable.
- **Decision:** LLM is **opt-in per action**, never in the critical path. The planner never calls an LLM. Recipe creation works fully without LLM (the "LLM assist" button is additive). This preserves determinism (G7) and keeps the bill small.

### R4. Planner determinism with stochastic scoring

- **Risk:** Adding variety penalties + tie-breaking can make plans non-reproducible.
- **Decision:** Every randomness source is seeded. Default seed is a hash of (profile_version, week_start_date). Exposed via `PlanRequest.seed`. Verified by a parity test between CLI and Flutter.

### R5. Tag sprawl (esp. from LLM)

- **Risk:** LLM invents `super-high-protein`, `ultra-high-protein`, etc.
- **Decision:** LLM-created tags are **quarantined** (flagged `source="llm"`, badge in UI) until confirmed. Tag merge tooling in settings. Hard cap on tag count per type per recipe (§4.3).

### R6. Back-compat with existing profile YAML

- **Risk:** Current `user_profile.yaml` has `schedule: {"08:00": 2, ...}`; slot-based schedule is a bigger shape.
- **Decision:** `src/models/legacy_schedule_migration.py` already exists; extend it. On load, auto-promote old profiles into a single-day-type template (`"default"`). User prompted on first Flutter launch to split into workout/golf/rest templates.

### R7. `time-0` semantics vs workout slots (`busyness=0`)

- **Risk:** Overloading `0` for both workouts and instant meals causes invalid migration and planner confusion.
- **Decision:** `busyness=0` remains workout-only at the schedule level; instant meal recipes use `time-0` from `cooking_time_minutes = 0`. These are separate concepts. `time-0` recipes should usually carry `context:portable` and/or `context:no-kitchen` for slot matching.

---

# 8. Exit Criteria for Sprint 1

- Every recipe in `data/recipes/recipes.json` carries ≥ 1 `context` tag and exactly 1 `time-`* tag.
- `UserProfile` supports day-type templates; workout/golf/rest fixtures exist in `config/`.
- Planner produces a 7-day plan for the user's profile in < 120 s, with tag constraints honored (100 % in tests).
- Meal Prep Tray creates a batch and pre-fills ≥ 3 slots end-to-end from Flutter in < 30 s.
- LLM suggest → generate round-trips a new `shrimp + high-protein` recipe that validates, gets auto-tagged, and is plannable.
- Parity test (CLI vs Flutter, same seed) passes.
- UI review: planner screen does not resemble a spreadsheet (card layout, tag chips, DnD working).

---

## Summary of opinionated decisions

1. **Two required tag types (`context`, `time`); the rest optional.** Minimum viable constraint surface.
2. **No separate "force recipe" control** — tags + single-recipe tags cover it.
3. **Meal prep is a first-class entity** and lives in a **persistent, collapsible tray** on the planner, plus a CTA on each recipe. No separate menu.
4. **LLM is opt-in, two-stage (suggest → approve → generate), and cannot write nutrition.** Planner never calls an LLM.
5. **Busyness split is explicit:** schedule `0` stays workout-only; meal slot busyness `1..4` maps to recipe time tags, with `time-0` reserved for instant/no-prep recipes.
6. **Planner is deterministic given (profile, week, seed).** All randomness seeded; CLI/Flutter parity tested.
7. **Critical path for Week 1:** DM-1..DM-5 → BE-1..BE-3, BE-5 → FE-1, FE-3, FE-5. Everything else ships in Week 2.

