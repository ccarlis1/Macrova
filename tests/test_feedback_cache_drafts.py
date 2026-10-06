"""Cached LLM feedback drafts must pass the current validate_recipe_draft (F12a)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.llm.feedback_cache import DEFAULT_FEEDBACK_CACHE_PATH, DEFAULT_CACHE_SCHEMA_VERSION
from src.llm.schemas import RecipeDraft
from src.llm.recipe_validator import validate_recipe_draft

_REPO = Path(__file__).resolve().parents[1]
_CACHE = _REPO / DEFAULT_FEEDBACK_CACHE_PATH


class _StubProvider:
    """Minimal USDA-shaped provider for offline draft validation."""

    def resolve_all(self, names):
        return {n: self.get_ingredient_info(n) for n in names}

    def get_ingredient_info(self, name: str):
        return {
            "name": name,
            "per_100g": {
                "calories": 100.0,
                "protein_g": 10.0,
                "fat_g": 2.0,
                "carbs_g": 10.0,
            },
            "provenance": {"description": name, "fdc_id": 1},
        }


def _all_cached_drafts() -> List[Dict[str, Any]]:
    if not _CACHE.exists():
        return []
    raw = json.loads(_CACHE.read_text(encoding="utf-8"))
    if int(raw.get("cache_schema_version", -1)) != DEFAULT_CACHE_SCHEMA_VERSION:
        return []
    drafts: List[Dict[str, Any]] = []
    for items in (raw.get("entries_by_key") or {}).values():
        if isinstance(items, list):
            drafts.extend([d for d in items if isinstance(d, dict)])
    return drafts


def test_feedback_cache_schema_is_current():
    raw = json.loads(_CACHE.read_text(encoding="utf-8"))
    assert int(raw["cache_schema_version"]) == DEFAULT_CACHE_SCHEMA_VERSION


def test_every_cached_draft_passes_validate_recipe_draft():
    """After the schema bump, stale v1 drafts are ignored; any v2 draft must validate."""
    provider = _StubProvider()
    failures: List[str] = []
    for i, raw_draft in enumerate(_all_cached_drafts()):
        try:
            draft = RecipeDraft.model_validate(raw_draft)
        except Exception as exc:
            failures.append(f"draft[{i}] schema: {exc}")
            continue
        ok, res = validate_recipe_draft(draft, provider)
        if not ok:
            failures.append(f"draft[{i}] {getattr(draft, 'name', '?')}: {res}")
    assert not failures, "Cached drafts failed validation:\n" + "\n".join(failures[:20])
