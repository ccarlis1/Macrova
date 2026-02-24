"""Tests for USDA FoodData Central API client.

Step 2.1: Ingredient API Connection – Lookup Foundation.

Tests use mocked API responses to avoid hitting real endpoints.
"""

import pytest
from unittest.mock import Mock, patch
from dataclasses import asdict

from src.ingestion.usda_client import (
    USDAClient,
    USDALookupResult,
    USDALookupError,
    DataType,
)


class TestUSDALookupResult:
    """Tests for USDALookupResult data model."""

    def test_successful_result_has_required_fields(self):
        """Test that successful result contains all required fields."""
        result = USDALookupResult(
            success=True,
            fdc_id=12345,
            description="Chicken, breast, boneless, skinless, raw",
            data_type=DataType.SR_LEGACY,
            raw_nutrients=[{"nutrientId": 1003, "value": 23.0}],
            raw_measures=[{"id": 1, "measureUnitName": "g"}],
            source_metadata={"api_version": "v1"}
        )
        
        assert result.success is True
        assert result.fdc_id == 12345
        assert result.description == "Chicken, breast, boneless, skinless, raw"
        assert result.data_type == DataType.SR_LEGACY
        assert len(result.raw_nutrients) == 1
        assert result.error_code is None

    def test_failed_result_has_error_info(self):
        """Test that failed result contains error information."""
        result = USDALookupResult(
            success=False,
            fdc_id=None,
            description=None,
            data_type=None,
            raw_nutrients=[],
            raw_measures=[],
            source_metadata={},
            error_code="NOT_FOUND",
            error_message="No results found for 'xyzfoodnotexist'"
        )
        
        assert result.success is False
        assert result.fdc_id is None
        assert result.error_code == "NOT_FOUND"
        assert "xyzfoodnotexist" in result.error_message


class TestDataType:
    """Tests for DataType enum."""

    def test_data_type_priority_order(self):
        """Test that data types have correct priority for selection."""
        # SR Legacy and Foundation are preferred over Branded
        assert DataType.SR_LEGACY.value == "SR Legacy"
        assert DataType.FOUNDATION.value == "Foundation"
        assert DataType.BRANDED.value == "Branded"
        assert DataType.SURVEY.value == "Survey (FNDDS)"


