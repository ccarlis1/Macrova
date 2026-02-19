"""Phase 10: Structured failure reporting and sodium advisory. Spec Section 11.

Reporting and advisory only. No search, constraint, scoring, or backtracking changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.planning.phase0_models import Assignment, DailyTracker, PlanningUserProfile, WeeklyTracker


# --- Canonical result schema ---


@dataclass
class MealPlanResult:
    """Canonical result for both success and failure. Spec Section 10, 11.

    JSON-serializable (plan, report, warning, stats). daily_trackers/weekly_tracker
    set on success for consumers that need full state.
    """

    success: bool
    termination_code: str  # TC-1, TC-2, TC-3, TC-4
    failure_mode: Optional[str] = None  # FM-1 .. FM-5
    plan: Optional[List[Assignment]] = None
    daily_trackers: Optional[Dict[int, DailyTracker]] = None  # success path
    weekly_tracker: Optional[WeeklyTracker] = None  # success path
    warning: Optional[Dict[str, Any]] = None  # e.g. sodium_advisory
    report: Dict[str, Any] = field(default_factory=dict)  # structured diagnostics
    stats: Optional[Dict[str, Any]] = None  # attempts, backtracks if available


# --- Plan snapshot (serializable) ---


def assignment_to_dict(a: Assignment) -> Dict[str, Any]:
    """JSON-serializable assignment. Omit variant_index when 0 for backward compat."""
    out: Dict[str, Any] = {
        "day_index": a.day_index,
        "slot_index": a.slot_index,
        "recipe_id": a.recipe_id,
    }
    if a.variant_index != 0:
        out["variant_index"] = a.variant_index
    return out


def daily_tracker_to_dict(t: DailyTracker) -> Dict[str, Any]:
    """JSON-serializable daily tracker summary."""
    return {
        "calories_consumed": t.calories_consumed,
        "protein_consumed": t.protein_consumed,
        "fat_consumed": t.fat_consumed,
        "carbs_consumed": t.carbs_consumed,
        "slots_assigned": t.slots_assigned,
        "slots_total": t.slots_total,
    }


def build_plan_snapshot(
    assignments: List[Assignment],
    daily_trackers: Dict[int, DailyTracker],
) -> Dict[str, Any]:
    """Closest/best plan snapshot for FM-2 and FM-5."""
    return {
        "assignments": [assignment_to_dict(a) for a in assignments],
        "daily_trackers": {str(d): daily_tracker_to_dict(t) for d, t in sorted(daily_trackers.items())},
    }


# --- FM report builders ---


def build_report_fm1(
    day_index: int,
    slot_index: int,
    constraint_detail: str,
    eligible_recipe_count: int = 0,
) -> Dict[str, Any]:
    """FM-1: Unfillable slots. Spec Section 11."""
    return {
        "unfillable_slots": [
            {
                "day": day_index,
                "slot_index": slot_index,
                "eligible_recipe_count": eligible_recipe_count,
                "blocking_constraints": [constraint_detail] if constraint_detail else [],
            }
        ]
    }


def build_report_fm2(
    day_index: Optional[int],
    constraint_detail: Optional[str],
    macro_violations: Optional[Dict[str, Any]],
    ul_violations: Optional[Dict[str, Any]],
    closest_plan: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """FM-2: Daily infeasibility. Spec Section 11."""
    failed_days: List[Dict[str, Any]] = []
    if day_index is not None:
        failed_days.append({
            "day": day_index,
            "macro_violations": macro_violations if macro_violations is not None else {},
            "ul_violations": ul_violations if ul_violations is not None else {},
            "constraint_detail": constraint_detail,
        })
    return {
        "failed_days": failed_days,
        "closest_plan": closest_plan,
    }


def build_report_fm3(
    pinned_conflicts: List[Dict[str, Any]],
    remaining_budget: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """FM-3: Pinned conflict. Spec Section 11."""
    return {
        "pinned_conflicts": pinned_conflicts,
        "remaining_budget": remaining_budget if remaining_budget is not None else {},
    }


def _deficient_nutrients_list(
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
    max_daily_achievable: Optional[Dict[str, Dict[int, float]]] = None,
    max_slots: int = 8,
) -> List[Dict[str, Any]]:
    """Compute deficient nutrients: achieved, required, deficit, classification (marginal vs structural)."""
    from src.planning.phase0_models import micronutrient_profile_to_dict

    tracked = profile.micronutrient_targets
    if not tracked:
        return []
    micro = micronutrient_profile_to_dict(getattr(weekly_tracker.weekly_totals, "micronutrients", None))
    out: List[Dict[str, Any]] = []
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        required = daily_rdi * D
        achieved = micro.get(n, 0.0)
        deficit = required - achieved
        if deficit <= 0:
            continue
        mda_one_day = 0.0
        if max_daily_achievable and n in max_daily_achievable:
            mda_one_day = max(max_daily_achievable[n].get(s, 0.0) for s in range(1, max_slots + 1))
        classification = "marginal" if deficit <= mda_one_day * 1.0 else "structural"
        out.append({
            "nutrient": n,
            "achieved": achieved,
            "required": required,
            "deficit": deficit,
            "classification": classification,
        })
    return out


def build_report_fm4(
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
    max_daily_achievable: Optional[Dict[str, Dict[int, float]]] = None,
) -> Dict[str, Any]:
    """FM-4: Weekly micronutrient infeasibility. Spec Section 11."""
    deficient_nutrients = _deficient_nutrients_list(weekly_tracker, profile, D, max_daily_achievable)
    return {"deficient_nutrients": deficient_nutrients}


def build_report_fm5(
    attempts: int,
    backtracks: int,
    best_plan: Optional[Dict[str, Any]],
    best_plan_violations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """FM-5: Attempt limit. Spec Section 11."""
    return {
        "attempts": attempts,
        "backtracks": backtracks,
        "search_exhaustive": False,
        "best_plan": best_plan,
        "best_plan_violations": best_plan_violations if best_plan_violations is not None else {},
    }


# --- Sodium advisory (success path only) ---


def build_sodium_warning(
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
) -> Optional[Dict[str, Any]]:
    """If weekly sodium > 2.0 * daily_RDI * D, return advisory dict; else None. Spec 6.6."""
    tracked = profile.micronutrient_targets
    if not tracked or "sodium_mg" not in tracked:
        return None
    daily_rdi = tracked["sodium_mg"]
    if daily_rdi <= 0:
        return None
    micro = getattr(weekly_tracker.weekly_totals, "micronutrients", None)
    if micro is None:
        return None
    weekly_sodium = getattr(micro, "sodium_mg", 0.0)
    recommended_max = 2.0 * daily_rdi * D
    if weekly_sodium <= recommended_max:
        return None
    return {
        "type": "sodium_advisory",
        "weekly_sodium_mg": weekly_sodium,
        "recommended_max_mg": recommended_max,
        "ratio": weekly_sodium / recommended_max if recommended_max else 0.0,
    }


# --- Build MealPlanResult from internal success/failure ---


def result_from_success(
    assignments: List[Assignment],
    daily_trackers: Dict[int, DailyTracker],
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
    termination_code: str = "TC-1",
    stats: Optional[Dict[str, Any]] = None,
) -> MealPlanResult:
    """Build MealPlanResult for TC-1 or TC-4 success."""
    warning = build_sodium_warning(weekly_tracker, profile, D)
    return MealPlanResult(
        success=True,
        termination_code=termination_code,
        failure_mode=None,
        plan=list(assignments),
        daily_trackers=dict(daily_trackers),
        weekly_tracker=weekly_tracker,
        warning=warning,
        report={},
        stats=stats,
    )


def result_from_failure(
    termination_code: str,
    failure_mode: str,
    report: Dict[str, Any],
    best_assignments: List[Assignment],
    best_daily_trackers: Dict[int, DailyTracker],
    attempt_count: int,
    backtrack_count: int = 0,
    sodium_advisory: Optional[str] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> MealPlanResult:
    """Build MealPlanResult for failure path."""
    warning = None
    if sodium_advisory:
        warning = {"type": "sodium_advisory_text", "message": sodium_advisory}
    st = dict(stats) if stats else {}
    st["attempts"] = attempt_count
    st["backtracks"] = backtrack_count
    return MealPlanResult(
        success=False,
        termination_code=termination_code,
        failure_mode=failure_mode,
        plan=None,
        daily_trackers=None,
        weekly_tracker=None,
        warning=warning,
        report=report,
        stats=st,
    )
