"""FastAPI server for the Nutrition Agent meal planning pipeline."""

from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.data_layer.models import UserProfile
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.providers.local_provider import LocalIngredientProvider
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes, convert_profile, extract_ingredient_names
from src.planning.planner import plan_meals
from src.output.formatters import format_result_json
from src.ingestion.usda_client import USDAClient
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.providers.api_provider import APIIngredientProvider
from src.config.llm_settings import load_llm_settings
from src.llm.client import LLMClient
from src.llm.pipeline import generate_validate_persist_recipes


recipes_path = "data/recipes/recipes.json"
ingredients_path = "data/ingredients/custom_ingredients.json"

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


@app.post("/api/plan")
def plan_meals_endpoint(request: PlanRequest) -> Dict[str, Any]:
    try:
        user_profile = _build_user_profile(request)

        recipe_db = RecipeDB(recipes_path)
        all_recipes = recipe_db.get_all_recipes()

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

        result = plan_meals(planning_profile, recipe_pool, request.days)

        return format_result_json(result, recipe_by_id, planning_profile, request.days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/recipes/generate-validated", response_model=RecipeGenerationResponse)
def generate_validated_recipes_endpoint(
    request: RecipeGenerationRequest,
) -> RecipeGenerationResponse:
    try:
        llm_settings = load_llm_settings()
        client = LLMClient(llm_settings)

        # USDA-backed provider for deterministic, authoritative validation.
        usda_client = USDAClient.from_env()
        cached_lookup = CachedIngredientLookup(usda_client=usda_client)
        provider = APIIngredientProvider(cached_lookup)

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
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "PIPELINE_INTERNAL_ERROR", "message": str(exc)}},
        )


@app.get("/api/recipes")
def list_recipes() -> List[Dict[str, str]]:
    try:
        recipe_db = RecipeDB(recipes_path)
        return [{"id": r.id, "name": r.name} for r in recipe_db.get_all_recipes()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
