"""FastAPI server for the Nutrition Agent meal planning pipeline."""

import json
import sys
from typing import Any, Dict, List, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, constr

from src.data_layer.models import UserProfile
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.providers.local_provider import LocalIngredientProvider
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes, convert_profile, extract_ingredient_names
from src.planning.planner import plan_meals
from src.planning.orchestrator import LLMPlanningModeError, plan_with_llm_feedback
from src.output.formatters import format_result_json
from src.ingestion.usda_client import USDAClient
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.providers.api_provider import APIIngredientProvider
from src.config.llm_settings import load_llm_settings
from src.api.error_mapping import map_exception_to_api_error
from src.llm.client import LLMClient
from src.llm.constraint_parser import PlannerConfigParsingError, parse_nl_config
from src.llm.pipeline import generate_validate_persist_recipes
from src.llm.ingredient_matcher import (
    IngredientMatchingError,
    match_ingredient_queries,
    validate_matches,
)
from src.llm.schemas import BudgetLevel, DietaryFlag, PrepTimeBucket, PlannerConfigJson
from src.data_layer.user_profile import user_profile_from_planner_config
from src.llm.tag_filtering_service import apply_tag_filtering
from src.llm.recipe_tagger import tag_recipes
from src.llm.tag_repository import load_recipe_tags
from src.llm.tag_repository import upsert_recipe_tags


recipes_path = "data/recipes/recipes.json"
ingredients_path = "data/ingredients/custom_ingredients.json"
DEFAULT_TAG_PATH = "data/recipes/recipe_tags.json"

app = FastAPI(title="Nutrition Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _request_validation_exception_handler(
    request, exc: RequestValidationError
) -> JSONResponse:
    # Per contract: structured 400 instead of FastAPI's default 422.
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "INVALID_REQUEST", "message": "Invalid request schema."}},
    )


class PlanRequest(BaseModel):
    daily_calories: int
    daily_protein_g: float
    daily_fat_g_min: float
    daily_fat_g_max: float
    schedule: Dict[str, int]
    liked_foods: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    days: int = Field(default=1, ge=1, le=7)
    ingredient_source: str = Field(default="local", pattern="^(local|api)$")
    micronutrient_goals: Optional[Dict[str, float]] = None

    # Optional tag-based recipe pool filtering (deterministic).
    cuisine: Optional[List[str]] = None
    cost_level: Optional[BudgetLevel] = None
    prep_time_bucket: Optional[PrepTimeBucket] = None
    dietary_flags: Optional[List[DietaryFlag]] = None
    recipe_tags_path: Optional[str] = None

    # Planner behavior selection:
    # - `deterministic`: never call the LLM planner feedback loop
    # - `assisted`: use the LLM feedback loop using normal cache behavior
    # - `assisted_cached`: deterministic strict mode on cache miss
    # - `assisted_live`: bypass feedback cache and generate drafts live
    planning_mode: Optional[
        Literal["deterministic", "assisted", "assisted_cached", "assisted_live"]
    ] = None


class PlanFromTextRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    ingredient_source: str = Field(default="local", pattern="^(local|api)$")

    # Optional tag-based recipe pool filtering overrides.
    cuisine: Optional[List[str]] = None
    cost_level: Optional[BudgetLevel] = None
    prep_time_bucket: Optional[PrepTimeBucket] = None
    dietary_flags: Optional[List[DietaryFlag]] = None
    recipe_tags_path: Optional[str] = None

    # Planner behavior selection parity with `/api/plan`.
    planning_mode: Optional[
        Literal["deterministic", "assisted", "assisted_cached", "assisted_live"]
    ] = None


def _normalize_tag_pref_value(value: Any) -> Any:
    """Normalize incoming tag preference values to plain JSON types.

    Keeps tag filtering deterministic and compatible with enum-backed
    Pydantic values.
    """

    if value is None:
        return None

    # Pydantic enums (BudgetLevel/PrepTimeBucket/DietaryFlag) expose `.value`.
    if hasattr(value, "value"):
        try:
            return getattr(value, "value")
        except Exception:
            pass

    return value