class TestUSDAClient:
    """Tests for USDAClient API interactions."""

    @pytest.fixture
    def mock_api_key(self):
        """Provide test API key."""
        return "TEST_API_KEY_12345"

    @pytest.fixture
    def client(self, mock_api_key):
        """Create USDAClient with test API key."""
        return USDAClient(api_key=mock_api_key)

    # === Successful Lookup Tests ===

    def test_lookup_successful_sr_legacy(self, client):
        """Test successful lookup returning SR Legacy result."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 171705,
                    "description": "Chicken, broilers or fryers, breast, boneless, skinless, raw",
                    "dataType": "SR Legacy",
                    "foodNutrients": [
                        {"nutrientId": 1003, "nutrientName": "Protein", "value": 22.5, "unitName": "G"},
                        {"nutrientId": 1004, "nutrientName": "Total lipid (fat)", "value": 2.62, "unitName": "G"},
                    ]
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken breast")
        
        assert result.success is True
        assert result.fdc_id == 171705
        assert "Chicken" in result.description
        assert result.data_type == DataType.SR_LEGACY
        assert len(result.raw_nutrients) == 2
        assert result.error_code is None

    def test_lookup_successful_foundation(self, client):
        """Test successful lookup returning Foundation result."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 789012,
                    "description": "Egg, whole, raw",
                    "dataType": "Foundation",
                    "foodNutrients": [
                        {"nutrientId": 1003, "nutrientName": "Protein", "value": 12.6, "unitName": "G"},
                    ]
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("egg")
        
        assert result.success is True
        assert result.data_type == DataType.FOUNDATION

    def test_lookup_prefers_sr_legacy_over_branded(self, client):
        """Test that SR Legacy is preferred over Branded when both exist."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 111111,
                    "description": "CHICKEN BREAST, BRANDED PRODUCT",
                    "dataType": "Branded",
                    "foodNutrients": []
                },
                {
                    "fdcId": 222222,
                    "description": "Chicken, breast, raw",
                    "dataType": "SR Legacy",
                    "foodNutrients": []
                },
            ],
            "totalHits": 2
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken breast")
        
        # Should select SR Legacy (fdcId 222222), not Branded
        assert result.success is True
        assert result.fdc_id == 222222
        assert result.data_type == DataType.SR_LEGACY

    def test_lookup_prefers_foundation_over_branded(self, client):
        """Test that Foundation is preferred over Branded when both exist."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 111111,
                    "description": "SALMON, BRANDED",
                    "dataType": "Branded",
                    "foodNutrients": []
                },
                {
                    "fdcId": 333333,
                    "description": "Salmon, Atlantic, raw",
                    "dataType": "Foundation",
                    "foodNutrients": []
                },
            ],
            "totalHits": 2
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("salmon")
        
        assert result.fdc_id == 333333
        assert result.data_type == DataType.FOUNDATION

    def test_lookup_falls_back_to_branded_if_only_option(self, client):
        """Test that Branded is used if no other data types available."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 444444,
                    "description": "PROTEIN POWDER, WHEY",
                    "dataType": "Branded",
                    "foodNutrients": [
                        {"nutrientId": 1003, "nutrientName": "Protein", "value": 80.0, "unitName": "G"},
                    ]
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("whey protein powder")
        
        assert result.success is True
        assert result.fdc_id == 444444
        assert result.data_type == DataType.BRANDED

    def test_lookup_returns_raw_nutrients_unmodified(self, client):
        """Test that raw nutrients are returned as-is from API."""
        mock_nutrients = [
            {"nutrientId": 1003, "nutrientName": "Protein", "value": 22.5, "unitName": "G"},
            {"nutrientId": 1004, "nutrientName": "Total lipid (fat)", "value": 2.62, "unitName": "G"},
            {"nutrientId": 1005, "nutrientName": "Carbohydrate, by difference", "value": 0.0, "unitName": "G"},
            {"nutrientId": 1008, "nutrientName": "Energy", "value": 120, "unitName": "KCAL"},
        ]
        mock_response = {
            "foods": [
                {
                    "fdcId": 171705,
                    "description": "Chicken breast",
                    "dataType": "SR Legacy",
                    "foodNutrients": mock_nutrients
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken")
        
        # Raw nutrients should be unchanged
        assert result.raw_nutrients == mock_nutrients

    def test_lookup_returns_raw_measures_if_available(self, client):
        """Test that portion measures are returned if available."""
        mock_measures = [
            {"id": 1, "measureUnitName": "cup", "gramWeight": 140.0},
            {"id": 2, "measureUnitName": "oz", "gramWeight": 28.35},
        ]
        mock_response = {
            "foods": [
                {
                    "fdcId": 171705,
                    "description": "Chicken breast",
                    "dataType": "SR Legacy",
                    "foodNutrients": [],
                    "foodMeasures": mock_measures
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken")
        
        assert result.raw_measures == mock_measures

    def test_lookup_includes_source_metadata(self, client):
        """Test that source metadata is included in result."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 171705,
                    "description": "Chicken breast",
                    "dataType": "SR Legacy",
                    "foodNutrients": [],
                    "publicationDate": "2021-10-28",
                    "foodCode": "05064"
                }
            ],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken")
        
        assert "query" in result.source_metadata
        assert result.source_metadata["query"] == "chicken"

    # === No Results Tests ===

    def test_lookup_no_results_returns_structured_failure(self, client):
        """Test that no results returns structured failure, not exception."""
        mock_response = {
            "foods": [],
            "totalHits": 0
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("xyzfoodthatdoesnotexist123")
        
        assert result.success is False
        assert result.fdc_id is None
        assert result.error_code == "NOT_FOUND"
        assert "xyzfoodthatdoesnotexist123" in result.error_message

    def test_lookup_empty_query_returns_failure(self, client):
        """Test that empty query returns structured failure."""
        result = client.lookup("")
        
        assert result.success is False
        assert result.error_code == "INVALID_QUERY"

    def test_lookup_whitespace_query_returns_failure(self, client):
        """Test that whitespace-only query returns structured failure."""
        result = client.lookup("   ")
        
        assert result.success is False
        assert result.error_code == "INVALID_QUERY"

    # === API Error Tests ===

    def test_lookup_api_error_returns_structured_failure(self, client):
        """Test that API errors return structured failure."""
        with patch.object(client, '_make_request', side_effect=USDALookupError("API_ERROR", "Connection failed")):
            result = client.lookup("chicken")
        
        assert result.success is False
        assert result.error_code == "API_ERROR"

    def test_lookup_rate_limited_returns_meaningful_error(self, client):
        """Test that rate limiting returns meaningful error message."""
        with patch.object(client, '_make_request', side_effect=USDALookupError("RATE_LIMITED", "Too many requests")):
            result = client.lookup("chicken")
        
        assert result.success is False
        assert result.error_code == "RATE_LIMITED"
        assert "rate" in result.error_message.lower() or "too many" in result.error_message.lower()

    # === API Key Tests ===

    def test_client_requires_api_key(self):
        """Test that client requires API key."""
        with pytest.raises(ValueError, match="API key"):
            USDAClient(api_key="")

    def test_client_from_environment_variable(self, monkeypatch, mock_api_key):
        """Test that client can read API key from environment."""
        monkeypatch.setenv("USDA_API_KEY", mock_api_key)
        
        client = USDAClient.from_env()
        assert client.api_key == mock_api_key

    def test_client_from_env_raises_if_not_set(self, monkeypatch):
        """Test that from_env raises if environment variable not set."""
        monkeypatch.delenv("USDA_API_KEY", raising=False)
        
        with pytest.raises(ValueError, match="USDA_API_KEY"):
            USDAClient.from_env()


class TestLookupValidatedIngredient:
    """Tests for lookup using ValidatedIngredient with canonical_name."""

    @pytest.fixture
    def client(self):
        """Create USDAClient with test API key."""
        return USDAClient(api_key="TEST_KEY")

    def test_lookup_validated_uses_canonical_name(self, client):
        """Test that lookup_validated uses canonical_name for search."""
        from src.data_layer.models import ValidatedIngredient
        
        validated = ValidatedIngredient(
            name="Large Boneless Chicken Breast",
            quantity=200.0,
            unit="g",
            normalized_quantity=200.0,
            normalized_unit="g",
            is_to_taste=False,
            canonical_name="chicken breast"
        )
        
        mock_response = {
            "foods": [{
                "fdcId": 171705,
                "description": "Chicken, breast",
                "dataType": "SR Legacy",
                "foodNutrients": []
            }],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response) as mock:
            result = client.lookup_validated(validated)
            # Verify canonical_name was used (not original name)
            mock.assert_called_once_with("chicken breast")
        
        assert result.success is True
        assert result.fdc_id == 171705

    def test_lookup_validated_to_taste_returns_excluded(self, client):
        """Test that 'to taste' ingredients return EXCLUDED error."""
        from src.data_layer.models import ValidatedIngredient
        
        validated = ValidatedIngredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            normalized_quantity=0.0,
            normalized_unit="to taste",
            is_to_taste=True,
            canonical_name="salt"
        )
        
        result = client.lookup_validated(validated)
        
        assert result.success is False
        assert result.error_code == "EXCLUDED"
        assert "to taste" in result.error_message.lower()

    def test_lookup_validated_falls_back_to_name_if_no_canonical(self, client):
        """Test that lookup_validated falls back to name if canonical_name is empty."""
        from src.data_layer.models import ValidatedIngredient
        
        validated = ValidatedIngredient(
            name="salmon",
            quantity=150.0,
            unit="g",
            normalized_quantity=150.0,
            normalized_unit="g",
            is_to_taste=False,
            canonical_name=""  # Empty canonical name
        )
        
        mock_response = {
            "foods": [{
                "fdcId": 123456,
                "description": "Salmon",
                "dataType": "SR Legacy",
                "foodNutrients": []
            }],
            "totalHits": 1
        }
        
        with patch.object(client, '_make_request', return_value=mock_response) as mock:
            result = client.lookup_validated(validated)
            # Should fall back to original name
            mock.assert_called_once_with("salmon")
        
        assert result.success is True


