"""Plain-language failure table (src/api/failure_explanations.py)."""

from __future__ import annotations

import pytest

from src.api.failure_explanations import (
    explain_failure,
    failure_cause_block,
    nutrient_label,
)
from src.llm.recovery_types import GapSpec, UnrecoverableReason
from src.planning.phase10_reporting import build_failure, fix_hint_for_code, normalize_failure_object


def _gap(kind: str, **kw) -> GapSpec:
    base = dict(failure_mode="FM-2", days=3, meals_per_day=3, per_meal_calories=733.3, per_meal_protein_g=46.7)
    base.update(kw)
    return GapSpec(kind=kind, **base)


def _unrecoverable(code: str, **details) -> UnrecoverableReason:
    return UnrecoverableReason(code=code, message="", details=details)


@pytest.mark.parametrize(
    "key, label",
    [("vitamin_c_mg", "vitamin C"), ("vitamin_b12_ug", "vitamin B12"), ("fiber_g", "fiber"), ("omega_3_g", "omega 3")],
)
def test_nutrient_label(key, label):
    assert nutrient_label(key) == label


def test_fm1_exclusions_names_slot_one_based():
    failure = build_failure(code="FM-1", details={"blocking_constraints": ["HC-1"]}, day_index=1, slot_index=2)
    out = explain_failure(failure, _gap("candidate_gap", slots=[[1, 2]]))
    assert out == {
        "explanation": "Day 2, meal 3 has no recipe without your excluded ingredients.",
        "fix": "Add a recipe for day 2, meal 3 that avoids them, or remove an exclusion.",
        "cause": "candidate_gap",
    }


def test_fm1_cook_time_names_the_cap():
    failure = build_failure(
        code="FM-1", details={"blocking_constraints": ["HC-3: cook time <= 15 min"]}, day_index=0, slot_index=0
    )
    out = explain_failure(failure, _gap("candidate_gap"))
    assert out["explanation"] == "Day 1, meal 1 has no recipe that can be cooked in 15 minutes or less."


def test_fm1_day_level_hc8():
    failure = build_failure(
        code="FM-1",
        details={"blocking_constraints": ["HC-8: consecutive-day non-workout recipe reuse leaves no valid day sequence"]},
        day_index=3,
    )
    out = explain_failure(failure, _gap("macro_gap"))
    assert "back-to-back days (first blocked at day 4)" in out["explanation"]


def test_macro_infeasible_reads_day_from_date_and_uses_gap_numbers():
    # Search-time FM-MACRO-INFEASIBLE sets only date / details.date, not day_index.
    failure = build_failure(
        code="FM-MACRO-INFEASIBLE", details={"date": "day-3", "deltas": {}, "constraint": "x"}, date="day-3"
    )
    out = explain_failure(failure, _gap("macro_gap"))
    assert out["explanation"].endswith("calorie and macro targets for day 3.")
    assert out["fix"] == "Add recipes close to 733 kcal and 47 g protein per meal, or widen the macro targets."


def test_macro_infeasible_without_gap_uses_generic_fix():
    failure = build_failure(code="FM-MACRO-INFEASIBLE", details={})
    out = explain_failure(failure, _unrecoverable("SEARCH_BUDGET"))
    assert out["explanation"].endswith("for the plan.")
    assert out["fix"] == "Widen the calorie or macro targets, or add recipes that fit them."


def test_fm2_alias_and_uniqueness_gap():
    failure = normalize_failure_object({"code": "FM-2", "details": {}})
    out = explain_failure(failure, _gap("uniqueness_gap"))
    assert out["explanation"].startswith("There are fewer different recipes than meals per day")


def test_impossible_targets_overrides_any_code():
    failure = build_failure(code="FM-1", details={"blocking_constraints": ["HC-1"]}, day_index=0, slot_index=0)
    diagnosis = _unrecoverable(
        "IMPOSSIBLE_TARGETS", protein_fat_vs_calories="...", calorie_ceiling="..."
    )
    out = explain_failure(failure, diagnosis)
    assert out["explanation"] == (
        "Your daily targets can't all be met at the same time: protein and minimum fat alone "
        "exceed the calorie target and the calorie ceiling is below the calorie target."
    )
    assert out["cause"] == "IMPOSSIBLE_TARGETS"


def test_fm3_pin_vs_batch():
    pin = normalize_failure_object(
        {"code": "FM-3", "day_index": 1, "slot_index": 0, "details": {"violation_type": "direct"}}
    )
    reason = _unrecoverable("PIN_OR_BATCH_CONFLICT")
    assert explain_failure(pin, reason)["explanation"].startswith("A pinned meal on day 2, meal 1")
    # Same failure, but the slot is batch-locked.
    assert explain_failure(pin, reason, {(1, 0)})["explanation"].startswith("A meal-prep batch on day 2, meal 1")

    downstream = normalize_failure_object(
        {
            "code": "FM-3",
            "day_index": 1,
            "details": {"violation_type": "downstream", "pinned_slots": [{"slot_index": 0, "source": "batch"}]},
        }
    )
    assert explain_failure(downstream, reason)["explanation"].startswith("A meal-prep batch on day 2 ")


def test_fm4_lists_nutrients():
    failure = normalize_failure_object(
        {
            "code": "FM-4",
            "details": {"deficient_nutrients": [{"nutrient": "vitamin_d_ug"}, {"nutrient": "iron_mg"}, {"nutrient": "fiber_g"}]},
        }
    )
    out = explain_failure(failure, _gap("nutrient_gap", nutrient_min_per_recipe={"vitamin_d_ug": 3.0}))
    assert out["explanation"] == "The available recipes can't provide enough vitamin D, iron and fiber over the plan."


def test_fm4_falls_back_to_gap_nutrients():
    failure = normalize_failure_object({"code": "FM-4", "details": {}})
    out = explain_failure(failure, _gap("nutrient_gap", nutrient_min_per_recipe={"vitamin_c_mg": 10.0}))
    assert "enough vitamin C over" in out["explanation"]


def test_fm5_does_not_claim_infeasible():
    failure = normalize_failure_object({"code": "FM-5", "details": {"attempts": 5000}})
    out = explain_failure(failure, _unrecoverable("SEARCH_BUDGET"))
    assert "doesn't mean no plan exists" in out["explanation"]


def test_tag_empty_names_tag():
    failure = build_failure(code="FM-TAG-EMPTY", details={"missing_tag": "high-fiber"}, day_index=0, slot_index=1)
    out = explain_failure(failure, _unrecoverable("REQUIRED_TAG_UNHELD"))
    assert out["explanation"] == 'Day 1, meal 2 requires the "high-fiber" tag, and no available recipe has it.'


def test_unknown_code_falls_back_to_message_and_hint():
    failure = {"code": "FM-NEW", "message": "Something new.", "details": {}}
    out = explain_failure(failure, None)
    assert out == {"explanation": "Something new.", "fix": fix_hint_for_code("FM-NEW"), "cause": None}


def test_failure_cause_block():
    assert failure_cause_block(None) is None
    assert failure_cause_block(_unrecoverable("SEARCH_BUDGET")) == {"cause": "SEARCH_BUDGET", "recipe_could_help": False}
    block = failure_cause_block(_gap("candidate_gap", slots=[[0, 1]], cook_time_cap_minutes=15, meal_types=["lunch"]))
    assert block["cause"] == "candidate_gap"
    assert block["recipe_could_help"] is True
    assert block["recipe_gap"]["slots"] == [[0, 1]]
    assert block["recipe_gap"]["cook_time_cap_minutes"] == 15
    assert "existing_recipe_names" not in block["recipe_gap"]
