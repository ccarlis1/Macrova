import pytest
from unittest.mock import Mock

from src.ingestion.ingredient_cache import CachedIngredientLookup


def _mock_food_details_payload(fdc_id: int):
    return {
        "fdcId": fdc_id,
        "description": "Test ingredient",
        "dataType": "SR Legacy",
        "foodNutrients": [
            {"nutrient": {"id": 1008}, "amount": 10.0},  # calories
            {"nutrient": {"id": 1003}, "amount": 1.0},  # protein
            {"nutrient": {"id": 1004}, "amount": 0.5},  # fat
            {"nutrient": {"id": 1005}, "amount": 0.2},  # carbs
        ],
    }


@pytest.mark.parametrize(
    "resolution_mode,expected_llm_calls,expected_fdc_id",
    [
        ("deterministic", 0, 111),
        ("assisted", 1, 222),
    ],
)
def test_confidence_gates_call_llm_only_in_assisted_mode(
    tmp_path,
    resolution_mode,
    expected_llm_calls,
    expected_fdc_id,
):
    mock_client = Mock()
    # Two identical candidates => extremely small margin => low confidence.
    mock_client.search_candidates.return_value = [
        {"fdcId": 111, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": 222, "description": "egg, raw", "dataType": "SR Legacy"},
    ]
    mock_client.get_food_details.return_value = Mock(
        success=True,
        raw_payload=_mock_food_details_payload(expected_fdc_id),
    )

    llm_disambiguator = Mock()
    llm_disambiguator.choose_fdc_id.return_value = 222

    lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode=resolution_mode,
        confidence_threshold=0.75,
        llm_disambiguator=llm_disambiguator,
    )

    entry = lookup.lookup("egg")
    assert entry is not None
    assert entry.fdc_id == expected_fdc_id

    assert llm_disambiguator.choose_fdc_id.call_count == expected_llm_calls

    if expected_llm_calls:
        args, kwargs = llm_disambiguator.choose_fdc_id.call_args
        assert kwargs["query"] == "egg"
        candidate_ids = [c["fdc_id"] for c in kwargs["candidates"]]
        assert candidate_ids == [111, 222]

    mock_client.get_food_details.assert_called_once_with(expected_fdc_id)

