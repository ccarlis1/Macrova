# Sprint 1 — Tagging v2, Meal Prep, Planner Intelligence, UI Revamp

**Owner:** ccarls1  ·  **Duration:** Week 1 (5 working days) + Week 2 buffer  ·  **Status:** Ready to build (architecture-reconciled)

> Per-task stubs live in `[docs/sprint1/](./sprint1/README.md)`. This revision aligns the sprint with `[../.cursor/architecture.json](../.cursor/architecture.json)` and resolves issues in `[../.cursor/report.json](../.cursor/report.json)`.

---

# 0. Brief Summary

This sprint makes meal planning smarter and easier to use. We are moving to one clear tag system, improving how meal prep and pinned meals are handled, keeping planner behavior consistent, and updating the app UI so users can set meal needs with simple controls. The goal is better meal matches, fewer conflicts, and a cleaner planning experience.

---

# 1. Product Requirements Document

## 1.1 Problem Definition


| #   | Problem                                                                                                                               | User behavior evidence                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| P1  | **Planner cannot express real-world meal slot intent.** A slot is not "breakfast" — it's "portable, no-kitchen, must be kiwis + bar." | User manually overrides output; plan fights reality.                                      |
| P2  | **Recipes cannot be reliably reused across busy schedules.** Meal prep exists in the user's head, not the system.                     | User cooks one batch Sunday → eats it Mon/Tue/Wed but planner re-picks different lunches. |
| P3  | **Tagging is nominal, not functional.** Tags exist but do not drive selection through one canonical path.                             | User cannot filter planner to a tag; LLM tags are free-form noise.                        |
| P4  | **UI feels like a spreadsheet.** High cognitive load to read or rearrange a day.                                                      | User reads CLI markdown output instead of using the Flutter screens.                      |
| P5  | **LLM recipe generation is a blind fire-and-forget.** User cannot preview before paying full generation cost + USDA lookups.          | User distrusts auto-generated recipes; manually edits after.                              |


## 1.2 Goals & Success Metrics


| Goal | Metric                                                     | Target                                                                                                                                                                                                                                |
| ---- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1   | Time to generate a full 7-day plan from a clean profile    | < 120 s end-to-end (90 s planner + 30 s user confirms)                                                                                                                                                                                |
| G2   | Time to add a meal-prep batch and have it populate 3 slots | < 30 s, ≤ 4 taps                                                                                                                                                                                                                      |
| G3   | Planner respects hard tag constraints                      | 100 % of slots with a required tag match it (enforced in tests)                                                                                                                                                                       |
| G4   | LLM-generated recipes are schema-valid and USDA-grounded   | 100 % pass `RecipeValidator`; 0 hallucinated nutrient values                                                                                                                                                                          |
| G5   | User reuses recipes instead of re-picking                  | Meal prep is optional. If a meal-prep batch is created, target ≥ 60 % lunch reuse from that batch; plans with partial reuse (for example 2/5 days) or 0 prepped meals are still valid.                                         |
| G6   | Tag coverage of recipe corpus                              | ≥ 95 % of recipes carry ≥ 1 `context` tag (after unified tag migration)                                                                                                                                                               |
| G7   | Planner determinism parity (CLI vs Flutter)                | Same plan outcome for same seed and inputs; parity artifacts per `[docs/DEBUG_PLANNER_PARITY.md](./DEBUG_PLANNER_PARITY.md)` (`cli_plan_request.json`, `recipe_pool_snapshot.json` including `recipe_ids_sha256`, `planner_run.json`) |


## 1.3 Core Features

### Must-have (Sprint 1)

#### F1. Tagging System v2 (unified)

- **Description:** Typed tag slugs (`context`, `time`, `nutrition`, `constraint`) attached to every recipe and consumed by planner + LLM through **one** path: extend `RecipeTagsJson` / persisted recipe records and `tag_repository.py` + `recipe_tags.json`; evolve `apply_tag_filtering` in `tag_filtering_service.py` (do not fork a second filter pipeline).
- **Why:** Prerequisite for P1, P3, P5. Eliminates parallel tag sources.
- **Edge cases:**
  - Recipe with incomplete typed coverage → surfaced with a warning badge in UI; not silently eligible for hard tag-constrained slots.
  - Conflicting typed time tags → reject at save-time with inline error.
  - User merges duplicate slugs → `POST` merge on tag API rewrites recipe references in one transaction (extends BE-1 pattern).
