"""Tests for src/llm/feedback_cache.py — deterministic LLM feedback draft cache."""

import json

import pytest

from src.llm.feedback_cache import (
    FeedbackCache,
    FeedbackCacheError,
    build_feedback_cache_key,
    get_cached_drafts,
    load_feedback_cache,
    upsert_cached_drafts,
)
from src.llm.schemas import RecipeDraft, RecipeIngredientDraft


def _draft(name="Chili"):
    return RecipeDraft(
        name=name,
        ingredients=[RecipeIngredientDraft(name="beans", quantity=100.0, unit="g")],
        instructions=["simmer"],
    )


def _key(**overrides):
    kwargs = dict(
        failure_signature="FM-4:iron_mg",
        feedback_context={"deficit": "iron_mg"},
        recipes_to_generate=2,
        model_version="test-model-1",
    )
    kwargs.update(overrides)
    return build_feedback_cache_key(**kwargs)


class TestCacheKey:
    def test_key_is_deterministic_for_identical_inputs(self):
        assert _key() == _key()

    def test_key_changes_when_any_component_changes(self):
        base = _key()
        assert _key(failure_signature="FM-4:calcium_mg") != base
        assert _key(recipes_to_generate=3) != base
        assert _key(model_version="test-model-2") != base
        assert _key(feedback_context={"deficit": "calcium_mg"}) != base

    def test_key_is_stable_under_dict_key_ordering(self):
        a = _key(feedback_context={"a": 1, "b": 2})
        b = _key(feedback_context={"b": 2, "a": 1})
        assert a == b


class TestLoadAndRoundTrip:
    def test_missing_file_loads_as_empty_cache(self, tmp_path):
        cache = load_feedback_cache(str(tmp_path / "absent.json"))
        assert cache.entries() == {}

    def test_upsert_then_load_round_trips_drafts(self, tmp_path):
        path = str(tmp_path / "cache.json")
        key = _key()
        upsert_cached_drafts(
            cache_path=path,
            cache_schema_version=1,
            cache_key=key,
            drafts=[_draft()],
        )

        cache = load_feedback_cache(path, cache_schema_version=1)
        drafts = get_cached_drafts(cache, key)

        assert drafts is not None
        assert [d.name for d in drafts] == ["Chili"]
        assert isinstance(drafts[0], RecipeDraft)

    def test_schema_version_mismatch_is_treated_as_empty(self, tmp_path):
        path = str(tmp_path / "cache.json")
        upsert_cached_drafts(
            cache_path=path,
            cache_schema_version=1,
            cache_key=_key(),
            drafts=[_draft()],
        )

        cache = load_feedback_cache(path, cache_schema_version=2)
        assert cache.entries() == {}

    def test_unreadable_file_raises_feedback_cache_error(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(FeedbackCacheError):
            load_feedback_cache(str(path))

    def test_get_cached_drafts_returns_none_on_miss(self):
        cache = FeedbackCache(path="unused", entries_by_key={})
        assert get_cached_drafts(cache, "no-such-key") is None

    def test_stored_file_is_canonical_sorted_json(self, tmp_path):
        path = tmp_path / "cache.json"
        upsert_cached_drafts(
            cache_path=str(path),
            cache_schema_version=1,
            cache_key=_key(),
            drafts=[_draft()],
        )

        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["cache_schema_version"] == 1
        assert isinstance(raw["entries_by_key"], dict)
