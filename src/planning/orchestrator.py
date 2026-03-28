from __future__ import annotations

import copy
import hashlib
import os
import json
import sys
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
from src.llm.feedback_cache import (
    DEFAULT_FEEDBACK_CACHE_PATH,
    DEFAULT_CACHE_SCHEMA_VERSION,
    FeedbackCache,
    DeterministicCacheMissError,
    build_feedback_cache_key,
    get_cached_drafts,
    load_feedback_cache,
    upsert_cached_drafts,
)


class LLMFeedbackOrchestratorError(RuntimeError):
    """Raised when the LLM feedback loop cannot safely proceed."""

    def __init__(self, *, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class LLMPlanningModeError(RuntimeError):
    """Raised when an API requests an LLM-assisted mode while LLM is disabled."""

    def __init__(self, *, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code



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


def _parse_bool_env(value: Optional[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    cleaned = value.strip().lower()
    if cleaned in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if cleaned in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


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


def _append_new_recipes_to_pool(
    *,
    recipes_path: str,
    provider: IngredientDataProvider,
    current_pool: List[PlanningRecipe],
    persisted_ids: List[str],
) -> List[PlanningRecipe]:
    """Incrementally expand `current_pool` with newly persisted recipes."""
    if not persisted_ids:
        return current_pool

    recipe_db = RecipeDB(recipes_path)
    new_recipes: List[Any] = []
    for rid in persisted_ids:
        r = recipe_db.get_recipe_by_id(rid)
        if r is not None:
            new_recipes.append(r)

    if not new_recipes:
        return current_pool

    ingredient_names = extract_ingredient_names(new_recipes)
    provider.resolve_all(ingredient_names)
    calculator = NutritionCalculator(provider)
    new_pool = convert_recipes(new_recipes, calculator)

    merged = list(current_pool) + list(new_pool)
    merged.sort(key=lambda r: r.id)
    return merged


def _ensure_orchestrator_stats(result: MealPlanResult) -> None:
    if result.stats is None:
        result.stats = {}


def _normalize_instruction_text(s: str) -> str:
    # Deterministic normalization: casefold + whitespace collapse.
    parts = str(s).strip().lower().split()
    return " ".join(parts)


def _draft_fingerprint(draft: RecipeDraft) -> str:
    """Fingerprint a RecipeDraft by measurable ingredients + instruction text.

    Mirrors `compute_recipe_fingerprint()` but operates on LLM `RecipeDraft`s.
    """
    normalized: List[Dict[str, Any]] = []
    for ing in draft.ingredients:
        unit_norm = str(ing.unit).strip().lower()
        if unit_norm == "to taste":
            continue
        qty = round(float(ing.quantity), 6)
        normalized.append(
            {
                "name": str(ing.name).strip().lower(),
                "quantity": qty,
                "unit": unit_norm,
            }
        )

    normalized.sort(key=lambda d: (d["name"], d["unit"], d["quantity"]))

    normalized_instructions: List[str] = [
        _normalize_instruction_text(i) for i in (draft.instructions or [])
    ]
    instr_json = json.dumps(
        {"instructions": normalized_instructions},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    instructions_sha256 = hashlib.sha256(instr_json.encode("utf-8")).hexdigest()

    payload = {
        "ingredients": normalized,
        "instructions_sha256": instructions_sha256,
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


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
    deterministic_strict_override: Optional[bool] = None,
    use_feedback_cache: bool = True,
    force_live_generation: bool = False,
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

    deterministic_strict = (
        _parse_bool_env(os.getenv("LLM_DETERMINISTIC_STRICT"), default=False)
        if deterministic_strict_override is None
        else bool(deterministic_strict_override)
    )
    feedback_cache_path = os.getenv(
        "LLM_FEEDBACK_CACHE_PATH", DEFAULT_FEEDBACK_CACHE_PATH
    )
    cache_schema_version = int(
        os.getenv(
            "LLM_FEEDBACK_CACHE_SCHEMA_VERSION",
            str(DEFAULT_CACHE_SCHEMA_VERSION),
        )
    )
    cache_enabled = use_feedback_cache and not force_live_generation
    if cache_enabled:
        feedback_cache = load_feedback_cache(
            feedback_cache_path,
            cache_schema_version=cache_schema_version,
        )
    else:
        # Avoid disk reads/writes and ensure cache-miss behavior is explicit.
        feedback_cache = FeedbackCache(
            path=feedback_cache_path,
            cache_schema_version=cache_schema_version,
            entries_by_key={},
        )

    # Use the configured LLM model as part of the cache key.
    model_version = ""
    try:
        settings = getattr(client, "_settings", None)
        if settings is not None and getattr(settings, "model", None):
            model_version = str(settings.model)
    except Exception:
        model_version = ""
    if not model_version:
        model_version = os.getenv("LLM_MODEL", "")

    result_recipe_pool = recipe_pool

    for attempt_idx in range(1, max_feedback_retries + 1):
        # Create deterministic prompt context from planner diagnostics.
        curr_failure_sig = _stable_failure_signature(result)
        feedback_context = build_feedback_context(result, profile)

        cache_key = build_feedback_cache_key(
            failure_signature=curr_failure_sig,
            feedback_context=feedback_context,
            recipes_to_generate=recipes_to_generate,
            model_version=model_version,
            cache_schema_version=cache_schema_version,
        )

        cached_drafts = (
            get_cached_drafts(feedback_cache, cache_key) if cache_enabled else None
        )
        if cached_drafts is not None:
            drafts = cached_drafts
        else:
            if deterministic_strict and cache_enabled:
                history.append(
                    {
                        "attempt": attempt_idx,
                        "status": "deterministic_cache_miss_abort",
                        "failure_type": result.failure_mode,
                        "recipes_generated": recipes_to_generate,
                        "accepted": 0,
                        "persisted_ids": [],
                        "validation_error": "DETERMINISTIC_CACHE_MISS",
                    }
                )
                raise DeterministicCacheMissError(
                    f"DETERMINISTIC_CACHE_MISS: cache miss for key={cache_key}"
                )

            drafts = suggest_targeted_recipe_drafts(
                client=client,
                context=feedback_context,
                count=recipes_to_generate,
            )

            canonical_payload = [d.model_dump() for d in drafts]
            # Keep in-memory cache warm for additional retries in this call.
            if cache_enabled and feedback_cache.entries_by_key is not None:
                feedback_cache.entries_by_key[cache_key] = canonical_payload

            if cache_enabled:
                upsert_cached_drafts(
                    cache_path=feedback_cache_path,
                    cache_schema_version=cache_schema_version,
                    cache_key=cache_key,
                    drafts=drafts,
                )

        # Pre-validation dedupe: remove drafts already present in the accepted
        # fingerprint set, and de-dupe within this attempt too.
        local_seen: Set[str] = set()
        duplicate_only = False
        filtered_drafts: List[RecipeDraft] = []
        for d in drafts:
            fp = _draft_fingerprint(d)
            if fp in generated_fingerprints or fp in local_seen:
                duplicate_only = True
                continue
            local_seen.add(fp)
            filtered_drafts.append(d)

        if filtered_drafts:
            drafts = filtered_drafts
        else:
            drafts = []

        duplicate_only = duplicate_only and len(drafts) == 0

        accepted_wrapped: List[ValidatedRecipeForPersistence] = []
        persisted_ids: List[str] = []
        accepted_count = 0

        try:
            accepted_wrapped, _failures = validate_recipe_drafts(drafts, provider)
        except Exception as exc:
            history.append(
                {
                    "attempt": attempt_idx,
                    "status": "error",
                    "error_code": "VALIDATION_EXCEPTION",
                    "failure_type": result.failure_mode,
                    "recipes_generated": len(drafts),
                    "accepted": 0,
                    "persisted_ids": [],
                    "validation_error": "LLM_RECIPE_VALIDATION_RAISED",
                }
            )
            raise LLMFeedbackOrchestratorError(
                error_code="VALIDATION_EXCEPTION",
                message="LLM recipe validation raised an unexpected error.",
            ) from exc

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
                "status": "duplicate_only" if duplicate_only else "fail",
                "failure_type": result.failure_mode,
                "recipes_generated": len(drafts),
                "accepted": accepted_count,
                "persisted_ids": list(persisted_ids),
                "validation_error": None,
            }
        )

        # Incremental expansion when we actually persisted new recipes; otherwise
        # avoid full rebuild since the recipe pool is unchanged.
        if persisted_ids:
            try:
                result_recipe_pool = _append_new_recipes_to_pool(
                    recipes_path=recipes_path,
                    provider=provider,
                    current_pool=result_recipe_pool,
                    persisted_ids=persisted_ids,
                )
            except Exception:
                # Safety fallback: full rebuild if incremental update fails.
                # Observability: emit structured signal without changing behavior.
                print(
                    json.dumps(
                        {
                            "fallback_triggered": True,
                            "reason": "incremental_update_failed",
                        },
                        sort_keys=True,
                        ensure_ascii=True,
                    ),
                    file=sys.stderr,
                )
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

