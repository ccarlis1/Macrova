import pytest

from src.data_layer.user_profile import (
    PlannerConfigMappingError,
    user_profile_from_planner_config,
)
from src.models.schedule import DaySchedule, MealSlot as CanonMeal, WorkoutSlot
from src.llm.schemas import BudgetLevel, PlannerConfigJson, PlannerPreferences, PlannerTargets


def _cfg(*, days: int, meals_per_day: int, calories: int, protein: float, cuisine: list[str], budget: BudgetLevel):
    return PlannerConfigJson(
        days=days,
        meals_per_day=meals_per_day,
        targets=PlannerTargets(calories=calories, protein=protein),
        preferences=PlannerPreferences(cuisine=cuisine, budget=budget),
    )


def test_user_profile_from_planner_config_derives_schedule_and_macros():
    cfg = _cfg(
        days=3,
        meals_per_day=3,
        calories=2400,
        protein=150.0,
        cuisine=["chicken", "salad"],
        budget=BudgetLevel.cheap,
    )

    profile = user_profile_from_planner_config(cfg)

    assert profile.daily_calories == 2400
    assert profile.daily_protein_g == pytest.approx(150.0)
    assert profile.liked_foods == ["chicken", "salad"]
    assert profile.disliked_foods == []
    assert profile.allergies == []

    assert list(profile.schedule.keys()) == ["07:00", "12:00", "18:00"]
    assert all(v == 4 for v in profile.schedule.values())

    # carbs derived from deterministic fat ratio bounds for BudgetLevel.cheap
    remaining_after_protein_cal = 2400 - 150.0 * 4.0
    fat_ratio_min, fat_ratio_max = (0.25, 0.30)
    fat_g_min = (remaining_after_protein_cal * fat_ratio_min) / 9.0
    fat_g_max = (remaining_after_protein_cal * fat_ratio_max) / 9.0
    median_fat_g = (fat_g_min + fat_g_max) / 2.0
    expected_carbs = (
        2400 - 150.0 * 4.0 - median_fat_g * 9.0
    ) / 4.0

    assert profile.daily_fat_g[0] == pytest.approx(fat_g_min)
    assert profile.daily_fat_g[1] == pytest.approx(fat_g_max)
    assert profile.daily_carbs_g == pytest.approx(expected_carbs)
    assert profile.daily_carbs_g >= 0.0


def test_user_profile_from_planner_config_rejects_negative_derived_carbs():
    cfg = _cfg(
        days=1,
        meals_per_day=1,
        calories=1000,
        protein=300.0,
        cuisine=["anything"],
        budget=BudgetLevel.standard,
    )

    with pytest.raises(PlannerConfigMappingError) as exc:
        user_profile_from_planner_config(cfg)

    assert exc.value.error_code in (
        "NEGATIVE_REMAINING_AFTER_PROTEIN",
        "NEGATIVE_CARBS_DERIVED",
    )


def test_user_profile_from_planner_config_with_schedule_days_sets_canonical_schedule():
    """LLM-facing config can carry per-meal busyness + workout gaps."""
    cfg = PlannerConfigJson(
        days=1,
        meals_per_day=2,
        targets=PlannerTargets(calories=2200, protein=140.0),
        preferences=PlannerPreferences(cuisine=[], budget=BudgetLevel.standard),
        schedule_days=[
            DaySchedule(
                day_index=1,
                meals=[
                    CanonMeal(index=1, busyness_level=2, tags=["breakfast"]),
                    CanonMeal(index=2, busyness_level=4, tags=["dinner"]),
                ],
                workouts=[
                    WorkoutSlot(
                        after_meal_index=1, type="PM", intensity="moderate"
                    )
                ],
            )
        ],
    )
    profile = user_profile_from_planner_config(cfg)
    assert profile.schedule_days is not None
    assert len(profile.schedule_days) == 1
    assert len(profile.schedule_days[0].meals) == 2
    assert profile.schedule_days[0].meals[0].busyness_level == 2
    assert profile.schedule_days[0].workouts[0].after_meal_index == 1
    assert len(profile.schedule) == 2



# ---- LLM overhaul Stage 8: typed constraints, stated fields, derived-field transparency ----
from src.data_layer.user_profile import planner_config_interpretation_report
from src.llm.schemas import PlannerConstraints, parse_llm_json


