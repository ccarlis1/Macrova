import pytest

from src.llm.ingredient_matcher import (
    IngredientMatchingError,
    match_ingredient_queries,
    validate_matches,
)
from src.llm.schemas import IngredientMatchResult
from src.providers.ingredient_provider import IngredientDataProvider


class DummyLLMClient:
    def __init__(self, *, raw_response):
        self._raw_response = raw_response
        self.calls = []

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema_name": schema_name,
                "temperature": temperature,
            }
        )
        return self._raw_response


class FakeProvider(IngredientDataProvider):
    def __init__(self, *, ingredient_info_by_name):
        self.ingredient_info_by_name = ingredient_info_by_name
        self.resolve_calls = []

    def get_ingredient_info(self, name: str):
        return self.ingredient_info_by_name.get(name.lower())

    def resolve_all(self, ingredient_names):
        self.resolve_calls.append(list(ingredient_names))


def test_match_ingredient_queries_happy_path_preserves_order_and_overrides_query():
    raw = {
        "matches": [
            {
                "query": "SHOULD_BE_IGNORED",
                "normalized_name": "chicken breast",
                "confidence": 0.91,
            },
            {
                "query": "ALSO_IGNORED",
                "normalized_name": "rice",
                "confidence": 0.8,
            },
        ]
    }
    client = DummyLLMClient(raw_response=raw)
    out = match_ingredient_queries(client, queries=[" chicken breast ", "rice"])

    assert [m.query for m in out] == ["chicken breast", "rice"]
    assert [m.normalized_name for m in out] == ["chicken breast", "rice"]
    assert [m.confidence for m in out] == [0.91, 0.8]

    assert len(client.calls) == 1
    assert client.calls[0]["schema_name"] == "IngredientMatchResult[]"


def test_match_ingredient_queries_wrong_count_raises():
    raw = {"matches": [{"query": "x", "normalized_name": "y", "confidence": 0.9}]}
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(IngredientMatchingError) as exc:
        match_ingredient_queries(client, queries=["a", "b"])

    assert exc.value.error_code == "LLM_WRONG_MATCH_COUNT"


def test_match_ingredient_queries_rejects_envelope_extra_keys():
    raw = {"matches": [], "extra": 1}
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(IngredientMatchingError) as exc:
        match_ingredient_queries(client, queries=["a"])

    assert exc.value.error_code == "LLM_ENVELOPE_INVALID_KEYS"


def test_match_ingredient_queries_rejects_invalid_match_schema():
    raw = {
        "matches": [
            {
                "query": "chicken",
                "normalized_name": "chicken breast",
                "confidence": 1.1,  # out of range
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(IngredientMatchingError) as exc:
        match_ingredient_queries(client, queries=["chicken"])

    assert exc.value.error_code == "LLM_MATCH_SCHEMA_VALIDATION_FAILED"


def _ingredient_info(name: str):
    return {"name": name, "per_100g": {"calories": 100.0, "protein_g": 10.0, "fat_g": 5.0, "carbs_g": 20.0}}


def test_validate_matches_low_confidence_rejected_and_order_preserved():
    matches = [
        IngredientMatchResult(query="a", normalized_name="chicken", confidence=0.6),
        IngredientMatchResult(query="b", normalized_name="rice", confidence=0.9),
    ]
    provider = FakeProvider(ingredient_info_by_name={"rice": _ingredient_info("Rice")})

    accepted, rejected = validate_matches(matches, provider)

    assert [m.query for m in accepted] == ["b"]
    assert accepted[0].canonical_name == "Rice"
    assert accepted[0].validation_status == "ACCEPTED"

    assert len(rejected) == 1
    assert rejected[0].error_code == "LOW_CONFIDENCE_MATCH"
    assert rejected[0].field_errors == ["original_query=a"]

    assert provider.resolve_calls == [["rice"]]


def test_validate_matches_ingredient_not_found_rejected():
    matches = [
        IngredientMatchResult(query="q", normalized_name="missing", confidence=0.99),
    ]
    provider = FakeProvider(ingredient_info_by_name={})

    accepted, rejected = validate_matches(matches, provider)

    assert accepted == []
    assert len(rejected) == 1
    assert rejected[0].error_code == "INGREDIENT_NOT_FOUND"
    assert rejected[0].field_errors == ["original_query=q"]


def test_validate_matches_accepts_when_provider_has_info():
    matches = [
        IngredientMatchResult(
            query="q",
            normalized_name="chicken",
            confidence=0.91,
        ),
    ]
    provider = FakeProvider(
        ingredient_info_by_name={"chicken": _ingredient_info("Chicken")},
    )

    accepted, rejected = validate_matches(matches, provider)

    assert rejected == []
    assert len(accepted) == 1
    assert accepted[0].canonical_name == "Chicken"
    assert accepted[0].validation_status == "ACCEPTED"
    assert provider.resolve_calls == [["chicken"]]

