"""FastAPI server for the Nutrition Agent meal planning pipeline."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# Load repo-root `.env` when present (same behavior as `src.cli`). Uvicorn does not do this
# automatically, so without this block only the CLI would see LLM_API_KEY / USDA_API_KEY.
_ROOT = Path(__file__).resolve().parent.parent.parent
_env_file = _ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, constr, model_validator
from dataclasses import fields as dc_fields

from src.ingestion.nutrient_mapper import MappedNutrition, NutrientMapper
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.ingestion.usda_client import DataType, USDAClient, USDALookupError

from src.data_layer.models import (
    UserProfile,
    Recipe as DataRecipe,
    Ingredient as DataIngredient,
    MicronutrientProfile,
)
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.providers.local_provider import LocalIngredientProvider
from src.providers.summary_hybrid_provider import SummaryHybridIngredientProvider
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes, convert_profile, extract_ingredient_names
from src.planning.planner import plan_meals
from src.planning.orchestrator import LLMPlanningModeError, plan_with_llm_feedback
from src.output.formatters import format_result_json
from src.providers.api_provider import APIIngredientProvider
from src.config.llm_settings import load_llm_settings
from src.api.error_mapping import map_exception_to_api_error
from src.api.recipe_sync import (
    RecipeSyncItem,
    RecipeSyncRequest,
    RecipeSyncResponse,
    atomic_upsert_recipes_by_id,
)
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
from src.models.legacy_schedule_migration import (
    canonical_day_to_meal_only_legacy_dict,
    legacy_schedule_dict_to_schedule_days,
    merge_schedule_warnings_into_result,
    schedule_days_to_meal_only_legacy_dict,
)
from src.models.schedule import DaySchedule, validate_day_schedule
from src.llm.tag_filtering_service import apply_tag_filtering
from src.llm.recipe_tagger import tag_recipes
from src.llm.tag_repository import load_recipe_tags
from src.llm.tag_repository import upsert_recipe_tags
from src.api.tag_routes import router as tag_router


recipes_path = "data/recipes/recipes.json"
ingredients_path = "data/ingredients/custom_ingredients.json"
DEFAULT_TAG_PATH = "data/recipes/recipe_tags.json"

app = FastAPI(title="Nutrition Agent API")
app.include_router(tag_router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _request_validation_exception_handler(
    request: Request, exc: RequestValidationError
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
    # Canonical per-day schedule (preferred). When set, must have length == ``days``.
    schedule_days: Optional[List[DaySchedule]] = None
    # Deprecated: ``"HH:MM"`` -> busyness (1–4) or 0 for workout time; use ``schedule_days``.
    schedule: Optional[Dict[str, int]] = None
    # Deprecated alias for ``schedule`` (same semantics).
    legacy_schedule: Optional[Dict[str, int]] = None
    liked_foods: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    days: int = Field(default=1, ge=1, le=7)
    ingredient_source: str = Field(default="local", pattern="^(local|api)$")
    micronutrient_goals: Optional[Dict[str, float]] = None
    micronutrient_weekly_min_fraction: float = Field(default=1.0, gt=0.0, le=1.0)

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

    # When set, restrict the in-memory recipe pool to this id subset (Planner parity).
    recipe_ids: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def _merge_legacy_schedule(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("schedule_days") is not None:
            return data
        leg = data.get("legacy_schedule")
        sch = data.get("schedule")
        if leg is not None and sch is not None:
            raise ValueError("Provide only one of schedule and legacy_schedule")
        if leg is not None:
            out = {**data, "schedule": leg}
            out.pop("legacy_schedule", None)
            return out
        return data

    @model_validator(mode="after")
    def _schedule_contract(self) -> "PlanRequest":
        if self.schedule_days is not None:
            if len(self.schedule_days) != self.days:
                raise ValueError(
                    f"schedule_days length ({len(self.schedule_days)}) must equal days ({self.days})"
                )
            for i, d in enumerate(self.schedule_days):
                if d.day_index != i + 1:
                    raise ValueError(
                        f"schedule_days[{i}].day_index must be {i + 1}, got {d.day_index}"
                    )
                validate_day_schedule(d)
            return self
        if self.schedule is None:
            raise ValueError("Provide schedule_days or schedule (legacy)")
        return self


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


def _filter_recipes_by_ids(
    recipes: List[Any],
    recipe_ids: Optional[List[str]],
) -> List[Any]:
    if recipe_ids is None:
        return recipes
    by_id = {getattr(r, "id", None): r for r in recipes}
    out: List[Any] = []
    for rid in recipe_ids:
        r = by_id.get(rid)
        if r is not None:
            out.append(r)
    return out


def _mapped_nutrition_to_resolve_payload(
    *,
    source: Literal["usda", "local"],
    fdc_id: Optional[int],
    name: str,
    description: Optional[str],
    nutrition: MappedNutrition,
) -> Dict[str, Any]:
    micro = nutrition.micronutrients
    micronutrients: Dict[str, float] = {}
    for f in dc_fields(micro):
        val = float(getattr(micro, f.name))
        if val != 0.0:
            micronutrients[f.name] = val
    per_100g: Dict[str, float] = {
        "calories": float(nutrition.calories),
        "protein_g": float(nutrition.protein_g),
        "fat_g": float(nutrition.fat_g),
        "carbs_g": float(nutrition.carbs_g),
    }
    return {
        "source": source,
        "fdc_id": str(fdc_id) if fdc_id is not None else None,
        "name": name,
        "description": description,
        "per_100g": per_100g,
        "micronutrients": micronutrients,
        "nutrition_by_unit": None,
    }


def _flutter_ingredient_entries(
    recipe: DataRecipe,
    calculator: NutritionCalculator,
) -> List[Dict[str, Any]]:
    """Map data-layer recipe lines to Flutter `RecipeIngredientEntry` JSON."""
    out: List[Dict[str, Any]] = []
    for idx, ing in enumerate(recipe.ingredients):
        iid = f"{recipe.id}:line:{idx}"
        if ing.is_to_taste:
            out.append(
                {
                    "ingredient_id": iid,
                    "ingredient_name": ing.name,
                    "quantity": float(ing.quantity),
                    "unit": ing.unit,
                    "calories_per_100g": 0.0,
                    "protein_per_100g": 0.0,
                    "carbs_per_100g": 0.0,
                    "fat_per_100g": 0.0,
                    "micronutrients_per_100g": {},
                    "unit_conversions": {},
                }
            )
            continue
        try:
            prof = calculator.calculate_ingredient_nutrition(ing)
            grams = calculator._convert_quantity_to_grams(ing)  # noqa: SLF001
            if grams <= 0:
                raise ValueError("nonpositive grams")
            factor = 100.0 / grams
            micro_per_100g: Dict[str, float] = {}
            if prof.micronutrients is not None:
                for field in NutritionCalculator.MICRONUTRIENT_FIELDS:
                    total = float(getattr(prof.micronutrients, field, 0.0))
                    scaled = total * factor
                    if scaled != 0.0:
                        micro_per_100g[field] = scaled
            out.append(
                {
                    "ingredient_id": iid,
                    "ingredient_name": ing.name,
                    "quantity": float(ing.quantity),
                    "unit": ing.unit,
                    "calories_per_100g": float(prof.calories) * factor,
                    "protein_per_100g": float(prof.protein_g) * factor,
                    "carbs_per_100g": float(prof.carbs_g) * factor,
                    "fat_per_100g": float(prof.fat_g) * factor,
                    "micronutrients_per_100g": micro_per_100g,
                    "unit_conversions": {},
                }
            )
        except Exception:
            out.append(
                {
                    "ingredient_id": iid,
                    "ingredient_name": ing.name,
                    "quantity": float(ing.quantity),
                    "unit": ing.unit,
                    "calories_per_100g": 0.0,
                    "protein_per_100g": 0.0,
                    "carbs_per_100g": 0.0,
                    "fat_per_100g": 0.0,
                    "micronutrients_per_100g": {},
                    "unit_conversions": {},
                }
            )
    return out


def _micronutrient_totals_dict(profile: MicronutrientProfile) -> Dict[str, float]:
    d: Dict[str, float] = {}
    for field in NutritionCalculator.MICRONUTRIENT_FIELDS:
        v = float(getattr(profile, field, 0.0))
        if v != 0.0:
            d[field] = v
    return d


def _local_ingredient_to_resolve_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize a NutritionDB ingredient dict into a resolve DTO."""
    by_unit: Dict[str, Dict[str, float]] = {}
    primary_per_100g: Optional[Dict[str, float]] = None
    primary_micros: Dict[str, float] = {}
    macro_keys = {"calories", "protein_g", "fat_g", "carbs_g"}

    for k, v in data.items():
        if k.startswith("per_") and isinstance(v, dict):
            block: Dict[str, float] = {}
            for kk, vv in v.items():
                if isinstance(vv, (int, float)):
                    block[kk] = float(vv)
            if block:
                by_unit[k] = block
                if k == "per_100g":
                    primary_per_100g = {
                        kk: vv for kk, vv in block.items() if kk in macro_keys
                    }
                    primary_micros = {
                        kk: vv for kk, vv in block.items() if kk not in macro_keys
                    }

    meta = {
        mk: float(data[mk])
        for mk in ("scoop_size_g", "large_size_g")
        if mk in data and isinstance(data[mk], (int, float))
    }
    return {
        "source": "local",
        "fdc_id": None,
        "name": str(data.get("name", "")),
        "description": None,
        "per_100g": primary_per_100g,
        "micronutrients": primary_micros,
        "nutrition_by_unit": by_unit or None,
        "metadata": meta or None,
    }


