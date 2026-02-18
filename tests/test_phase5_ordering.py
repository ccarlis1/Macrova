"""Phase 5 unit tests: heuristic ordering (tie-breaking cascade). Spec Section 7.1."""

from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile
from src.planning.phase0_models import (
    DailyTracker,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase5_ordering import (
    OrderingStateView,
    order_scored_candidates,
    ordering_key,
    gap_fill_count,
    deficit_reduction,
    liked_foods_count,
)


def _make_recipe(
    rid: str = "r1",
    ingredients: list | None = None,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=ingredients or [],
        cooking_time_minutes=15,
        nutrition=NutritionProfile(
            500.0, 30.0, 20.0, 40.0,
            micronutrients=micronutrients or MicronutrientProfile(),
        ),
        primary_carb_contribution=None,
    )


def _make_state(
    daily_trackers: dict | None = None,
    weekly_tracker: WeeklyTracker | None = None,
) -> OrderingStateView:
    return OrderingStateView(
        daily_trackers=daily_trackers or {},
        weekly_tracker=weekly_tracker or WeeklyTracker(),
    )


# --- Rule 1: Two candidates tied on score → resolved by gap-fill ---


class TestTieBreakByGapFill:
    """Rule 1: Higher micronutrient gap-fill coverage wins."""

    def test_tied_on_score_resolved_by_gap_fill(self):
        # Day 0: vitamin_a_ug and iron_mg deficient (consumed < target).
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            micronutrient_targets={"vitamin_a_ug": 900.0, "iron_mg": 18.0},
        )
        consumed = {"vitamin_a_ug": 100.0, "iron_mg": 2.0}  # both below target
        state = _make_state(
            daily_trackers={
                0: DailyTracker(
                    micronutrients_consumed=consumed,
                    slots_total=2,
                )
            },
            weekly_tracker=WeeklyTracker(days_remaining=2, carryover_needs={}),
        )
        # Recipe A: provides vitamin_a only → gap_fill_count = 1
        micro_a = MicronutrientProfile(vitamin_a_ug=500.0, iron_mg=0.0)
        # Recipe B: provides both → gap_fill_count = 2
        micro_b = MicronutrientProfile(vitamin_a_ug=200.0, iron_mg=5.0)
        ra = _make_recipe("rA", micronutrients=micro_a)
        rb = _make_recipe("rB", micronutrients=micro_b)
        scored = [(ra, 50.0), (rb, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["rB", "rA"]

    def test_tied_on_score_and_gap_fill_falls_through(self):
        # Same gap-fill count; next rule (deficit reduction) or ID will decide.
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            micronutrient_targets={"vitamin_a_ug": 900.0},
        )
        consumed = {"vitamin_a_ug": 100.0}
        state = _make_state(
            daily_trackers={
                0: DailyTracker(
                    micronutrients_consumed=consumed,
                    slots_total=2,
                )
            },
            weekly_tracker=WeeklyTracker(days_remaining=2, carryover_needs={}),
        )
        gap = 800.0  # 900 - 100
        # Both provide vitamin_a: same gap-fill count (1). A gives 400, B gives 100 → deficit reduction A > B.
        micro_a = MicronutrientProfile(vitamin_a_ug=400.0)
        micro_b = MicronutrientProfile(vitamin_a_ug=100.0)
        ra = _make_recipe("rA", micronutrients=micro_a)
        rb = _make_recipe("rB", micronutrients=micro_b)
        scored = [(ra, 50.0), (rb, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["rA", "rB"]


# --- Rule 2: Tied on gap-fill → resolved by deficit reduction ---


class TestTieBreakByDeficitReduction:
    """Rule 2: Higher total deficit reduction wins."""

    def test_tied_on_gap_fill_resolved_by_deficit_reduction(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            micronutrient_targets={"vitamin_a_ug": 900.0, "iron_mg": 18.0},
        )
        consumed = {"vitamin_a_ug": 100.0, "iron_mg": 2.0}
        state = _make_state(
            daily_trackers={
                0: DailyTracker(
                    micronutrients_consumed=consumed,
                    slots_total=2,
                )
            },
            weekly_tracker=WeeklyTracker(days_remaining=2, carryover_needs={}),
        )
        # Both cover both nutrients (gap_fill_count = 2). A fills more of the gaps (higher deficit reduction).
        micro_a = MicronutrientProfile(vitamin_a_ug=500.0, iron_mg=10.0)  # 400/800 + 8/16 = 0.5 + 0.5 = 1.0
        micro_b = MicronutrientProfile(vitamin_a_ug=200.0, iron_mg=3.0)   # 100/800 + 1/16 ≈ 0.125 + 0.0625
        ra = _make_recipe("rA", micronutrients=micro_a)
        rb = _make_recipe("rB", micronutrients=micro_b)
        scored = [(ra, 50.0), (rb, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["rA", "rB"]


# --- Rule 3: Tied on deficit reduction → resolved by liked foods ---


class TestTieBreakByLikedFoods:
    """Rule 3: More liked_foods matches wins; case-insensitive."""

    def test_tied_on_deficit_resolved_by_liked_foods(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            liked_foods=["egg", "Oatmeal"],
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        # No deficient nutrients → same gap-fill and deficit. Liked: A has 2 matches, B has 0.
        ra = _make_recipe("rA", ingredients=[
            Ingredient("egg", 1.0, "unit", False, "", 0.0),
            Ingredient("Oatmeal", 50.0, "g", False, "g", 50.0),
        ])
        rb = _make_recipe("rB", ingredients=[
            Ingredient("chicken", 100.0, "g", False, "g", 100.0),
        ])
        scored = [(ra, 50.0), (rb, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["rA", "rB"]

    def test_liked_foods_case_insensitive(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            liked_foods=["EGG"],
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        r_lower = _make_recipe("r1", ingredients=[
            Ingredient("egg", 1.0, "unit", False, "", 0.0),
        ])
        assert liked_foods_count(r_lower, profile) == 1


# --- Rule 4: Tied on liked foods → resolved by recipe ID ---


class TestTieBreakByRecipeId:
    """Rule 4: Lexicographically smaller recipe ID wins."""

    def test_tied_on_liked_resolved_by_recipe_id(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            liked_foods=[],
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        ra = _make_recipe("rZ")
        rb = _make_recipe("rA")
        scored = [(ra, 50.0), (rb, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["rA", "rZ"]

    def test_fully_identical_except_id_id_decides(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        r1 = _make_recipe("recipe_002")
        r2 = _make_recipe("recipe_001")
        scored = [(r1, 50.0), (r2, 50.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["recipe_001", "recipe_002"]


# --- Primary order: composite score descending ---


class TestPrimaryOrderByScore:
    """Primary order is by composite score descending."""

    def test_higher_score_first(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        r1 = _make_recipe("r1")
        r2 = _make_recipe("r2")
        scored = [(r1, 30.0), (r2, 70.0)]
        ordered = order_scored_candidates(scored, state, profile, 0)
        ids = [r.id for r, _ in ordered]
        assert ids == ["r2", "r1"]


# --- Determinism ---


class TestDeterminism:
    """Repeated sorting produces identical order."""

    def test_repeated_sort_same_order(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        recipes = [_make_recipe(f"r{i}") for i in range(5)]
        scored = [(r, 50.0) for r in recipes]
        run1 = order_scored_candidates(scored, state, profile, 0)
        run2 = order_scored_candidates(scored, state, profile, 0)
        ids1 = [r.id for r, _ in run1]
        ids2 = [r.id for r, _ in run2]
        assert ids1 == ids2

    def test_key_is_deterministic(self):
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_total=2)},
            weekly_tracker=WeeklyTracker(days_remaining=2),
        )
        r = _make_recipe("r1")
        item = (r, 50.0)
        k1 = ordering_key(item, state, profile, 0)
        k2 = ordering_key(item, state, profile, 0)
        assert k1 == k2
