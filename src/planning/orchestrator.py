from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from src.config.llm_settings import load_llm_settings
from src.data_layer.recipe_db import RecipeDB
from src.llm.client import LLMClient
from src.llm.planner_assistant import build_feedback_context, suggest_targeted_recipe_drafts
from src.llm.recipe_validator import validate_recipe_drafts
from src.llm.repository import append_validated_recipes, compute_recipe_fingerprint
from src.llm.usda_contract import assert_usda_capable_provider
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.ingestion.usda_client import USDAClient
from src.llm.types import ValidatedRecipeForPersistence
from src.nutrition.calculator import NutritionCalculator
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult
from src.planning.converters import convert_recipes, extract_ingredient_names
from src.planning.planner import plan_meals
from src.providers.api_provider import APIIngredientProvider
from src.providers.ingredient_provider import IngredientDataProvider
from src.llm.schemas import RecipeDraft


_ELIGIBLE_FAILURE_MODES: Set[str] = {"FM-1", "FM-2", "FM-4", "FM-5"}


def _stable_obj_for_hash(obj: Any) -> Any:
    """Make an object JSON-stable for hashing."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _stable_obj_for_hash(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, list):
        return [_stable_obj_for_hash(v) for v in obj]
    # Fallback: deterministic-ish repr
    return repr(obj)


def _stable_failure_signature(result: MealPlanResult) -> str:
    payload = {
        "failure_mode": result.failure_mode,
        "termination_code": result.termination_code,
        "report": _stable_obj_for_hash(result.report or {}),
    }
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _default_recipe_drafts_count(profile: PlanningUserProfile) -> int:
    meals_per_day = len(profile.schedule[0]) if profile.schedule else 1
    return max(1, min(3, meals_per_day))


def _default_usda_provider() -> APIIngredientProvider:
    usda_client = USDAClient.from_env()
    cached_lookup = CachedIngredientLookup(usda_client=usda_client)
    return APIIngredientProvider(cached_lookup)


def _default_llm_client() -> LLMClient:
    llm_settings = load_llm_settings()
    return LLMClient(llm_settings)


def _rebuild_recipe_pool(
    *,
    recipes_path: str,
    provider: IngredientDataProvider,
) -> List[PlanningRecipe]:
    recipe_db = RecipeDB(recipes_path)
    all_recipes = recipe_db.get_all_recipes()
    all_ingredient_names = extract_ingredient_names(all_recipes)
    provider.resolve_all(all_ingredient_names)
    calculator = NutritionCalculator(provider)
    return convert_recipes(all_recipes, calculator)


def _ensure_orchestrator_stats(result: MealPlanResult) -> None:
    if result.stats is None:
        result.stats = {}


def plan_with_llm_feedback(
    profile: PlanningUserProfile,
    recipe_pool: List[PlanningRecipe],
    days: int,
    *,
    max_feedback_retries: int = 3,
    recipes_path: str = "data/recipes/recipes.json",
    client: Optional[LLMClient] = None,
    provider: Optional[IngredientDataProvider] = None,
    recipes_to_generate_per_attempt: Optional[int] = None,
) -> MealPlanResult:
    """Wrap `plan_meals()` with a bounded LLM-driven recipe generation feedback loop.

    Invariant: the planner remains a black-box; we only add recipes between retries.
    """

    # Initial (non-LLM) attempt.
    result: MealPlanResult = plan_meals(profile, recipe_pool, days)
    if result.success:
        return result

    if result.failure_mode not in _ELIGIBLE_FAILURE_MODES:
        return result

    if client is None:
        client = _default_llm_client()
    if provider is None:
        provider = _default_usda_provider()

    assert_usda_capable_provider(provider)

    recipes_to_generate = (
        int(recipes_to_generate_per_attempt)
        if recipes_to_generate_per_attempt is not None
        else _default_recipe_drafts_count(profile)
    )

    history: List[Dict[str, Any]] = []
    generated_fingerprints: Set[str] = set()

    prev_failure_sig = _stable_failure_signature(result)

    for attempt_idx in range(1, max_feedback_retries + 1):
        # Create deterministic prompt context from planner diagnostics.
        feedback_context = build_feedback_context(result, profile)

        drafts: List[RecipeDraft] = suggest_targeted_recipe_drafts(
            client=client,
            context=feedback_context,
            count=recipes_to_generate,
        )

        accepted_wrapped: List[ValidatedRecipeForPersistence] = []
        persisted_ids: List[str] = []
        accepted_count = 0
        validation_error: Optional[str] = None

        try:
            accepted_wrapped, _failures = validate_recipe_drafts(drafts, provider)
        except Exception:
            validation_error = "LLM_RECIPE_VALIDATION_RAISED"
            accepted_wrapped = []

        accepted_count = len(accepted_wrapped)
        if accepted_count:
            # Maintain our own fingerprint-set for loop progress detection.
            newly_accepted_fps: Set[str] = set()
            accepted_recipes = [w.recipe for w in accepted_wrapped]
            for r in accepted_recipes:
                newly_accepted_fps.add(compute_recipe_fingerprint(r))
            generated_fingerprints.update(newly_accepted_fps)

            persisted_ids = append_validated_recipes(
                path=recipes_path,
                recipes=accepted_wrapped,
            )

        history.append(
            {
                "attempt": attempt_idx,
                "status": "fail",
                "failure_type": result.failure_mode,
                "recipes_generated": len(drafts),
                "accepted": accepted_count,
                "persisted_ids": list(persisted_ids),
                "validation_error": validation_error,
            }
        )

        # Spec requirement: rebuild pool each iteration before the next planner call.
        result_recipe_pool = _rebuild_recipe_pool(
            recipes_path=recipes_path,
            provider=provider,
        )

        # Retry planner with the updated recipe pool.
        result = plan_meals(profile, result_recipe_pool, days)
        if result.success:
            _ensure_orchestrator_stats(result)
            stats = copy.deepcopy(result.stats) if result.stats else {}
            stats["llm_feedback_attempts"] = history
            result.stats = stats
            result.report = copy.deepcopy(result.report or {})
            result.report["llm_feedback"] = {"max_feedback_retries": max_feedback_retries}
            return result

        if result.failure_mode not in _ELIGIBLE_FAILURE_MODES:
            _ensure_orchestrator_stats(result)
            stats = copy.deepcopy(result.stats) if result.stats else {}
            stats["llm_feedback_attempts"] = history
            result.stats = stats
            result.report = copy.deepcopy(result.report or {})
            result.report["llm_feedback"] = {"max_feedback_retries": max_feedback_retries}
            return result

        curr_failure_sig = _stable_failure_signature(result)

        # Abort if planner is stuck on the same failure signature AND we didn't
        # append any new recipes.
        if curr_failure_sig == prev_failure_sig:
            # If append_validated_recipes returned nothing, treat as no progress.
            if not persisted_ids:
                # Mark the last feedback attempt as aborted (avoid double-logging).
                if history:
                    history[-1]["status"] = "abort"
                _ensure_orchestrator_stats(result)
                stats = copy.deepcopy(result.stats) if result.stats else {}
                stats["llm_feedback_attempts"] = history
                result.stats = stats
                result.report = copy.deepcopy(result.report or {})
                result.report["llm_feedback"] = {"max_feedback_retries": max_feedback_retries}
                return result

        prev_failure_sig = curr_failure_sig

    _ensure_orchestrator_stats(result)
    stats = copy.deepcopy(result.stats) if result.stats else {}
    stats["llm_feedback_attempts"] = history
    result.stats = stats
    result.report = copy.deepcopy(result.report or {})
    result.report["llm_feedback"] = {"max_feedback_retries": max_feedback_retries}
    return result

