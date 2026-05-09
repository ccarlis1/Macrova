"""Phase 10: Structured failure reporting and sodium advisory. Spec Section 11.

Reporting and advisory only. No search, constraint, scoring, or backtracking changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.planning.phase0_models import Assignment, DailyTracker, PlanningUserProfile, WeeklyTracker
from src.planning.micronutrient_policy import (
    MICRONUTRIENT_EPSILON,
    sodium_weekly_advisory_max_mg,
    tau_from_profile,
    weekly_minimum_total,
)


# --- Canonical result schema ---


@dataclass
class Failure:
    """Stable UI-actionable failure object carried in MealPlanResult.report.failures."""

    code: str
    slot_id: str
    date: str
    details: Dict[str, Any]
    fix_hint: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "slot_id": self.slot_id,
            "date": self.date,
            "details": dict(self.details),
            "fix_hint": self.fix_hint,
        }


_FIX_HINTS: Dict[str, str] = {
    "FM-1": "No recipes satisfy hard constraints for this slot. Widen the recipe pool or relax slot constraints.",
    "FM-3": "A pinned meal conflicts with planning rules. Change the pin, pick a compatible recipe, or relax constraints.",
    "FM-4": "Weekly micronutrient targets cannot be met. Lower tracked goals, add richer recipes, or relax filters.",
    "FM-5": "Planning hit the attempt limit. Simplify the schedule, widen macro targets, or reduce constraints.",
    "FM-TAG-EMPTY": "No recipes match tag `{missing_tag}`. Add one or relax constraints.",
    "FM-BATCH-CONFLICT": "Batch locks conflict for this slot. Remove one lock so only one batch assignment remains.",
    "FM-MACRO-INFEASIBLE": "Daily macro targets are infeasible. Widen macro ranges or adjust meal constraints.",
}


def fix_hint_for_code(code: str) -> str:
    return _FIX_HINTS.get(code, "Resolve conflicting planner constraints and retry.")


def build_failure(
    *,
    code: str,
    details: Dict[str, Any],
    message: Optional[str] = None,
    day_index: Optional[int] = None,
    slot_index: Optional[int] = None,
    slot_id: str = "",
    date: str = "",
) -> Dict[str, Any]:
    resolved_day_index = day_index if day_index is not None else _as_int_or_none((details or {}).get("day_index"))
    resolved_slot_index = slot_index if slot_index is not None else _as_int_or_none((details or {}).get("slot_index"))
    failure = Failure(
        code=str(code),
        slot_id=str(slot_id),
        date=str(date),
        details=dict(details or {}),
        fix_hint=fix_hint_for_code(str(code)),
    )
    resolved_message = str(message or "").strip()
    if not resolved_message:
        resolved_message = f"Planner failure: {code}."
    if code == "FM-TAG-EMPTY":
        missing_tag = str((details or {}).get("missing_tag", "")).strip()
        if missing_tag:
            failure.fix_hint = failure.fix_hint.replace("{missing_tag}", missing_tag)
        if message is None:
            resolved_message = f"No recipes satisfy required tag `{missing_tag}` for this slot."
    if code == "FM-BATCH-CONFLICT" and message is None:
        resolved_message = "Batch locks conflict for this slot."
    if code == "FM-MACRO-INFEASIBLE" and message is None:
        resolved_message = "Macro targets are infeasible under current constraints."
    return normalize_failure_object(
        {
            **failure.to_dict(),
            "message": resolved_message,
            "day_index": resolved_day_index,
            "slot_index": resolved_slot_index,
        }
    )


def ensure_report_failures(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = dict(report or {})
    failures = normalized.get("failures")
    if not isinstance(failures, list):
        normalized["failures"] = []
    return normalized


def _as_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_failure_object(raw_failure: Any) -> Dict[str, Any]:
    """Normalize arbitrary failure objects into the stable additive API shape."""
    item = dict(raw_failure or {}) if isinstance(raw_failure, dict) else {}
    code = str(item.get("code", "")).strip()
    details = item.get("details")
    if not isinstance(details, dict):
        details = {}
    message = str(item.get("message", "")).strip()
    if not message:
        message = "Planner constraints could not be satisfied for this slot."

    normalized: Dict[str, Any] = {
        "code": code,
        "message": message,
    }

    day_index = _as_int_or_none(item.get("day_index"))
    slot_index = _as_int_or_none(item.get("slot_index"))
    if day_index is not None:
        normalized["day_index"] = day_index
    if slot_index is not None:
        normalized["slot_index"] = slot_index

    slot_id = item.get("slot_id")
    if isinstance(slot_id, str):
        normalized["slot_id"] = slot_id
    date = item.get("date")
    if isinstance(date, str):
        normalized["date"] = date
    normalized["details"] = dict(details)

    fix_hint = item.get("fix_hint")
    if isinstance(fix_hint, str) and fix_hint.strip():
        normalized["fix_hint"] = fix_hint.strip()
    else:
        hint = fix_hint_for_code(code)
        if code == "FM-TAG-EMPTY":
            missing_tag = str(details.get("missing_tag", "")).strip()
            if missing_tag:
                hint = hint.replace("{missing_tag}", missing_tag)
        normalized["fix_hint"] = hint
    return normalized


def _fm1_failures_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for slot in report.get("unfillable_slots", []) or []:
        if not isinstance(slot, dict):
            continue
        day_index = _as_int_or_none(slot.get("day"))
        slot_index = _as_int_or_none(slot.get("slot_index"))
        details = {
            "eligible_recipe_count": int(slot.get("eligible_recipe_count", 0)),
            "blocking_constraints": list(slot.get("blocking_constraints", []) or []),
        }
        out.append(
            normalize_failure_object(
                {
                    "code": "FM-1",
                    "message": "No feasible recipe candidates for this slot.",
                    "day_index": day_index,
                    "slot_index": slot_index,
                    "details": details,
                    "date": "" if day_index is None else f"day-{day_index + 1}",
                    "slot_id": (
                        ""
                        if day_index is None or slot_index is None
                        else f"day-{day_index + 1}-slot-{slot_index}"
                    ),
                }
            )
        )
    return out


def _fm3_failures_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    remaining_budget = report.get("remaining_budget", {})
    for conflict in report.get("pinned_conflicts", []) or []:
        if not isinstance(conflict, dict):
            continue
        day_index = _as_int_or_none(conflict.get("day"))
        slot_index = _as_int_or_none(conflict.get("slot_index"))
        details = {
            "recipe_id": conflict.get("recipe_id"),
            "violation_type": conflict.get("violation_type"),
            "remaining_budget": remaining_budget if isinstance(remaining_budget, dict) else {},
        }
        out.append(
            normalize_failure_object(
                {
                    "code": "FM-3",
                    "message": "Pinned assignment conflicts with planner constraints.",
                    "day_index": day_index,
                    "slot_index": slot_index,
                    "details": details,
                    "date": "" if day_index is None else f"day-{day_index + 1}",
                    "slot_id": (
                        ""
                        if day_index is None or slot_index is None
                        else f"day-{day_index + 1}-slot-{slot_index}"
                    ),
                }
            )
        )
    return out


def _fm4_failures_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    deficient = list(report.get("deficient_nutrients", []) or [])
    return [
        normalize_failure_object(
            {
                "code": "FM-4",
                "message": "Weekly micronutrient targets are infeasible with current constraints.",
                "details": {"deficient_nutrients": deficient},
            }
        )
    ] if deficient else []


def _fm5_failures_from_report(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = {
        "attempts": int(report.get("attempts", 0)),
        "backtracks": int(report.get("backtracks", 0)),
        "search_exhaustive": bool(report.get("search_exhaustive", False)),
        "best_plan_violations": dict(report.get("best_plan_violations", {}) or {}),
    }
    if details["attempts"] <= 0 and not details["best_plan_violations"]:
        return []
    return [
        normalize_failure_object(
            {
                "code": "FM-5",
                "message": "Planner stopped after reaching attempt limits.",
                "details": details,
            }
        )
    ]


def normalize_planner_report(
    *,
    failure_mode: Optional[str],
    report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ensure planner report always has stable `failures[]` entries."""
    normalized = ensure_report_failures(report)
    raw_failures = normalized.get("failures", [])
    failures: List[Dict[str, Any]] = []
    if isinstance(raw_failures, list):
        failures = [normalize_failure_object(item) for item in raw_failures]

    if not failures:
        if failure_mode == "FM-1":
            failures = _fm1_failures_from_report(normalized)
        elif failure_mode == "FM-3":
            failures = _fm3_failures_from_report(normalized)
        elif failure_mode == "FM-4":
            failures = _fm4_failures_from_report(normalized)
        elif failure_mode == "FM-5":
            failures = _fm5_failures_from_report(normalized)

    normalized["failures"] = failures
    return normalized


