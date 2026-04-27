"""Focused tests for preferred tags and variety soft scoring additions."""

from __future__ import annotations

from src.data_layer.models import NutritionProfile
from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase4_scoring import (
    ScoringConfig,
    ScoringStateView,
    composite_score,
    preferred_match_count,
    preferred_tag_bonus,
    variety_penalty,
)


def _recipe(
    rid: str,
    tags: set[str] | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(calories=500.0, protein_g=30.0, fat_g=18.0, carbs_g=45.0),
        canonical_tag_slugs=tags or set(),
    )


def _profile(preferred: list[str] | None = None) -> PlanningUserProfile:
    slot = MealSlot(
        time="12:00",
        busyness_level=2,
        meal_type="lunch",
        preferred_tag_slugs=preferred,
    )
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=[[slot], [slot]],
    )


def _state(
    day0_ids: set[str] | None = None,
    meal_prep_ids: set[str] | None = None,
    day0_micro: dict[str, float] | None = None,
) -> ScoringStateView:
    trackers = {
        0: DailyTracker(
            used_recipe_ids=day0_ids or set(),
            micronutrients_consumed=day0_micro or {},
            slots_assigned=1,
            slots_total=1,
        )
    }
    return ScoringStateView(
        daily_trackers=trackers,
        weekly_tracker=WeeklyTracker(days_remaining=2),
        schedule=[[_profile().schedule[0][0]], [_profile().schedule[0][0]]],
        meal_prep_recipe_ids=meal_prep_ids or set(),
    )


def test_preferred_tags_influence_selection():
    profile = _profile(preferred=["high-protein", "quick"])
    schedule = profile.schedule
    state = ScoringStateView(
        daily_trackers={},
        weekly_tracker=WeeklyTracker(days_remaining=2),
        schedule=schedule,
    )
    better = _recipe("better", {"high-protein", "quick"})
    worse = _recipe("worse", {"slow-cook"})
    score_better = composite_score(better, 0, 0, state, profile)
    score_worse = composite_score(worse, 0, 0, state, profile)
    assert score_better > score_worse


def test_variety_penalty_alters_day2_score():
    profile = _profile(preferred=["quick"])
    state = _state(day0_ids={"repeat-recipe"})
    recipe = _recipe("repeat-recipe", {"quick"})
    baseline = preferred_tag_bonus(recipe, profile.schedule[1][0], 1, state, profile)
    penalty = variety_penalty(recipe, 1, state, ScoringConfig(w_pref=1.0, w_var=2.0))
    assert baseline > 0
    assert penalty == 2.0


def test_meal_prep_exemption_skips_variety_penalty():
    profile = _profile(preferred=["quick"])
    state = _state(day0_ids={"batch-recipe"}, meal_prep_ids={"batch-recipe"})
    recipe = _recipe("batch-recipe", {"quick"})
    assert variety_penalty(recipe, 1, state) == 0.0
    assert composite_score(recipe, 1, 0, state, profile) >= 0.0


def test_micronutrient_deficit_adds_high_tag_preference():
    profile = _profile(preferred=None)
    profile.micronutrient_targets = {"iron_mg": 10.0}
    state = _state(day0_ids=set(), day0_micro={"iron_mg": 0.0})
    recipe = _recipe("iron-rich", {"high-iron"})
    count = preferred_match_count(recipe, profile.schedule[1][0], 1, state, profile)
    assert count >= 1


def test_regression_preferred_match_above_80_percent():
    preferred = ["high-protein", "quick", "fiber-rich", "high-iron", "meal-prep-friendly"]
    profile = _profile(preferred=preferred)
    state = ScoringStateView(
        daily_trackers={},
        weekly_tracker=WeeklyTracker(days_remaining=2),
        schedule=profile.schedule,
    )
    recipe = _recipe("strong-match", {"high-protein", "quick", "fiber-rich", "high-iron"})
    matches = preferred_match_count(recipe, profile.schedule[0][0], 0, state, profile)
    assert matches / len(preferred) >= 0.8
