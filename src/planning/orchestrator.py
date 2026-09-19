from __future__ import annotations

import json
import copy
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.config.llm_settings import load_llm_settings
from src.data_layer.meal_prep import MealPrepBatchRepository
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.user_profile import load_profile_pins
from src.llm.client import LLMClient
from src.llm.planner_assistant import build_feedback_context, suggest_targeted_recipe_drafts
from src.llm.recipe_validator import validate_recipe_drafts
from src.llm.repository import append_validated_recipes, compute_recipe_fingerprint
from src.llm.usda_contract import assert_usda_capable_provider
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.ingestion.usda_client import USDAClient
from src.llm.types import ValidatedRecipeForPersistence
from src.nutrition.calculator import NutritionCalculator
from src.data_layer.models import ProfilePin
from src.planning.phase0_models import PlanningBatchLock, PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult
from src.planning.converters import convert_recipes, extract_ingredient_names
from src.planning.planner import plan_meals
from src.providers.api_provider import APIIngredientProvider
from src.providers.ingredient_provider import IngredientDataProvider
from src.llm.schemas import RecipeDraft
from src.llm.recovery_types import AttemptRecord, GapSpec, RecoveryOutcome, RecoveryState, UnrecoverableReason
from src.llm.recovery_diagnosis import diagnose, feasibility_signal, improved
from src.llm.repository import generate_deterministic_recipe_id
from src.llm.recipe_generator import RecipeGenerationError
from src.llm.client import LLMClientError
from src.providers.api_provider import IngredientResolutionError
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


def _serialize_active_batches(batches: List[Any]) -> List[Dict[str, Any]]:
    """Serialize repository batch entities to a stable plan-request shape."""
    rows: List[Dict[str, Any]] = []
    for batch in sorted(batches, key=lambda item: str(getattr(item, "id", ""))):
        assignments_raw = list(getattr(batch, "assignments", []) or [])
        assignments = []
        for item in sorted(
            assignments_raw,
            key=lambda a: (
                int(getattr(a, "day_index", 0)),
                int(getattr(a, "slot_index", 0)),
                float(getattr(a, "servings", 1.0)),
            ),
        ):
            assignments.append(
                {
                    "day_index": int(getattr(item, "day_index")),
                    "slot_index": int(getattr(item, "slot_index")),
                    "servings": float(getattr(item, "servings", 1.0)),
                }
            )
        rows.append(
            {
                "id": str(getattr(batch, "id")),
                "recipe_id": str(getattr(batch, "recipe_id")),
                "total_servings": int(getattr(batch, "total_servings")),
                "cook_date": str(getattr(batch, "cook_date")),
                "status": str(getattr(batch, "status")),
                "assignments": assignments,
            }
        )
    return rows


def _serialize_persisted_pins(pins: List[ProfilePin]) -> List[Dict[str, Any]]:
    """Serialize persisted profile pins to a stable diagnostic shape."""
    rows: List[Dict[str, Any]] = []
    for pin in sorted(
        pins,
        key=lambda item: (int(item.day_index), int(item.slot_index), str(item.recipe_id)),
    ):
        rows.append(
            {
                "day_index": int(pin.day_index),
                "slot_index": int(pin.slot_index),
                "recipe_id": str(pin.recipe_id),
            }
        )
    return rows


@dataclass(frozen=True)
class ParityPlanContext:
    """Canonical parity-critical planner context hydrated from backend state."""

    active_batches: List[Any]
    persisted_pins: List[ProfilePin]
    seed: Optional[int]
    batch_locks: List[PlanningBatchLock]


def hydrate_parity_plan_context(
    *,
    seed: Optional[int] = None,
    yaml_path: str | Path | None = None,
) -> ParityPlanContext:
    """Load active batches and persisted pins from canonical backend state."""
    active_batches = MealPrepBatchRepository().list_active()
    persisted_pins = load_profile_pins(yaml_path=yaml_path)
    explicit_seed = int(seed) if seed is not None else None
    return ParityPlanContext(
        active_batches=list(active_batches),
        persisted_pins=list(persisted_pins),
        seed=explicit_seed,
        batch_locks=planning_batch_locks_from_batches(active_batches),
    )


def parity_diagnostics_payload(context: ParityPlanContext) -> Dict[str, Any]:
    """Build parity-critical diagnostic fields for CLI/export artifacts."""
    return {
        "active_batches": _serialize_active_batches(context.active_batches),
        "persisted_pins": _serialize_persisted_pins(context.persisted_pins),
        "seed": context.seed,
    }