def _build_user_profile(request: PlanRequest) -> tuple[UserProfile, List[str]]:
    daily_fat_g = (request.daily_fat_g_min, request.daily_fat_g_max)
    median_fat_g = (daily_fat_g[0] + daily_fat_g[1]) / 2
    daily_carbs_g = (
        request.daily_calories - request.daily_protein_g * 4 - median_fat_g * 9
    ) / 4

    warnings: List[str] = []
    schedule_days: Optional[List[DaySchedule]] = None
    schedule_dict: Dict[str, int]

    if request.schedule_days is not None:
        schedule_days = list(request.schedule_days)
        if request.schedule is not None:
            warnings.append(
                "Both schedule_days and legacy schedule were provided; using schedule_days."
            )
        schedule_dict, sw = schedule_days_to_meal_only_legacy_dict(schedule_days)
        warnings.extend(sw)
    else:
        assert request.schedule is not None
        schedule_days, mw = legacy_schedule_dict_to_schedule_days(
            request.schedule, days=request.days
        )
        warnings.extend(mw)
        schedule_dict = canonical_day_to_meal_only_legacy_dict(schedule_days[0])

    profile = UserProfile(
        daily_calories=request.daily_calories,
        daily_protein_g=request.daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        schedule={str(k): int(v) for k, v in schedule_dict.items()},
        liked_foods=[str(food) for food in request.liked_foods],
        disliked_foods=[str(food) for food in request.disliked_foods],
        allergies=[str(allergen) for allergen in request.allergies],
        daily_micronutrient_targets=request.micronutrient_goals,
        micronutrient_weekly_min_fraction=request.micronutrient_weekly_min_fraction,
        schedule_days=schedule_days,
    )
    return profile, warnings


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


