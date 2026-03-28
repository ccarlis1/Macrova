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


def test_generate_recipe_drafts_prompt_contract_includes_required_forbidden_keys():
    raw = {"drafts": [_valid_draft_payload("A")]}
    client = DummyLLMClient(raw_response=raw)

    generate_recipe_drafts(client, context={}, count=1)

    system_prompt = client.calls[0]["system_prompt"]
    assert '"drafts"' in system_prompt
    assert '"name"' in system_prompt
    assert '"instructions"' in system_prompt
    assert '"ingredients"' in system_prompt
    assert "title" in system_prompt
    assert "servings" in system_prompt
    assert "prep_time" in system_prompt
    assert "cook_time" in system_prompt
    assert "ingredients[].amount" in system_prompt
    assert '"quantity"' in system_prompt
    assert '"unit"' in system_prompt
    assert 'g, oz, lb, ml, cup, tsp, tbsp, large, scoop, serving, to taste' in system_prompt
    assert "unit must match one of these tokens exactly (no other unit strings)." in system_prompt
    assert 'if unit == "to taste" then quantity = 0' in system_prompt
    assert "otherwise quantity > 0" in system_prompt
    assert "count words like 'cloves' into the `unit` field" in system_prompt


def test_generate_recipe_drafts_normalizes_title_amount_and_coerces_instructions():
    raw = {
        "drafts": [
            {
                "title": "Chicken Bowl",
                "ingredients": [
                    {"name": "chicken breast", "amount": 200.0, "unit": "g", "extra": "ignored"}
                ],
                "instructions": "Cook it.",
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    out = generate_recipe_drafts(client, context={}, count=1)

    assert len(out) == 1
    assert out[0].name == "Chicken Bowl"
    assert out[0].ingredients[0].name == "chicken breast"
    assert out[0].ingredients[0].quantity == 200.0
    assert out[0].ingredients[0].unit == "g"
    assert out[0].instructions == ["Cook it."]


def test_generate_recipe_drafts_normalizes_drops_non_schema_metadata_keys():
    raw = {
        "drafts": [
            {
                "name": "A",
                "servings": 2,
                "prep_time": 5,
                "cook_time": 10,
                "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    out = generate_recipe_drafts(client, context={}, count=1)

    assert len(out) == 1
    assert out[0].name == "A"


def test_generate_recipe_drafts_error_details_include_normalization_actions_on_schema_fail():
    # Normalization should apply (title->name, amount->quantity),
    # but schema validation should fail because quantity must be > 0 for unit "g".
    raw = {
        "drafts": [
            {
                "title": "Bad Quantity",
                "ingredients": [{"name": "chicken breast", "amount": 0, "unit": "g"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=1)

    assert exc.value.error_code == "LLM_DRAFT_SCHEMA_VALIDATION_FAILED"
    assert exc.value.details["normalization_applied"] is True
    actions = exc.value.details["normalization_actions"]
    assert "remap draft.title->draft.name" in actions
    assert "remap ingredient[0].amount->ingredient[0].quantity" in actions


def test_generate_recipe_drafts_hard_fails_on_missing_name_and_title():
    raw = {
        "drafts": [
            {
                "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=1)

    assert exc.value.error_code == "LLM_DRAFT_NORMALIZATION_HARDFAIL"


def test_generate_recipe_drafts_hard_fails_on_non_numeric_quantity():
    raw = {
        "drafts": [
            {
                "name": "A",
                "ingredients": [{"name": "chicken breast", "quantity": "two", "unit": "g"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=1)

    assert exc.value.error_code == "LLM_DRAFT_NORMALIZATION_HARDFAIL"


def test_generate_recipe_drafts_accepts_to_taste_quantity_zero():
    raw = {
        "drafts": [
            {
                "name": "A",
                "ingredients": [{"name": "salt", "quantity": 0, "unit": "to taste"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    out = generate_recipe_drafts(client, context={}, count=1)

    assert len(out) == 1
    assert out[0].ingredients[0].unit == "to taste"
    assert out[0].ingredients[0].quantity == 0.0


def test_generate_recipe_drafts_rejects_unsupported_unit_cloves():
    raw = {
        "drafts": [
            {
                "name": "A",
                # LLM should not put count words (like "cloves") into `unit`.
                "ingredients": [{"name": "garlic", "quantity": 1, "unit": "cloves"}],
                "instructions": ["Cook it."],
            }
        ]
    }
    client = DummyLLMClient(raw_response=raw)

    with pytest.raises(RecipeGenerationError) as exc:
        generate_recipe_drafts(client, context={}, count=1)

    assert exc.value.error_code == "LLM_DRAFT_SCHEMA_VALIDATION_FAILED"
    validation_failure = exc.value.details.get("validation_failure", {})
    field_errors = validation_failure.get("field_errors", [])
    assert any("cloves" in err for err in field_errors)

