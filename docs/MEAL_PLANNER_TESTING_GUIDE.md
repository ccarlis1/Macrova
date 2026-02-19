# Meal Planner Testing Guide (Phases 1–7)

This guide explains how to test the spec-aligned meal planner (phases 0–7) for **functionality**, **output correctness**, and **run time**.

**Reference:** `docs/MEALPLAN_SPECIFICATION_v1.md`, `src/planning/phase7_search.py` (`run_meal_plan_search`).

---

## 1. Run existing unit tests (functionality)

The phase 0–7 pipeline is covered by pytest. Run all planning tests:

```bash
# From repo root
pytest tests/test_phase0_meal_plan_foundation.py tests/test_phase1_state.py tests/test_phase2_constraints.py tests/test_phase3_feasibility.py tests/test_phase4_scoring.py tests/test_phase5_ordering.py tests/test_phase6_candidates.py tests/test_phase7_search.py -v
```

Or run only the full-search integration tests (phase 7):

```bash
pytest tests/test_phase7_search.py -v
```

**What this verifies:**

- Phase 0: Schedule/profile/recipe structures, validation.
- Phase 1: Initial state, pinned assignments, trackers.
- Phase 2: Hard constraints (HC-1–HC-8) and UL checks.
- Phase 3: Feasibility (FC-1–FC-4).
- Phase 4: Scoring.
- Phase 5: Ordering.
- Phase 6: Candidate generation.
- Phase 7: End-to-end search: success (D=1,2,7), pinned slots, failure modes (FM-1–FM-5), determinism, and **SearchStats** (run time, attempts).

---

## 2. Measure run time and attempts (SearchStats)

`run_meal_plan_search` accepts an optional `SearchStats` object. When `stats.enabled=True`, it records:

- **Total run time** (seconds): `stats.total_runtime()`
- **Total attempts**: `stats.total_attempts`
- **Time per attempt**: `stats.time_per_attempt()`
- **Per-day run times**: `stats.day_runtimes` (day_index → seconds)
- **Backtrack depth**: `stats.max_depth`, `stats.average_backtrack_depth`

**Example (from your tests):**

```python
from src.planning.phase7_search import run_meal_plan_search, SearchStats, PlanSuccess

# Build profile and recipe pool (e.g. with _make_profile, _make_recipe from test_phase7_search)
stats = SearchStats(enabled=True)
ok, result = run_meal_plan_search(profile, recipe_pool, D=7, resolved_ul=None, stats=stats)

assert ok is True
assert isinstance(result, PlanSuccess)
print(f"Runtime: {stats.total_runtime():.3f}s")
print(f"Attempts: {stats.total_attempts}")
print(f"Time per attempt: {stats.time_per_attempt():.6f}s")
print(f"Day runtimes: {stats.day_runtimes}")
```

Existing tests that already use stats:

- `TestSearchStatsInstrumentation::test_stats_populated_when_enabled`
- `TestSearchStatsInstrumentation::test_d7_timing_measurable`
- `TestDeterminism::test_stats_enabled_vs_disabled_identical_plan`

---

## 3. Validate output (success case)

For a **success** (`ok is True`, `result` is `PlanSuccess`):

1. **Assignments**
   - `result.assignments`: list of `(day_index, slot_index, recipe_id)`.
   - Length must equal total slots across all D days (e.g. D=7, 2 slots/day → 14 assignments).
   - Each `(day_index, slot_index)` appears exactly once; each `recipe_id` in the pool.

2. **Daily trackers**
   - `result.daily_trackers[day_index]`: `slots_assigned`, `calories_consumed`, `protein_consumed`, etc.
   - For each day: `slots_assigned` = number of slots that day; daily totals consistent with assigned recipes.

3. **Weekly tracker**
   - `result.weekly_tracker.days_completed == D`.
   - If you use `micronutrient_targets`, weekly totals should meet or exceed prorated RDI (Spec Section 6.6).

4. **Determinism**
   - Same `profile`, `recipe_pool`, `D`, `resolved_ul`, `attempt_limit` → same `result.assignments` (same order).

5. **Sodium advisory**
   - Optional: `result.sodium_advisory` may be set; check your spec for when it is reported.

---

## 4. Validate output (failure case)

For **failure** (`ok is False`, `result` is `PlanFailure`):

1. **Failure mode**: `result.failure_mode` in `{"FM-1", "FM-2", "FM-3", "FM-4", "FM-5"}` (Spec Section 11).
2. **Detail**: `result.constraint_detail`, `result.day_index`, `result.slot_index` when applicable.
3. **Best partial**: `result.best_partial_assignments`, `result.best_partial_daily_trackers`, `result.attempt_count` for FM-2, FM-4, FM-5.