@dataclass
class MealPlanResult:
    """Canonical result for both success and failure. Spec Section 10, 11.

    JSON-serializable (plan, report, warning, stats). daily_trackers/weekly_tracker
    set on success (or best-effort) for consumers that need full state.
    When plan_incomplete_reason is set, plan/daily_trackers/weekly_tracker are
    a best-effort plan that did not meet all targets (e.g. weekly validation).
    """

    success: bool
    termination_code: str  # TC-1, TC-2, TC-3, TC-4
    failure_mode: Optional[str] = None  # FM-1 .. FM-5
    plan: Optional[List[Assignment]] = None
    daily_trackers: Optional[Dict[int, DailyTracker]] = None  # success or best-effort
    weekly_tracker: Optional[WeeklyTracker] = None  # success or best-effort
    warning: Optional[Dict[str, Any]] = None  # e.g. sodium_advisory
    report: Dict[str, Any] = field(default_factory=lambda: {"failures": []})  # structured diagnostics
    stats: Optional[Dict[str, Any]] = None  # attempts, backtracks if available
    plan_incomplete_reason: Optional[str] = None  # e.g. "Did not meet weekly targets."


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


def build_report_fm_tag_empty(
    *,
    day_index: int,
    slot_index: int,
    required_tag_slugs: List[str],
    candidate_count_before: int,
    candidate_count_after: int,
    reason: str,
) -> Dict[str, Any]:
    """FM-TAG-EMPTY: slot-level required-tag empties the candidate set."""
    return {
        "tag_empty_slots": [
            {
                "code": "FM-TAG-EMPTY",
                "day_index": day_index,
                "slot_index": slot_index,
                "required_tag_slugs": list(required_tag_slugs),
                "candidate_count_before": int(candidate_count_before),
                "candidate_count_after": int(candidate_count_after),
                "reason": str(reason),
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


def build_report_fm_batch_conflict(
    conflicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """FM-BATCH-CONFLICT: two meal-prep batch locks target the same slot."""
    failures = []
    for item in conflicts:
        slot_address = item.get("slot_address", {}) or {}
        day_index = int(slot_address.get("day_index", 0))
        slot_index = int(slot_address.get("slot_index", 0))
        slot_id = f"day-{day_index + 1}-slot-{slot_index}"
        batch_ids = [
            str(item.get("existing_batch_id", "")),
            str(item.get("incoming_batch_id", "")),
        ]
        failures.append(
            build_failure(
                code="FM-BATCH-CONFLICT",
                day_index=day_index,
                slot_index=slot_index,
                slot_id=slot_id,
                date="",
                details={
                    "batch_ids": batch_ids,
                    "date": "",
                    "slot_id": slot_id,
                },
            )
        )
    return ensure_report_failures(
        {
            "failure_mode": "FM-BATCH-CONFLICT",
            "batch_conflicts": list(conflicts),
            "failures": failures,
        }
    )


def append_batch_tag_mismatch_warning(
    report: Optional[Dict[str, Any]],
    tag_mismatches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach non-fatal batch-lock required-tag mismatch diagnostics."""
    normalized = dict(report or {})
    warnings = list(normalized.get("warnings", []))
    warnings.append(
        {
            "code": "BATCH_TAG_MISMATCH",
            "message": "Batch lock recipe does not satisfy slot required tags.",
            "details": list(tag_mismatches),
        }
    )
    normalized["warnings"] = warnings
    return normalized


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
    tau = tau_from_profile(profile)
    out: List[Dict[str, Any]] = []
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        required = weekly_minimum_total(daily_rdi, D, tau)
        full_req = weekly_minimum_total(daily_rdi, D, 1.0)
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
            "full_req": full_req,
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


def build_micronutrient_soft_deficit_warning(
    weekly_tracker: WeeklyTracker,
    profile: PlanningUserProfile,
    D: int,
) -> List[Dict[str, Any]]:
    """When τ < 1, list nutrients that meet τ-floor but sit below full prorated RDI (transparency)."""
    tau = tau_from_profile(profile)
    if tau >= 1.0 - MICRONUTRIENT_EPSILON:
        return []
    tracked = profile.micronutrient_targets
    if not tracked:
        return []
    from src.planning.phase0_models import micronutrient_profile_to_dict

    micro = micronutrient_profile_to_dict(getattr(weekly_tracker.weekly_totals, "micronutrients", None))
    out: List[Dict[str, Any]] = []
    for n, daily_rdi in tracked.items():
        if daily_rdi <= 0:
            continue
        min_req = weekly_minimum_total(daily_rdi, D, tau)
        full_req = weekly_minimum_total(daily_rdi, D, 1.0)
        achieved = micro.get(n, 0.0)
        if achieved < min_req - MICRONUTRIENT_EPSILON:
            continue
        if achieved >= full_req - MICRONUTRIENT_EPSILON:
            continue
        frac = achieved / full_req if full_req > MICRONUTRIENT_EPSILON else 0.0
        out.append({
            "nutrient": n,
            "achieved": achieved,
            "min_req": min_req,
            "full_req": full_req,
            "fraction_of_full": frac,
        })
    return out


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
    recommended_max = sodium_weekly_advisory_max_mg(daily_rdi, D)
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
    warning_parts: Dict[str, Any] = {}
    sw = build_sodium_warning(weekly_tracker, profile, D)
    if sw:
        warning_parts.update(sw)
    soft = build_micronutrient_soft_deficit_warning(weekly_tracker, profile, D)
    if soft:
        warning_parts["micronutrient_soft_deficit"] = soft
    warning = warning_parts if warning_parts else None
    return MealPlanResult(
        success=True,
        termination_code=termination_code,
        failure_mode=None,
        plan=list(assignments),
        daily_trackers=dict(daily_trackers),
        weekly_tracker=weekly_tracker,
        warning=warning,
        report=normalize_planner_report(failure_mode=None, report={}),
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
    *,
    best_effort_plan: Optional[List[Assignment]] = None,
    best_effort_daily_trackers: Optional[Dict[int, DailyTracker]] = None,
    best_effort_weekly_tracker: Optional[WeeklyTracker] = None,
    plan_incomplete_reason: Optional[str] = None,
) -> MealPlanResult:
    """Build MealPlanResult for failure path.

    When best_effort_plan and plan_incomplete_reason are provided (e.g. TC-2/FM-4),
    the result includes the best-effort plan so the user can see the assignment
    that failed weekly validation, with a clear incomplete label.
    """
    warning = None
    if sodium_advisory:
        warning = {"type": "sodium_advisory_text", "message": sodium_advisory}
    st = dict(stats) if stats else {}
    st["attempts"] = attempt_count
    st["backtracks"] = backtrack_count
    # Prefer explicit best-effort kwargs (e.g. FM-4 weekly incomplete); otherwise use the
    # positional closest-plan snapshots — those were incorrectly dropped before, which made
    # format_result_json emit empty daily_plans for almost all failure terminations.
    if best_effort_plan is not None:
        plan: Optional[List[Assignment]] = list(best_effort_plan)
    elif best_assignments:
        plan = list(best_assignments)
    else:
        plan = None
    if best_effort_daily_trackers is not None:
        daily_trackers: Optional[Dict[int, DailyTracker]] = dict(best_effort_daily_trackers)
    elif best_daily_trackers:
        daily_trackers = dict(best_daily_trackers)
    else:
        daily_trackers = None
    weekly_tracker = best_effort_weekly_tracker if best_effort_weekly_tracker is not None else None
    return MealPlanResult(
        success=False,
        termination_code=termination_code,
        failure_mode=failure_mode,
        plan=plan,
        daily_trackers=daily_trackers,
        weekly_tracker=weekly_tracker,
        warning=warning,
        report=normalize_planner_report(failure_mode=failure_mode, report=report),
        stats=st,
        plan_incomplete_reason=plan_incomplete_reason,
    )
