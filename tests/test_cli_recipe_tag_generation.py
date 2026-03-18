import src.cli as cli
from src.config.llm_settings import LLMSettings
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
        instructions=["Step 1"],
    )


def _tags_for(recipe_id: str) -> RecipeTagsJson:
    return RecipeTagsJson(
        cuisine="italian" if recipe_id == "r1" else "mexican",
        cost_level=BudgetLevel.cheap,
        prep_time_bucket=PrepTimeBucket.quick_meal,
        dietary_flags=[DietaryFlag.vegan],
    )


def test_cli_tag_recipes_persists_tag_repository(
    monkeypatch, tmp_path
):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text("{}", encoding="utf-8")

    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text("{}", encoding="utf-8")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("{}", encoding="utf-8")

    tag_path = tmp_path / "recipe_tags.json"

    recipes = [_make_recipe("r1"), _make_recipe("r2")]
    tags_by_id = {"r1": _tags_for("r1"), "r2": _tags_for("r2")}

    monkeypatch.setattr("src.cli.RecipeDB", lambda _: DummyRecipeDB(recipes))
    monkeypatch.setattr("src.cli.tag_recipes", lambda _client, _recipes: tags_by_id)
    monkeypatch.setattr(
        "src.cli.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy-model",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )

    def _should_not_plan(*_args, **_kwargs):
        raise AssertionError("planning should not run for --tag-recipes")

    monkeypatch.setattr("src.cli.plan_meals", _should_not_plan)
    monkeypatch.setattr("src.cli.plan_with_llm_feedback", _should_not_plan)

    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "cli.py",
            "--profile",
            str(profile_path),
            "--recipes",
            str(recipes_path),
            "--ingredients",
            str(ingredients_path),
            "--output",
            "json",
            "--tag-recipes",
            "--recipe-tags-path",
            str(tag_path),
        ],
    )

    cli.main()

    loaded = load_recipe_tags(str(tag_path))
    assert set(loaded.keys()) == {"r1", "r2"}

