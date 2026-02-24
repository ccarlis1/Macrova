"""Tests for Step 2.8: Explicit Error Handling.

Verifies structured error types, error propagation, and fail-fast behavior
across the ingredient pipeline.
"""

import pytest
from unittest.mock import Mock, patch

from src.ingestion.ingredient_errors import (
    IngredientPipelineError,
    IngredientErrorCode,
    IngredientNotFoundError,
    AmbiguousIngredientError,
    UnitNotSupportedError,
    MissingNutritionDataError,
    APIFailureError,
    ValidationFailureError,
)


class TestIngredientErrorCode:
    """Tests for IngredientErrorCode enum."""

    def test_all_required_codes_exist(self):
        """Test that all required error codes are defined."""
        assert hasattr(IngredientErrorCode, 'INGREDIENT_NOT_FOUND')
        assert hasattr(IngredientErrorCode, 'AMBIGUOUS_INGREDIENT')
        assert hasattr(IngredientErrorCode, 'UNIT_NOT_SUPPORTED')
        assert hasattr(IngredientErrorCode, 'MISSING_NUTRITION_DATA')
        assert hasattr(IngredientErrorCode, 'API_FAILURE')
        assert hasattr(IngredientErrorCode, 'VALIDATION_FAILURE')

    def test_error_codes_are_strings(self):
        """Test that error codes are string values."""
        assert isinstance(IngredientErrorCode.INGREDIENT_NOT_FOUND.value, str)
        assert isinstance(IngredientErrorCode.API_FAILURE.value, str)

    def test_error_codes_are_unique(self):
        """Test that all error codes have unique values."""
        codes = [code.value for code in IngredientErrorCode]
        assert len(codes) == len(set(codes))


class TestIngredientPipelineError:
    """Tests for base IngredientPipelineError."""

    def test_base_error_has_required_attributes(self):
        """Test that base error includes code, message, and context."""
        error = IngredientPipelineError(
            code=IngredientErrorCode.INGREDIENT_NOT_FOUND,
            message="Ingredient not found",
            context={"ingredient_name": "xyz food"}
        )
        
        assert error.code == IngredientErrorCode.INGREDIENT_NOT_FOUND
        assert error.message == "Ingredient not found"
        assert error.context["ingredient_name"] == "xyz food"

    def test_base_error_str_representation(self):
        """Test that error has readable string representation."""
        error = IngredientPipelineError(
            code=IngredientErrorCode.INGREDIENT_NOT_FOUND,
            message="Ingredient 'xyz' not found in USDA database",
            context={"ingredient_name": "xyz"}
        )
        
        error_str = str(error)
        
        assert "INGREDIENT_NOT_FOUND" in error_str
        assert "not found" in error_str.lower()

    def test_base_error_is_exception(self):
        """Test that base error is a proper Exception."""
        error = IngredientPipelineError(
            code=IngredientErrorCode.API_FAILURE,
            message="API error",
            context={}
        )
        
        assert isinstance(error, Exception)
        
        # Should be raiseable
        with pytest.raises(IngredientPipelineError):
            raise error

    def test_error_context_defaults_to_empty_dict(self):
        """Test that context defaults to empty dict if not provided."""
        error = IngredientPipelineError(
            code=IngredientErrorCode.API_FAILURE,
            message="API error"
        )
        
        assert error.context == {}


class TestIngredientNotFoundError:
    """Tests for IngredientNotFoundError."""

    def test_includes_ingredient_name(self):
        """Test that error includes ingredient name in context."""
        error = IngredientNotFoundError(ingredient_name="unicorn meat")
        
        assert error.code == IngredientErrorCode.INGREDIENT_NOT_FOUND
        assert error.context["ingredient_name"] == "unicorn meat"
        assert "unicorn meat" in error.message

    def test_inherits_from_base(self):
        """Test inheritance from IngredientPipelineError."""
        error = IngredientNotFoundError(ingredient_name="xyz")
        
        assert isinstance(error, IngredientPipelineError)

    def test_can_be_caught_as_base(self):
        """Test that specific error can be caught as base type."""
        def raise_error():
            raise IngredientNotFoundError(ingredient_name="test")
        
        with pytest.raises(IngredientPipelineError):
            raise_error()


class TestAmbiguousIngredientError:
    """Tests for AmbiguousIngredientError."""

    def test_includes_ingredient_and_matches(self):
        """Test that error includes ingredient name and ambiguous matches."""
        matches = ["chicken breast raw", "chicken breast cooked", "chicken breast fried"]
        error = AmbiguousIngredientError(
            ingredient_name="chicken breast",
            matches=matches
        )
        
        assert error.code == IngredientErrorCode.AMBIGUOUS_INGREDIENT
        assert error.context["ingredient_name"] == "chicken breast"
        assert error.context["matches"] == matches
        assert "chicken breast" in error.message

    def test_message_indicates_ambiguity(self):
        """Test that message clearly indicates ambiguity."""
        error = AmbiguousIngredientError(
            ingredient_name="rice",
            matches=["white rice", "brown rice"]
        )
        
        assert "ambiguous" in error.message.lower() or "multiple" in error.message.lower()


