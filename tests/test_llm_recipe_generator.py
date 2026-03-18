import pytest

from src.llm.recipe_generator import RecipeGenerationError, generate_recipe_drafts
from src.llm.schemas import RecipeDraft


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


def _valid_draft_payload(name: str):
    return {
        "name": name,
        "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
        "instructions": ["Cook it."],
    }


def test_generate_recipe_drafts_happy_path_preserves_order():
    raw = {
        "drafts": [_valid_draft_payload("A"), _valid_draft_payload("B")],
    }
    client = DummyLLMClient(raw_response=raw)
    out = generate_recipe_drafts(client, context={"x": 1}, count=2)

    assert len(out) == 2
    assert isinstance(out[0], RecipeDraft)
    assert [d.name for d in out] == ["A", "B"]

    assert len(client.calls) == 1
    assert client.calls[0]["schema_name"] == "RecipeDraftEnvelope"


def test_generate_recipe_drafts_wrong_count_raises():
    raw = {"drafts": [_valid_draft_payload("A")]}  # expected 2
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=2)

    assert exc.value.error_code == "LLM_WRONG_DRAFT_COUNT"


def test_generate_recipe_drafts_rejects_envelope_extra_keys():
    raw = {"drafts": [], "extra": 1}
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=1)

    assert exc.value.error_code == "LLM_ENVELOPE_INVALID_KEYS"

