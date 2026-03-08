"""Single public planning API. Wraps phase7 search with validation; no transformation."""

from typing import List, Optional

from src.data_layer.models import UpperLimits
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile
from src.planning.phase7_search import (
    run_meal_plan_search,
    SearchStats,
    DEFAULT_ATTEMPT_LIMIT,
)
from src.planning.phase10_reporting import MealPlanResult


def plan_meals(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    days: int = 1,
    resolved_ul: Optional[UpperLimits] = None,
    attempt_limit: int = DEFAULT_ATTEMPT_LIMIT,
    stats: Optional[SearchStats] = None,
) -> MealPlanResult:
    """Run the meal plan search. Validates inputs and delegates to run_meal_plan_search.

    Args:
        profile: Planning user profile with schedule and goals.
        recipe_pool: Pre-computed planning recipes (nutrition attached).
        days: Planning horizon 1--7.
        resolved_ul: Optional upper limits for daily UL validation.
        attempt_limit: Max search attempts (default from phase7).
        stats: Optional stats collector for instrumentation.

    Returns:
        MealPlanResult unchanged from run_meal_plan_search.

    Raises:
        ValueError: If days not in 1--7 or len(profile.schedule) != days.
    """
    if not (1 <= days <= 7):
        raise ValueError(f"days must be 1--7, got {days}")
    if len(profile.schedule) != days:
        raise ValueError(
            f"profile.schedule length ({len(profile.schedule)}) must equal days ({days})"
        )
    return run_meal_plan_search(
        profile,
        recipe_pool,
        days,
        resolved_ul,
        attempt_limit,
        stats,
    )
