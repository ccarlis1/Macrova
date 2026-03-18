import json

import pytest

from src.llm.pipeline import generate_validate_persist_recipes
from src.llm.usda_contract import USDAProviderRequiredError
from src.providers.ingredient_provider import IngredientDataProvider


class DummyLLMClient:
    def __init__(self, *, raw_response):
        self._raw_response = raw_response

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        return self._raw_response


class FakeProvider(IngredientDataProvider):
    usda_capable = True
    def __init__(self, *, ingredient_info_by_name):
        self.ingredient_info_by_name = ingredient_info_by_name

    def get_ingredient_info(self, name: str):
        return self.ingredient_info_by_name.get(name.lower())

    def resolve_all(self, ingredient_names):
        # no-op
        return None


def _nutrition_dict(*, calories=100.0, protein_g=10.0, fat_g=5.0, carbs_g=20.0):
    return {
        "per_100g": {
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
        }
    }


def test_generate_validate_persist_recipes_happy_path(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    raw = {
        "drafts": [
            {
                "name": "LLM Recipe",
                "ingredients": [
                    {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
                ],
                "instructions": ["Cook it."],
            }
        ]
    }

    provider = FakeProvider(ingredient_info_by_name={"chicken breast": _nutrition_dict()})
    client = DummyLLMClient(raw_response=raw)

    summary = generate_validate_persist_recipes(
        context={},
        count=1,
        recipes_path=recipes_path,
        provider=provider,
        client=client,
    )

    assert summary["requested"] == 1
    assert summary["generated"] == 1
    assert summary["accepted"] == 1
    assert summary["rejected"] == []
    assert len(summary["persisted_ids"]) == 1

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 1


def test_generate_validate_persist_recipes_partial_acceptance(tmp_path):
    recipes_path = str(tmp_path / "recipes.json")

    raw = {
        "drafts": [
            {
                "name": "Accept",
                "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
                "instructions": ["Cook it."],
            },
            {
                "name": "Reject",
                "ingredients": [{"name": "missing ingredient", "quantity": 200.0, "unit": "g"}],
                "instructions": ["Cook it."],
            },
        ]
    }

    provider = FakeProvider(ingredient_info_by_name={"chicken breast": _nutrition_dict()})
    client = DummyLLMClient(raw_response=raw)

    summary = generate_validate_persist_recipes(
        context={},
        count=2,
        recipes_path=recipes_path,
        provider=provider,
        client=client,
    )

    assert summary["generated"] == 2
    assert summary["accepted"] == 1
    assert len(summary["rejected"]) == 1
    assert summary["rejected"][0]["error_code"] == "INGREDIENT_NOT_FOUND"

    data = json.loads((tmp_path / "recipes.json").read_text(encoding="utf-8"))
    assert len(data["recipes"]) == 1


def test_generate_validate_persist_recipes_rejects_non_usda_provider(tmp_path):
    class NonUSDAProvider(IngredientDataProvider):
        def get_ingredient_info(self, name: str):
            return None

        def resolve_all(self, ingredient_names):
            return None

    recipes_path = str(tmp_path / "recipes.json")

    provider = NonUSDAProvider()
    client = DummyLLMClient(
        raw_response={
            "drafts": [
                {
                    "name": "X",
                    "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
                    "instructions": ["Cook it."],
                }
            ]
        }
    )

    with pytest.raises(USDAProviderRequiredError) as exc:
        generate_validate_persist_recipes(
            context={},
            count=1,
            recipes_path=recipes_path,
            provider=provider,
            client=client,
        )

    assert exc.value.error_code == "USDA_PROVIDER_REQUIRED"