- **Dependencies:** Migration from current `RecipeTagsJson` + free-form slot `tags` into canonical slug lists; planner reads only the unified store.

#### F2. Meal Prep Batches

- **Description:** A recipe can be started as a meal prep batch: user picks servings (N) and target `(day_index, slot_index)` pairs (aligned with `Assignment` / `pinned_assignments` addressing). Batch owns assignments; planner treats them as locked slots before search.
- **Why:** P2.
- **Edge cases:** N > assigned slots → leftovers surfaced; slot occupied → Replace / Skip / Cancel; recipe deleted → batch `orphaned`; partial consumption updates remaining servings.
- **Dependencies:** F1; new `MealPrepBatch` persistence; integration with `plan_meals` / orchestrator inputs (not a parallel planner).

#### F3. Planner Tag-Constrained Selection

- **Description:** Extend `MealSlot` in `src/models/schedule.py` with optional `**required_tag_slugs`** and `**preferred_tag_slugs**` (additive fields). Hard filter: slot’s required slugs ⊆ recipe’s resolved tag slug set. Preferred slugs contribute in `phase4_scoring.py` only.
- **Why:** P1; extends canonical `DaySchedule` / `MealSlot` rather than a parallel slot model.
- **Edge cases:** Empty candidate set → `FM-TAG-EMPTY`; exactly one recipe matches required set → deterministic pick; meal-prep lock + pin + tags → follow **§3.5 precedence**.
- **Dependencies:** F1; extends `recipe_tag_filtering` / `tag_filtering_service.py`.

#### F4. LLM Recipe Suggestion → Approval → Generation

- **Description:** Two-stage flow: `POST /api/v1/llm/suggest` → user picks candidate → `POST /api/v1/llm/generate` (or align names with existing `POST /api/v1/recipes/generate-validated` by sharing validation + tagging steps). Stage B uses existing `IngredientMatcher`, `RecipeValidator`, and unified tag persistence.
- **Why:** P5 + G4.
- **Edge cases:** Unresolved ingredient → `INGREDIENT_UNRESOLVED`; reject-all → bounded retry; duplicate name → AI-5 behavior.
- **Dependencies:** `src/llm/pipeline.py` extended, not replaced; `src/llm/schemas.py` for structured outputs.

#### F5. UI Revamp (Cards, Drag-and-Drop, Visual Tags)

- **Description:** Flutter rebuild per §5; complete `flutter_plan_request_vs_server_tag_fields` parity so client sends the same tag filter fields the server already accepts.
- **Why:** P4.
- **Dependencies:** F1–F3.

### Nice-to-have (Future / Week 2+)

- Smart suggestions; nutrition heat-map; grocery list diff; LLM rescue plan; URL import.

---

# 2. System Design (High Level)

## 2.1 Core Entities (architecture-aligned)

```
UserProfile ──< DaySchedule (canonical per day_index)
                    │
                    ├─ meals: List[MealSlot]     # src.models.schedule.MealSlot
                    └─ workouts: List[WorkoutSlot]

Recipe ──(tags)── RecipeTagsJson (+ additive typed slug fields in persistence)
  │
  └─< MealPrepBatch ──< BatchAssignment (day_index, slot_index, servings)

DailyMealPlan ──< Meal ──> Recipe
                     │
                     └── (optional extensions) slot_index, source, batch_id, servings
```

### Entity detail

**Recipe** (`src/data_layer/models.py::Recipe`) — **extend**

- Existing: `id`, `name`, `ingredients`, `cooking_time_minutes`, `instructions`
- Add: `default_servings: int` (default 1); typed tag slugs persisted **in the same JSON store as today’s recipe bank**, merged with / mirrored from `RecipeTagsJson` so `tag_repository.py` remains authoritative for planner reads.
- `is_meal_prep_capable`: derived (`default_servings ≥ 2` and `context:meal-prep` present).

**RecipeTagsJson** (`src/llm/schemas.py`) — **extend**

- Existing: `cuisine`, `cost_level`, `prep_time_bucket`, `dietary_flags`
- Add optional parallel typed lists **or** a single `typed_tags: Dict[str, List[str]]` keyed by `context|time|nutrition|constraint` (implementation choice: one additive object on `Recipe` / draft; must serialize round-trip with `recipes.json` and LLM drafts).