def _extract_tag_preferences(obj: Any) -> Dict[str, Any]:
    """Extract tag filter preferences from a request-like object.

    Returns an empty dict when no explicit preferences are provided.
    """

    cuisine = getattr(obj, "cuisine", None)
    cost_level = getattr(obj, "cost_level", None)
    prep_time_bucket = getattr(obj, "prep_time_bucket", None)
    dietary_flags = getattr(obj, "dietary_flags", None)

    # Treat "explicitly requested" as non-empty values only.
    preferences: Dict[str, Any] = {}
    if cuisine is not None:
        # Allow `cuisine` to be either a single string or a list of strings.
        if isinstance(cuisine, list) and cuisine:
            preferences["cuisine"] = [
                _normalize_tag_pref_value(v) for v in cuisine
            ]
        elif isinstance(cuisine, str) and cuisine.strip():
            preferences["cuisine"] = _normalize_tag_pref_value(cuisine)
        elif not isinstance(cuisine, list) and cuisine:
            preferences["cuisine"] = _normalize_tag_pref_value(cuisine)

    cost_level = _normalize_tag_pref_value(cost_level)
    if isinstance(cost_level, str) and cost_level.strip():
        preferences["cost_level"] = cost_level

    prep_time_bucket = _normalize_tag_pref_value(prep_time_bucket)
    if isinstance(prep_time_bucket, str) and prep_time_bucket.strip():
        preferences["prep_time_bucket"] = prep_time_bucket

    if dietary_flags is not None:
        # Allow single value or list of enum-backed values.
        if isinstance(dietary_flags, list) and dietary_flags:
            preferences["dietary_flags"] = [
                _normalize_tag_pref_value(v) for v in dietary_flags
            ]
        elif isinstance(dietary_flags, str) and dietary_flags.strip():
            preferences["dietary_flags"] = [_normalize_tag_pref_value(dietary_flags)]
        elif not isinstance(dietary_flags, list) and dietary_flags:
            preferences["dietary_flags"] = [_normalize_tag_pref_value(dietary_flags)]

    return preferences


def _apply_recipe_tag_filter_pre_convert(
    *,
    recipes: List[Any],
    request_like: Any,
    tag_path: str,
) -> tuple[List[Any], Dict[str, Any]]:
    """Optionally filter recipes deterministically based on strict tag metadata."""

    input_recipe_count = len(recipes)
    if input_recipe_count == 0:
        return (
            recipes,
            {
                "filter_applied": False,
                "input_recipe_count": 0,
                "output_recipe_count": 0,
            },
        )

    preferences = _extract_tag_preferences(request_like)
    filter_applied = bool(preferences)
    tags_by_id = load_recipe_tags(tag_path) if filter_applied else {}

    filtered_recipes = apply_tag_filtering(
        recipes=list(recipes),
        tags_by_id=tags_by_id,
        preferences=preferences,
    )

    log_payload = {
        "filter_applied": filter_applied,
        "input_recipe_count": input_recipe_count,
        "output_recipe_count": len(filtered_recipes),
    }
    return filtered_recipes, log_payload


def _build_user_profile(request: PlanRequest) -> UserProfile:
    daily_fat_g = (request.daily_fat_g_min, request.daily_fat_g_max)
    median_fat_g = (daily_fat_g[0] + daily_fat_g[1]) / 2
    daily_carbs_g = (
        request.daily_calories - request.daily_protein_g * 4 - median_fat_g * 9
    ) / 4

    return UserProfile(
        daily_calories=request.daily_calories,
        daily_protein_g=request.daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        schedule={str(k): int(v) for k, v in request.schedule.items()},
        liked_foods=[str(food) for food in request.liked_foods],
        disliked_foods=[str(food) for food in request.disliked_foods],
        allergies=[str(allergen) for allergen in request.allergies],
        daily_micronutrient_targets=request.micronutrient_goals,
    )


def build_llm_client() -> LLMClient:
    """Factory for LLM client creation (patchable in tests)."""
    llm_settings = load_llm_settings()
    return LLMClient(llm_settings)


def build_usda_provider() -> APIIngredientProvider:
    """Factory for USDA-backed ingredient provider creation (patchable in tests)."""
    usda_client = USDAClient.from_env()
    cached_lookup = CachedIngredientLookup(usda_client=usda_client)
    return APIIngredientProvider(cached_lookup)


class RecipeGenerationRequest(BaseModel):
    context: Dict[str, Any]
    count: int = Field(..., ge=1, le=20)


class RecipeGenerationFailure(BaseModel):
    code: str
    message: str


class RecipeGenerationResponse(BaseModel):
    accepted_count: int
    rejected_count: int
    recipe_ids: List[str]
    failures: List[RecipeGenerationFailure]


class IngredientMatchRequest(BaseModel):
    queries: List[constr(strip_whitespace=True, min_length=1)] = Field(
        ..., min_length=1
    )


