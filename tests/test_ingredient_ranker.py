from src.ingestion.ingredient_ranker import filter_candidates, rank_candidates


def test_filter_candidates_rejects_likely_compound_product_terms():
    foods = [
        {
            "fdcId": 1,
            "description": "Egg salad, with mayonnaise",
            "dataType": "SR Legacy",
        },
        {
            "fdcId": 2,
            "description": "Egg, whole, raw",
            "dataType": "SR Legacy",
        },
    ]

    filtered = filter_candidates("egg", foods)
    assert [f["fdcId"] for f in filtered] == [2]


def test_rank_candidates_prefers_canonical_over_compound_like_candidate():
    foods = [
        {
            "fdcId": 1,
            "description": "Egg salad, with mayonnaise",
            "dataType": "SR Legacy",
        },
        {
            "fdcId": 2,
            "description": "Egg, whole, raw",
            "dataType": "SR Legacy",
        },
    ]

    result = rank_candidates("egg", foods)
    assert result.selected.fdc_id == 2
    assert result.confidence >= 0.0
    assert result.margin >= 0.0
    assert any("margin=" in r for r in result.selection_reasons)
    assert any("confidence=" in r for r in result.selection_reasons)


def test_rank_candidates_is_deterministic_with_stable_tie_breaker():
    # Both candidates are identical in description and data type; only
    # the original index tie-breaker should determine selection.
    foods = [
        {
            "fdcId": 101,
            "description": "Rice, plain, raw",
            "dataType": "SR Legacy",
        },
        {
            "fdcId": 202,
            "description": "Rice, plain, raw",
            "dataType": "SR Legacy",
        },
    ]

    result = rank_candidates("rice", foods)
    assert result.selected.fdc_id == 101
    assert result.top_candidates[0].original_index == 0


def test_rank_candidates_selection_reasons_include_data_type_and_features():
    foods = [
        {
            "fdcId": 303,
            "description": "Egg, whole, raw",
            "dataType": "Foundation",
        },
        {
            "fdcId": 404,
            "description": "Egg, whole, raw",
            "dataType": "SR Legacy",
        },
    ]

    result = rank_candidates("egg", foods)
    assert result.selected.fdc_id == 404  # SR Legacy wins
    reasons = result.selected.score.reasons
    assert any(r.startswith("data_type_priority=") for r in reasons)
    assert any(r.startswith("exact_start_match=") for r in reasons)

