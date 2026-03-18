import json

from src.llm.repository import append_validated_recipes
from src.data_layer.models import Ingredient, Recipe


def _recipe(*, recipe_id_suffix: str, name: str, ingredients, instructions):
    # cooking_time_minutes must be present for RecipeDB parsing.
    return Recipe(
        id="",
        name=name,
        ingredients=ingredients,
        cooking_time_minutes=10,
        instructions=instructions,
    )


def _ing(*, name: str, quantity: float, unit: str, is_to_taste: bool = False):
    return Ingredient(
        name=name,
        quantity=quantity,
        unit=unit,
        is_to_taste=is_to_taste,
        normalized_unit=unit,
        normalized_quantity=quantity,
    )


def test_append_validated_recipes_creates_file_and_dedupes(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    r1 = _recipe(
        recipe_id_suffix="1",
        name="R1",
        ingredients=[_ing(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook"],
    )

    appended = append_validated_recipes(path=recipes_path, recipes=[r1])
    assert len(appended) == 1

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert "recipes" in data
    assert len(data["recipes"]) == 1
    assert data["recipes"][0]["name"] == "R1"

    # Re-append same recipe: should dedupe and not insert.
    appended_again = append_validated_recipes(path=recipes_path, recipes=[r1])
    assert appended_again == []
    data2 = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data2["recipes"]) == 1


def test_append_validated_recipes_fingerprint_ignores_ingredient_order(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    ing_a = _ing(name="chicken breast", quantity=200.0, unit="g")
    ing_b = _ing(name="rice", quantity=300.0, unit="g")

    r1 = _recipe(
        recipe_id_suffix="1",
        name="Order 1",
        ingredients=[ing_a, ing_b],
        instructions=["Cook"],
    )
    r2 = _recipe(
        recipe_id_suffix="2",
        name="Order 2",
        ingredients=[ing_b, ing_a],  # reversed
        instructions=["Cook"],
    )

    append_validated_recipes(path=recipes_path, recipes=[r1])
    appended_ids = append_validated_recipes(path=recipes_path, recipes=[r2])

    # Same measurable ingredients => same fingerprint => deduped.
    assert appended_ids == []

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 1

