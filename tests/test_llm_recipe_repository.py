import json

import pytest

from src.data_layer.recipe_db import RecipeDB
from src.llm.schemas import BudgetLevel, PrepTimeBucket, RecipeTagsJson
from src.llm.repository import append_validated_recipes
from src.llm.tag_repository import (
    add_alias,
    create,
    list_by_type,
    merge,
    rename_display,
    resolve,
    upsert_recipe_tags,
)
from src.data_layer.models import Ingredient, Recipe
from src.llm.types import ValidatedRecipeForPersistence


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

    appended = append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r1)],
    )
    assert len(appended) == 1

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert "recipes" in data
    assert len(data["recipes"]) == 1
    assert data["recipes"][0]["name"] == "R1"

    # Re-append same recipe: should dedupe and not insert.
    appended_again = append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r1)],
    )
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

    append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r1)],
    )
    appended_ids = append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r2)],
    )

    # Same measurable ingredients => same fingerprint => deduped.
    assert appended_ids == []

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 1


def test_append_validated_recipes_instructions_affect_deduplication(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    ing_a = _ing(name="chicken breast", quantity=200.0, unit="g")
    ing_b = _ing(name="rice", quantity=300.0, unit="g")

    r1 = _recipe(
        recipe_id_suffix="1",
        name="Order 1",
        ingredients=[ing_a, ing_b],
        instructions=["Cook A"],
    )
    r2 = _recipe(
        recipe_id_suffix="2",
        name="Order 2",
        ingredients=[ing_a, ing_b],
        instructions=["Cook B"],
    )

    append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r1)],
    )
    appended_ids = append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r2)],
    )

    assert len(appended_ids) == 1
    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 2


def test_append_validated_recipes_instruction_normalization_dedupes(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    ing_a = _ing(name="chicken breast", quantity=200.0, unit="g")
    ing_b = _ing(name="rice", quantity=300.0, unit="g")

    r1 = _recipe(
        recipe_id_suffix="1",
        name="R1",
        ingredients=[ing_a, ing_b],
        instructions=["Cook it."],
    )
    r2 = _recipe(
        recipe_id_suffix="2",
        name="R2",
        ingredients=[ing_a, ing_b],
        # Same instruction text but different whitespace/case.
        instructions=["  cook  it.  "],
    )

    append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r1)],
    )
    appended_ids = append_validated_recipes(
        path=recipes_path,
        recipes=[ValidatedRecipeForPersistence(recipe=r2)],
    )

    assert appended_ids == []
    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 1


