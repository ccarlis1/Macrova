"""Tests for IngredientValidator - strict, deterministic ingredient validation.

Per SYSTEM_RULES.md:
- Inputs must be structured (name, quantity, unit)
- Ambiguous inputs are rejected with ValidationError
- No NLP, heuristics, or guessing
- "to taste" ingredients are allowed but excluded from nutrition
"""

import pytest
from dataclasses import asdict

from src.data_layer.models import IngredientInput, ValidatedIngredient
from src.ingestion.ingredient_validator import (
    IngredientValidator,
    ValidationError,
    ValidationResult,
)


class TestIngredientInput:
    """Tests for IngredientInput model."""

    def test_ingredient_input_required_fields(self):
        """Test that IngredientInput requires name, quantity, unit."""
        inp = IngredientInput(name="chicken breast", quantity=200.0, unit="g")
        
        assert inp.name == "chicken breast"
        assert inp.quantity == 200.0
        assert inp.unit == "g"

    def test_ingredient_input_to_taste(self):
        """Test IngredientInput with 'to taste' unit."""
        inp = IngredientInput(name="salt", quantity=0.0, unit="to taste")
        
        assert inp.name == "salt"
        assert inp.quantity == 0.0
        assert inp.unit == "to taste"

    def test_ingredient_input_is_dataclass(self):
        """Test that IngredientInput can be converted to dict."""
        inp = IngredientInput(name="egg", quantity=2.0, unit="large")
        d = asdict(inp)
        
        assert d["name"] == "egg"
        assert d["quantity"] == 2.0
        assert d["unit"] == "large"


class TestValidatedIngredient:
    """Tests for ValidatedIngredient model."""

    def test_validated_ingredient_has_normalized_values(self):
        """Test that ValidatedIngredient includes normalized quantity and unit."""
        ing = ValidatedIngredient(
            name="chicken breast",
            quantity=200.0,
            unit="g",
            normalized_quantity=200.0,
            normalized_unit="g",
            is_to_taste=False,
            canonical_name="chicken breast"
        )
        
        assert ing.normalized_quantity == 200.0
        assert ing.normalized_unit == "g"
        assert ing.is_to_taste is False

    def test_validated_ingredient_to_taste(self):
        """Test ValidatedIngredient for 'to taste' ingredient."""
        ing = ValidatedIngredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            normalized_quantity=0.0,
            normalized_unit="to taste",
            is_to_taste=True,
            canonical_name="salt"
        )
        
        assert ing.is_to_taste is True

    def test_validated_ingredient_has_canonical_name(self):
        """Test that ValidatedIngredient includes canonical_name for API lookup."""
        ing = ValidatedIngredient(
            name="Large Chicken Breast",
            quantity=200.0,
            unit="g",
            normalized_quantity=200.0,
            normalized_unit="g",
            is_to_taste=False,
            canonical_name="chicken breast"  # Normalized: lowercase, "large" removed
        )
        
        assert ing.canonical_name == "chicken breast"
        assert ing.name == "Large Chicken Breast"  # Original preserved


class TestValidationError:
    """Tests for ValidationError model."""

    def test_validation_error_has_field_and_message(self):
        """Test that ValidationError contains field and message."""
        err = ValidationError(
            field="unit",
            message="Unsupported unit: 'xyz'",
            value="xyz"
        )
        
        assert err.field == "unit"
        assert "Unsupported unit" in err.message
        assert err.value == "xyz"


