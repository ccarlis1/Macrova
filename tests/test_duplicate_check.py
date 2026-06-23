from src.data_layer.models import Recipe
from src.llm.duplicate_check import find_duplicate


def _recipe(*, recipe_id: str, name: str) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=name,
        ingredients=[],
        cooking_time_minutes=10,
        instructions=[],
    )


def test_find_duplicate_matches_token_sorted_name():
    existing = _recipe(recipe_id="recipe_1", name="chicken and rice bowl")

    duplicate = find_duplicate("Chicken Rice Bowl", [existing])

    assert duplicate == existing


def test_find_duplicate_returns_none_below_threshold():
    existing = _recipe(recipe_id="recipe_1", name="Chicken Pasta")

    duplicate = find_duplicate("Shrimp Pasta", [existing])

    assert duplicate is None


def test_find_duplicate_uses_env_threshold(monkeypatch):
    existing = _recipe(recipe_id="recipe_1", name="chicken and rice bowl")
    monkeypatch.setenv("DUPLICATE_THRESHOLD", "0.99")

    duplicate = find_duplicate("Chicken Rice Bowl", [existing])

    assert duplicate is None