**Tag slug registry** — **extend `tag_repository.py` + `recipe_tags.json`**

- Canonical slug, display label, type, source (`user|llm|system`), aliases.
- **Not** a second tag database alongside `recipe_tags.json`; DM-1 evolves this module.

**MealSlot** (`src/models/schedule.py::MealSlot`) — **extend**

- Existing: `index`, `busyness_level`, `tags`, `preferred_time`
- Add (optional, additive): `required_tag_slugs: Optional[List[str]]`, `preferred_tag_slugs: Optional[List[str]]`
- `busyness_level` remains **1–4** for meals. Workouts are **never** meals; they live only under `DaySchedule.workouts`.

**WorkoutSlot** (`src/models/schedule.py::WorkoutSlot`) — **extend only additively**

- Authoritative fields: `after_meal_index`, `type` (`AM`|`PM`|`general`), `intensity` (`low`|`moderate`|`high`|None).
- Do **not** replace this schema with `slot_id` / `day_type` / `ordinal`. If stable UI ids are needed, derive them at render time (e.g. `day-{d}-gap-{after_meal_index}`).

**DaySchedule** — unchanged contract; sprint adds optional tag slugs on `MealSlot` only.

**Meal** (`src/data_layer/models.py::Meal`) — **extend (additive)**

- Existing: `recipe`, `nutrition`, `meal_type`, `scheduled_time`, `busyness_level`
- Add optional: `slot_index: Optional[int]`, `source: Optional[Literal["planner","meal_prep_batch","user_override"]]`, `batch_id: Optional[str]`, `servings: Optional[float]`

**DailyMealPlan** — keep `date`, `meals`, `total_nutrition`, `goals`, `meets_goals`; add optional `warnings: Optional[List[str]]]` if needed for batch tag mismatches.

**MealPlanResult** (`src/planning/phase10_reporting.py`) — **authoritative server planning output**

- Sprint failure / report fields attach here (or nested `report`) as already used by orchestrator; **do not** introduce a conflicting top-level `MealPlan` type in backend Python. API responses may add optional `terminationCode` / `failureDetails` **without removing** existing fields consumed by Flutter.

**Flutter `MealPlan` / `MealPlanDay` / `Meal`** — **additive JSON fields only**

- Extend client models in lockstep with API optional fields (`slotId`, `source`, `batchId`, `servings`, `terminationCode`, `failureDetails`). Preserve existing field names (`day`, `dayTotals`, etc.).

**MealPrepBatch** (new)

- `id`, `recipe_id`, `total_servings`, `cook_date`, `assignments: List[{day_index, slot_index, servings}]`, `status`

**PlanningUserProfile** (`src/planning/phase0_models.py`) — **use as planner input**

- Includes `pinned_assignments: Dict[Tuple[int,int], str]` today; remains the forcing mechanism alongside tags and meal-prep locks.

### Slot / profile mapping table (naming reconciliation)


| Concept in sprint UX     | Canonical store                             | Notes                                                                                      |
| ------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Stable slot address      | `(day_index, slot_index)`                   | Aligns with `Assignment`, `pinned_assignments`, and `MealSlot.index` (1-based meal index). |
| Max cook band            | `MealSlot.busyness_level`                   | Existing 1–4; maps to recipe `time-*` tags per §2.4.                                       |
| Legacy clock             | `MealSlot.preferred_time`                   | Optional `HH:MM`.                                                                          |
| Informal labels          | `MealSlot.tags`                             | Legacy string labels; may overlap with slugs during migration.                             |
| Hard / soft planner tags | `required_tag_slugs`, `preferred_tag_slugs` | New optional fields on `MealSlot`.                                                         |
| Workout                  | `WorkoutSlot` on same `DaySchedule`         | `after_meal_index`, `type`, `intensity` only.                                              |


## 2.2 Tagging System Redesign

### Tag types


| Type           | Purpose                              | Examples                                                              | Required on recipe? |
| -------------- | ------------------------------------ | --------------------------------------------------------------------- | ------------------- |
| **context**    | Where/when this recipe fits in a day | `meal-prep`, `instant-snack`, `pre-workout`, `portable`, `no-kitchen` | Yes, ≥ 1            |
| **time**       | Meal prep/cook effort (recipe-only)  | `time-0` … `time-4`                                                   | Yes, exactly 1      |
| **nutrition**  | Macro / micronutrient emphasis       | `high-protein`, `high-omega-3`, `high-fiber`, `high-calcium`          | Optional            |
| **constraint** | Hard exclusions                      | `no-dairy`, `nut-free`                                                | Optional            |


