import pytest
from unittest.mock import Mock

from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.providers.api_provider import APIIngredientProvider


def _details_payload(*, fdc_id: int, calories: float, protein_g: float, fat_g: float, carbs_g: float):
    return {
        "fdcId": fdc_id,
        "description": f"fdc {fdc_id}",
        "dataType": "SR Legacy",
        "foodNutrients": [
            {"nutrient": {"id": 1008}, "amount": calories},
            {"nutrient": {"id": 1003}, "amount": protein_g},
            {"nutrient": {"id": 1004}, "amount": fat_g},
            {"nutrient": {"id": 1005}, "amount": carbs_g},
        ],
    }


def test_egg_resolves_to_canonical_in_deterministic_mode(tmp_path):
    canonical_fdc_id = 2001
    compound_fdc_id = 2002

    mock_client = Mock()
    mock_client.search_candidates.return_value = [
        # Compound/product-like candidate should be filtered out.
        {
            "fdcId": compound_fdc_id,
            "description": "bagels, egg and cheese",
            "dataType": "SR Legacy",
        },
        {
            "fdcId": canonical_fdc_id,
            "description": "egg, whole, raw",
            "dataType": "SR Legacy",
        },
    ]

    payloads = {
        canonical_fdc_id: _details_payload(
            fdc_id=canonical_fdc_id, calories=140.0, protein_g=12.6, fat_g=9.5, carbs_g=0.7
        ),
        compound_fdc_id: _details_payload(
            fdc_id=compound_fdc_id, calories=1.0, protein_g=0.1, fat_g=0.1, carbs_g=0.0
        ),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="deterministic",
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="deterministic")

    provider.resolve_all(["egg"])
    info = provider.get_ingredient_info("egg")

    assert info["per_100g"]["calories"] == 140.0
    assert info["per_100g"]["protein_g"] == 12.6


def test_rice_resolves_to_canonical_in_deterministic_mode(tmp_path):
    canonical_fdc_id = 3001
    compound_fdc_id = 3002

    mock_client = Mock()
    mock_client.search_candidates.return_value = [
        {
            "fdcId": compound_fdc_id,
            "description": "rice pudding",
            "dataType": "SR Legacy",
        },
        {
            "fdcId": canonical_fdc_id,
            "description": "rice, white, cooked",
            "dataType": "SR Legacy",
        },
    ]

    payloads = {
        canonical_fdc_id: _details_payload(
            fdc_id=canonical_fdc_id, calories=130.0, protein_g=2.7, fat_g=0.3, carbs_g=28.0
        ),
        compound_fdc_id: _details_payload(
            fdc_id=compound_fdc_id, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=9.0
        ),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="deterministic",
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="deterministic")

    provider.resolve_all(["rice"])
    info = provider.get_ingredient_info("rice")

    assert info["per_100g"]["calories"] == 130.0
    assert info["per_100g"]["carbs_g"] == 28.0


