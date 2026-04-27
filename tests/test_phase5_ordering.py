"""Phase 5 unit tests: preferred-tag tie-breaking cascade."""

from __future__ import annotations

from src.data_layer.models import MicronutrientProfile, NutritionProfile
from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase5_ordering import (
    OrderingStateView,
    order_scored_candidates,
    ordering_key,
)


def _recipe(
    rid: str = "r1",
    tags: set[str] | None = None,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=15,
        nutrition=NutritionProfile(
            500.0, 30.0, 20.0, 40.0,
            micronutrients=micronutrients or MicronutrientProfile(),
        ),
        primary_carb_contribution=None,
        canonical_tag_slugs=tags or set(),
    )


def _state(
    daily_trackers: dict | None = None,
    weekly_tracker: WeeklyTracker | None = None,
) -> OrderingStateView:
    return OrderingStateView(
        daily_trackers=daily_trackers or {},
        weekly_tracker=weekly_tracker or WeeklyTracker(),
    )


def _profile(slot: MealSlot | None = None) -> PlanningUserProfile:
    s = slot or MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick", "high-protein"])
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=[[s]],
    )


class TestTieBreakCascade:
    def test_preferred_matches_win_before_recipe_id(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick", "high-protein"])
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        high_pref = _recipe("rZ", tags={"quick", "high-protein"})
        low_pref = _recipe("rA", tags={"quick"})
        scored = [(high_pref, 50.0), (low_pref, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0, slot=slot, tie_break_seed="seed-x")
        assert [r.id for r, _ in ordered] == ["rZ", "rA"]

    def test_recipe_id_is_next_tie_breaker(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick"])
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        a = _recipe("recipe_b", tags={"quick"})
        b = _recipe("recipe_a", tags={"quick"})
        scored = [(a, 50.0), (b, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0, slot=slot, tie_break_seed="seed-y")
        assert [r.id for r, _ in ordered] == ["recipe_a", "recipe_b"]

    def test_seeded_rng_changes_final_tie_only_when_needed(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=None)
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        recipe = _recipe("same-id", tags=set())
        k1 = ordering_key((recipe, 50.0), state, profile, 0, slot=slot, tie_break_seed="seed-1")
        k2 = ordering_key((recipe, 50.0), state, profile, 0, slot=slot, tie_break_seed="seed-2")
        assert k1[:3] == k2[:3]
        assert k1[3] != k2[3]


# --- Primary order: composite score descending ---


class TestPrimaryOrderByScore:
    """Primary order is by composite score descending."""

    def test_higher_score_first(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick"])
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        r1 = _recipe("r1", tags={"quick"})
        r2 = _recipe("r2", tags={"quick"})
        scored = [(r1, 30.0), (r2, 70.0)]
        ordered = order_scored_candidates(scored, state, profile, 0, slot=slot, tie_break_seed="seed-z")
        ids = [r.id for r, _ in ordered]
        assert ids == ["r2", "r1"]


# --- Determinism ---


class TestDeterminism:
    """Repeated sorting produces identical order."""

    def test_repeated_sort_same_order(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick"])
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        recipes = [_recipe(f"r{i}", tags={"quick"}) for i in range(5)]
        scored = [(r, 50.0) for r in recipes]
        run1 = order_scored_candidates(scored, state, profile, 0, slot=slot, tie_break_seed="seed-det")
        run2 = order_scored_candidates(scored, state, profile, 0, slot=slot, tie_break_seed="seed-det")
        ids1 = [r.id for r, _ in run1]
        ids2 = [r.id for r, _ in run2]
        assert ids1 == ids2

    def test_key_is_deterministic(self):
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch", preferred_tag_slugs=["quick"])
        profile = _profile(slot)
        state = _state(daily_trackers={0: DailyTracker(slots_total=1)}, weekly_tracker=WeeklyTracker(days_remaining=1))
        r = _recipe("r1", tags={"quick"})
        item = (r, 50.0)
        k1 = ordering_key(item, state, profile, 0, slot=slot, tie_break_seed="seed-k")
        k2 = ordering_key(item, state, profile, 0, slot=slot, tie_break_seed="seed-k")
        assert k1 == k2