def apply_persisted_pins_to_profile(user_profile: Any, persisted_pins: List[ProfilePin]) -> None:
    """Ensure ``UserProfile.pins`` reflects canonical persisted pin state."""
    user_profile.pins = list(persisted_pins)


def build_plan_request_from_profile(
    profile: Any,
    recipes: List[Any],
    batches: List[Any],
    seed: Optional[int],
) -> Dict[str, Any]:
    """Build a PlanRequest-compatible payload from canonical local/server inputs."""
    payload: Dict[str, Any] = {
        "daily_calories": int(profile.daily_calories),
        "daily_protein_g": float(profile.daily_protein_g),
        "daily_fat_g_min": float(profile.daily_fat_g[0]),
        "daily_fat_g_max": float(profile.daily_fat_g[1]),
        "schedule": dict(profile.schedule),
        "liked_foods": list(profile.liked_foods),
        "disliked_foods": list(profile.disliked_foods),
        "allergies": list(profile.allergies),
        "micronutrient_weekly_min_fraction": float(
            profile.micronutrient_weekly_min_fraction
        ),
        "recipe_ids": sorted(
            [str(getattr(recipe, "id")) for recipe in recipes if getattr(recipe, "id", None)]
        ),
        "active_batches": _serialize_active_batches(batches),
    }
    if getattr(profile, "daily_micronutrient_targets", None):
        payload["micronutrient_goals"] = dict(profile.daily_micronutrient_targets)
    if seed is not None:
        payload["seed"] = int(seed)
    return payload


def planning_batch_locks_from_batches(batches: List[Any]) -> List[PlanningBatchLock]:
    """Build planner batch locks from repository batches."""
    locks: List[PlanningBatchLock] = []
    for batch in _serialize_active_batches(batches):
        for assignment in batch["assignments"]:
            locks.append(
                PlanningBatchLock(
                    batch_id=str(batch["id"]),
                    recipe_id=str(batch["recipe_id"]),
                    day_index=int(assignment["day_index"]),
                    slot_index=int(assignment["slot_index"]),
                    servings=float(assignment.get("servings", 1.0)),
                )
            )
    return locks