class TestIngredientValidator:
    """Tests for IngredientValidator."""

    @pytest.fixture
    def validator(self):
        """Create an IngredientValidator instance."""
        return IngredientValidator()

    # === Valid Input Tests ===

    def test_validate_valid_grams(self, validator):
        """Test validation of valid input with grams."""
        inp = IngredientInput(name="chicken breast", quantity=200.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.ingredient is not None
        assert result.ingredient.name == "chicken breast"
        assert result.ingredient.quantity == 200.0
        assert result.ingredient.unit == "g"
        assert result.ingredient.normalized_unit == "g"
        assert result.ingredient.is_to_taste is False

    def test_validate_valid_ounces(self, validator):
        """Test validation of valid input with ounces."""
        inp = IngredientInput(name="cheese", quantity=2.0, unit="oz")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "oz"
        # Normalized to grams: 2 oz * 28.35 = 56.7g
        assert result.ingredient.normalized_unit == "g"
        assert abs(result.ingredient.normalized_quantity - 56.7) < 0.1

    def test_validate_valid_cup(self, validator):
        """Test validation of valid input with cup."""
        inp = IngredientInput(name="milk", quantity=1.0, unit="cup")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "cup"
        # Normalized to ml: 1 cup = 240ml
        assert result.ingredient.normalized_unit == "ml"
        assert result.ingredient.normalized_quantity == 240.0

    def test_validate_valid_teaspoon(self, validator):
        """Test validation with teaspoon."""
        inp = IngredientInput(name="salt", quantity=1.0, unit="tsp")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "tsp"
        assert result.ingredient.normalized_unit == "ml"

    def test_validate_valid_tablespoon(self, validator):
        """Test validation with tablespoon."""
        inp = IngredientInput(name="olive oil", quantity=2.0, unit="tbsp")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "tbsp"
        assert result.ingredient.normalized_unit == "ml"

    def test_validate_valid_scoop(self, validator):
        """Test validation with scoop (special unit)."""
        inp = IngredientInput(name="whey protein", quantity=1.0, unit="scoop")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "scoop"
        # Scoop is a special unit, normalized as-is
        assert result.ingredient.normalized_unit == "scoop"

    def test_validate_valid_large(self, validator):
        """Test validation with 'large' (for eggs)."""
        inp = IngredientInput(name="egg", quantity=3.0, unit="large")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "large"
        assert result.ingredient.normalized_unit == "large"

    def test_validate_valid_serving(self, validator):
        """Test validation with explicit serving unit."""
        inp = IngredientInput(name="rice", quantity=2.0, unit="serving")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.unit == "serving"

    def test_validate_to_taste(self, validator):
        """Test validation of 'to taste' ingredient."""
        inp = IngredientInput(name="salt", quantity=0.0, unit="to taste")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.is_to_taste is True
        assert result.ingredient.quantity == 0.0
        assert result.ingredient.normalized_quantity == 0.0

    def test_validate_to_taste_with_nonzero_quantity(self, validator):
        """Test that 'to taste' with quantity > 0 is normalized to 0."""
        inp = IngredientInput(name="pepper", quantity=5.0, unit="to taste")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.is_to_taste is True
        # Quantity normalized to 0 for "to taste"
        assert result.ingredient.normalized_quantity == 0.0

    # === Invalid Input Tests (Rejection Cases) ===

    def test_validate_empty_name_rejected(self, validator):
        """Test that empty name is rejected."""
        inp = IngredientInput(name="", quantity=100.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].field == "name"
        assert "empty" in result.errors[0].message.lower()

    def test_validate_whitespace_name_rejected(self, validator):
        """Test that whitespace-only name is rejected."""
        inp = IngredientInput(name="   ", quantity=100.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert result.errors[0].field == "name"

    def test_validate_negative_quantity_rejected(self, validator):
        """Test that negative quantity is rejected."""
        inp = IngredientInput(name="chicken", quantity=-5.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].field == "quantity"
        assert "negative" in result.errors[0].message.lower()

    def test_validate_zero_quantity_non_to_taste_rejected(self, validator):
        """Test that zero quantity is rejected for non 'to taste' ingredients."""
        inp = IngredientInput(name="chicken", quantity=0.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert result.errors[0].field == "quantity"
        assert "zero" in result.errors[0].message.lower() or "positive" in result.errors[0].message.lower()

    def test_validate_empty_unit_rejected(self, validator):
        """Test that empty unit is rejected."""
        inp = IngredientInput(name="chicken", quantity=100.0, unit="")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert result.errors[0].field == "unit"

    def test_validate_unsupported_unit_rejected(self, validator):
        """Test that unsupported unit is rejected."""
        inp = IngredientInput(name="chicken", quantity=100.0, unit="xyz")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert result.errors[0].field == "unit"
        assert "unsupported" in result.errors[0].message.lower()

    def test_validate_multiple_errors(self, validator):
        """Test that multiple validation errors are collected."""
        inp = IngredientInput(name="", quantity=-5.0, unit="xyz")
        result = validator.validate(inp)
        
        assert result.is_valid is False
        assert len(result.errors) >= 2  # At least name and unit errors

    # === Unit Normalization Tests ===

    def test_normalize_unit_grams_variations(self, validator):
        """Test that gram variations are normalized."""
        for unit in ["g", "gram", "grams", "G", "GRAMS"]:
            inp = IngredientInput(name="chicken", quantity=100.0, unit=unit)
            result = validator.validate(inp)
            
            assert result.is_valid is True, f"Failed for unit: {unit}"
            assert result.ingredient.normalized_unit == "g"

    def test_normalize_unit_ounce_variations(self, validator):
        """Test that ounce variations are normalized."""
        for unit in ["oz", "ounce", "ounces", "OZ"]:
            inp = IngredientInput(name="cheese", quantity=2.0, unit=unit)
            result = validator.validate(inp)
            
            assert result.is_valid is True, f"Failed for unit: {unit}"
            assert result.ingredient.unit == "oz"

    def test_normalize_unit_teaspoon_variations(self, validator):
        """Test that teaspoon variations are normalized."""
        for unit in ["tsp", "teaspoon", "teaspoons", "TSP"]:
            inp = IngredientInput(name="salt", quantity=1.0, unit=unit)
            result = validator.validate(inp)
            
            assert result.is_valid is True, f"Failed for unit: {unit}"
            assert result.ingredient.unit == "tsp"

    def test_normalize_unit_tablespoon_variations(self, validator):
        """Test that tablespoon variations are normalized."""
        for unit in ["tbsp", "tablespoon", "tablespoons", "TBSP"]:
            inp = IngredientInput(name="oil", quantity=1.0, unit=unit)
            result = validator.validate(inp)
            
            assert result.is_valid is True, f"Failed for unit: {unit}"
            assert result.ingredient.unit == "tbsp"

    # === Supported Units List Test ===

    def test_supported_units_documented(self, validator):
        """Test that supported units are accessible."""
        supported = validator.get_supported_units()
        
        assert "g" in supported
        assert "oz" in supported
        assert "cup" in supported
        assert "tsp" in supported
        assert "tbsp" in supported
        assert "scoop" in supported
        assert "large" in supported
        assert "serving" in supported
        assert "to taste" in supported
        assert "ml" in supported
        assert "lb" in supported


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_validation_result_success(self):
        """Test successful validation result."""
        ing = ValidatedIngredient(
            name="chicken",
            quantity=100.0,
            unit="g",
            normalized_quantity=100.0,
            normalized_unit="g",
            is_to_taste=False,
            canonical_name="chicken"
        )
        result = ValidationResult(is_valid=True, ingredient=ing, errors=[])
        
        assert result.is_valid is True
        assert result.ingredient is not None
        assert result.errors == []

    def test_validation_result_failure(self):
        """Test failed validation result."""
        err = ValidationError(field="unit", message="Unsupported unit", value="xyz")
        result = ValidationResult(is_valid=False, ingredient=None, errors=[err])
        
        assert result.is_valid is False
        assert result.ingredient is None
        assert len(result.errors) == 1


class TestCanonicalNameGeneration:
    """Tests for canonical_name generation in IngredientValidator.
    
    Per Step 2.1 (Ingredient Name Normalization):
    - canonical_name is lowercased
    - controlled descriptors are removed
    - result is deterministic for USDA API lookup
    """

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return IngredientValidator()

    def test_canonical_name_is_lowercased(self, validator):
        """Test that canonical_name is lowercased."""
        inp = IngredientInput(name="CHICKEN BREAST", quantity=200.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "chicken breast"

    def test_canonical_name_removes_large(self, validator):
        """Test that 'large' descriptor is removed from canonical_name."""
        inp = IngredientInput(name="Large Egg", quantity=1.0, unit="large")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "egg"

    def test_canonical_name_removes_raw(self, validator):
        """Test that 'raw' descriptor is removed from canonical_name."""
        inp = IngredientInput(name="Raw Chicken Breast", quantity=200.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "chicken breast"

    def test_canonical_name_removes_boneless_skinless(self, validator):
        """Test that 'boneless' and 'skinless' are removed from canonical_name."""
        inp = IngredientInput(name="Boneless Skinless Chicken Thigh", quantity=150.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "chicken thigh"

    def test_canonical_name_removes_organic(self, validator):
        """Test that 'organic' descriptor is removed from canonical_name."""
        inp = IngredientInput(name="Organic Broccoli", quantity=100.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "broccoli"

    def test_canonical_name_removes_fresh(self, validator):
        """Test that 'fresh' descriptor is removed from canonical_name."""
        inp = IngredientInput(name="Fresh Spinach", quantity=50.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "spinach"

    def test_canonical_name_removes_multiple_descriptors(self, validator):
        """Test that multiple descriptors are removed from canonical_name."""
        inp = IngredientInput(name="Large Raw Organic Chicken Breast", quantity=200.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "chicken breast"

    def test_canonical_name_preserves_original_name(self, validator):
        """Test that original name is preserved while canonical_name is normalized."""
        inp = IngredientInput(name="Large Boneless Chicken Breast", quantity=200.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.name == "Large Boneless Chicken Breast"  # Original
        assert result.ingredient.canonical_name == "chicken breast"  # Normalized

    def test_canonical_name_simple_ingredient(self, validator):
        """Test that simple ingredient names are unchanged except for case."""
        inp = IngredientInput(name="Salmon", quantity=150.0, unit="g")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "salmon"

    def test_canonical_name_to_taste_ingredient(self, validator):
        """Test canonical_name for 'to taste' ingredient."""
        inp = IngredientInput(name="Sea Salt", quantity=0.0, unit="to taste")
        result = validator.validate(inp)
        
        assert result.is_valid is True
        assert result.ingredient.canonical_name == "sea salt"
        assert result.ingredient.is_to_taste is True