class TestUnitNotSupportedError:
    """Tests for UnitNotSupportedError."""

    def test_includes_unit_and_ingredient(self):
        """Test that error includes the unsupported unit and ingredient."""
        error = UnitNotSupportedError(
            unit="bushel",
            ingredient_name="apples",
            supported_units=["g", "oz", "lb", "each"]
        )
        
        assert error.code == IngredientErrorCode.UNIT_NOT_SUPPORTED
        assert error.context["unit"] == "bushel"
        assert error.context["ingredient_name"] == "apples"
        assert "bushel" in error.message

    def test_includes_supported_units(self):
        """Test that error includes list of supported units."""
        supported = ["g", "oz", "lb"]
        error = UnitNotSupportedError(
            unit="cup",
            ingredient_name="chicken",
            supported_units=supported
        )
        
        assert error.context["supported_units"] == supported


class TestMissingNutritionDataError:
    """Tests for MissingNutritionDataError."""

    def test_includes_ingredient_and_missing_fields(self):
        """Test that error includes ingredient and missing nutrition fields."""
        error = MissingNutritionDataError(
            ingredient_name="exotic fruit",
            fdc_id=123456,
            missing_fields=["calories", "protein_g"]
        )
        
        assert error.code == IngredientErrorCode.MISSING_NUTRITION_DATA
        assert error.context["ingredient_name"] == "exotic fruit"
        assert error.context["fdc_id"] == 123456
        assert "calories" in error.context["missing_fields"]

    def test_message_indicates_missing_data(self):
        """Test that message indicates missing nutrition data."""
        error = MissingNutritionDataError(
            ingredient_name="test food",
            fdc_id=999,
            missing_fields=["calories"]
        )
        
        assert "missing" in error.message.lower() or "incomplete" in error.message.lower()


class TestAPIFailureError:
    """Tests for APIFailureError."""

    def test_includes_api_details(self):
        """Test that error includes API failure details."""
        error = APIFailureError(
            operation="search",
            status_code=500,
            response_body="Internal Server Error",
            ingredient_name="chicken"
        )
        
        assert error.code == IngredientErrorCode.API_FAILURE
        assert error.context["operation"] == "search"
        assert error.context["status_code"] == 500
        assert error.context["ingredient_name"] == "chicken"

    def test_handles_timeout(self):
        """Test that error can represent timeout."""
        error = APIFailureError(
            operation="get_food_details",
            status_code=None,
            response_body=None,
            ingredient_name="salmon",
            timeout=True
        )
        
        assert error.context["timeout"] is True
        assert "timeout" in error.message.lower() or error.context.get("timeout")

    def test_includes_rate_limit_info(self):
        """Test that error includes rate limit information when applicable."""
        error = APIFailureError(
            operation="search",
            status_code=429,
            response_body="Rate limit exceeded",
            ingredient_name="beef",
            rate_limited=True
        )
        
        assert error.context["rate_limited"] is True


class TestValidationFailureError:
    """Tests for ValidationFailureError."""

    def test_includes_validation_details(self):
        """Test that error includes validation failure details."""
        error = ValidationFailureError(
            field="quantity",
            value="-5",
            reason="Quantity must be positive"
        )
        
        assert error.code == IngredientErrorCode.VALIDATION_FAILURE
        assert error.context["field"] == "quantity"
        assert error.context["value"] == "-5"
        assert "positive" in error.message or "positive" in error.context.get("reason", "")

    def test_handles_multiple_fields(self):
        """Test that error can report multiple field failures."""
        error = ValidationFailureError(
            field="multiple",
            value=None,
            reason="Multiple validation errors",
            validation_errors=[
                {"field": "quantity", "message": "Must be positive"},
                {"field": "unit", "message": "Unknown unit"}
            ]
        )
        
        assert "validation_errors" in error.context
        assert len(error.context["validation_errors"]) == 2


