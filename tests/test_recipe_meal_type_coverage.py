"""§4.3: every committed recipe carries a hard-eligible meal_role tag."""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.tag_repository import (
    enrich_tag_meta,
    is_planner_hard_eligible,
    load_recipe_tags,
    resolve,
)

_ROOT = Path(__file__).resolve().parents[1]
_RECIPES = _ROOT / "data" / "recipes" / "recipes.json"
_TAGS = str(_ROOT / "data" / "recipes" / "recipe_tags.json")
_MEAL_ROLE_SLUGS = frozenset({"breakfast", "lunch", "dinner", "snack"})


def _recipe_ids() -> list[str]:
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    recipes = data if isinstance(data, list) else data.get("recipes", [])
    return [str(r["id"]) for r in recipes]


def test_every_recipe_has_at_least_one_meal_role_tag() -> None:
    tags_by_id = load_recipe_tags(_TAGS)
    missing: list[str] = []
    for rid in _recipe_ids():
        entry = tags_by_id.get(rid)
        if entry is None:
            missing.append(f"{rid}: no tags_by_id entry")
            continue
        by_type = entry.tag_slugs_by_type or {}
        context = {str(s).strip().lower() for s in (by_type.get("context") or [])}
        if not (context & _MEAL_ROLE_SLUGS):
            missing.append(f"{rid}: context={sorted(context)}")
    assert missing == [], f"recipes missing meal_role tags: {missing}"


def test_meal_role_registry_slugs_have_meal_role_semantic_class() -> None:
    for slug in sorted(_MEAL_ROLE_SLUGS):
        meta = enrich_tag_meta(resolve(slug, _TAGS))
        assert meta.semantic_class == "meal_role", slug
        assert meta.tag_type == "context", slug
        assert meta.source == "system", slug


def test_hand_meal_role_tags_are_hard_eligible() -> None:
    tags_by_id = load_recipe_tags(_TAGS)
    ineligible: list[str] = []
    for rid in _recipe_ids():
        entry = tags_by_id[rid]
        by_type = entry.tag_slugs_by_type or {}
        roles = [
            s
            for s in (by_type.get("context") or [])
            if str(s).strip().lower() in _MEAL_ROLE_SLUGS
        ]
        meta_map = entry.tag_metadata or {}
        for slug in roles:
            meta = meta_map.get(slug) or resolve(slug, _TAGS)
            if not is_planner_hard_eligible(enrich_tag_meta(meta)):
                ineligible.append(f"{rid}:{slug}")
    assert ineligible == [], f"meal_role tags not hard-eligible: {ineligible}"
