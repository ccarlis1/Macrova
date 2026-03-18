import pytest

from src.llm.schemas import (
    IngredientMatchResult,
    PlannerConfigJson,
    RecipeDraft,
    RecipeIngredientDraft,
    ValidationFailure,
    parse_llm_json,
)


def test_parse_llm_json_accepts_valid_recipe_draft():
    raw = {
        "name": "Chicken Salad",
        "ingredients": [
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
        ],
        "instructions": ["Cook chicken.", "Mix salad."],
    }
    result = parse_llm_json(RecipeDraft, raw)
    assert isinstance(result, RecipeDraft)
    assert result.name == "Chicken Salad"
    assert result.ingredients[0].unit == "g"


def test_parse_llm_json_rejects_extra_fields():
    raw = {
        "name": "Chicken Salad",
        "ingredients": [
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
        ],
        "instructions": ["Cook chicken.", "Mix salad."],
        "extra_field": 123,
    }
    result = parse_llm_json(RecipeDraft, raw)
    assert isinstance(result, ValidationFailure)
    assert result.error_code == "LLM_SCHEMA_VALIDATION_ERROR"


def test_parse_llm_json_rejects_invalid_unit_enum():
    raw = {
        "name": "Chicken Salad",
        "ingredients": [
            {"name": "chicken breast", "quantity": 200.0, "unit": "miles"},
        ],
        "instructions": ["Cook chicken."],
    }
    result = parse_llm_json(RecipeDraft, raw)
    assert isinstance(result, ValidationFailure)


def test_parse_llm_json_rejects_quantity_zero_for_non_to_taste():
    raw = {
        "name": "Chicken Salad",
        "ingredients": [
            {"name": "chicken breast", "quantity": 0.0, "unit": "g"},
        ],
        "instructions": ["Cook chicken."],
    }
    result = parse_llm_json(RecipeDraft, raw)
    assert isinstance(result, ValidationFailure)


def test_parse_llm_json_rejects_wrong_types_and_out_of_range():
    raw = {
        "query": "chicken",
        "normalized_name": "chicken",
        "confidence": "1.1",  # wrong type + out of range
    }
    result = parse_llm_json(IngredientMatchResult, raw)
    assert isinstance(result, ValidationFailure)


def test_parse_llm_json_rejects_planner_days_out_of_range():
    raw = {
        "days": 8,
        "meals_per_day": 2,
        "targets": {"calories": 2000, "protein": 150.0},
        "preferences": {"cuisine": ["chicken"], "budget": "cheap"},
    }
    result = parse_llm_json(PlannerConfigJson, raw)
    assert isinstance(result, ValidationFailure)

