import pytest

from src.llm.constraint_parser import (
    PlannerConfigParsingError,
    parse_nl_config,
)
from src.llm.schemas import BudgetLevel


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


def test_parse_nl_config_happy_path_validates_schema():
    raw = {
        "days": 3,
        "meals_per_day": 2,
        "targets": {"calories": 2000, "protein": 150.0},
        "preferences": {"cuisine": ["chicken", "salad"], "budget": "cheap"},
    }
    client = DummyLLMClient(raw_response=raw)

    out = parse_nl_config(client, "I want 3 days, 2 meals/day, cheap, chicken")
    assert out.days == 3
    assert out.meals_per_day == 2
    assert out.targets.calories == 2000
    assert out.targets.protein == pytest.approx(150.0)
    assert out.preferences.budget == BudgetLevel.cheap
    assert out.preferences.cuisine == ["chicken", "salad"]

    assert len(client.calls) == 1
    assert client.calls[0]["schema_name"] == "PlannerConfigJson"
    assert client.calls[0]["temperature"] == 0.0


def test_parse_nl_config_rejects_invalid_budget_enum():
    raw = {
        "days": 3,
        "meals_per_day": 2,
        "targets": {"calories": 2000, "protein": 150.0},
        "preferences": {"cuisine": ["chicken"], "budget": "nope"},
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(PlannerConfigParsingError) as exc:
        parse_nl_config(client, "bad config")

    assert exc.value.error_code == "LLM_SCHEMA_VALIDATION_ERROR"
    assert "field_errors" in exc.value.details
    assert exc.value.details["field_errors"]  # non-empty


def test_parse_nl_config_rejects_empty_prompt():
    client = DummyLLMClient(
        raw_response={
            "days": 1,
            "meals_per_day": 1,
            "targets": {"calories": 2000, "protein": 150.0},
            "preferences": {"cuisine": ["chicken"], "budget": "cheap"},
        }
    )

    with pytest.raises(PlannerConfigParsingError) as exc:
        parse_nl_config(client, "   ")

    assert exc.value.error_code == "INVALID_NL_INPUT"

