import pytest

from src.llm.recipe_validator import validate_recipe_draft, validate_recipe_drafts
from src.llm.schemas import RecipeDraft
from src.llm.usda_contract import USDAProviderRequiredError
from src.providers.ingredient_provider import IngredientDataProvider


class FakeProvider(IngredientDataProvider):
    usda_capable = True
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
    assert [w.recipe.name for w in accepted] == ["Accept"]
    assert [f.error_code for f in rejected] == ["INGREDIENT_NOT_FOUND"]


def test_validate_recipe_draft_rejects_non_usda_provider():
    class NonUSDAProvider(IngredientDataProvider):
        def get_ingredient_info(self, name: str):
            return None

        def resolve_all(self, ingredient_names):
            return None

    provider = NonUSDAProvider()

    draft = RecipeDraft(
        name="My Recipe",
        ingredients=[{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
        instructions=["Cook it."],
    )

    with pytest.raises(USDAProviderRequiredError) as exc:
        validate_recipe_draft(draft, provider)

    assert exc.value.error_code == "USDA_PROVIDER_REQUIRED"


def test_validate_recipe_draft_memoizes_nutrition_computation_for_duplicate_ingredients():
    class CountingProvider(IngredientDataProvider):
        usda_capable = True

        def __init__(self):
            self.get_calls = 0
            self._by_name = {
                "chicken breast": {
                    "name": "chicken breast",
                    **_nutrition_dict(),
                }
            }

        def get_ingredient_info(self, name: str):
            self.get_calls += 1
            return self._by_name.get(str(name).lower().strip())

        def resolve_all(self, ingredient_names):
            return None

    provider = CountingProvider()

    draft = RecipeDraft(
        name="My Recipe",
        ingredients=[
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
            {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
        ],
        instructions=["Cook it."],
    )

    ok, res = validate_recipe_draft(draft, provider)
    assert ok is True
    # validate_recipe_draft calls provider.get_ingredient_info:
    # - twice in existence check (one per ingredient occurrence)
    # - once for nutrition computation (memoized on second duplicate)
    assert provider.get_calls == 3

