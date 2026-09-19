"""Stage 7: tagging is hybrid — LLM proposes from a closed vocabulary, deterministic facts win, writes merge."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.data_layer.models import Ingredient, Recipe
from src.llm.recipe_tagger import CUISINE_VOCABULARY, deterministic_prep_time_bucket, tag_recipes
from src.llm.schemas import RecipeTagsJson
from src.llm.tag_repository import load_hard_eligible_recipe_tag_slugs, load_recipe_tags, upsert_recipe_tags

BENCH_TAGS = Path("evaluation/benchmark/recipe_tags.json")


class Client:
    def __init__(self, responses):
        self.responses = list(responses); self.calls = []

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        self.calls.append(system_prompt)
        return self.responses.pop(0)


def _recipe(rid, cook):
    return Recipe(id=rid, name=rid, ingredients=[Ingredient("chicken breast", 200, "g")], cooking_time_minutes=cook, instructions=["Cook."])


def test_upsert_merges_by_default_and_replace_is_explicit(tmp_path):
    p = tmp_path / "tags.json"; shutil.copy(BENCH_TAGS, p)
    before = len(load_recipe_tags(str(p)))
    upsert_recipe_tags(str(p), {"new_recipe": RecipeTagsJson(cuisine="unknown", cost_level="cheap", prep_time_bucket="snack", dietary_flags=[])})
    assert len(load_recipe_tags(str(p))) == before + 1
    upsert_recipe_tags(str(p), {})  # what a tagging run with zero valid outputs writes
    assert len(load_recipe_tags(str(p))) == before + 1
    upsert_recipe_tags(str(p), {"only": RecipeTagsJson(cuisine="unknown", cost_level="cheap", prep_time_bucket="snack", dietary_flags=[])}, replace=True)
    assert list(load_recipe_tags(str(p)).keys()) == ["only"]


def test_prompt_embeds_schema_and_registry_slugs(tmp_path):
    p = tmp_path / "tags.json"; shutil.copy(BENCH_TAGS, p)
    client = Client([{"cuisine": "mexican", "cost_level": "cheap", "prep_time_bucket": "meal_prep", "dietary_flags": []}])
    tag_recipes(client, [_recipe("r1", 12)], tag_repo_path=str(p))
    sp = client.calls[0]
    assert '"additionalProperties":false' in sp and '"prep_time_bucket"' in sp
    assert '"meal-prep"' in sp and '"breakfast"' in sp  # registry slugs shown to the model


def test_deterministic_facts_override_llm_guesses(tmp_path):
    p = tmp_path / "tags.json"; shutil.copy(BENCH_TAGS, p)
    client = Client([{"cuisine": "Martian Fusion", "cost_level": "cheap", "prep_time_bucket": "meal_prep", "dietary_flags": ["vegan"]}])
    out = tag_recipes(client, [_recipe("r1", 12)], tag_repo_path=str(p))
    t = out["r1"]
    assert t.prep_time_bucket.value == "quick_meal"  # from 12 minutes, not the guess
    assert t.cuisine == "unknown"  # outside the closed vocabulary
    assert t.tag_slugs_by_type["time"] == ["time-2"]
    assert deterministic_prep_time_bucket(31) == "meal_prep" and "mexican" in CUISINE_VOCABULARY


def test_proposed_slugs_are_quarantined_and_invented_slugs_dropped(tmp_path):
    p = tmp_path / "tags.json"; shutil.copy(BENCH_TAGS, p)
    client = Client([{"cuisine": "italian", "cost_level": "standard", "prep_time_bucket": "snack", "dietary_flags": [],
                      "tag_slugs_by_type": {"context": ["meal-prep", "unicorn-friendly", "time-4"], "constraint": ["nut-free"]}}])
    out = tag_recipes(client, [_recipe("r1", 40)], tag_repo_path=str(p))
    t = out["r1"]
    assert t.tag_slugs_by_type["context"] == ["meal-prep"] and t.tag_slugs_by_type["constraint"] == ["nut-free"]
    assert "unicorn-friendly" not in json.dumps(t.model_dump())
    assert t.tag_metadata["meal-prep"].source == "llm" and t.tag_metadata["meal-prep"].eligibility == "proposed"
    upsert_recipe_tags(str(p), out)
    hard = load_hard_eligible_recipe_tag_slugs(str(p))["r1"]
    assert "meal-prep" not in hard and "nut-free" not in hard  # proposed -> not hard-eligible
    assert "time-4" in hard  # system-derived effort tag is


def test_invalid_llm_shape_is_omitted_not_written(tmp_path):
    p = tmp_path / "tags.json"; shutil.copy(BENCH_TAGS, p)
    client = Client([{"recipe_name": "x", "tags": ["healthy"]}])
    out = tag_recipes(client, [_recipe("r1", 5)], tag_repo_path=str(p))
    assert out == {}
