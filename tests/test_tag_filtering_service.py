"""Tests for src/llm/tag_filtering_service.py — deterministic pool-level tag filtering."""

from src.data_layer.models import Recipe
from src.llm.schemas import RecipeTagsJson
from src.llm.tag_filtering_service import apply_tag_filtering


def _recipe(recipe_id):
    return Recipe(
        id=recipe_id,
        name=f"Recipe {recipe_id}",
        ingredients=[],
        cooking_time_minutes=10,
        instructions=["step"],
    )


def _tags(cuisine):
    return RecipeTagsJson(cuisine=cuisine, cost_level="cheap", prep_time_bucket="quick_meal")


RECIPES = [_recipe("r1"), _recipe("r2"), _recipe("r3")]
TAGS = {
    "r1": _tags("mexican"),
    "r2": _tags("italian"),
    "r3": None,  # missing tag metadata
}


def test_empty_pool_passes_through():
    assert apply_tag_filtering(recipes=[], tags_by_id={}, preferences={"cuisine": "mexican"}) == []


def test_no_preferences_returns_full_pool_as_new_list():
    out = apply_tag_filtering(recipes=RECIPES, tags_by_id=TAGS, preferences={})
    assert out == RECIPES
    assert out is not RECIPES


def test_single_cuisine_filters_and_preserves_input_order():
    out = apply_tag_filtering(
        recipes=RECIPES, tags_by_id=TAGS, preferences={"cuisine": "mexican"}
    )
    assert [r.id for r in out] == ["r1"]


def test_multi_cuisine_or_union():
    out = apply_tag_filtering(
        recipes=RECIPES,
        tags_by_id=TAGS,
        preferences={"cuisine": ["mexican", "italian"]},
    )
    assert [r.id for r in out] == ["r1", "r2"]


def test_empty_filter_result_falls_back_to_full_pool():
    out = apply_tag_filtering(
        recipes=RECIPES, tags_by_id=TAGS, preferences={"cuisine": "klingon"}
    )
    assert [r.id for r in out] == ["r1", "r2", "r3"]


def test_all_tags_missing_falls_back_to_full_pool():
    out = apply_tag_filtering(
        recipes=RECIPES,
        tags_by_id={"r1": None, "r2": None, "r3": None},
        preferences={"cuisine": "mexican"},
    )
    assert [r.id for r in out] == ["r1", "r2", "r3"]


def test_filtering_is_deterministic_across_repeated_calls():
    runs = [
        [r.id for r in apply_tag_filtering(
            recipes=RECIPES, tags_by_id=TAGS, preferences={"cuisine": ["italian", "mexican"]}
        )]
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]
