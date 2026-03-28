import json
import os

import pytest

from src.data_layer.models import Ingredient, Recipe
from src.llm.recipe_tagger import tag_recipes
from src.llm.schemas import (
    BudgetLevel,
    DietaryFlag,
    PrepTimeBucket,
    RecipeTagsJson,
)
from src.llm.tag_repository import load_recipe_tags, upsert_recipe_tags


class DummyLLMClient:
    def __init__(self, *, raw_responses):
        self._raw_responses = list(raw_responses)
        self.calls = []
        self._i = 0

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema_name": schema_name,
                "temperature": temperature,
            }
        )
        resp = self._raw_responses[self._i]
        self._i += 1
        return resp


def _ing(*, name: str, quantity: float, unit: str, is_to_taste: bool = False):
    return Ingredient(
        name=name,
        quantity=quantity,
        unit=unit,
        is_to_taste=is_to_taste,
        normalized_unit=unit,
        normalized_quantity=quantity,
    )


def _recipe(*, recipe_id: str, name: str):
    return Recipe(
        id=recipe_id,
        name=name,
        ingredients=[_ing(name="chicken breast", quantity=200.0, unit="g")],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )


def test_tag_recipes_happy_path_preserves_order():
    r1 = _recipe(recipe_id="r1", name="Taco Chicken")
    r2 = _recipe(recipe_id="r2", name="Veggie Bowl")

    raw_tags_1 = {
        "cuisine": "mexican",
        "cost_level": "cheap",
        "prep_time_bucket": "quick_meal",
        "dietary_flags": ["vegan"],
    }
    raw_tags_2 = {
        "cuisine": "italian",
        "cost_level": "standard",
        "prep_time_bucket": "weeknight_meal",
        "dietary_flags": [],
    }

    client = DummyLLMClient(raw_responses=[raw_tags_1, raw_tags_2])
    out = tag_recipes(client, [r1, r2])

    assert list(out.keys()) == ["r1", "r2"]
    assert out["r1"].cuisine == "mexican"
    assert out["r1"].cost_level == BudgetLevel.cheap
    assert out["r1"].prep_time_bucket == PrepTimeBucket.quick_meal
    assert out["r1"].dietary_flags == [DietaryFlag.vegan]

    assert out["r2"].cuisine == "italian"
    assert out["r2"].cost_level == BudgetLevel.standard
    assert out["r2"].prep_time_bucket == PrepTimeBucket.weeknight_meal
    assert out["r2"].dietary_flags == []

    assert len(client.calls) == 2
    for call in client.calls:
        assert call["schema_name"] == "RecipeTagsJson"
        assert call["temperature"] == 0.0


def test_tag_recipes_rejects_extra_fields_for_single_recipe():
    r1 = _recipe(recipe_id="r1", name="Taco Chicken")
    r2 = _recipe(recipe_id="r2", name="Veggie Bowl")

    raw_tags_1 = {
        "cuisine": "mexican",
        "cost_level": "cheap",
        "prep_time_bucket": "quick_meal",
        "dietary_flags": ["vegan"],
    }
    raw_tags_2 = {
        "cuisine": "italian",
        "cost_level": "standard",
        "prep_time_bucket": "weeknight_meal",
        "dietary_flags": [],
        "unexpected": 123,  # forbidden
    }

    client = DummyLLMClient(raw_responses=[raw_tags_1, raw_tags_2])
    out = tag_recipes(client, [r1, r2])

    assert list(out.keys()) == ["r1"]


def test_tag_repository_upsert_is_idempotent_and_atomic(tmp_path):
    path = str(tmp_path / "recipe_tags.json")
    tmp_file = path + ".tmp"  # recipe_tags.json.tmp

    tags_by_id = {
        "r1": RecipeTagsJson(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
        "r2": RecipeTagsJson(
            cuisine="italian",
            cost_level=BudgetLevel.standard,
            prep_time_bucket=PrepTimeBucket.weeknight_meal,
            dietary_flags=[],
        ),
    }

    upsert_recipe_tags(path, tags_by_id)
    assert not os.path.exists(tmp_file), "Temporary tag file should not remain after atomic replace."

    first_payload = json.loads(open(path, "r", encoding="utf-8").read())

    upsert_recipe_tags(path, tags_by_id)
    second_payload = json.loads(open(path, "r", encoding="utf-8").read())

    assert first_payload == second_payload
    assert set(first_payload["tags_by_id"].keys()) == {"r1", "r2"}

    loaded = load_recipe_tags(path)
    assert list(loaded.keys()) == ["r1", "r2"]
    assert loaded["r1"] == tags_by_id["r1"]
    assert loaded["r2"] == tags_by_id["r2"]