class IngredientMatchAcceptedItem(BaseModel):
    original_query: str
    normalized_name: str
    confidence: float


class IngredientMatchRejectedItem(BaseModel):
    code: str
    message: str
    original_query: str


class IngredientMatchResponse(BaseModel):
    accepted: List[IngredientMatchAcceptedItem]
    rejected: List[IngredientMatchRejectedItem]


@app.post("/api/plan")
def plan_meals_endpoint(request: PlanRequest) -> Dict[str, Any]:
    try:
        user_profile = _build_user_profile(request)

        recipe_db = RecipeDB(recipes_path)
        all_recipes = recipe_db.get_all_recipes()

        tag_path = getattr(request, "recipe_tags_path", None) or DEFAULT_TAG_PATH
        all_recipes, filter_log = _apply_recipe_tag_filter_pre_convert(
            recipes=all_recipes,
            request_like=request,
            tag_path=tag_path,
        )
        print(
            json.dumps(filter_log, sort_keys=True, ensure_ascii=True),
            file=sys.stderr,
        )

        if request.ingredient_source == "api":
            usda_client = USDAClient.from_env()
            cached_lookup = CachedIngredientLookup(usda_client=usda_client)
            provider = APIIngredientProvider(cached_lookup)
        else:
            nutrition_db = NutritionDB(ingredients_path)
            provider = LocalIngredientProvider(nutrition_db)

        all_ingredient_names = extract_ingredient_names(all_recipes)
        provider.resolve_all(all_ingredient_names)

        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        recipe_by_id = {r.id: r for r in recipe_pool}
        planning_profile = convert_profile(user_profile, request.days)

        llm_settings = load_llm_settings()
        planning_mode_provided = request.planning_mode is not None
        effective_mode = request.planning_mode
        if effective_mode is None:
            # Backward compatible default:
            # - when LLM is enabled by config => use assisted (cache-enabled) mode
            # - otherwise => deterministic planning
            effective_mode = "assisted" if llm_settings.enabled else "deterministic"

        if effective_mode == "deterministic":
            result = plan_meals(planning_profile, recipe_pool, request.days)
        else:
            if not llm_settings.enabled:
                raise LLMPlanningModeError(
                    error_code="LLM_DISABLED",
                    message=(
                        f"planning_mode={effective_mode!r} requires LLM_ENABLED/LLM_API_KEY."
                    ),
                )

            # Feedback-enabled planning routes through an outer orchestrator.
            llm_client = build_llm_client()
            validation_provider = build_usda_provider()

            # Mode controls cache behavior and strictness on cache miss.
            deterministic_strict_override = None
            use_feedback_cache = True
            force_live_generation = False

            if effective_mode == "assisted":
                deterministic_strict_override = (
                    False if planning_mode_provided else None
                )
                use_feedback_cache = True
                force_live_generation = False
            elif effective_mode == "assisted_cached":
                deterministic_strict_override = True
                use_feedback_cache = True
                force_live_generation = False
            elif effective_mode == "assisted_live":
                deterministic_strict_override = False
                use_feedback_cache = False
                force_live_generation = True

            result = plan_with_llm_feedback(
                planning_profile,
                recipe_pool,
                request.days,
                max_feedback_retries=3,
                recipes_path=recipes_path,
                client=llm_client,
                provider=validation_provider,
                deterministic_strict_override=deterministic_strict_override,
                use_feedback_cache=use_feedback_cache,
                force_live_generation=force_live_generation,
            )

            # Ensure formatter sees any recipes persisted by the feedback loop.
            recipe_db_updated = RecipeDB(recipes_path)
            all_recipes_updated = recipe_db_updated.get_all_recipes()
            ingredient_names_updated = extract_ingredient_names(all_recipes_updated)
            validation_provider.resolve_all(ingredient_names_updated)
            calculator_updated = NutritionCalculator(validation_provider)
            recipe_pool_updated = convert_recipes(all_recipes_updated, calculator_updated)
            recipe_by_id = {r.id: r for r in recipe_pool_updated}

        return format_result_json(result, recipe_by_id, planning_profile, request.days)
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        # Per contract: structured error payload (never raw exception details).
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/plan-from-text")
def plan_from_text_endpoint(request: PlanFromTextRequest) -> Dict[str, Any]:
    try:
        llm_settings = load_llm_settings()
        planning_mode_provided = request.planning_mode is not None
        effective_mode = request.planning_mode
        if effective_mode is None:
            # Backward compatible default:
            # - when LLM is enabled by config => use assisted (cache-enabled) mode
            # - otherwise => deterministic planning
            effective_mode = "assisted" if llm_settings.enabled else "deterministic"

        if effective_mode == "deterministic":
            # Deterministic mode MUST not invoke any LLM logic.
            # Prompt must be explicit PlannerConfigJson-compatible JSON.
            try:
                parsed_prompt = json.loads(request.prompt)
            except json.JSONDecodeError as e:
                raise PlannerConfigParsingError(
                    error_code="INVALID_NL_INPUT",
                    message="deterministic mode requires prompt to be PlannerConfigJson-compatible JSON",
                    details={"json_error": str(e)},
                ) from e

            try:
                cfg = PlannerConfigJson.model_validate(parsed_prompt)
            except Exception as e:
                raise PlannerConfigParsingError(
                    error_code="LLM_SCHEMA_VALIDATION_ERROR",
                    message="deterministic prompt JSON did not match PlannerConfigJson schema",
                    details={"error": str(e)},
                ) from e

            user_profile = user_profile_from_planner_config(cfg)
            days = int(cfg.days)
            # Deterministic mode only allows explicit request fields for recipe-pool filtering;
            # never infer cuisine/cost from the prompt.
            parsed_cost_level = None
            parsed_cuisines = None
        else:
            if not llm_settings.enabled:
                raise LLMPlanningModeError(
                    error_code="LLM_DISABLED",
                    message=(
                        f"planning_mode={effective_mode!r} requires LLM_ENABLED/LLM_API_KEY."
                    ),
                )

            client = build_llm_client()
            cfg = parse_nl_config(client, request.prompt)
            user_profile = user_profile_from_planner_config(cfg)
            days = int(cfg.days)

            # Assisted modes allow baseline cuisine + cost_level inferred from prompt cfg.
            parsed_cost_level = getattr(cfg.preferences, "budget", None)
            parsed_cuisines = getattr(cfg.preferences, "cuisine", None)

        recipe_db = RecipeDB(recipes_path)
        all_recipes = recipe_db.get_all_recipes()

        # Build tag filter preferences:
        # - assisted modes use baseline cuisine + cost_level from prompt cfg
        # - deterministic modes set parsed_cost_level/parsed_cuisines=None, so
        #   only explicit request fields are used for filtering.
        final_cuisines = (
            request.cuisine if request.cuisine is not None else parsed_cuisines
        )
        final_cost_level = (
            request.cost_level if request.cost_level is not None else parsed_cost_level
        )

        tag_path = getattr(request, "recipe_tags_path", None) or DEFAULT_TAG_PATH
        shim = type(
            "_TagPrefShim",
            (),
            {
                "cuisine": final_cuisines,
                "cost_level": final_cost_level,
                "prep_time_bucket": request.prep_time_bucket,
                "dietary_flags": request.dietary_flags,
            },
        )()
        all_recipes, filter_log = _apply_recipe_tag_filter_pre_convert(
            recipes=all_recipes,
            request_like=shim,
            tag_path=tag_path,
        )
        print(
            json.dumps(filter_log, sort_keys=True, ensure_ascii=True),
            file=sys.stderr,
        )

        if request.ingredient_source == "api":
            provider = build_usda_provider()
        else:
            nutrition_db = NutritionDB(ingredients_path)
            provider = LocalIngredientProvider(nutrition_db)

        all_ingredient_names = extract_ingredient_names(all_recipes)
        provider.resolve_all(all_ingredient_names)

        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        recipe_by_id = {r.id: r for r in recipe_pool}
        planning_profile = convert_profile(user_profile, days)

        if effective_mode == "deterministic":
            result = plan_meals(planning_profile, recipe_pool, days)
        else:
            llm_client = build_llm_client()
            validation_provider = build_usda_provider()

            # Mode controls cache behavior and strictness on cache miss.
            deterministic_strict_override = None
            use_feedback_cache = True
            force_live_generation = False

            if effective_mode == "assisted":
                deterministic_strict_override = (
                    False if planning_mode_provided else None
                )
                use_feedback_cache = True
                force_live_generation = False
            elif effective_mode == "assisted_cached":
                deterministic_strict_override = True
                use_feedback_cache = True
                force_live_generation = False
            elif effective_mode == "assisted_live":
                deterministic_strict_override = False
                use_feedback_cache = False
                force_live_generation = True

            result = plan_with_llm_feedback(
                planning_profile,
                recipe_pool,
                days,
                max_feedback_retries=3,
                recipes_path=recipes_path,
                client=llm_client,
                provider=validation_provider,
                deterministic_strict_override=deterministic_strict_override,
                use_feedback_cache=use_feedback_cache,
                force_live_generation=force_live_generation,
            )

            # Ensure formatter sees any recipes persisted by the feedback loop.
            recipe_db_updated = RecipeDB(recipes_path)
            all_recipes_updated = recipe_db_updated.get_all_recipes()
            ingredient_names_updated = extract_ingredient_names(all_recipes_updated)
            validation_provider.resolve_all(ingredient_names_updated)
            calculator_updated = NutritionCalculator(validation_provider)
            recipe_pool_updated = convert_recipes(
                all_recipes_updated, calculator_updated
            )
            recipe_by_id = {r.id: r for r in recipe_pool_updated}

        return format_result_json(result, recipe_by_id, planning_profile, days)
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