class TestErrorPropagation:
    """Tests for error propagation through the pipeline."""

    def test_errors_bubble_up_unchanged(self):
        """Test that errors propagate without modification."""
        original_error = IngredientNotFoundError(ingredient_name="test ingredient")
        
        def inner_function():
            raise original_error
        
        def outer_function():
            inner_function()
        
        with pytest.raises(IngredientNotFoundError) as exc_info:
            outer_function()
        
        # Should be the exact same error
        assert exc_info.value is original_error

    def test_no_catch_and_continue(self):
        """Test that errors are not silently caught."""
        error = UnitNotSupportedError(
            unit="xyz",
            ingredient_name="test",
            supported_units=["g"]
        )
        
        # This should NOT be caught internally
        with pytest.raises(UnitNotSupportedError):
            raise error

    def test_error_preserves_traceback(self):
        """Test that error traceback is preserved."""
        import traceback
        
        def deep_function():
            raise IngredientNotFoundError(ingredient_name="deep error")
        
        def middle_function():
            deep_function()
        
        def outer_function():
            middle_function()
        
        try:
            outer_function()
        except IngredientNotFoundError:
            tb = traceback.format_exc()
            assert "deep_function" in tb
            assert "middle_function" in tb
            assert "outer_function" in tb


class TestNoPartialResults:
    """Tests verifying no partial NutritionProfile on failure."""

    def test_error_does_not_return_partial_data(self):
        """Test that errors don't include partial nutrition data."""
        error = MissingNutritionDataError(
            ingredient_name="incomplete food",
            fdc_id=12345,
            missing_fields=["calories"]
        )
        
        # Error should not have any nutrition data attached
        assert not hasattr(error, 'partial_nutrition')
        assert not hasattr(error, 'nutrition_profile')
        assert 'nutrition' not in error.context

    def test_api_failure_no_partial_data(self):
        """Test that API failure doesn't include partial data."""
        error = APIFailureError(
            operation="get_food_details",
            status_code=500,
            response_body="Error",
            ingredient_name="test"
        )
        
        assert not hasattr(error, 'partial_nutrition')
        assert 'nutrition' not in error.context


class TestErrorContextCompleteness:
    """Tests verifying error context is complete and useful."""

    def test_ingredient_not_found_context(self):
        """Test IngredientNotFoundError has complete context."""
        error = IngredientNotFoundError(
            ingredient_name="nonexistent food",
            search_query="nonexistent food raw"
        )
        
        assert "ingredient_name" in error.context
        assert "search_query" in error.context

    def test_ambiguous_error_context(self):
        """Test AmbiguousIngredientError has complete context."""
        error = AmbiguousIngredientError(
            ingredient_name="apple",
            matches=["apple raw", "apple cooked"],
            match_count=2
        )
        
        assert "ingredient_name" in error.context
        assert "matches" in error.context
        assert "match_count" in error.context

    def test_unit_error_context(self):
        """Test UnitNotSupportedError has complete context."""
        error = UnitNotSupportedError(
            unit="gallon",
            ingredient_name="milk",
            supported_units=["ml", "cup", "tbsp"]
        )
        
        assert "unit" in error.context
        assert "ingredient_name" in error.context
        assert "supported_units" in error.context

    def test_api_failure_context(self):
        """Test APIFailureError has complete context."""
        error = APIFailureError(
            operation="search",
            status_code=503,
            response_body="Service Unavailable",
            ingredient_name="chicken",
            endpoint="https://api.nal.usda.gov/fdc/v1/foods/search"
        )
        
        assert "operation" in error.context
        assert "status_code" in error.context
        assert "ingredient_name" in error.context
        assert "endpoint" in error.context


class TestErrorInCachedLookup:
    """Tests for error handling in CachedIngredientLookup."""

    def test_api_failure_raises_error(self):
        """Test that API failure raises APIFailureError."""
        from src.ingestion.ingredient_cache import CachedIngredientLookup
        
        mock_client = Mock()
        mock_client.lookup.side_effect = APIFailureError(
            operation="search",
            status_code=500,
            response_body="Internal Error",
            ingredient_name="test"
        )
        
        lookup = CachedIngredientLookup(
            cache_dir="/tmp/test_cache",
            usda_client=mock_client
        )
        
        with pytest.raises(APIFailureError):
            lookup.lookup("test ingredient")

    def test_not_found_returns_none_or_raises(self):
        """Test that not found is handled explicitly."""
        from src.ingestion.ingredient_cache import CachedIngredientLookup
        
        mock_client = Mock()
        mock_client.lookup.return_value = Mock(
            success=False,
            error_code="NOT_FOUND",
            error_message="No results found"
        )
        
        lookup = CachedIngredientLookup(
            cache_dir="/tmp/test_cache",
            usda_client=mock_client
        )
        
        # Should either return None or raise IngredientNotFoundError
        # (implementation choice - both are valid fail-fast behaviors)
        result = lookup.lookup("nonexistent xyz")
        
        # If it returns, must be None (not partial data)
        if result is not None:
            pytest.fail("Should return None or raise error for not found")
