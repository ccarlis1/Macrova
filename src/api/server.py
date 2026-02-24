"""FastAPI server for the Nutrition Agent meal planning pipeline."""

from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.data_layer.models import UserProfile
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.ingredient_db import IngredientDB
from src.nutrition.calculator import NutritionCalculator
from src.nutrition.aggregator import NutritionAggregator
from src.scoring.recipe_scorer import RecipeScorer
from src.ingestion.recipe_retriever import RecipeRetriever
from src.planning.meal_planner import MealPlanner, DailySchedule
from src.output.formatters import format_plan_json


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


class PlanRequest(BaseModel):
    daily_calories: int
    daily_protein_g: float
    daily_fat_g_min: float
    daily_fat_g_max: float
    schedule: Dict[str, int]
    liked_foods: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)


def create_daily_schedule(user_profile) -> DailySchedule:
    """Convert UserProfile schedule dict to DailySchedule object.

    Args:
        user_profile: UserProfile object with schedule dict

    Returns:
        DailySchedule object

    Raises:
        ValueError: If schedule doesn't have required meal times
    """
    schedule = user_profile.schedule

    # Separate workout time (busyness level 0) from meal times
    workout_time = None
    meal_times = []
    for time_str, busyness in schedule.items():
        if busyness == 0:
            workout_time = time_str
        else:
            meal_times.append(time_str)

    # Sort meal times chronologically
    meal_times = sorted(meal_times)

    if len(meal_times) < 3:
        raise ValueError(
            f"Schedule must have at least 3 meal times, found {len(meal_times)}"
        )

    # Assume first meal is breakfast, second is lunch, third is dinner
    breakfast_time = meal_times[0]
    lunch_time = meal_times[1]
    dinner_time = meal_times[2]

    return DailySchedule(
        breakfast_time=breakfast_time,
        breakfast_busyness=schedule[breakfast_time],
        lunch_time=lunch_time,
        lunch_busyness=schedule[lunch_time],
        dinner_time=dinner_time,
        dinner_busyness=schedule[dinner_time],
        workout_time=workout_time,
    )


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
    )


@app.post("/api/plan")
def plan_meals(request: PlanRequest) -> Dict[str, Any]:
    try:
        user_profile = _build_user_profile(request)

        recipe_db = RecipeDB(recipes_path)
        ingredient_db = IngredientDB(ingredients_path)
        nutrition_db = NutritionDB(ingredients_path)

        # Keep ingredient_db loaded for parity with CLI data initialization.
        _ = ingredient_db

        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_retriever = RecipeRetriever(recipe_db)
        meal_planner = MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)

        daily_schedule = create_daily_schedule(user_profile)
        all_recipes = recipe_db.get_all_recipes()
        result = meal_planner.plan_daily_meals(
            user_profile=user_profile,
            schedule=daily_schedule,
            available_recipes=all_recipes,
        )

        return format_plan_json(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/recipes")
def list_recipes() -> List[Dict[str, str]]:
    try:
        recipe_db = RecipeDB(recipes_path)
        return [{"id": r.id, "name": r.name} for r in recipe_db.get_all_recipes()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