class TestBestMatchSelection:
    """Tests for deterministic best-match selection logic."""

    @pytest.fixture
    def client(self):
        """Create USDAClient with test API key."""
        return USDAClient(api_key="TEST_KEY")

    def test_selects_exact_name_match_first(self, client):
        """Test that exact name match is preferred."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 111,
                    "description": "Chicken, breast, with skin, raw",
                    "dataType": "SR Legacy",
                    "foodNutrients": []
                },
                {
                    "fdcId": 222,
                    "description": "Chicken breast",
                    "dataType": "SR Legacy",
                    "foodNutrients": []
                },
            ],
            "totalHits": 2
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("chicken breast")
        
        # Should prefer the more exact match
        assert result.fdc_id == 222

    def test_selects_first_result_when_no_exact_match(self, client):
        """Test that first result is selected when no exact match."""
        mock_response = {
            "foods": [
                {
                    "fdcId": 111,
                    "description": "Broccoli, raw",
                    "dataType": "SR Legacy",
                    "foodNutrients": []
                },
                {
                    "fdcId": 222,
                    "description": "Broccoli, cooked",
                    "dataType": "SR Legacy",
                    "foodNutrients": []
                },
            ],
            "totalHits": 2
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("broccoli fresh")
        
        # No exact match, should select first SR Legacy
        assert result.fdc_id == 111

    def test_data_type_priority_sr_legacy_first(self, client):
        """Test SR Legacy > Foundation > Survey > Branded priority."""
        mock_response = {
            "foods": [
                {"fdcId": 1, "description": "Rice", "dataType": "Survey (FNDDS)", "foodNutrients": []},
                {"fdcId": 2, "description": "Rice", "dataType": "Branded", "foodNutrients": []},
                {"fdcId": 3, "description": "Rice", "dataType": "Foundation", "foodNutrients": []},
                {"fdcId": 4, "description": "Rice", "dataType": "SR Legacy", "foodNutrients": []},
            ],
            "totalHits": 4
        }
        
        with patch.object(client, '_make_request', return_value=mock_response):
            result = client.lookup("rice")
        
        # Should select SR Legacy (fdcId 4)
        assert result.fdc_id == 4
        assert result.data_type == DataType.SR_LEGACY


class TestNutritionDataRetrieval:
    """Tests for Step 2.3: Nutrition Data Retrieval.
    
    Tests for fetching raw nutrition data using the USDA Food Details endpoint.
    The raw payload is returned unchanged for downstream processing.
    """

    @pytest.fixture
    def client(self):
        """Create USDAClient with test API key."""
        return USDAClient(api_key="TEST_KEY")

    # === Successful Retrieval Tests ===

    def test_get_food_details_returns_raw_payload(self, client):
        """Test that get_food_details returns raw USDA payload unchanged."""
        mock_response = {
            "fdcId": 171705,
            "description": "Chicken, broilers or fryers, breast, skinless, boneless, meat only, raw",
            "dataType": "SR Legacy",
            "publicationDate": "2019-04-01",
            "foodNutrients": [
                {
                    "nutrient": {
                        "id": 1003,
                        "number": "203",
                        "name": "Protein",
                        "rank": 600,
                        "unitName": "g"
                    },
                    "amount": 22.5
                },
                {
                    "nutrient": {
                        "id": 1004,
                        "number": "204",
                        "name": "Total lipid (fat)",
                        "rank": 800,
                        "unitName": "g"
                    },
                    "amount": 2.62
                },
                {
                    "nutrient": {
                        "id": 1008,
                        "number": "208",
                        "name": "Energy",
                        "rank": 300,
                        "unitName": "kcal"
                    },
                    "amount": 120
                }
            ],
            "foodPortions": [
                {
                    "id": 123456,
                    "gramWeight": 100.0,
                    "measureUnit": {"name": "g"}
                }
            ]
        }
        
        with patch.object(client, '_get_food_details_request', return_value=mock_response):
            result = client.get_food_details(171705)
        
        # Verify raw payload is returned unchanged
        assert result.success is True
        assert result.fdc_id == 171705
        assert result.raw_payload == mock_response
        assert len(result.raw_payload["foodNutrients"]) == 3
        
        # Verify specific nutrient data is preserved exactly
        protein = result.raw_payload["foodNutrients"][0]
        assert protein["nutrient"]["id"] == 1003
        assert protein["nutrient"]["name"] == "Protein"
        assert protein["amount"] == 22.5

    def test_get_food_details_preserves_all_nutrients(self, client):
        """Test that all nutrients are preserved without filtering."""
        # Include a variety of macro and micronutrients
        mock_nutrients = [
            {"nutrient": {"id": 1003, "name": "Protein", "unitName": "g"}, "amount": 22.5},
            {"nutrient": {"id": 1004, "name": "Total lipid (fat)", "unitName": "g"}, "amount": 2.62},
            {"nutrient": {"id": 1005, "name": "Carbohydrate, by difference", "unitName": "g"}, "amount": 0.0},
            {"nutrient": {"id": 1008, "name": "Energy", "unitName": "kcal"}, "amount": 120},
            {"nutrient": {"id": 1087, "name": "Calcium, Ca", "unitName": "mg"}, "amount": 5.0},
            {"nutrient": {"id": 1089, "name": "Iron, Fe", "unitName": "mg"}, "amount": 0.37},
            {"nutrient": {"id": 1106, "name": "Vitamin A, RAE", "unitName": "µg"}, "amount": 6.0},
            {"nutrient": {"id": 1162, "name": "Vitamin C, total ascorbic acid", "unitName": "mg"}, "amount": 0.0},
        ]
        
        mock_response = {
            "fdcId": 171705,
            "description": "Chicken breast",
            "dataType": "SR Legacy",
            "foodNutrients": mock_nutrients
        }
        
        with patch.object(client, '_get_food_details_request', return_value=mock_response):
            result = client.get_food_details(171705)
        
        # All 8 nutrients should be preserved
        assert len(result.raw_payload["foodNutrients"]) == 8
        
        # Verify no nutrients were filtered or modified
        returned_ids = [n["nutrient"]["id"] for n in result.raw_payload["foodNutrients"]]
        expected_ids = [1003, 1004, 1005, 1008, 1087, 1089, 1106, 1162]
        assert returned_ids == expected_ids

    def test_get_food_details_preserves_portion_data(self, client):
        """Test that portion/measure data is preserved."""
        mock_response = {
            "fdcId": 171705,
            "description": "Chicken breast",
            "dataType": "SR Legacy",
            "foodNutrients": [],
            "foodPortions": [
                {
                    "id": 111,
                    "gramWeight": 174.0,
                    "amount": 1.0,
                    "measureUnit": {"name": "breast, bone and skin removed"}
                },
                {
                    "id": 222,
                    "gramWeight": 100.0,
                    "amount": 100.0,
                    "measureUnit": {"name": "g"}
                }
            ]
        }
        
        with patch.object(client, '_get_food_details_request', return_value=mock_response):
            result = client.get_food_details(171705)
        
        assert "foodPortions" in result.raw_payload
        assert len(result.raw_payload["foodPortions"]) == 2
        assert result.raw_payload["foodPortions"][0]["gramWeight"] == 174.0

    def test_get_food_details_includes_metadata(self, client):
        """Test that metadata fields are included in raw payload."""
        mock_response = {
            "fdcId": 171705,
            "description": "Chicken breast",
            "dataType": "SR Legacy",
            "publicationDate": "2019-04-01",
            "foodClass": "FinalFood",
            "foodCategory": {"description": "Poultry Products"},
            "foodNutrients": []
        }
        
        with patch.object(client, '_get_food_details_request', return_value=mock_response):
            result = client.get_food_details(171705)
        
        assert result.raw_payload["publicationDate"] == "2019-04-01"
        assert result.raw_payload["foodClass"] == "FinalFood"
        assert result.raw_payload["foodCategory"]["description"] == "Poultry Products"

    # === Error Handling Tests ===

    def test_get_food_details_invalid_fdc_id(self, client):
        """Test that invalid fdcId returns structured error."""
        result = client.get_food_details(0)
        
        assert result.success is False
        assert result.error_code == "INVALID_FDC_ID"

    def test_get_food_details_negative_fdc_id(self, client):
        """Test that negative fdcId returns structured error."""
        result = client.get_food_details(-123)
        
        assert result.success is False
        assert result.error_code == "INVALID_FDC_ID"

    def test_get_food_details_not_found(self, client):
        """Test that non-existent fdcId returns NOT_FOUND error."""
        with patch.object(client, '_get_food_details_request', 
                         side_effect=USDALookupError("NOT_FOUND", "Food not found")):
            result = client.get_food_details(999999999)
        
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    def test_get_food_details_api_error(self, client):
        """Test that API errors are surfaced properly."""
        with patch.object(client, '_get_food_details_request',
                         side_effect=USDALookupError("API_ERROR", "Server error")):
            result = client.get_food_details(171705)
        
        assert result.success is False
        assert result.error_code == "API_ERROR"
        assert "Server error" in result.error_message

    def test_get_food_details_rate_limited(self, client):
        """Test that rate limiting is surfaced properly."""
        with patch.object(client, '_get_food_details_request',
                         side_effect=USDALookupError("RATE_LIMITED", "Too many requests")):
            result = client.get_food_details(171705)
        
        assert result.success is False
        assert result.error_code == "RATE_LIMITED"

    # === JSON Serializable Tests ===

    def test_get_food_details_result_is_json_serializable(self, client):
        """Test that result can be serialized to JSON."""
        import json
        
        mock_response = {
            "fdcId": 171705,
            "description": "Chicken breast",
            "dataType": "SR Legacy",
            "foodNutrients": [
                {"nutrient": {"id": 1003, "name": "Protein"}, "amount": 22.5}
            ]
        }
        
        with patch.object(client, '_get_food_details_request', return_value=mock_response):
            result = client.get_food_details(171705)
        
        # Should not raise
        json_str = json.dumps(result.raw_payload)
        assert "171705" in json_str
        assert "Protein" in json_str


class TestFoodDetailsResult:
    """Tests for FoodDetailsResult data model."""

    def test_successful_result_structure(self):
        """Test that successful result has required fields."""
        from src.ingestion.usda_client import FoodDetailsResult
        
        result = FoodDetailsResult(
            success=True,
            fdc_id=171705,
            raw_payload={"fdcId": 171705, "foodNutrients": []},
            error_code=None,
            error_message=None
        )
        
        assert result.success is True
        assert result.fdc_id == 171705
        assert result.raw_payload is not None
        assert result.error_code is None

    def test_failure_result_structure(self):
        """Test that failure result has error info."""
        from src.ingestion.usda_client import FoodDetailsResult
        
        result = FoodDetailsResult.failure(
            fdc_id=999999,
            error_code="NOT_FOUND",
            error_message="Food not found"
        )
        
        assert result.success is False
        assert result.fdc_id == 999999
        assert result.raw_payload == {}
        assert result.error_code == "NOT_FOUND"
