import pytest

from src.llm.ingredient_disambiguator import (
    ConstrainedIngredientFdcDisambiguator,
    IngredientFdcDisambiguationError,
)


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


def test_constrained_disambiguator_returns_valid_candidate_id():
    dummy = DummyLLMClient(raw_response={"chosen_fdc_id": 222, "confidence": 0.86})
    d = ConstrainedIngredientFdcDisambiguator(dummy)

    chosen = d.choose_fdc_id(
        query="egg",
        candidates=[
            {"fdc_id": 111, "description": "egg salad", "data_type": "SR Legacy"},
            {"fdc_id": 222, "description": "egg, whole, raw", "data_type": "SR Legacy"},
        ],
    )

    assert chosen == 222
    assert len(dummy.calls) == 1
    assert dummy.calls[0]["schema_name"] == d.schema_name


def test_constrained_disambiguator_rejects_out_of_candidate_id():
    dummy = DummyLLMClient(raw_response={"chosen_fdc_id": 999, "confidence": 0.5})
    d = ConstrainedIngredientFdcDisambiguator(dummy)

    with pytest.raises(IngredientFdcDisambiguationError) as exc:
        d.choose_fdc_id(
            query="egg",
            candidates=[
                {"fdc_id": 111, "description": "egg salad", "data_type": "SR Legacy"},
                {"fdc_id": 222, "description": "egg, whole, raw", "data_type": "SR Legacy"},
            ],
        )

    assert exc.value.error_code == "LLM_CHOSEN_FDC_NOT_ALLOWED"


def test_constrained_disambiguator_rejects_schema_invalid_output():
    # Missing `confidence`.
    dummy = DummyLLMClient(raw_response={"chosen_fdc_id": 222})
    d = ConstrainedIngredientFdcDisambiguator(dummy)

    with pytest.raises(IngredientFdcDisambiguationError) as exc:
        d.choose_fdc_id(
            query="egg",
            candidates=[
                {"fdc_id": 111, "description": "egg salad", "data_type": "SR Legacy"},
                {"fdc_id": 222, "description": "egg, whole, raw", "data_type": "SR Legacy"},
            ],
        )

    assert exc.value.error_code == "LLM_SCHEMA_VALIDATION_ERROR"