---

## 5. Run a quick benchmark (script)

To get a single measured run (time + output) without writing Python by hand, you can use the script below. Save it as `scripts/benchmark_meal_plan_search.py` (or run the snippet in a test or notebook).

**Prerequisites:** Same as tests: construct `PlanningUserProfile` and a list of `PlanningRecipe`; optionally `UpperLimits` for `resolved_ul`.

**Minimal benchmark pattern:**

```python
import time
from src.planning.phase0_models import MealSlot, PlanningUserProfile, PlanningRecipe
from src.planning.phase7_search import run_meal_plan_search, SearchStats, PlanSuccess, PlanFailure
from src.data_layer.models import NutritionProfile, MicronutrientProfile

def make_slot(busyness=2):
    return MealSlot("12:00", busyness, "lunch")

def make_schedule(ndays=7, slots_per_day=2):
    return [[make_slot() for _ in range(slots_per_day)] for _ in range(ndays)]

def make_recipe(rid, calories=1000.0, protein=50.0, fat=32.0, carbs=125.0, cooking_min=10):
    return PlanningRecipe(
        id=rid, name=rid, ingredients=[], cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(calories, protein, fat, carbs, micronutrients=MicronutrientProfile()),
        primary_carb_contribution=None,
    )

def main():
    D = 7
    slots_per_day = 2
    schedule = make_schedule(ndays=D, slots_per_day=slots_per_day)
    profile = PlanningUserProfile(
        daily_calories=2000, daily_protein_g=100.0, daily_fat_g=(50.0, 80.0), daily_carbs_g=250.0,
        schedule=schedule,
    )
    pool = [make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(D * slots_per_day)]

    stats = SearchStats(enabled=True)
    t0 = time.perf_counter()
    ok, result = run_meal_plan_search(profile, pool, D, resolved_ul=None, stats=stats)
    t1 = time.perf_counter()

    print(f"Success: {ok}")
    print(f"Wall time: {t1 - t0:.3f}s")
    print(f"Stats total_runtime: {stats.total_runtime():.3f}s")
    print(f"Attempts: {stats.total_attempts}")
    print(f"Time per attempt: {stats.time_per_attempt():.6f}s")
    if ok and isinstance(result, PlanSuccess):
        print(f"Assignments: {len(result.assignments)}")
        print(f"Days completed: {result.weekly_tracker.days_completed}")
    else:
        print(f"Failure mode: {getattr(result, 'failure_mode', None)}")

if __name__ == "__main__":
    main()
```

Run it:

```bash
python scripts/benchmark_meal_plan_search.py
```

---

## 6. Testing with real recipe data (optional)

The phase 1–7 API uses `PlanningUserProfile` and `PlanningRecipe`, not the legacy `UserProfile` and `Recipe`. To test with real data:

1. Load recipes (e.g. `RecipeDB("path/to/recipes.json").get_all_recipes()`).
2. Load nutrition DB and compute per-recipe nutrition (e.g. `NutritionCalculator(nutrition_db).calculate_recipe_nutrition(recipe)`).
3. Map each `Recipe` to `PlanningRecipe`: same `id`, `name`, `ingredients`, `cooking_time_minutes`; set `nutrition` to the computed `NutritionProfile` (with `micronutrients` if you use them); set `primary_carb_contribution=None` unless you use carb downscaling.
4. Build `PlanningUserProfile`: map your user’s schedule to `List[List[MealSlot]]`, set `daily_calories`, `daily_protein_g`, `daily_fat_g`, `daily_carbs_g`, `excluded_ingredients`, `pinned_assignments`, `micronutrient_targets`, etc., per Spec Section 2.1.
5. Optionally build `UpperLimits` from your reference data (e.g. `data/reference/ul_by_demographic.json`) and pass as `resolved_ul`; otherwise pass `None`.

Then call `run_meal_plan_search(profile, planning_recipe_list, D, resolved_ul, stats=SearchStats(enabled=True))` and use Sections 2–4 above to measure and validate.

---

## Summary

| Goal                    | Action |
|-------------------------|--------|
| **Functionality**       | `pytest tests/test_phase7_search.py` (and other phase tests). |
| **Run time / attempts** | Use `SearchStats(enabled=True)` in `run_meal_plan_search`; read `total_runtime()`, `total_attempts`, `time_per_attempt()`, `day_runtimes`. |
| **Output (success)**    | Check `assignments` length and shape, `daily_trackers`, `weekly_tracker.days_completed`, determinism. |
| **Output (failure)**    | Check `failure_mode`, `constraint_detail`, `best_partial_*`, `attempt_count`. |
| **One-off benchmark**   | Use the script in Section 5 or add a similar test that prints stats and result summary. |