class IngredientSearchResultItem(BaseModel):
    fdc_id: str
    description: str
    score: float


class IngredientSearchResponse(BaseModel):
    results: List[IngredientSearchResultItem]


class IngredientResolveRequest(BaseModel):
    """Resolve by USDA id or by canonical name (+ ingredient source)."""

    fdc_id: Optional[int] = Field(default=None, gt=0)
    name: Optional[str] = None
    ingredient_source: Optional[str] = Field(default=None, pattern="^(local|api)$")

    @model_validator(mode="after")
    def _fdc_or_name(self) -> "IngredientResolveRequest":
        if self.fdc_id is not None:
            return self
        raw = (self.name or "").strip()
        if not raw:
            raise ValueError("Provide fdc_id or a non-empty name")
        if self.ingredient_source is None:
            raise ValueError("ingredient_source is required when resolving by name")
        return self


class NutritionIngredientLine(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)  # type: ignore[valid-type]
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1)


class NutritionSummaryRequest(BaseModel):
    servings: int = Field(1, ge=1)
    ingredients: List[NutritionIngredientLine] = Field(..., min_length=1)


def _nutrition_line_to_data_ingredient(line: NutritionIngredientLine) -> DataIngredient:
    unit = line.unit.strip()
    lowered = unit.lower()
    is_tt = lowered == "to taste" or "to taste" in lowered
    qty = 0.0 if is_tt else float(line.quantity)
    return DataIngredient(
        name=line.name.strip(),
        quantity=qty,
        unit=unit,
        is_to_taste=is_tt,
        normalized_unit=unit,
        normalized_quantity=qty,
    )


@app.get("/api/v1/llm/status")
@app.get("/api/llm/status")
def llm_status_endpoint() -> Dict[str, Any]:
    """Whether LLM is enabled in this API process's environment (no secrets exposed)."""

    settings = load_llm_settings()
    return {"enabled": bool(settings.enabled)}