class RecipeTagGenerationRequest(BaseModel):
    recipes_path: Optional[str] = None
    recipe_tags_path: Optional[str] = None
    # Explicit opt-in required to avoid implicit LLM usage for tagging.
    llm_enabled: bool = False


class RecipeTagGenerationResponse(BaseModel):
    tagged_recipe_count: int


@app.post("/api/recipes/tags/generate", response_model=RecipeTagGenerationResponse)
def generate_recipe_tags_endpoint(
    request: RecipeTagGenerationRequest,
) -> RecipeTagGenerationResponse:
    try:
        if not request.llm_enabled:
            raise HTTPException(
                status_code=400,
                detail="LLM usage disabled for tagging operation",
            )

        client = build_llm_client()

        recipes_file = getattr(request, "recipes_path", None) or recipes_path
        recipe_db = RecipeDB(recipes_file)
        all_recipes = recipe_db.get_all_recipes()

        tags_by_id = tag_recipes(client, all_recipes)

        tag_path = getattr(request, "recipe_tags_path", None) or DEFAULT_TAG_PATH
        upsert_recipe_tags(tag_path, tags_by_id)

        return RecipeTagGenerationResponse(tagged_recipe_count=len(tags_by_id))
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/recipes/generate-validated", response_model=RecipeGenerationResponse)
def generate_validated_recipes_endpoint(
    request: RecipeGenerationRequest,
) -> RecipeGenerationResponse:
    try:
        client = build_llm_client()
        provider = build_usda_provider()

        summary = generate_validate_persist_recipes(
            context=request.context,
            count=request.count,
            recipes_path=recipes_path,
            provider=provider,
            client=client,
        )

        rejected = summary.get("rejected", [])
        failures: List[RecipeGenerationFailure] = []
        for item in rejected:
            failures.append(
                RecipeGenerationFailure(
                    code=str(item.get("error_code", "VALIDATION_FAILURE")),
                    message=str(item.get("message", "")),
                )
            )

        recipe_ids = summary.get("persisted_ids", [])
        return RecipeGenerationResponse(
            accepted_count=len(recipe_ids),
            rejected_count=len(rejected),
            recipe_ids=list(recipe_ids),
            failures=failures,
        )
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


