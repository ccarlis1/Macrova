#!/usr/bin/env python3
"""Benchmark run_meal_plan_search: run time and output summary.

Run from repo root:
  python scripts/benchmark_meal_plan_search.py

Optional: D and slots_per_day via env or edit below.
"""
from __future__ import annotations

import os
import sys
import time

# Allow importing from src when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_layer.models import NutritionProfile, MicronutrientProfile
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase7_search import (
    PlanFailure,
    PlanSuccess,
    SearchStats,
    run_meal_plan_search,
)


def make_slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def make_schedule(ndays: int = 7, slots_per_day: int = 2) -> list:
    return [[make_slot() for _ in range(slots_per_day)] for _ in range(ndays)]


def make_recipe(
    rid: str,
    calories: float = 1000.0,
    protein: float = 50.0,
    fat: float = 32.0,
    carbs: float = 125.0,
    cooking_min: int = 10,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(
            calories, protein, fat, carbs, micronutrients=MicronutrientProfile()
        ),
        primary_carb_contribution=None,
    )


def main() -> None:
    D = int(os.environ.get("MEALPLAN_D_DAYS", "7"))
    slots_per_day = int(os.environ.get("MEALPLAN_SLOTS_PER_DAY", "2"))

    schedule = make_schedule(ndays=D, slots_per_day=slots_per_day)
    profile = PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=schedule,
    )
    pool = [
        make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0)
        for i in range(D * slots_per_day)
    ]

    stats = SearchStats(enabled=True)
    t0 = time.perf_counter()
    ok, result = run_meal_plan_search(profile, pool, D, resolved_ul=None, stats=stats)
    t1 = time.perf_counter()

    print("--- Meal plan search benchmark ---")
    print(f"Success: {ok}")
    print(f"Wall time: {t1 - t0:.3f}s")
    print(f"Stats total_runtime: {stats.total_runtime():.3f}s")
    print(f"Attempts: {stats.total_attempts}")
    print(f"Time per attempt: {stats.time_per_attempt():.6f}s")
    if ok and isinstance(result, PlanSuccess):
        print(f"Assignments: {len(result.assignments)}")
        print(f"Days completed: {result.weekly_tracker.days_completed}")
        for day_index in range(D):
            dt = result.daily_trackers.get(day_index)
            if dt:
                print(
                    f"  Day {day_index + 1}: slots={dt.slots_assigned}, "
                    f"cal={dt.calories_consumed:.0f}, protein={dt.protein_consumed:.1f}g"
                )
    else:
        assert isinstance(result, PlanFailure)
        print(f"Failure mode: {result.failure_mode}")
        print(f"Constraint detail: {result.constraint_detail}")
        print(f"Attempt count: {result.attempt_count}")
    print("----------------------------------")


if __name__ == "__main__":
    main()