def _cfg_with(constraints=None, stated=None, schedule_days=None):
    return PlannerConfigJson(
        days=2, meals_per_day=3,
        targets=PlannerTargets(calories=2000, protein=150.0),
        preferences=PlannerPreferences(cuisine=["mexican"], budget=BudgetLevel.standard),
        constraints=constraints, stated_fields=stated or [], schedule_days=schedule_days,
    )


def test_constraints_map_to_planner_inputs():
    cfg = _cfg_with(PlannerConstraints(allergies=["peanuts"], disliked_foods=["cilantro"], liked_foods=["salmon"],
                                       max_daily_calories=1900, micronutrient_goals={"fiber_g": 30, "iron_mg": 18},
                                       dietary_flags=["vegan"], micronutrient_weekly_min_fraction=0.8))
    p = user_profile_from_planner_config(cfg)
    assert p.allergies == ["peanuts"] and p.disliked_foods == ["cilantro"]
    assert p.liked_foods == ["mexican", "salmon"]  # cuisine stays a soft preference
    assert p.max_daily_calories == 1900
    assert p.daily_micronutrient_targets == {"fiber_g": 30.0, "iron_mg": 18.0}
    assert p.micronutrient_weekly_min_fraction == pytest.approx(0.8)


def test_stated_fat_range_overrides_budget_derived_range():
    p = user_profile_from_planner_config(_cfg_with(PlannerConstraints(fat_g_min=50, fat_g_max=70)))
    assert p.daily_fat_g == (50.0, 70.0)
    assert p.daily_carbs_g == pytest.approx((2000 - 150 * 4 - 60 * 9) / 4)
    rep = planner_config_interpretation_report(_cfg_with(PlannerConstraints(fat_g_min=50, fat_g_max=70)))
    assert "fat_range_from_budget" not in rep["derived_fields"]
    assert "fat_range_from_budget" in planner_config_interpretation_report(_cfg_with())["derived_fields"]


def test_invented_schedule_is_dropped_when_not_stated_but_kept_when_stated_or_unknown():
    sd = [DaySchedule(day_index=1, meals=[CanonMeal(index=i, busyness_level=3) for i in (1, 2, 3)])]
    dropped = user_profile_from_planner_config(_cfg_with(stated=["days", "calories"], schedule_days=sd))
    assert dropped.schedule_days is None and all(v == 4 for v in dropped.schedule.values())
    kept = user_profile_from_planner_config(_cfg_with(stated=["days", "schedule_days"], schedule_days=sd))
    assert kept.schedule_days is not None and kept.schedule_days[0].meals[0].busyness_level == 3
    unknown = user_profile_from_planner_config(_cfg_with(stated=[], schedule_days=sd))  # model did not report stated fields
    assert unknown.schedule_days is not None
    rep = planner_config_interpretation_report(_cfg_with(stated=["days", "calories"], schedule_days=sd))
    assert rep["dropped_fields"] == ["schedule_days_not_stated"]
    assert set(rep["defaulted_fields"]) == {"meals_per_day", "protein", "budget", "cuisine", "schedule_days"}


def test_stated_field_names_are_filtered_and_constraint_schema_is_strict():
    cfg = _cfg_with(stated=["calories", "numberOfMeals", " protein "])
    assert cfg.stated_fields == ["calories", "protein"]
    bad = parse_llm_json(PlannerConfigJson, {"days": 1, "meals_per_day": 3, "targets": {"calories": 2000, "protein": 100},
                                             "preferences": {"cuisine": [], "budget": "standard"},
                                             "constraints": {"micronutrient_goals": {"unobtainium_mg": 5}}})
    assert bad.error_code == "LLM_SCHEMA_VALIDATION_ERROR"
    bad2 = parse_llm_json(PlannerConfigJson, {"days": 1, "meals_per_day": 3, "targets": {"calories": 2000, "protein": 100},
                                              "preferences": {"cuisine": [], "budget": "standard"},
                                              "constraints": {"fat_g_min": 80, "fat_g_max": 60}})
    assert bad2.error_code == "LLM_SCHEMA_VALIDATION_ERROR"
    ok = parse_llm_json(PlannerConfigJson, {"days": 1, "meals_per_day": 3, "targets": {"calories": 2000, "protein": 100},
                                            "preferences": {"cuisine": [], "budget": "standard"},
                                            "constraints": {"allergies": ["peanuts"]}, "stated_fields": ["allergies", "calories"]})
    assert isinstance(ok, PlannerConfigJson) and ok.constraints.allergies == ["peanuts"]
