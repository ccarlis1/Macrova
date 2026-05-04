import pytest

from src.llm.tag_repository import (
    TagConflictError,
    TagInvalidError,
    TagNotFoundError,
    TagRegistry,
    load_recipe_tag_slugs,
    normalize_slug,
    upsert_recipe_tag_slugs,
)


def test_normalize_slug_examples():
    assert normalize_slug("High Fiber") == "high-fiber"
    assert normalize_slug("high fiber!") == "high-fiber"


def test_registry_seeds_curated_tags(tmp_path):
    registry = TagRegistry(str(tmp_path / "recipe_tags.json"))

    nutrition_slugs = {tag.slug for tag in registry.list_by_type("nutrition")}
    time_slugs = {tag.slug for tag in registry.list_by_type("time")}

    assert {"high-omega-3", "high-fiber", "high-calcium"}.issubset(nutrition_slugs)
    assert {"time-0", "time-1", "time-2", "time-3", "time-4"}.issubset(time_slugs)


def test_create_resolve_and_alias(tmp_path):
    registry = TagRegistry(str(tmp_path / "recipe_tags.json"))

    tag = registry.create(display="Meal Prep", type="context")
    registry.add_alias("meal-prep", "batch cooking")

    assert tag.slug == "meal-prep"
    assert registry.resolve("Meal Prep").slug == "meal-prep"
    assert registry.resolve("batch-cooking").slug == "meal-prep"


def test_create_duplicate_conflict_and_unknown_resolve(tmp_path):
    registry = TagRegistry(str(tmp_path / "recipe_tags.json"))
    registry.create(display="Meal Prep", type="context")

    with pytest.raises(TagConflictError):
        registry.create(display="Meal Prep", type="context")

    with pytest.raises(TagNotFoundError):
        registry.resolve("does-not-exist")


def test_merge_rewrites_recipe_slug_assignments_and_alias(tmp_path):
    path = str(tmp_path / "recipe_tags.json")
    registry = TagRegistry(path)
    registry.create(display="Meal Prep", type="context")
    registry.create(display="Batch Cooking", type="context")
    upsert_recipe_tag_slugs(path, {"r1": ["meal-prep"], "r2": ["batch-cooking"]})

    registry.merge("batch-cooking", "meal-prep")

    assert load_recipe_tag_slugs(path) == {"r1": ["meal-prep"], "r2": ["meal-prep"]}
    assert registry.resolve("batch-cooking").slug == "meal-prep"


def test_merge_rejects_different_types(tmp_path):
    registry = TagRegistry(str(tmp_path / "recipe_tags.json"))
    registry.create(display="Meal Prep", type="context")

    with pytest.raises(TagInvalidError):
        registry.merge("meal-prep", "high-fiber")
