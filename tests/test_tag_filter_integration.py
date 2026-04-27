from types import SimpleNamespace

from src.llm.schemas import (
    BudgetLevel,
    DietaryFlag,
    PrepTimeBucket,
    RecipeTagsJson,
)
from src.llm.tag_filtering_service import apply_tag_filtering
from src.llm.tag_filter import filter_recipe_ids_by_preferences


def _tags(*, cuisine: str, cost_level: BudgetLevel, prep_time_bucket: PrepTimeBucket, dietary_flags):
    return RecipeTagsJson(
        cuisine=cuisine,
        cost_level=cost_level,
        prep_time_bucket=prep_time_bucket,
        dietary_flags=dietary_flags,
    )


def test_filter_recipe_ids_basic_cuisine():
    tags_by_id = {
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
        "r2": _tags(
            cuisine="italian",
            cost_level=BudgetLevel.standard,
            prep_time_bucket=PrepTimeBucket.weeknight_meal,
            dietary_flags=[],
        ),
    }

    out = filter_recipe_ids_by_preferences(tags_by_id, preferences={"cuisine": "mexican"})
    assert out == ["r1"]


def test_filter_recipe_ids_multiple_constraints_deterministic_order():
    # Intentionally insert in reverse order to validate stable/deterministic output ordering.
    tags_by_id = {
        "r2": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
    }

    out = filter_recipe_ids_by_preferences(
        tags_by_id,
        preferences={"cuisine": "mexican", "dietary_flags": ["vegan"]},
    )
    assert out == ["r2", "r1"]


def test_filter_recipe_ids_ignores_unknown_preference_fields():
    tags_by_id = {
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
    }

    out = filter_recipe_ids_by_preferences(
        tags_by_id,
        preferences={"cuisine": "mexican", "unknown_field": "ignored", "diet": ["vegan"]},
    )
    assert out == ["r1"]


def test_filter_recipe_ids_fallback_when_all_tags_missing():
    tags_by_id = {"r1": None, "r2": None}

    out = filter_recipe_ids_by_preferences(tags_by_id, preferences={"cuisine": "mexican"})
    assert out == []


def test_filter_recipe_ids_rejects_missing_tag_when_any_tags_present():
    tags_by_id = {
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
        "r2": None,
    }

    out = filter_recipe_ids_by_preferences(tags_by_id, preferences={"cuisine": "mexican"})
    assert out == ["r1"]


def test_filter_recipe_ids_requires_multi_slug_intersection_for_dietary_flags():
    tags_by_id = {
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan, DietaryFlag.gluten_free],
        ),
        "r2": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[DietaryFlag.vegan],
        ),
    }

    out = filter_recipe_ids_by_preferences(
        tags_by_id,
        preferences={"dietary_flags": ["vegan", "gluten-free"]},
    )
    assert out == ["r1"]


def test_apply_tag_filtering_uses_canonical_tags_not_recipe_tags_projection():
    recipes = [
        SimpleNamespace(
            id="r1",
            tags=[{"slug": "vegan", "type": "constraint"}],
        )
    ]
    tags_by_id = {
        "r1": _tags(
            cuisine="mexican",
            cost_level=BudgetLevel.cheap,
            prep_time_bucket=PrepTimeBucket.quick_meal,
            dietary_flags=[],
        )
    }

    out = apply_tag_filtering(
        recipes=recipes,
        tags_by_id=tags_by_id,
        preferences={"dietary_flags": ["vegan"]},
    )

    assert out == []