**[DECISION]** Single read path: planner tag filter reads the same structures as `recipe_tag_filtering` after migration.

### How the planner consumes tags

1. Build `PlanningUserProfile` + `PlanningRecipe` list via existing `converters.py`.
2. Apply **existing** `apply_tag_filtering` pipeline, extended for typed slugs + slot `required_tag_slugs`.
3. Hard constraint: `required_tag_slugs` ⊆ resolved recipe slug set.
4. Soft: `preferred_tag_slugs` in `phase4_scoring.py`.

### Micronutrient deficit recovery (optional)

- Deficit recovery uses **preferred** nutrition slugs (soft), not hard-required tags by default.
- Example: omega-3 deficit can raise preference for recipes tagged `high-omega-3`.
- Plans remain valid with partial or zero micronutrient-tag matches when constraints or availability limit options.
- Keep nutrient-recovery tags in a curated slug set (start small; expand with evidence).

### Canonical slug + aliases

- Stored alongside `recipe_tags.json` / tag repository; exposed via tag HTTP API (BE-1 extends existing surface).

## 2.3 Meal Prep System

### What makes a recipe "meal prep"

1. Carries `context:meal-prep` (typed slug).
2. `default_servings ≥ 2`.

### Serving distribution logic

- Assignments use `(day_index, slot_index)` matching planner addressing.
- One serving per assignment in Sprint 1 unless explicitly extended later.

### Planner integration

- Before search: materialize locked `(day_index, slot_index) → recipe_id` from active batches (same precedence tier as pins; see §3.5).
- Orchestrator / `plan_meals` consumes these locks; no duplicate pre-fill outside that path.

### UI + backend interaction

- `POST/GET/DELETE /api/v1/meal_prep_batches` as additive REST.
- `PlanningUserProfile` or plan request DTO extended to pass batch locks into `plan_meals` (exact hook: **REQUIRES_VERIFICATION** against current `plan_meals` signature during implementation).

## 2.4 Busyness scale reconciliation (+ workouts)

**[DECISION]** `MealSlot.busyness_level` stays **1–4** for meals. Workouts use `**WorkoutSlot`** on `DaySchedule.workouts`, not `busyness_level = 0` on a meal after canonical migration.


| Legacy `schedule` int (pre-migration) | Canonical target                                                                                                                           |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `0`                                   | Workout time → becomes a `WorkoutSlot` (gap after a meal) or workout row per `src.models.legacy_schedule_migration`; **not** a `MealSlot`. |
| `1`–`4`                               | `MealSlot.busyness_level`                                                                                                                  |


**Recipe `time-`* tags** (effort class, independent of meal count):


| Tag      | `cooking_time_minutes` | Label             |
| -------- | ---------------------- | ----------------- |
| `time-0` | 0                      | Instant / no prep |
| `time-1` | 1–5                    | Quick             |
| `time-2` | 6–15                   | Fast              |
| `time-3` | 16–30                  | Medium            |
| `time-4` | 31+                    | Long              |


Canonical slug values (`time-0` ... `time-4`) are machine-facing identifiers for filtering, persistence, and API contracts. User-facing surfaces should render the `Label` text (or equivalent localized copy), not raw slug names like `time-2`.

`time-`* is **not** the same dimension as “8 meals per day”; it classifies **recipes**, while each of the eight `MealSlot`s carries its own `busyness_level` cap.

---

# 3. Planner Logic (Critical)

## 3.1 Inputs (orchestrator-aligned)

Planning runs through the **existing** deterministic stack:

- **Convert** `UserProfile` + recipes → `PlanningUserProfile`, `List[PlanningRecipe]`, schedules, trackers (`converters.py`, `phase0_models.py`).
- **Inputs to search / assignment:** `PlanningUserProfile` (includes `pinned_assignments`, micronutrient knobs, workout indices), `PlanningRecipe` pool, `WeeklyTracker` / `DailyTracker` state, `Assignment` mutations across days/slots, optional **active meal-prep locks** (same keying as pins: `(day_index, slot_index)` → `recipe_id`).
- **Entrypoint:** `plan_meals` in `src/planning/planner.py` as invoked from API / CLI paths (orchestrator in `orchestrator.py` for LLM-assisted modes). **REQUIRES_VERIFICATION:** exact parameter list when wiring `active_batches`; must not bypass `phase7_search` pinned validation.

