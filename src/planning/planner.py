"""Single public planning API. Wraps phase7 search with validation."""

import copy
from typing import Any, Dict, List, Optional, Tuple

from src.data_layer.models import UpperLimits
from src.planning.phase0_models import PlanningBatchLock, PlanningRecipe, PlanningUserProfile
from src.planning.phase7_search import (
    run_meal_plan_search,
    SearchStats,
    DEFAULT_ATTEMPT_LIMIT,
)
from src.planning.phase10_reporting import MealPlanResult


def _merge_batch_locks_into_pins(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
) -> Tuple[Optional[MealPlanResult], Dict[Tuple[int, int], str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (early_failure, effective_pins, conflicts, tag_mismatches)."""
    # Integration approach: plan_meals reads profile.batch_locks and normalizes them
    # into pinned assignments before search.
    # Precedence is: batch lock > explicit pin > required tags > free search scoring.
    # Reusing pinned semantics keeps locked slots deterministic and included in nutrition/state updates.
    effective_pins: Dict[Tuple[int, int], str] = dict(profile.pinned_assignments)
    conflicts: List[Dict[str, Any]] = []
    tag_mismatches: List[Dict[str, Any]] = []

    sorted_locks: List[PlanningBatchLock] = sorted(
        profile.batch_locks,
        key=lambda lock: (str(lock.batch_id), int(lock.day_index), int(lock.slot_index), str(lock.recipe_id)),
    )
    seen_slots: Dict[Tuple[int, int], Dict[str, Any]] = {}
    recipe_by_id = {recipe.id: recipe for recipe in recipe_pool}

    for lock in sorted_locks:
        slot_address = (int(lock.day_index), int(lock.slot_index))
        prior = seen_slots.get(slot_address)
        if prior is not None:
            conflicts.append(
                {
                    "slot_address": {"day_index": slot_address[0], "slot_index": slot_address[1]},
                    "existing_batch_id": prior["batch_id"],
                    "existing_recipe_id": prior["recipe_id"],
                    "incoming_batch_id": str(lock.batch_id),
                    "incoming_recipe_id": str(lock.recipe_id),
                }
            )
            continue
        seen_slots[slot_address] = {"batch_id": str(lock.batch_id), "recipe_id": str(lock.recipe_id)}
        effective_pins[(slot_address[0] + 1, slot_address[1])] = str(lock.recipe_id)

        if 0 <= slot_address[0] < len(profile.schedule):
            day_slots = profile.schedule[slot_address[0]]
            if 0 <= slot_address[1] < len(day_slots):
                required = list(day_slots[slot_address[1]].required_tag_slugs or [])
                if required:
                    lock_recipe = recipe_by_id.get(str(lock.recipe_id))
                    if lock_recipe is None:
                        recipe_tags = set()
                    elif lock_recipe.hard_eligible_tag_slugs is None:
                        recipe_tags = set(lock_recipe.canonical_tag_slugs)
                    else:
                        recipe_tags = set(lock_recipe.hard_eligible_tag_slugs)
                    missing = sorted([slug for slug in required if slug not in recipe_tags])
                    if missing:
                        tag_mismatches.append(
                            {
                                "batch_id": str(lock.batch_id),
                                "recipe_id": str(lock.recipe_id),
                                "slot_address": {"day_index": slot_address[0], "slot_index": slot_address[1]},
                                "missing_required_tag_slugs": missing,
                            }
                        )

    if conflicts:
        return (
            MealPlanResult(
                success=False,
                termination_code="TC-3",
                failure_mode="FM-BATCH-CONFLICT",
                report={
                    "failure_mode": "FM-BATCH-CONFLICT",
                    "batch_conflicts": conflicts,
                },
                stats={"attempts": 0, "backtracks": 0},
            ),
            effective_pins,
            conflicts,
            tag_mismatches,
        )
    return None, effective_pins, conflicts, tag_mismatches


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
    early_failure, effective_pins, _conflicts, tag_mismatches = _merge_batch_locks_into_pins(
        profile, recipe_pool
    )
    if early_failure is not None:
        return early_failure

    search_profile = copy.deepcopy(profile)
    search_profile.pinned_assignments = effective_pins
    result = run_meal_plan_search(
        search_profile,
        recipe_pool,
        days,
        resolved_ul,
        attempt_limit,
        stats,
    )
    if tag_mismatches:
        result.report = dict(result.report or {})
        warnings = list(result.report.get("warnings", []))
        warnings.append(
            {
                "code": "BATCH_TAG_MISMATCH",
                "message": "Batch lock recipe does not satisfy slot required tags.",
                "details": tag_mismatches,
            }
        )
        result.report["warnings"] = warnings
    return result