def test_append_validated_recipes_rejects_raw_recipe(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")
    r1 = _recipe(
        recipe_id_suffix="1",
        name="R1",
        ingredients=[_ing(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook"],
    )

    try:
        append_validated_recipes(path=recipes_path, recipes=[r1])  # type: ignore[arg-type]
        assert False, "Expected TypeError when persisting raw Recipe"
    except TypeError as e:
        assert "ValidatedRecipeForPersistence" in str(e)


def test_resolve_normalization_variants_map_to_high_fiber(tmp_path):
    tags_path = str(tmp_path / "recipe_tags.json")
    upsert_recipe_tags(
        tags_path,
        {
            "r1": RecipeTagsJson(
                cuisine="mexican",
                cost_level=BudgetLevel.cheap,
                prep_time_bucket=PrepTimeBucket.quick_meal,
                dietary_flags=[],
            )
        },
    )

    assert resolve("High Fiber", tags_path).slug == "high-fiber"
    assert resolve("high fiber!", tags_path).slug == "high-fiber"
    assert resolve("HIGH-FIBER", tags_path).slug == "high-fiber"


def test_resolve_alias_valid_and_invalid(tmp_path):
    tags_path = tmp_path / "recipe_tags.json"
    tags_path.write_text(
        json.dumps(
            {
                "tags_by_id": {},
                "tag_registry": {
                    "high-fiber": {
                        "slug": "high-fiber",
                        "display": "High Fiber",
                        "tag_type": "nutrition",
                        "source": "system",
                        "created_at": "1970-01-01T00:00:00Z",
                        "aliases": ["fiber-high"],
                    }
                },
                "tag_aliases": {"fiber-rich": "high-fiber"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert resolve("fiber-rich", str(tags_path)).slug == "high-fiber"
    assert resolve("fiber-high", str(tags_path)).slug == "high-fiber"
    with pytest.raises(ValueError):
        resolve("not-a-real-alias", str(tags_path))


def test_registry_create_rename_alias_and_list_preserve_recipe_tags(tmp_path):
    tags_path = str(tmp_path / "recipe_tags.json")
    upsert_recipe_tags(
        tags_path,
        {
            "r1": RecipeTagsJson(
                cuisine="mexican",
                cost_level=BudgetLevel.cheap,
                prep_time_bucket=PrepTimeBucket.quick_meal,
                dietary_flags=[],
            )
        },
    )

    created = create(
        path=tags_path,
        display="High Protein",
        tag_type="nutrition",
        source="user",
    )
    renamed = rename_display(
        path=tags_path,
        slug=created.slug,
        display="Protein Rich",
    )
    aliased = add_alias(
        path=tags_path,
        slug=renamed.slug,
        alias_slug="protein-rich",
    )

    assert aliased.slug == "high-protein"
    assert resolve("protein-rich", tags_path).slug == "high-protein"
    assert resolve("Protein Rich", tags_path).slug == "high-protein"
    assert "high-protein" in {tag.slug for tag in list_by_type(tags_path, "nutrition")}

    payload = json.loads((tmp_path / "recipe_tags.json").read_text(encoding="utf-8"))
    assert set(payload["tags_by_id"].keys()) == {"r1"}
    assert payload["tag_aliases"]["protein-rich"] == "high-protein"


def test_merge_updates_registry_and_recipes_without_duplicates(tmp_path):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Tagged",
                        "ingredients": [],
                        "cooking_time_minutes": 10,
                        "instructions": [],
                        "default_servings": 1,
                        "tags": [
                            {"slug": "fiber-rich", "type": "nutrition"},
                            {"slug": "high-fiber", "type": "nutrition"},
                            {"slug": "high-fiber", "type": "nutrition"},
                        ],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tags_path = tmp_path / "recipe_tags.json"
    tags_path.write_text(
        json.dumps(
            {
                "tags_by_id": {
                    "r1": {
                        "cuisine": "mexican",
                        "cost_level": "cheap",
                        "prep_time_bucket": "quick_meal",
                        "dietary_flags": [],
                        "tag_slugs_by_type": {"nutrition": ["fiber-rich", "high-fiber"]},
                    }
                },
                "tag_registry": {
                    "fiber-rich": {
                        "slug": "fiber-rich",
                        "display": "Fiber Rich",
                        "tag_type": "nutrition",
                        "source": "system",
                        "created_at": "1970-01-01T00:00:00Z",
                        "aliases": [],
                    },
                    "high-fiber": {
                        "slug": "high-fiber",
                        "display": "High Fiber",
                        "tag_type": "nutrition",
                        "source": "system",
                        "created_at": "1970-01-01T00:00:00Z",
                        "aliases": [],
                    },
                },
                "tag_aliases": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    merge("fiber-rich", "high-fiber", str(tags_path))

    merged_payload = json.loads(tags_path.read_text(encoding="utf-8"))
    assert "fiber-rich" not in merged_payload["tag_registry"]
    assert merged_payload["tag_aliases"]["fiber-rich"] == "high-fiber"
    assert merged_payload["tags_by_id"]["r1"]["tag_slugs_by_type"]["nutrition"] == ["high-fiber"]

    recipe = RecipeDB(str(recipes_path), tag_repo_path=str(tags_path)).get_all_recipes()[0]
    assert recipe.tags == [{"slug": "high-fiber", "type": "nutrition"}]


def test_recipe_db_drops_unknown_tags(tmp_path):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Unknown Tag Recipe",
                        "ingredients": [],
                        "cooking_time_minutes": 10,
                        "instructions": [],
                        "tags": [{"slug": "does-not-exist", "type": "nutrition"}],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tags_path = tmp_path / "recipe_tags.json"
    upsert_recipe_tags(
        str(tags_path),
        {
            "r1": RecipeTagsJson(
                cuisine="mexican",
                cost_level=BudgetLevel.cheap,
                prep_time_bucket=PrepTimeBucket.quick_meal,
                dietary_flags=[],
            )
        },
    )

    recipe = RecipeDB(str(recipes_path), tag_repo_path=str(tags_path)).get_all_recipes()[0]
    assert recipe.tags == []


def test_recipe_db_roundtrip_tags_stable(tmp_path):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Roundtrip",
                        "ingredients": [],
                        "cooking_time_minutes": 10,
                        "instructions": [],
                        "default_servings": 3,
                        "tags": [{"slug": "high-fiber", "type": "nutrition"}],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tags_path = tmp_path / "recipe_tags.json"
    upsert_recipe_tags(
        str(tags_path),
        {
            "r1": RecipeTagsJson(
                cuisine="mexican",
                cost_level=BudgetLevel.cheap,
                prep_time_bucket=PrepTimeBucket.quick_meal,
                dietary_flags=[],
                tag_slugs_by_type={"nutrition": ["high-fiber"]},
            )
        },
    )

    db = RecipeDB(str(recipes_path), tag_repo_path=str(tags_path))
    db.save()
    reloaded = RecipeDB(str(recipes_path), tag_repo_path=str(tags_path)).get_all_recipes()[0]
    assert reloaded.default_servings == 3
    assert reloaded.tags == [{"slug": "high-fiber", "type": "nutrition"}]