## 3.2 Output

- **Server:** `MealPlanResult` from `phase10_reporting` (existing `termination_code`, `failure_mode`, `report`, etc.). Extend `report` with structured failure entries for `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT` without breaking existing consumers.
- **Persisted daily shape:** `DailyMealPlan` + `Meal` with **optional** extended fields for UI (`slot_index`, `source`, `batch_id`, `servings`).
- **Flutter:** extend response DTOs additively; do not rename `day` → `date` or `dayTotals` → `totals` in a breaking way.

## 3.3 Algorithm (pseudocode, conceptual)

```
function planDeterministic(profile, recipes, active_batches, seed):
    p_profile, p_recipes, initial_assignments = convert(profile, recipes)
    apply_batch_locks(initial_assignments, active_batches)   # same shape as pinned locks
    validate_pinned_assignments(p_profile, recipe_by_id, horizon_days)

    result = plan_meals(
        user_profile=p_profile,
        planning_recipes=p_recipes,
        seed=seed,
        ... // existing args per planner.py — REQUIRES_VERIFICATION at implementation
    )

    if result.failure_mode:
        return result   # carries termination_code / report per MealPlanResult

    attach_optional_meal_metadata(result.days, active_batches)
    return result
```

Tag filtering and scoring occur **inside** the existing phase pipeline (`tag_filtering_service`, `phase4_scoring`, `phase7_search`), not in a standalone `plan()` helper.

## 3.4 Constraints

- Hard: required tag slugs ⊆ recipe slugs; allergies; batch locks; pin validity (`validate_pinned_assignments`).
- Soft: preferred tags, variety, macros, `busyness_level` vs recipe `time-*` fit.

## 3.5 Forced-recipe selection and precedence

The product **does** support forcing via `**PlanningUserProfile.pinned_assignments`** (existing). Sprint additions coexist as follows:


| Priority    | Mechanism                        | Key                                           |
| ----------- | -------------------------------- | --------------------------------------------- |
| 1 (highest) | Meal-prep batch lock for a slot  | `(day_index, slot_index)` from batch          |
| 2           | Pinned assignment                | `pinned_assignments[(day_index, slot_index)]` |
| 3           | Required tag slugs (hard filter) | On `MealSlot`                                 |
| 4           | Planner search / scoring         | Default fill                                  |


**[DECISION]** Tags do not remove pins; pins do not remove batch locks. UI may offer “pin this recipe” and “assign batch serving” as separate actions that both map into the table above.

---

# 4. LLM Integration Design

## 4.1 Recipe Generation Flow

- Stage A: suggest shortlist (structured schema in `schemas.py`).
- Stage B: generate draft → validate → USDA resolve → compute nutrition in aggregator → write unified tags → persist.
- Reuse / align with existing validated recipe endpoints so one validation path remains.

## 4.2 Tagging Loop

- LLM proposes typed slugs → normalize through **tag_repository** (aliases, caps) → persist on recipe / `RecipeTagsJson` extension.
- Nutrition slugs use a curated vocabulary (for example `high-omega-3`, `high-fiber`, `high-calcium`) and are treated as recommendation signals (soft).
- Where nutrient values are needed to confirm tags, rely on post-validation USDA-computed nutrition, not LLM-declared nutrition values.

## 4.3 Guardrails

- Unchanged intent: no hallucinated nutrition in LLM JSON; schema-only outputs; caps on tag counts; bounded retries.
- Nutrition-tag quality guardrail: micronutrient-focused tags must be selected from the curated registry and validated against computed nutrition when thresholds are used.

---

# 5. UX / UI Spec

Unchanged intent: card layout, DnD, tag chips, meal-prep tray, failure banners keyed off `MealPlanResult.report` / API `failureDetails`.

**Critical UX adjustments**

- “Force recipe” may be **pin** (existing) **or** single-recipe required tag **or** meal-prep lock; copy must mention all three.
- Slot editing maps to `**MealSlot` fields** in `DaySchedule` (`required_tag_slugs` / `preferred_tag_slugs`), not a parallel schema.