def test_deterministic_mode_is_repeatable_across_runs(tmp_path):
    canonical_fdc_id = 2001
    other_fdc_id = 2002

    mock_client = Mock()
    mock_client.search_candidates.return_value = [
        {"fdcId": other_fdc_id, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": canonical_fdc_id, "description": "egg, whole, raw", "dataType": "SR Legacy"},
    ]

    payloads = {
        canonical_fdc_id: _details_payload(
            fdc_id=canonical_fdc_id, calories=140.0, protein_g=12.6, fat_g=9.5, carbs_g=0.7
        ),
        other_fdc_id: _details_payload(
            fdc_id=other_fdc_id, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=1.0
        ),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    results = []
    for run_idx in [1, 2]:
        run_cache_dir = tmp_path / f"run_{run_idx}"
        cached_lookup = CachedIngredientLookup(
            cache_dir=str(run_cache_dir),
            usda_client=mock_client,
            resolution_mode="deterministic",
        )
        provider = APIIngredientProvider(cached_lookup, resolution_mode="deterministic")
        provider.resolve_all(["egg"])
        info = provider.get_ingredient_info("egg")
        results.append(info["per_100g"]["calories"])

    assert results[0] == results[1] == 140.0


def test_assisted_mode_calls_llm_only_when_confidence_low(tmp_path):
    fdc_a = 111
    fdc_b = 222

    mock_client = Mock()
    # Identical candidates => tiny margin => low confidence.
    mock_client.search_candidates.return_value = [
        {"fdcId": fdc_a, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": fdc_b, "description": "egg, raw", "dataType": "SR Legacy"},
    ]

    payloads = {
        fdc_a: _details_payload(fdc_id=fdc_a, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=1.0),
        fdc_b: _details_payload(fdc_id=fdc_b, calories=20.0, protein_g=2.0, fat_g=2.0, carbs_g=2.0),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    llm = Mock()
    llm.choose_fdc_id.return_value = fdc_b

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="assisted",
        confidence_threshold=0.75,
        llm_disambiguator=llm,
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="assisted", confidence_threshold=0.75)

    provider.resolve_all(["egg"])
    info = provider.get_ingredient_info("egg")
    assert info["per_100g"]["calories"] == 20.0

    assert llm.choose_fdc_id.call_count == 1
    mock_client.get_food_details.assert_called_once_with(fdc_b)


def test_assisted_mode_does_not_call_llm_when_confidence_high(tmp_path):
    fdc_a = 111
    fdc_b = 222

    mock_client = Mock()
    # Data type priority difference yields huge margin => high confidence.
    mock_client.search_candidates.return_value = [
        {"fdcId": fdc_a, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": fdc_b, "description": "egg, raw", "dataType": "Branded"},
    ]

    payloads = {
        fdc_a: _details_payload(fdc_id=fdc_a, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=1.0),
        fdc_b: _details_payload(fdc_id=fdc_b, calories=20.0, protein_g=2.0, fat_g=2.0, carbs_g=2.0),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    llm = Mock()
    llm.choose_fdc_id.return_value = fdc_b

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="assisted",
        confidence_threshold=0.75,
        llm_disambiguator=llm,
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="assisted", confidence_threshold=0.75)

    provider.resolve_all(["egg"])
    info = provider.get_ingredient_info("egg")
    assert info["per_100g"]["calories"] == 10.0  # SR Legacy wins deterministically.

    assert llm.choose_fdc_id.call_count == 0
    mock_client.get_food_details.assert_called_once_with(fdc_a)


def test_assisted_mode_rejects_invalid_llm_output_and_falls_back(tmp_path):
    fdc_a = 111
    fdc_b = 222

    mock_client = Mock()
    mock_client.search_candidates.return_value = [
        {"fdcId": fdc_a, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": fdc_b, "description": "egg, raw", "dataType": "SR Legacy"},
    ]

    payloads = {
        fdc_a: _details_payload(fdc_id=fdc_a, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=1.0),
        fdc_b: _details_payload(fdc_id=fdc_b, calories=20.0, protein_g=2.0, fat_g=2.0, carbs_g=2.0),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    llm = Mock()
    # Invalid choice: not in candidate IDs.
    llm.choose_fdc_id.return_value = 999

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="assisted",
        confidence_threshold=0.75,
        llm_disambiguator=llm,
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="assisted", confidence_threshold=0.75)

    provider.resolve_all(["egg"])
    info = provider.get_ingredient_info("egg")
    # Should fall back to ranker selection (first candidate index).
    assert info["per_100g"]["calories"] == 10.0

    assert llm.choose_fdc_id.call_count == 1
    mock_client.get_food_details.assert_called_once_with(fdc_a)


def test_deterministic_mode_never_calls_llm(tmp_path):
    fdc_a = 111
    fdc_b = 222

    mock_client = Mock()
    mock_client.search_candidates.return_value = [
        {"fdcId": fdc_a, "description": "egg, raw", "dataType": "SR Legacy"},
        {"fdcId": fdc_b, "description": "egg, raw", "dataType": "SR Legacy"},
    ]

    payloads = {
        fdc_a: _details_payload(fdc_id=fdc_a, calories=10.0, protein_g=1.0, fat_g=1.0, carbs_g=1.0),
        fdc_b: _details_payload(fdc_id=fdc_b, calories=20.0, protein_g=2.0, fat_g=2.0, carbs_g=2.0),
    }
    mock_client.get_food_details.side_effect = (
        lambda fdc_id: Mock(success=True, raw_payload=payloads[fdc_id])
    )

    llm = Mock()
    llm.choose_fdc_id.return_value = fdc_b

    cached_lookup = CachedIngredientLookup(
        cache_dir=str(tmp_path),
        usda_client=mock_client,
        resolution_mode="deterministic",
        confidence_threshold=0.75,
        llm_disambiguator=llm,
    )
    provider = APIIngredientProvider(cached_lookup, resolution_mode="deterministic", confidence_threshold=0.75)

    provider.resolve_all(["egg"])
    info = provider.get_ingredient_info("egg")
    assert info["per_100g"]["calories"] == 10.0

    assert llm.choose_fdc_id.call_count == 0
    mock_client.get_food_details.assert_called_once_with(fdc_a)