@app.post("/api/v1/plan")
@app.post("/api/plan")
def plan_meals_endpoint(request: PlanRequest) -> Dict[str, Any]:
    try:
        user_profile, sched_warnings = _build_user_profile(request)

        recipe_db = RecipeDB(recipes_path)
        all_recipes = recipe_db.get_all_recipes()
        all_recipes = _filter_recipes_by_ids(all_recipes, request.recipe_ids)

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
            # Omitted => deterministic regardless of LLM env (assisted modes are explicit-only).
            effective_mode = "deterministic"

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

        out = format_result_json(result, recipe_by_id, planning_profile, request.days)
        merge_schedule_warnings_into_result(
            out,
            sched_warnings,
            deprecated_legacy=request.schedule_days is None and request.schedule is not None,
        )
        return out
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        # Per contract: structured error payload (never raw exception details).
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/v1/plan-from-text")
@app.post("/api/plan-from-text")
def plan_from_text_endpoint(request: PlanFromTextRequest) -> Dict[str, Any]:
    try:
        llm_settings = load_llm_settings()
        planning_mode_provided = request.planning_mode is not None
        effective_mode = request.planning_mode
        if effective_mode is None:
            # Omitted => deterministic regardless of LLM env (assisted modes are explicit-only).
            effective_mode = "deterministic"

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


@app.post("/api/v1/recipes/tags/generate", response_model=RecipeTagGenerationResponse)
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


@app.post("/api/v1/recipes/generate-validated", response_model=RecipeGenerationResponse)
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


@app.post("/api/v1/ingredients/match", response_model=IngredientMatchResponse)
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


