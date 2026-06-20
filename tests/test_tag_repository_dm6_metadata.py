from __future__ import annotations

import json

import pytest

from src.llm.schemas import TagMetaJson
from src.llm.tag_repository import (
    TagRepositoryError,
    _assert_semantic_class,
    create,
    enrich_tag_meta,
    is_planner_hard_eligible,
    list_by_type,
    load_hard_eligible_recipe_tag_slugs,
)


def _meta(
    *,
    slug: str = "quick-prep",
    tag_type: str = "context",
    source: str = "system",
    eligibility: str | None = None,
    semantic_class: str | None = None,
    hard_filter_allowed: bool | None = None,
    display_only: bool | None = None,
) -> TagMetaJson:
    return TagMetaJson(
        slug=slug,
        display="Quick Prep",
        tag_type=tag_type,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        created_at="2026-01-01T00:00:00Z",
        aliases=[],
        eligibility=eligibility,
        semantic_class=semantic_class,
        hard_filter_allowed=hard_filter_allowed,
        display_only=display_only,
    )


def test_enrich_tag_meta_applies_dm6_defaults_for_system_seed_tags():
    enriched = enrich_tag_meta(_meta(tag_type="nutrition"))
    assert enriched.semantic_class == "nutrition_claim"
    assert enriched.hard_filter_allowed is False
    assert enriched.soft_score_allowed is True
    assert enriched.display_only is False
    assert enriched.eligibility is None


def test_enrich_tag_meta_defaults_llm_tags_to_proposed():
    enriched = enrich_tag_meta(_meta(source="llm"))
    assert enriched.eligibility == "proposed"
    assert is_planner_hard_eligible(enriched) is False


def test_is_planner_hard_eligible_rejects_rejected_and_display_only_tags():
    rejected = enrich_tag_meta(_meta(eligibility="rejected"))
    display_only = enrich_tag_meta(
        _meta(semantic_class="identity_hint", tag_type="context")
    )
    assert is_planner_hard_eligible(rejected) is False
    assert is_planner_hard_eligible(display_only) is False


def test_is_planner_hard_eligible_allows_approved_llm_and_user_system_tags():
    approved_llm = enrich_tag_meta(_meta(source="llm", eligibility="approved"))
    user_tag = enrich_tag_meta(_meta(source="user", tag_type="constraint"))
    assert is_planner_hard_eligible(approved_llm) is True
    assert is_planner_hard_eligible(user_tag) is True


def test_list_by_type_exposes_dm6_metadata(tmp_path):
    tag_path = tmp_path / "recipe_tags.json"
    tag_path.write_text(
        json.dumps({"tags_by_id": {}, "tag_registry": {}, "tag_aliases": {}}),
        encoding="utf-8",
    )
    tags = list_by_type(str(tag_path), "nutrition")
    high_fiber = next(tag for tag in tags if tag.slug == "high-fiber")
    assert high_fiber.semantic_class == "nutrition_claim"
    assert high_fiber.hard_filter_allowed is False
    assert high_fiber.soft_score_allowed is True
    assert is_planner_hard_eligible(high_fiber) is False


def test_create_user_tag_persists_dm6_defaults(tmp_path):
    tag_path = tmp_path / "recipe_tags.json"
    tag_path.write_text(
        json.dumps({"tags_by_id": {}, "tag_registry": {}, "tag_aliases": {}}),
        encoding="utf-8",
    )
    created = create(
        path=str(tag_path),
        display="Portable Lunch",
        tag_type="context",
        slug="portable-lunch",
        source="user",
    )
    assert created.semantic_class == "capability"
    assert created.hard_filter_allowed is True
    assert is_planner_hard_eligible(created) is True


def test_assert_semantic_class_rejects_unknown_values():
    with pytest.raises(TagRepositoryError, match="Invalid semantic class"):
        _assert_semantic_class("not-a-class")


def test_load_hard_eligible_recipe_tag_slugs_excludes_proposed_llm_tags(tmp_path):
    tag_path = tmp_path / "recipe_tags.json"
    tag_path.write_text(
        json.dumps(
            {
                "tags_by_id": {
                    "recipe-a": {
                        "cuisine": "shared",
                        "cost_level": "cheap",
                        "prep_time_bucket": "quick_meal",
                        "dietary_flags": [],
                        "tag_slugs_by_type": {"constraint": ["high-protein"]},
                        "tag_metadata": {
                            "high-protein": {
                                "slug": "high-protein",
                                "display": "High Protein",
                                "tag_type": "constraint",
                                "source": "llm",
                                "created_at": "2026-01-01T00:00:00Z",
                                "aliases": [],
                                "eligibility": "proposed",
                            }
                        },
                    }
                },
                "tag_registry": {},
                "tag_aliases": {},
            }
        ),
        encoding="utf-8",
    )
    hard_eligible = load_hard_eligible_recipe_tag_slugs(str(tag_path))
    assert hard_eligible["recipe-a"] == set()
