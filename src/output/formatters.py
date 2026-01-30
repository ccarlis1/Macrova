"""Formatters for meal plan output (JSON and Markdown)."""

import json
from typing import Dict, List, Any
from src.data_layer.models import (
    DailyMealPlan,
    Meal,
    Recipe,
    Ingredient,
    NutritionProfile,
    NutritionGoals
)
from src.planning.meal_planner import PlanningResult


def format_ingredient_string(ingredient: Ingredient) -> str:
    """Format an ingredient as a string (e.g., "200g cream of rice").
    
    Args:
        ingredient: Ingredient object
        
    Returns:
        Formatted string like "200g cream of rice" or "salt to taste"
    """
    if ingredient.is_to_taste:
        return f"{ingredient.name} to taste"
    
    # Format quantity (remove .0 if whole number)
    if ingredient.quantity == int(ingredient.quantity):
        qty_str = str(int(ingredient.quantity))
    else:
        qty_str = f"{ingredient.quantity:.1f}".rstrip('0').rstrip('.')
    
    # Format unit
    unit_str = ingredient.unit if ingredient.unit else ""
    
    # Combine (add space between quantity/unit and name)
    if unit_str:
        return f"{qty_str} {unit_str} {ingredient.name}"
    else:
        return f"{qty_str} {ingredient.name}"


def format_nutrition_breakdown(nutrition: NutritionProfile, indent: str = "") -> str:
    """Format nutrition profile as a readable breakdown.
    
    Args:
        nutrition: NutritionProfile object
        indent: Optional indentation prefix
        
    Returns:
        Formatted string with calories and macros
    """
    lines = [
        f"{indent}**Calories:** {nutrition.calories:.0f} kcal",
        f"{indent}**Protein:** {nutrition.protein_g:.1f}g",
        f"{indent}**Fat:** {nutrition.fat_g:.1f}g",
        f"{indent}**Carbs:** {nutrition.carbs_g:.1f}g"
    ]
    return "\n".join(lines)


def format_plan_markdown(result: PlanningResult) -> str:
    """Format a PlanningResult as Markdown (matches README.md example).
    
    Args:
        result: PlanningResult from meal planning
        
    Returns:
        Formatted Markdown string
    """
    plan = result.daily_plan
    lines = []
    
    # Header
    lines.append("# Daily Meal Plan\n")
    
    # Success status
    if result.success:
        lines.append("✅ **Plan meets nutrition goals**\n")
    else:
        lines.append("⚠️ **Plan has warnings**\n")
    
    # Warnings (if any)
    if result.warnings:
        lines.append("## Warnings\n")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    
    # Meals
    meal_names = {
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "dinner": "Dinner",
        "snack": "Snack"
    }
    
    for idx, meal in enumerate(plan.meals, 1):
        meal_type_display = meal_names.get(meal.meal_type, meal.meal_type.capitalize())
        lines.append(f"## Meal {idx}: {meal.recipe.name}")
        lines.append(f"**Type:** {meal_type_display}")
        
        # Cooking time
        lines.append(f"**Cooking Time:** {meal.recipe.cooking_time_minutes} minutes")
        lines.append("")
        
        # Ingredients
        lines.append("### Ingredients")
        for ingredient in meal.recipe.ingredients:
            lines.append(f"- {format_ingredient_string(ingredient)}")
        lines.append("")
        
        # Instructions (if available)
        if meal.recipe.instructions:
            lines.append("### Instructions")
            for step_idx, instruction in enumerate(meal.recipe.instructions, 1):
                lines.append(f"{step_idx}. {instruction}")
            lines.append("")
        
        # Nutrition breakdown
        lines.append("### Nutrition Breakdown")
        lines.append(format_nutrition_breakdown(meal.nutrition))
        lines.append("")
    
    # Daily totals
    lines.append("## Daily Totals")
    lines.append(format_nutrition_breakdown(plan.total_nutrition))
    lines.append("")
    
    # Goals and adherence
    lines.append("## Goals & Adherence")
    goals = plan.goals
    lines.append(f"**Target Calories:** {goals.calories}")
    lines.append(f"**Target Protein:** {goals.protein_g:.1f}g")
    lines.append(f"**Target Fat:** {goals.fat_g_min:.1f}g - {goals.fat_g_max:.1f}g")
    lines.append(f"**Target Carbs:** {goals.carbs_g:.1f}g")
    lines.append("")
    
    lines.append("**Adherence:**")
    for macro, percentage in result.target_adherence.items():
        lines.append(f"- {macro.capitalize()}: {percentage:.1f}%")
    lines.append("")
    
    return "\n".join(lines)


def format_plan_json(result: PlanningResult) -> Dict[str, Any]:
    """Format a PlanningResult as JSON (for API usage).
    
    Args:
        result: PlanningResult from meal planning
        
    Returns:
        Dictionary ready for JSON serialization
    """
    plan = result.daily_plan
    
    # Format meals
    meals_json = []
    for meal in plan.meals:
        # Format ingredients
        ingredients_json = []
        for ingredient in meal.recipe.ingredients:
            ingredients_json.append({
                "name": ingredient.name,
                "quantity": ingredient.quantity,
                "unit": ingredient.unit,
                "is_to_taste": ingredient.is_to_taste,
                "display": format_ingredient_string(ingredient)
            })
        
        meal_json = {
            "meal_type": meal.meal_type,
            "recipe": {
                "id": meal.recipe.id,
                "name": meal.recipe.name,
                "ingredients": ingredients_json,
                "cooking_time_minutes": meal.recipe.cooking_time_minutes,
                "instructions": meal.recipe.instructions
            },
            "nutrition": {
                "calories": round(meal.nutrition.calories, 1),
                "protein_g": round(meal.nutrition.protein_g, 1),
                "fat_g": round(meal.nutrition.fat_g, 1),
                "carbs_g": round(meal.nutrition.carbs_g, 1)
            },
            "busyness_level": meal.busyness_level
        }
        meals_json.append(meal_json)
    
    # Format daily totals
    total_nutrition_json = {
        "calories": round(plan.total_nutrition.calories, 1),
        "protein_g": round(plan.total_nutrition.protein_g, 1),
        "fat_g": round(plan.total_nutrition.fat_g, 1),
        "carbs_g": round(plan.total_nutrition.carbs_g, 1)
    }
    
    # Format goals
    goals_json = {
        "calories": plan.goals.calories,
        "protein_g": plan.goals.protein_g,
        "fat_g_min": plan.goals.fat_g_min,
        "fat_g_max": plan.goals.fat_g_max,
        "carbs_g": plan.goals.carbs_g
    }
    
    # Build final JSON structure
    return {
        "success": result.success,
        "date": plan.date,
        "meals": meals_json,
        "total_nutrition": total_nutrition_json,
        "goals": goals_json,
        "target_adherence": {
            macro: round(percentage, 1) for macro, percentage in result.target_adherence.items()
        },
        "warnings": result.warnings,
        "meets_goals": plan.meets_goals
    }


def format_plan_json_string(result: PlanningResult, indent: int = 2) -> str:
    """Format a PlanningResult as a JSON string.
    
    Args:
        result: PlanningResult from meal planning
        indent: JSON indentation (default: 2)
        
    Returns:
        JSON string
    """
    return json.dumps(format_plan_json(result), indent=indent)

