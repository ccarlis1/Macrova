"""Stage 1: typed recovery outcome and error containment in plan_with_llm_feedback."""
from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, NutritionProfile, MicronutrientProfile
from src.llm.recipe_generator import RecipeGenerationError
from src.llm.recovery_types import RecoveryState
from src.output.formatters import format_result_json
from src.planning.orchestrator import plan_with_llm_feedback
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult
from src.providers.ingredient_provider import IngredientDataProvider


class _Provider(IngredientDataProvider):
    usda_capable = True

    def get_ingredient_info(self, name):
        return {"name": name, "per_100g": {"calories": 100.0, "protein_g": 10.0, "fat_g": 5.0, "carbs_g": 10.0}}

    def resolve_all(self, names):
        return None


class _Client:
    """Scripted LLM: returns the configured envelope, or raises."""

    _settings = None

    def __init__(self, envelope=None, raise_exc=None):
        self.envelope = envelope
        self.raise_exc = raise_exc
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.envelope


def _profile(days=1, slots=2, excluded=()):
    return PlanningUserProfile(
        daily_calories=2000, daily_protein_g=100.0, daily_fat_g=(50.0, 80.0), daily_carbs_g=250.0,
        schedule=[[MealSlot(time="12:00", busyness_level=4, meal_type="lunch") for _ in range(slots)] for _ in range(days)],
        excluded_ingredients=list(excluded), liked_foods=[], pinned_assignments={}, micronutrient_targets={},
    )


def _recipe(rid, kcal, p, f, c):
    return PlanningRecipe(id=rid, name=rid, ingredients=[Ingredient("x", 100, "g")], cooking_time_minutes=10,
                          nutrition=NutritionProfile(kcal, p, f, c, MicronutrientProfile()))


def _failing_pool():
    # Cannot reach a 2000 kcal / 2 slot window.
    return [_recipe("a", 300, 20, 10, 30), _recipe("b", 320, 22, 11, 32)]


def test_first_try_success_reports_not_attempted(tmp_path):
    pool = [_recipe("a", 1000, 50, 32.5, 125), _recipe("b", 1000, 50, 32.5, 125)]
    out = plan_with_llm_feedback(_profile(), pool, 1, recipes_path=str(tmp_path / "r.json"),
                                 client=_Client(), provider=_Provider(), use_feedback_cache=False, force_live_generation=True)
    assert out.success is True
    rec = out.report["llm_recovery"]
    assert rec["state"] == RecoveryState.NOT_ATTEMPTED.value
    assert rec["llm_calls"] == 0 and rec["planner_runs"] == 1


def test_llm_envelope_error_is_contained_and_planner_result_preserved(tmp_path):
    client = _Client(envelope={"drafts": []})  # wrong count -> RecipeGenerationError inside the loop
    out = plan_with_llm_feedback(_profile(), _failing_pool(), 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=_Provider(), use_feedback_cache=False, force_live_generation=True)
    assert out.success is False
    assert out.failure_mode is not None  # deterministic result preserved
    rec = out.report["llm_recovery"]
    assert rec["state"] == RecoveryState.DATA_SOURCE_FAILURE.value
    assert rec["error"]["code"] == "LLM_WRONG_DRAFT_COUNT"
    assert rec["llm_calls"] == 1
    assert client.calls == 1


def test_llm_transport_error_is_contained(tmp_path):
    from src.llm.client import LLMTimeoutError
    client = _Client(raise_exc=LLMTimeoutError(error_code="TIMEOUT_MAX_RETRIES_EXCEEDED", message="timeout"))
    out = plan_with_llm_feedback(_profile(), _failing_pool(), 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=_Provider(), use_feedback_cache=False, force_live_generation=True)
    rec = out.report["llm_recovery"]
    assert rec["state"] == RecoveryState.DATA_SOURCE_FAILURE.value
    assert rec["error"]["code"] == "TIMEOUT_MAX_RETRIES_EXCEEDED"


def test_ineligible_failure_mode_reports_unrecoverable(tmp_path):
    # Pinned recipe absent from the pool -> FM-3 pre-validation failure.
    prof = _profile()
    prof.pinned_assignments = {(1, 0): "missing"}
    client = _Client(envelope={"drafts": []})
    out = plan_with_llm_feedback(prof, _failing_pool(), 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=_Provider(), use_feedback_cache=False, force_live_generation=True)
    rec = out.report["llm_recovery"]
    assert out.failure_mode == "FM-3"
    assert rec["state"] == RecoveryState.UNRECOVERABLE_INFEASIBILITY.value
    assert client.calls == 0


def test_no_progress_reports_no_useful_recovery(tmp_path):
    draft = {"name": "Small snack", "ingredients": [{"name": "x", "quantity": 50.0, "unit": "g"}], "instructions": ["Eat."]}
    client = _Client(envelope={"drafts": [draft, draft]})
    out = plan_with_llm_feedback(_profile(), _failing_pool(), 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=_Provider(), use_feedback_cache=False, force_live_generation=True,
                                 recipes_to_generate_per_attempt=2)
    rec = out.report["llm_recovery"]
    # 50 g of rice is not useful for a ~1000 kcal per-meal gap: rejected, planner never re-run.
    assert rec["state"] == RecoveryState.INVALID_RECOVERY_OUTPUT.value
    assert rec["planner_runs"] == 1
    assert all(a["rejected"] for a in rec["attempts"])


def test_outcome_survives_json_formatting(tmp_path):
    client = _Client(envelope={"drafts": []})
    prof = _profile()
    out = plan_with_llm_feedback(prof, _failing_pool(), 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=_Provider(), use_feedback_cache=False, force_live_generation=True)
    js = format_result_json(out, {r.id: r for r in _failing_pool()}, prof, 1)
    assert js["report"]["llm_recovery"]["state"] == RecoveryState.DATA_SOURCE_FAILURE.value
