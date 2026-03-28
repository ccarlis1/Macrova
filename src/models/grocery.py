"""Pydantic models for grocery optimizer API (v1 JSON contract, camelCase on the wire)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GroceryIngredient(BaseModel):
    """Single ingredient line on a recipe."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    quantity: float
    unit: str
    is_to_taste: bool = Field(default=False, alias="isToTaste")


class GroceryRecipe(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    ingredients: List[GroceryIngredient]


class GroceryMealPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    recipes: List[GroceryRecipe]
    recipe_servings: Dict[str, float] = Field(default_factory=dict, alias="recipeServings")


class GroceryStoreRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    base_url: str = Field(alias="baseUrl")


class GroceryOptimizeRequest(BaseModel):
    """Request body for POST /api/grocery/optimize."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    meal_plan: GroceryMealPlan = Field(alias="mealPlan")
    preferences: Dict[str, Any] = Field(default_factory=dict)
    stores: List[GroceryStoreRef] = Field(min_length=1)


class GroceryOptimizeError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str


class GroceryOptimizeResponse(BaseModel):
    """Response envelope (success or handled failure)."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[GroceryOptimizeError] = None