def _extract_original_query_from_field_errors(
    field_errors: List[str],
) -> str:
    for item in field_errors:
        if item.startswith("original_query="):
            return item.split("=", 1)[1]
    return ""


@app.post("/api/ingredients/match", response_model=IngredientMatchResponse)
def ingredient_match_endpoint(request: IngredientMatchRequest) -> IngredientMatchResponse:
    try:
        client = build_llm_client()
        provider = build_usda_provider()

        matches = match_ingredient_queries(client, request.queries)
        accepted, failures = validate_matches(matches, provider)

        accepted_items: List[IngredientMatchAcceptedItem] = []
        for m in accepted:
            accepted_items.append(
                IngredientMatchAcceptedItem(
                    original_query=m.query,
                    normalized_name=m.normalized_name,
                    confidence=m.confidence,
                )
            )

        rejected_items: List[IngredientMatchRejectedItem] = []
        for f in failures:
            rejected_items.append(
                IngredientMatchRejectedItem(
                    code=f.error_code,
                    message=f.message,
                    original_query=_extract_original_query_from_field_errors(
                        f.field_errors
                    ),
                )
            )

        return IngredientMatchResponse(
            accepted=accepted_items,
            rejected=rejected_items,
        )
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.get("/api/recipes")
def list_recipes() -> List[Dict[str, str]]:
    try:
        recipe_db = RecipeDB(recipes_path)
        return [{"id": r.id, "name": r.name} for r in recipe_db.get_all_recipes()]
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
