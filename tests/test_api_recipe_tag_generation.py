from pathlib import Path

from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.models import Ingredient, Recipe
from src.llm.schemas import (
    BudgetLevel,
    DietaryFlag,
    PrepTimeBucket,
    RecipeTagsJson,
)
from src.llm.tag_repository import load_recipe_tags


class DummyRecipeDB:
    def __init__(self, recipes):
        self._recipes = list(recipes)

    def get_all_recipes(self):
        return list(self._recipes)


def _make_recipe(recipe_id: str) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=f"Recipe {recipe_id}",
        ingredients=[Ingredient(name="chicken", quantity=100.0, unit="g")],
        cooking_time_minutes=10,
        instructions=["Step 1", "Step 2"],
    )


def _tags_for(recipe_id: str) -> RecipeTagsJson:
    return RecipeTagsJson(
        cuisine="italian" if recipe_id == "r1" else "mexican",
        cost_level=BudgetLevel.cheap,
        prep_time_bucket=PrepTimeBucket.quick_meal,
        dietary_flags=[DietaryFlag.vegan],
    )


def test_api_generate_recipe_tags_persists_and_is_idempotent(
    monkeypatch, tmp_path
):
    recipes = [_make_recipe("r1"), _make_recipe("r2")]
    tags_by_id = {"r1": _tags_for("r1"), "r2": _tags_for("r2")}

    monkeypatch.setattr("src.api.server.build_llm_client", lambda: object())
    monkeypatch.setattr("src.api.server.RecipeDB", lambda _: DummyRecipeDB(recipes))
    monkeypatch.setattr(
        "src.api.server.tag_recipes",
        lambda _client, _recipes: tags_by_id,
    )

    tags_path = str(tmp_path / "recipe_tags.json")
    client = TestClient(app)

    resp1 = client.post(
        "/api/recipes/tags/generate",
        json={"recipe_tags_path": tags_path},
    )
    assert resp1.status_code == 200
    assert resp1.json()["tagged_recipe_count"] == 2

    loaded1 = load_recipe_tags(tags_path)
    assert set(loaded1.keys()) == {"r1", "r2"}

    before = Path(tags_path).read_text(encoding="utf-8")

    resp2 = client.post(
        "/api/recipes/tags/generate",
        json={"recipe_tags_path": tags_path},
    )
    assert resp2.status_code == 200
    assert resp2.json()["tagged_recipe_count"] == 2

    after = Path(tags_path).read_text(encoding="utf-8")
    assert before == after

    loaded2 = load_recipe_tags(tags_path)
    assert loaded2["r1"].cuisine == loaded1["r1"].cuisine
    assert loaded2["r2"].cuisine == loaded1["r2"].cuisine