@app.get("/api/v1/ingredients/search", response_model=IngredientSearchResponse)
def ingredient_search_endpoint(
    q: str = Query(..., min_length=1, description="USDA FoodData Central search query"),
    page: int = Query(1, ge=1, description="1-based page number (USDA pageNumber)"),
    page_size: int = Query(25, ge=1, le=50),
    data_types: Literal["all", "sr_legacy_only"] = Query(
        "all",
        description=(
            "FDC dataType filter: 'all' searches SR Legacy, Foundation, Survey, and "
            "Branded; 'sr_legacy_only' restricts to SR Legacy (typical whole ingredients)."
        ),
    ),
) -> Any:
    """Deterministic USDA search suggestions (no LLM)."""
    try:
        client = USDAClient.from_env()
        foods = client.search_candidates(
            q,
            page_size=page_size,
            page_number=page,
            include_branded=True,
            data_types=data_types,
        )
        results: List[IngredientSearchResultItem] = []
        base_rank = (page - 1) * page_size
        for i, food in enumerate(foods):
            fdc = food.get("fdcId")
            desc = str(food.get("description") or "")
            if fdc is None:
                continue
            dt = DataType.from_string(str(food.get("dataType", "")))
            type_rank = DataType.priority(dt) if dt is not None else 999
            score = float(type_rank * 1000 + base_rank + i)
            results.append(
                IngredientSearchResultItem(
                    fdc_id=str(int(fdc)),
                    description=desc,
                    score=score,
                )
            )
        return IngredientSearchResponse(results=results)
    except HTTPException:
        raise
    except USDALookupError as exc:
        status = 400 if exc.error_code == "INVALID_QUERY" else 502
        return JSONResponse(
            status_code=status,
            content={"error": {"code": exc.error_code, "message": exc.message}},
        )
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/v1/ingredients/resolve")
def ingredient_resolve_endpoint(request: IngredientResolveRequest) -> Any:
    """Resolve a USDA FDC id or a canonical ingredient name to nutrition facts."""
    try:
        if request.fdc_id is not None:
            usda = USDAClient.from_env()
            details = usda.get_food_details(int(request.fdc_id))
            if not details.success:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": details.error_code or "NOT_FOUND",
                            "message": details.error_message or "FDC lookup failed",
                        }
                    },
                )
            mapper = NutrientMapper()
            nutrition = mapper.map_nutrients(details.raw_payload)
            raw_desc = details.raw_payload.get("description")
            desc = str(raw_desc) if raw_desc else None
            name = desc or f"fdc_{request.fdc_id}"
            return _mapped_nutrition_to_resolve_payload(
                source="usda",
                fdc_id=int(request.fdc_id),
                name=name,
                description=desc,
                nutrition=nutrition,
            )

        raw_name = (request.name or "").strip()
        assert request.ingredient_source is not None

        if request.ingredient_source == "local":
            nutrition_db = NutritionDB(ingredients_path)
            info = nutrition_db.get_ingredient_info(raw_name)
            if info is None:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"No local ingredient match for {raw_name!r}",
                        }
                    },
                )
            return _local_ingredient_to_resolve_payload(info)

        usda = USDAClient.from_env()
        lookup = CachedIngredientLookup(usda_client=usda)
        entry = lookup.lookup(raw_name.lower())
        if entry is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"No USDA-backed match for {raw_name!r}",
                    }
                },
            )
        return _mapped_nutrition_to_resolve_payload(
            source="usda",
            fdc_id=entry.fdc_id,
            name=entry.canonical_name,
            description=entry.description or None,
            nutrition=entry.nutrition,
        )
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/v1/recipes/sync", response_model=RecipeSyncResponse)
@app.post("/api/recipes/sync", response_model=RecipeSyncResponse)
def sync_recipes_endpoint(body: RecipeSyncRequest) -> Any:
    """Upsert client-owned recipes into the server's file-backed pool by id."""
    try:
        if not body.recipes:
            return RecipeSyncResponse(synced_ids=[])
        synced_ids = atomic_upsert_recipes_by_id(
            path=recipes_path,
            items=body.recipes,
        )
        return RecipeSyncResponse(synced_ids=synced_ids)
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/v1/recipes", response_model=RecipeSyncResponse)
@app.post("/api/recipes", response_model=RecipeSyncResponse)
def create_recipe_endpoint(item: RecipeSyncItem) -> Any:
    """Upsert a single recipe (same semantics as sync)."""
    try:
        synced_ids = atomic_upsert_recipes_by_id(
            path=recipes_path,
            items=[item],
        )
        return RecipeSyncResponse(synced_ids=synced_ids)
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.put("/api/v1/recipes/{recipe_id}", response_model=RecipeSyncResponse)
@app.put("/api/recipes/{recipe_id}", response_model=RecipeSyncResponse)
def put_recipe_endpoint(recipe_id: str, item: RecipeSyncItem) -> Any:
    """Upsert by path id; body [id] must match the path."""
    try:
        if item.id != recipe_id:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "ID_MISMATCH",
                        "message": "Recipe id in body must match path recipe_id.",
                    }
                },
            )
        synced_ids = atomic_upsert_recipes_by_id(
            path=recipes_path,
            items=[item],
        )
        return RecipeSyncResponse(synced_ids=synced_ids)
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.get("/api/v1/recipes")
@app.get("/api/recipes")
def list_recipes() -> List[Dict[str, str]]:
    try:
        recipe_db = RecipeDB(recipes_path)
        return [{"id": r.id, "name": r.name} for r in recipe_db.get_all_recipes()]
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.get("/api/v1/recipes/{recipe_id}")
def get_recipe_detail(recipe_id: str) -> Any:
    """Full recipe with ingredient lines enriched for the Flutter client."""
    try:
        recipe_db = RecipeDB(recipes_path)
        recipe = recipe_db.get_recipe_by_id(recipe_id)
        if recipe is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"No recipe with id {recipe_id!r}",
                    }
                },
            )
        nutrition_db = NutritionDB(ingredients_path)
        calculator = NutritionCalculator(LocalIngredientProvider(nutrition_db))
        ingredients_json = _flutter_ingredient_entries(recipe, calculator)
        return {
            "id": recipe.id,
            "name": recipe.name,
            "servings": 1,
            "cooking_time_minutes": recipe.cooking_time_minutes,
            "instructions": recipe.instructions,
            "ingredients": ingredients_json,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@app.post("/api/v1/nutrition/summary")
def nutrition_summary_endpoint(request: NutritionSummaryRequest) -> Any:
    """Server-authoritative macro and micro totals for a draft ingredient list."""
    try:
        nutrition_db = NutritionDB(ingredients_path)
        try:
            usda_client = USDAClient.from_env()
        except ValueError:
            usda_client = None
        cached_lookup = CachedIngredientLookup(usda_client=usda_client)
        hybrid = SummaryHybridIngredientProvider(nutrition_db, cached_lookup)
        calculator = NutritionCalculator(hybrid)
        ingredients = [_nutrition_line_to_data_ingredient(l) for l in request.ingredients]
        draft = DataRecipe(
            id="_draft",
            name="_draft",
            ingredients=ingredients,
            cooking_time_minutes=0,
            instructions=[],
        )
        prof = calculator.calculate_recipe_nutrition(draft)
        servings = max(1, int(request.servings))
        micro: Dict[str, float] = {}
        if prof.micronutrients is not None:
            micro = _micronutrient_totals_dict(prof.micronutrients)
        return {
            "calories": float(prof.calories),
            "protein_g": float(prof.protein_g),
            "carbs_g": float(prof.carbs_g),
            "fat_g": float(prof.fat_g),
            "per_serving_calories": float(prof.calories) / servings,
            "per_serving_protein_g": float(prof.protein_g) / servings,
            "per_serving_carbs_g": float(prof.carbs_g) / servings,
            "per_serving_fat_g": float(prof.fat_g) / servings,
            "micronutrients": micro,
            "servings": servings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