---

# 6. Engineering Task Breakdown — Week 1

Complexity: **S** ≤ 0.5 day, **M** 0.5–1.5 days, **L** 1.5–3 days.

## Data Model


| #                                                 | Title                                    | Description                                                                                                                                           | Acceptance                                                       | C   |
| ------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --- |
| [DM-1](./sprint1/DM-1-tag-model-registry.md)      | Unify tag registry with `tag_repository` | Evolve `tag_repository.py` / `recipe_tags.json` + optional `RecipeTagsJson` / `Recipe` persistence for typed slugs; one planner read path.            | No duplicate tag DB; `apply_tag_filtering` uses unified slugs.   | M   |
| [DM-2](./sprint1/DM-2-recipe-tags-extension.md)   | Extend `Recipe` + JSON                   | Additive fields + migration for `default_servings` and typed tags.                                                                                    | Round-trip load/save; tests.                                     | M   |
| [DM-3](./sprint1/DM-3-meal-prep-batch-entity.md)  | `MealPrepBatch` + store                  | JSON store; assignments `(day_index, slot_index)`.                                                                                                    | CRUD + orphan tests.                                             | M   |
| [DM-4](./sprint1/DM-4-userprofile-slots.md)       | Extend `MealSlot` + schedules            | Add optional `required_tag_slugs` / `preferred_tag_slugs` on `src/models/schedule.py::MealSlot`; migrate legacy YAML via `legacy_schedule_migration`. | Valid `DaySchedule` invariants; workouts use `WorkoutSlot` only. | M   |
| [DM-5](./sprint1/DM-5-busyness-time-migration.md) | Recipe `time-`* migration                | Script from `cooking_time_minutes` only.                                                                                                              | Every recipe has exactly one `time-*` slug.                      | S   |


## Backend


| #                                               | Title                         | Description                                                                                                                                                                    | Acceptance                                            | C   |
| ----------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | --- |
| [BE-1](./sprint1/BE-1-tag-service.md)           | Tag HTTP API                  | Extends registry; merge/alias endpoints.                                                                                                                                       | Tests + OpenAPI.                                      | M   |
| [BE-2](./sprint1/BE-2-planner-batch-prefill.md) | Batch locks in planner        | Wire `active_batches` into `PlanningUserProfile` / `plan_meals` path at same precedence as pins; **REQUIRES_VERIFICATION** for exact insertion point in `planner.py` / phases. | Locked slots match batch.                             | M   |
| [BE-3](./sprint1/BE-3-hard-tag-filter.md)       | Extend `recipe_tag_filtering` | Evolve `tag_filtering_service.py` / `tag_filter.py` for slot `required_tag_slugs`; do not add a second filter pipeline.                                                        | `FM-TAG-EMPTY` test; Flutter parity fields completed. | M   |
| [BE-4](./sprint1/BE-4-soft-scoring-tags.md)     | Preferred tags + variety      | Extend `phase4_scoring.py`.                                                                                                                                                    | Regression tests.                                     | S   |
| [BE-5](./sprint1/BE-5-meal-prep-endpoints.md)   | Meal-prep REST                | Additive endpoints.                                                                                                                                                            | Integration tests.                                    | M   |
| [BE-6](./sprint1/BE-6-plan-request-wiring.md)   | Plan request hydration        | Server loads batches + seeds consistently for CLI/API.                                                                                                                         | Parity artifacts per DEBUG doc.                       | S   |
| [BE-7](./sprint1/BE-7-failure-codes.md)         | Structured failures           | Extend `MealPlanResult.report` / API envelope additively.                                                                                                                      | Schema tests.                                         | S   |


## AI / LLM


| #                                              | Title                     | Description                                                                    | Acceptance             | C   |
| ---------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------ | ---------------------- | --- |
| [AI-1](./sprint1/AI-1-llm-suggest.md)          | Suggest endpoint          | Structured shortlist.                                                          | Schema + timing tests. | M   |
| [AI-2](./sprint1/AI-2-two-stage-generation.md) | Two-stage pipeline        | Extends `pipeline.py`; shares validator with existing generate-validated flow. | E2E test.              | M   |
| [AI-3](./sprint1/AI-3-recipe-tagger-v2.md)     | Tagger → unified registry | Writes typed slugs through tag_repository.                                     | Corpus tests.          | M   |
| [AI-4](./sprint1/AI-4-nutrition-guardrail.md)  | Nutrition guardrail       | Schema excludes nutrition from LLM.                                            | Regression.            | S   |
| [AI-5](./sprint1/AI-5-duplicate-detection.md)  | Duplicate detection       | Fuzzy match before save.                                                       | Tests.                 | S   |


