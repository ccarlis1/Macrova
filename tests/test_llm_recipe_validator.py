import pytest

from src.llm.recipe_validator import validate_recipe_draft, validate_recipe_drafts
from src.llm.schemas import RecipeDraft
from src.providers.ingredient_provider import IngredientDataProvider


class FakeProvider(IngredientDataProvider):
    def __init__(self, *, ingredient_info_by_name):
        self.ingredient_info_by_name = ingredient_info_by_name
        self.resolve_calls = []

    def get_ingredient_info(self, name: str):
        return self.ingredient_info_by_name.get(name.lower())

    def resolve_all(self, ingredient_names):
        # Record for determinism checks; no side effects in tests.
        self.resolve_calls.append(list(ingredient_names))


def _nutrition_dict(*, calories=100.0, protein_g=10.0, fat_g=5.0, carbs_g=20.0):
    return {
        "per_100g": {
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
        }
    }


def test_validate_recipe_draft_happy_path_accepts_and_canonicalizes():
    provider = FakeProvider(
        ingredient_info_by_name={
            "chicken breast": _nutrition_dict(),
        }
    )

    draft = RecipeDraft(
        name="My Recipe",
        ingredients=[
            {"name": "Large Chicken Breast", "quantity": 200.0, "unit": "g"},
        ],
        instructions=["Cook it.", "Serve it."],
    )

    ok, res = validate_recipe_draft(draft, provider)
    assert ok is True
    recipe = res
    assert recipe.name == "My Recipe"
    assert recipe.cooking_time_minutes == 10  # 5 * len(instructions)
    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].name == "chicken breast"  # canonicalized


def test_validate_recipe_draft_ingredient_not_found_rejects():
    provider = FakeProvider(ingredient_info_by_name={})

    draft = RecipeDraft(
        name="My Recipe",
        ingredients=[
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
        ],
        instructions=["Cook it."],
    )

    ok, res = validate_recipe_draft(draft, provider)
    assert ok is False
    assert res.error_code == "INGREDIENT_NOT_FOUND"


def test_validate_recipe_draft_nutrition_computation_failed_rejects():
    # Missing "per_100g" key should make nutrition computation fail.
    provider = FakeProvider(ingredient_info_by_name={"chicken breast": {}})

    draft = RecipeDraft(
        name="My Recipe",
        ingredients=[
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
        ],
        instructions=["Cook it."],
    )

    ok, res = validate_recipe_draft(draft, provider)
    assert ok is False
    assert res.error_code == "NUTRITION_COMPUTATION_FAILED"


def test_validate_recipe_draft_empty_recipe_rejects():
    provider = FakeProvider(ingredient_info_by_name={"salt": _nutrition_dict()})

    draft = RecipeDraft(
        name="To Taste Only",
        ingredients=[{"name": "salt", "quantity": 0.0, "unit": "to taste"}],
        instructions=["Season it."],
    )

    ok, res = validate_recipe_draft(draft, provider)
    assert ok is False
    assert res.error_code == "EMPTY_RECIPE"


def test_validate_recipe_drafts_partial_acceptance_returns_both_sets():
    provider = FakeProvider(
        ingredient_info_by_name={
            "chicken breast": _nutrition_dict(),
        }
    )

    ok_1 = RecipeDraft(
        name="Accept",
        ingredients=[{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
        instructions=["Cook."],
    )
    bad = RecipeDraft(
        name="Reject",
        ingredients=[{"name": "missing ingredient", "quantity": 200.0, "unit": "g"}],
        instructions=["Cook."],
    )

    accepted, rejected = validate_recipe_drafts([ok_1, bad], provider)
    assert [r.name for r in accepted] == ["Accept"]
    assert [f.error_code for f in rejected] == ["INGREDIENT_NOT_FOUND"]