def build_planned_meal_metadata_index(
    active_batches: List[Any],
    persisted_pins: List[ProfilePin],
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Index slot addresses to batch vs pin provenance for API meal metadata.

    Batch assignments take precedence over pins on the same slot (mirrors
    ``_merge_batch_locks_into_pins``). Keys use ``(day_index, slot_index)``
    matching :class:`Assignment` and persisted pins.
    """
    index: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for batch in sorted(active_batches, key=lambda b: str(getattr(b, "id", ""))):
        rid = str(getattr(batch, "recipe_id", ""))
        bid = str(getattr(batch, "id", ""))
        for item in getattr(batch, "assignments", []) or []:
            day_i = int(getattr(item, "day_index", 0))
            slot_i = int(getattr(item, "slot_index", 0))
            index[(day_i, slot_i)] = {
                "kind": "batch",
                "recipe_id": rid,
                "batch_id": bid,
                "servings": float(getattr(item, "servings", 1.0)),
            }
    for pin in persisted_pins:
        key = (int(pin.day_index), int(pin.slot_index))
        if key not in index:
            index[key] = {
                "kind": "pin",
                "recipe_id": str(pin.recipe_id),
            }
    return index


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


def _attach_outcome(
    result: MealPlanResult,
    outcome: RecoveryOutcome,
    history: List[Dict[str, Any]],
    max_feedback_retries: int,
) -> MealPlanResult:
    """Attach the typed recovery outcome to the planner result (report + stats)."""
    _ensure_orchestrator_stats(result)
    stats = copy.deepcopy(result.stats) if result.stats else {}
    stats["llm_feedback_attempts"] = history
    result.stats = stats
    result.report = copy.deepcopy(result.report or {})
    result.report["llm_feedback"] = {"max_feedback_retries": max_feedback_retries}
    outcome.max_attempts = max_feedback_retries
    result.report["llm_recovery"] = outcome.to_dict()
    return result


_DATA_SOURCE_ERROR_TYPES: Tuple[type, ...] = (
    RecipeGenerationError,
    LLMClientError,
    IngredientResolutionError,
)


def _classify_exception(exc: BaseException) -> Tuple[RecoveryState, Dict[str, str]]:
    """Map an exception raised inside the loop to a typed terminal state."""
    code = str(getattr(exc, "error_code", "") or type(exc).__name__)
    info = {"type": type(exc).__name__, "code": code, "message": str(exc)[:300]}
    if isinstance(exc, _DATA_SOURCE_ERROR_TYPES):
        return RecoveryState.DATA_SOURCE_FAILURE, info
    return RecoveryState.SYSTEM_ERROR, info


def _known_ingredient_vocabulary(provider: Any, limit: int = 160) -> List[str]:
    """Names the resolver is known to handle (from the on-disk USDA cache), for the LLM prompt."""
    try:
        cache_dir = provider._lookup.cache.cache_dir  # APIIngredientProvider -> CachedIngredientLookup -> IngredientCache
    except Exception:
        return []
    names: List[str] = []
    try:
        for f in sorted(Path(cache_dir).glob("*.json")):
            try:
                names.append(str(json.load(open(f)).get("canonical_name", "")).strip())
            except Exception:
                continue
            if len(names) >= limit:
                break
    except Exception:
        return []
    return sorted({n for n in names if n})


def _candidate_planning_recipe(recipe: Any, provider: IngredientDataProvider) -> PlanningRecipe:
    """Convert an accepted (validated) recipe into an in-memory planning candidate.

    Deterministic tags only: the effort/time bucket derived from the cook time. No LLM tags.
    """
    calculator = NutritionCalculator(provider)
    planning = convert_recipes([recipe], calculator)[0]
    tags: Set[str] = set()
    try:
        from src.llm.time_bucket import time_bucket

        tags.add(time_bucket(int(recipe.cooking_time_minutes)))
    except Exception:
        tags = set()
    planning.canonical_tag_slugs = set(tags)
    planning.hard_eligible_tag_slugs = set(tags)  # system-derived, hard-eligible by contract
    return planning


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
    """Deterministic planner first; bounded, diagnosed, validated LLM recovery second.

    Control loop (see evaluation/llm_overhaul/LLM_OVERHAUL_PLAN.md):
      plan -> diagnose (deterministic; may refuse) -> GapSpec -> drafts (LLM or cache)
      -> semantic validation against the GapSpec -> in-memory candidate pool
      -> feasibility signal -> plan again -> typed outcome.
    Invariants:
    - the LLM is called only with a GapSpec, never with a bare failure code;
    - nothing is persisted unless the retried plan succeeds; then only the recipes the plan
      uses are written, with provenance;
    - the deterministic planner result is never replaced by an LLM-layer exception;
    - the request's pool is never rebuilt from disk.
    ``DeterministicCacheMissError`` still escapes in ``assisted_cached`` mode (caller contract).
    """

    result: MealPlanResult = plan_meals(profile, recipe_pool, days)
    if result.success:
        return _attach_outcome(
            result, RecoveryOutcome(state=RecoveryState.NOT_ATTEMPTED, reason="planner_succeeded"), [], max_feedback_retries
        )
    initial_result = result

    if result.failure_mode not in _ELIGIBLE_FAILURE_MODES:
        return _attach_outcome(
            result,
            RecoveryOutcome(
                state=RecoveryState.UNRECOVERABLE_INFEASIBILITY,
                reason="failure_mode_not_recoverable",
                unrecoverable={"code": "PIN_OR_BATCH_OR_TAG_CONFLICT", "message": f"{result.failure_mode} cannot be fixed by adding recipes.", "details": {}},
            ),
            [],
            max_feedback_retries,
        )

    if client is None:
        client = _default_llm_client()
    if provider is None:
        provider = _default_usda_provider()
    assert_usda_capable_provider(provider)

    # --- Deterministic diagnosis: decide whether recipes can help, and what they must satisfy.
    diagnosis = diagnose(result, profile, recipe_pool, days, known_ingredient_vocabulary=_known_ingredient_vocabulary(provider))
    if isinstance(diagnosis, UnrecoverableReason):
        return _attach_outcome(
            result,
            RecoveryOutcome(state=RecoveryState.UNRECOVERABLE_INFEASIBILITY, reason=diagnosis.code, unrecoverable=diagnosis.to_dict()),
            [],
            max_feedback_retries,
        )
    gap: GapSpec = diagnosis

    recipes_to_generate = (
        int(recipes_to_generate_per_attempt)
        if recipes_to_generate_per_attempt is not None
        else _default_recipe_drafts_count(profile)
    )

    history: List[Dict[str, Any]] = []
    outcome = RecoveryOutcome(state=RecoveryState.RECOVERY_LIMIT_REACHED, reason="attempts_exhausted", gap_spec=gap.to_dict())
    generated_fingerprints: Set[str] = set()
    candidate_pool: List[PlanningRecipe] = list(recipe_pool)
    candidates_by_id: Dict[str, ValidatedRecipeForPersistence] = {}
    previous_rejections: List[Dict[str, str]] = []
    any_accepted = False

    deterministic_strict = (
        _parse_bool_env(os.getenv("LLM_DETERMINISTIC_STRICT"), default=False)
        if deterministic_strict_override is None
        else bool(deterministic_strict_override)
    )
    feedback_cache_path = os.getenv("LLM_FEEDBACK_CACHE_PATH", DEFAULT_FEEDBACK_CACHE_PATH)
    cache_schema_version = int(os.getenv("LLM_FEEDBACK_CACHE_SCHEMA_VERSION", str(DEFAULT_CACHE_SCHEMA_VERSION)))
    cache_enabled = use_feedback_cache and not force_live_generation
    if cache_enabled:
        feedback_cache = load_feedback_cache(feedback_cache_path, cache_schema_version=cache_schema_version)
    else:
        feedback_cache = FeedbackCache(path=feedback_cache_path, cache_schema_version=cache_schema_version, entries_by_key={})

    model_version = ""
    try:
        settings = getattr(client, "_settings", None)
        if settings is not None and getattr(settings, "model", None):
            model_version = str(settings.model)
    except Exception:
        model_version = ""
    if not model_version:
        model_version = os.getenv("LLM_MODEL", "")

    signal_before = feasibility_signal(profile, candidate_pool, gap, days)

    for attempt_idx in range(1, max_feedback_retries + 1):
        # The LLM sees the GapSpec (what to satisfy) plus what was rejected so far and why.
        feedback_context: Dict[str, Any] = gap.to_dict()
        feedback_context["attempt"] = attempt_idx
        if previous_rejections:
            feedback_context["previous_attempt_rejections"] = previous_rejections[-12:]
        failure_sig = _stable_failure_signature(result)
        cache_key = build_feedback_cache_key(
            failure_signature=failure_sig,
            feedback_context=feedback_context,
            recipes_to_generate=recipes_to_generate,
            model_version=model_version,
            cache_schema_version=cache_schema_version,
        )

        cached_drafts = get_cached_drafts(feedback_cache, cache_key) if cache_enabled else None
        llm_called = False
        if cached_drafts is not None:
            drafts = cached_drafts
        else:
            if deterministic_strict and cache_enabled:
                history.append({"attempt": attempt_idx, "status": "deterministic_cache_miss_abort", "failure_type": result.failure_mode,
                                "recipes_generated": recipes_to_generate, "accepted": 0, "persisted_ids": [], "validation_error": "DETERMINISTIC_CACHE_MISS"})
                raise DeterministicCacheMissError(f"DETERMINISTIC_CACHE_MISS: cache miss for key={cache_key}")
            try:
                drafts = suggest_targeted_recipe_drafts(client=client, context=feedback_context, count=recipes_to_generate)
            except Exception as exc:
                state, info = _classify_exception(exc)
                outcome.llm_calls += 1
                history.append({"attempt": attempt_idx, "status": "error", "error_code": info["code"], "failure_type": result.failure_mode,
                                "recipes_generated": 0, "accepted": 0, "persisted_ids": [], "validation_error": info["code"]})
                outcome.state, outcome.reason, outcome.error, outcome.attempts = state, "draft_generation_failed", info, list(history)
                return _attach_outcome(result, outcome, history, max_feedback_retries)
            llm_called = True
            outcome.llm_calls += 1
            if cache_enabled and feedback_cache.entries_by_key is not None:
                feedback_cache.entries_by_key[cache_key] = [d.model_dump() for d in drafts]
            if cache_enabled:
                upsert_cached_drafts(cache_path=feedback_cache_path, cache_schema_version=cache_schema_version, cache_key=cache_key, drafts=drafts)

        drafts_received = len(drafts)
        local_seen: Set[str] = set()
        filtered: List[RecipeDraft] = []
        for d in drafts:
            fp = _draft_fingerprint(d)
            if fp in generated_fingerprints or fp in local_seen:
                continue
            local_seen.add(fp)
            filtered.append(d)
        drafts = filtered

        try:
            accepted_wrapped, failures = validate_recipe_drafts(
                drafts, provider, gap_spec=gap, existing_recipes=candidate_pool, source="llm_feedback"
            )
        except Exception as exc:
            state, info = _classify_exception(exc)
            history.append({"attempt": attempt_idx, "status": "error", "error_code": "VALIDATION_EXCEPTION", "failure_type": result.failure_mode,
                            "recipes_generated": len(drafts), "accepted": 0, "persisted_ids": [], "validation_error": "LLM_RECIPE_VALIDATION_RAISED"})
            outcome.state, outcome.reason, outcome.error, outcome.attempts = state, "draft_validation_failed", info, list(history)
            return _attach_outcome(result, outcome, history, max_feedback_retries)

        rejected = [{"code": f.error_code, "message": f.message} for f in failures]
        previous_rejections.extend({"name": d.name, **r} for d, r in zip([x for x in drafts if x.name not in {w.recipe.name for w in accepted_wrapped}], rejected))

        new_candidate_ids: List[str] = []
        for w in accepted_wrapped:
            recipe = w.recipe
            fp = compute_recipe_fingerprint(recipe)
            generated_fingerprints.add(fp)
            recipe.id = generate_deterministic_recipe_id(recipe, set(candidates_by_id) | {r.id for r in candidate_pool})
            recipe.provenance = dict(recipe.provenance or {})
            recipe.provenance.update({"source": "llm_feedback", "gap_kind": gap.kind, "attempt": attempt_idx, "model": model_version or None})
            try:
                candidate_pool.append(_candidate_planning_recipe(recipe, provider))
            except Exception as exc:
                state, info = _classify_exception(exc)
                history.append({"attempt": attempt_idx, "status": "error", "error_code": "POOL_UPDATE_FAILED", "failure_type": result.failure_mode,
                                "recipes_generated": len(drafts), "accepted": len(accepted_wrapped), "persisted_ids": [], "validation_error": "POOL_UPDATE_FAILED"})
                outcome.state, outcome.reason, outcome.error, outcome.attempts = state, "pool_update_failed", info, list(history)
                return _attach_outcome(result, outcome, history, max_feedback_retries)
            candidates_by_id[recipe.id] = w
            new_candidate_ids.append(recipe.id)
        accepted_count = len(new_candidate_ids)
        any_accepted = any_accepted or accepted_count > 0

        signal_after = feasibility_signal(profile, candidate_pool, gap, days)
        did_improve = improved(signal_before, signal_after, gap)

        record = {
            "attempt": attempt_idx, "status": "fail", "failure_type": result.failure_mode,
            "recipes_generated": len(drafts), "accepted": accepted_count, "persisted_ids": [], "validation_error": None,
            "llm_called": llm_called, "drafts_received": drafts_received, "rejected": rejected,
            "candidate_ids": list(new_candidate_ids), "signal_before": signal_before, "signal_after": signal_after, "improved": did_improve,
        }
        history.append(record)

        if accepted_count == 0:
            # Nothing new to plan over; the next attempt sees the rejection reasons.
            continue

        result = plan_meals(profile, candidate_pool, days)
        outcome.planner_runs += 1
        record["planner_code_after"] = "OK" if result.success else result.failure_mode

        if result.success:
            used_ids = {a.recipe_id for a in (result.plan or [])}
            to_persist = [candidates_by_id[rid] for rid in sorted(used_ids) if rid in candidates_by_id]
            try:
                persisted_ids = append_validated_recipes(path=recipes_path, recipes=to_persist) if to_persist else []
            except Exception as exc:
                state, info = _classify_exception(exc)
                record["status"] = "error"
                outcome.state, outcome.reason, outcome.error, outcome.attempts = RecoveryState.SYSTEM_ERROR, "persist_failed", info, list(history)
                return _attach_outcome(initial_result, outcome, history, max_feedback_retries)
            record["status"] = "success"
            record["persisted_ids"] = list(persisted_ids)
            outcome.persisted_recipe_ids = list(persisted_ids)
            outcome.state, outcome.reason, outcome.attempts = RecoveryState.SUCCESS, "planner_succeeded_after_recovery", list(history)
            return _attach_outcome(result, outcome, history, max_feedback_retries)

        if result.failure_mode not in _ELIGIBLE_FAILURE_MODES:
            outcome.state, outcome.reason, outcome.attempts = RecoveryState.UNRECOVERABLE_INFEASIBILITY, "failure_mode_not_recoverable_after_retry", list(history)
            return _attach_outcome(result, outcome, history, max_feedback_retries)

        if not did_improve:
            record["status"] = "abort"
            outcome.state, outcome.reason, outcome.attempts = RecoveryState.NO_USEFUL_RECOVERY_FOUND, "no_progress_in_gap_dimension", list(history)
            return _attach_outcome(result, outcome, history, max_feedback_retries)
        signal_before = signal_after

    outcome.state = RecoveryState.RECOVERY_LIMIT_REACHED if any_accepted else RecoveryState.INVALID_RECOVERY_OUTPUT
    outcome.reason = "attempts_exhausted" if any_accepted else "no_draft_accepted"
    outcome.attempts = list(history)
    return _attach_outcome(result, outcome, history, max_feedback_retries)
