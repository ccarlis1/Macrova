from __future__ import annotations

from src.data_layer.models import NutritionProfile
from src.planning.phase0_models import MealSlot, PlanningBatchLock, PlanningRecipe, PlanningUserProfile
from src.planning.planner import plan_meals


def _slot(*, required: list[str] | None = None) -> MealSlot:
    return MealSlot(
        time="12:00",
        busyness_level=2,
        meal_type="lunch",
        required_tag_slugs=required,
    )


def _recipe(
    rid: str,
    *,
    calories: float = 500.0,
    protein_g: float = 50.0,
    fat_g: float = 32.0,
    carbs_g: float = 125.0,
    tags: set[str] | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
        ),
        canonical_tag_slugs=set(tags or set()),
    )


def _profile(
    *,
    schedule: list[list[MealSlot]],
    batch_locks: list[PlanningBatchLock],
    pinned_assignments: dict[tuple[int, int], str] | None = None,
    daily_calories: int = 1000,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=schedule,
        pinned_assignments=dict(pinned_assignments or {}),
        batch_locks=list(batch_locks),
    )


def test_batch_lock_spread_across_3_days():
    schedule = [[_slot(), _slot()], [_slot(), _slot()], [_slot(), _slot()]]
    profile = _profile(
        schedule=schedule,
        # Mark each single-slot day as pre-workout so HC-8 does not reject repeated recipe ids.
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=0, slot_index=0),
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=1, slot_index=0),
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=2, slot_index=0),
        ],
    )
    profile.workout_after_meal_indices_by_day = [[1], [1], [1]]

    result = plan_meals(
        profile,
        [_recipe("r_batch"), _recipe("r_day_1"), _recipe("r_day_2"), _recipe("r_day_3")],
        days=3,
    )

    assert result.success is True
    assert result.plan is not None
    got = {(a.day_index, a.slot_index): a.recipe_id for a in result.plan}
    assert got[(0, 0)] == "r_batch"
    assert got[(1, 0)] == "r_batch"
    assert got[(2, 0)] == "r_batch"


def test_batch_lock_conflict_returns_fm_batch_conflict():
    profile = _profile(
        schedule=[[ _slot() ]],
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r1", day_index=0, slot_index=0),
            PlanningBatchLock(batch_id="batch-b", recipe_id="r2", day_index=0, slot_index=0),
        ],
    )

    result = plan_meals(profile, [_recipe("r1"), _recipe("r2")], days=1)

    assert result.success is False
    assert result.failure_mode == "FM-BATCH-CONFLICT"
    assert "batch_conflicts" in result.report
    assert len(result.report["batch_conflicts"]) == 1


def test_batch_tag_mismatch_is_warning_not_failure():
    profile = _profile(
        schedule=[[_slot(required=["high-protein"])]],
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=0, slot_index=0),
        ],
    )
    profile.schedule = [[_slot(required=["high-protein"]), _slot()]]
    result = plan_meals(profile, [_recipe("r_batch", tags={"quick"}), _recipe("r_other")], days=1)

    assert result.success is True
    warnings = result.report.get("warnings", [])
    assert any(w.get("code") == "BATCH_TAG_MISMATCH" for w in warnings)


def test_batch_lock_overrides_pin_and_skips_free_search():
    profile = _profile(
        schedule=[[_slot(), _slot()]],
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=0, slot_index=0),
        ],
        pinned_assignments={(1, 0): "r_pin"},
    )
    result = plan_meals(
        profile,
        [_recipe("r_batch"), _recipe("r_pin"), _recipe("r_other")],
        days=1,
    )
    assert result.success is True
    assert result.plan is not None
    assignments = {(a.day_index, a.slot_index): a.recipe_id for a in result.plan}
    assert assignments[(0, 0)] == "r_batch"


def test_locked_recipe_counts_in_daily_nutrition_totals():
    profile = _profile(
        schedule=[[_slot(), _slot()]],
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r_batch", day_index=0, slot_index=0),
        ],
    )
    result = plan_meals(
        profile,
        [
            _recipe("r_batch", calories=600.0, protein_g=40.0, fat_g=25.0, carbs_g=75.0),
            _recipe("r_other", calories=400.0, protein_g=60.0, fat_g=30.0, carbs_g=175.0),
            _recipe("r_other_2"),
        ],
        days=1,
    )

    assert result.success is True
    assert result.daily_trackers is not None
    assert result.daily_trackers[0].calories_consumed == 1000.0