## Frontend (Flutter)


| #    | Title            | Description                                   | Acceptance       | C   |
| ---- | ---------------- | --------------------------------------------- | ---------------- | --- |
| FE-1 | Planner cards    | Rebuild per §5.                               | Widget tests.    | L   |
| FE-2 | DnD              | Slot moves.                                   | Tests + QA.      | M   |
| FE-3 | Meal prep tray   | Uses batch API.                               | Integration.     | M   |
| FE-4 | Recipe builder   | Unified tags + `RecipeTagsJson` fields.       | Save validation. | L   |
| FE-5 | Tag chip picker  | Registry-backed.                              | A11y.            | S   |
| FE-6 | LLM suggest flow | Side sheet.                                   | E2E.             | M   |
| FE-7 | Meal-prep wizard | `(day_index, slot_index)` selection.          | E2E.             | M   |
| FE-8 | Slot config      | Edits `MealSlot` extensions on `DaySchedule`. | Persist API.     | M   |
| FE-9 | Failure surfaces | Reads extended `report` / API fields.         | Tests.           | S   |


**Rough total:** unchanged order-of-magnitude; Week 1 critical path DM-1 → DM-2 → DM-4 → BE-3 → BE-2 → FE-1/FE-3/FE-5.

---

# 7. Risks & Design Decisions

### R1. Tagging vs pins vs batch locks

- **Decision:** Explicit precedence in §3.5; UI documents all three forcing paths.

### R2. Meal prep visibility

- Unchanged: collapsible tray + empty state CTA.

### R3. LLM optional

- Unchanged: planner never calls LLM in deterministic mode.

### R4. Determinism

- Seeded RNG via existing planner mechanisms; parity via DEBUG doc artifacts.

### R5. Tag sprawl

- Quarantine LLM-created slugs until confirmed in tag management UI.

### R6. Legacy profile YAML

- **Decision:** Extend `src/models/legacy_schedule_migration.py` (referenced from `schedule.py`). **REQUIRES_VERIFICATION:** add this module to `architecture.json` in a follow-up doc maintenance task so the snapshot matches repo truth.

### R7. `time-0` vs workouts

- **Decision:** Workouts only on `WorkoutSlot`; `time-0` is recipe effort only.

---

# 8. Exit Criteria for Sprint 1

- Typed tag slugs populated for ≥ 95 % of corpus; single filter path in planner.
- `MealSlot` supports optional `required_tag_slugs` / `preferred_tag_slugs`; `DaySchedule` validates.
- Meal prep batch creates locks on `(day_index, slot_index)`; planner honors them with pins.
- `pinned_assignments` still works; precedence tests exist.
- Parity: CLI vs Flutter per `docs/DEBUG_PLANNER_PARITY.md` artifacts (including `recipe_ids_sha256` where produced by `scripts/export_planner_debug_artifacts.py`).
- Flutter plan request includes server-accepted tag fields (`flutter_plan_request_vs_server_tag_fields` resolved).
- UI: card planner + tray + chips; no spreadsheet layout.

---

## Summary of opinionated decisions

1. **One tag system:** extend `RecipeTagsJson` + `tag_repository` / `recipe_tags.json` + `apply_tag_filtering`.
2. **One slot system:** extend canonical `MealSlot` / `DaySchedule`; workouts stay `WorkoutSlot` (`after_meal_index`, `type`, `intensity`).
3. **Forcing:** batch locks + `pinned_assignments` + required tags — explicit precedence.
4. **One planner path:** `PlanningUserProfile` → `plan_meals` / phase pipeline; no shadow `plan()` API.
5. **Additive API and DTO evolution** for meal metadata and failures; no breaking renames.
6. **G7** anchored to DEBUG parity artifacts and export script.
7. **REQUIRES_VERIFICATION** only where code signature must be confirmed during implementation (`plan_meals` batch injection, architecture snapshot updates for phase files).

