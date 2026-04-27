"""Phase 10: FM-4 diagnostics and success-path micronutrient warnings."""

from __future__ import annotations

import pytest

from src.data_layer.models import MicronutrientProfile, NutritionProfile
from src.planning.phase0_models import MealSlot, PlanningUserProfile, WeeklyTracker
from src.planning.phase10_reporting import (
    build_failure,
    build_micronutrient_soft_deficit_warning,
    build_report_fm4,
    result_from_success,
)
from src.planning.phase0_models import Assignment


def _week_tracker(micro: MicronutrientProfile) -> WeeklyTracker:
    return WeeklyTracker(
        weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=micro),
        days_completed=0,
        days_remaining=1,
    )


def _profile(tau: float, targets: dict) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=200.0,
        schedule=[[MealSlot("12:00", 2, "lunch")]],
        micronutrient_targets=targets,
        micronutrient_weekly_min_fraction=tau,
    )


def test_fm4_required_uses_tau_floor_and_includes_full_req():
    D = 2
    profile = _profile(0.9, {"iron_mg": 100.0})
    wt = _week_tracker(MicronutrientProfile(iron_mg=0.0))
    report = build_report_fm4(wt, profile, D, max_daily_achievable=None)
    d0 = report["deficient_nutrients"][0]
    assert d0["nutrient"] == "iron_mg"
    assert d0["required"] == 180.0
    assert d0["full_req"] == 200.0


def test_success_merges_sodium_and_soft_deficit():
    D = 1
    profile = _profile(0.9, {"iron_mg": 10.0, "sodium_mg": 100.0})
    # Weekly sodium > 2 × daily RDI × D ⇒ sodium advisory; iron in soft band below full RDI.
    micro = MicronutrientProfile(iron_mg=9.0, sodium_mg=250.0)
    wt = _week_tracker(micro)
    result = result_from_success(
        [Assignment(0, 0, "r1")],
        {},
        wt,
        profile,
        D,
    )
    assert result.success
    assert result.warning is not None
    assert result.warning.get("type") == "sodium_advisory"
    assert "micronutrient_soft_deficit" in result.warning
    iron = next(x for x in result.warning["micronutrient_soft_deficit"] if x["nutrient"] == "iron_mg")
    assert iron["achieved"] == 9.0
    assert iron["min_req"] == 9.0
    assert iron["full_req"] == 10.0


def test_soft_deficit_empty_when_tau_strict():
    profile = _profile(1.0, {"iron_mg": 10.0})
    wt = _week_tracker(MicronutrientProfile(iron_mg=9.5))
    assert build_micronutrient_soft_deficit_warning(wt, profile, 1) == []


def test_mixed_nutrients_fm4_only_iron_deficient_soft_only_vitamin_c():
    """A: below τ-floor → FM-4 deficient only; B: in [min, full) → soft deficit; C: ≥ full → absent from both."""
    D = 1
    tau = 0.9
    targets = {"iron_mg": 10.0, "vitamin_c_mg": 100.0, "zinc_mg": 15.0}
    profile = _profile(tau, targets)
    micro = MicronutrientProfile(iron_mg=8.0, vitamin_c_mg=95.0, zinc_mg=20.0)
    wt = WeeklyTracker(
        weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=micro),
        days_completed=0,
        days_remaining=1,
    )
    report = build_report_fm4(wt, profile, D, max_daily_achievable=None)
    deficient = report["deficient_nutrients"]
    assert len(deficient) == 1
    d_iron = deficient[0]
    assert d_iron["nutrient"] == "iron_mg"
    assert d_iron["required"] == 9.0
    assert d_iron["full_req"] == 10.0
    assert d_iron["deficit"] == pytest.approx(1.0)
    assert d_iron["achieved"] == 8.0

    soft = build_micronutrient_soft_deficit_warning(wt, profile, D)
    nutrients_soft = {e["nutrient"] for e in soft}
    assert nutrients_soft == {"vitamin_c_mg"}
    vc = next(s for s in soft if s["nutrient"] == "vitamin_c_mg")
    assert vc["achieved"] == 95.0
    assert vc["min_req"] == 90.0
    assert vc["full_req"] == 100.0
    assert "iron_mg" not in nutrients_soft
    assert "zinc_mg" not in nutrients_soft


def test_mixed_nutrients_success_warning_only_soft_band():
    """Iron & zinc at/above full RDI; only vitamin C in [τ×full, full)."""
    D = 1
    tau = 0.9
    targets = {"iron_mg": 10.0, "vitamin_c_mg": 100.0, "zinc_mg": 15.0}
    profile = _profile(tau, targets)
    micro = MicronutrientProfile(iron_mg=10.0, vitamin_c_mg=95.0, zinc_mg=20.0)
    wt = WeeklyTracker(
        weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=micro),
        days_completed=1,
        days_remaining=0,
    )
    result = result_from_success(
        [Assignment(0, 0, "r1"), Assignment(0, 1, "r2")],
        {},
        wt,
        profile,
        D,
    )
    assert result.warning is not None
    assert "micronutrient_soft_deficit" in result.warning
    soft = result.warning["micronutrient_soft_deficit"]
    nutrients_soft = {e["nutrient"] for e in soft}
    assert nutrients_soft == {"vitamin_c_mg"}
    assert result.warning.get("type") != "sodium_advisory"


def test_macro_infeasible_failure_shape_and_fix_hint_snapshot():
    failure = build_failure(
        code="FM-MACRO-INFEASIBLE",
        slot_id="",
        date="day-2",
        details={
            "date": "day-2",
            "deltas": {"calories": -250.0, "protein_g": -20.0, "fat_g": -5.0, "carbs_g": -40.0},
            "constraint": "protein",
        },
    )
    assert failure == {
        "code": "FM-MACRO-INFEASIBLE",
        "slot_id": "",
        "date": "day-2",
        "details": {
            "date": "day-2",
            "deltas": {"calories": -250.0, "protein_g": -20.0, "fat_g": -5.0, "carbs_g": -40.0},
            "constraint": "protein",
        },
        "fix_hint": "Daily macro targets are infeasible. Widen macro ranges or adjust meal constraints.",
    }
