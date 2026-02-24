"""Strict, deterministic ingredient validation for MVP.

Per SYSTEM_RULES.md:
- Inputs must be structured (name, quantity, unit)
- Ambiguous inputs are REJECTED with ValidationError
- No NLP, heuristics, or guessing
- "to taste" ingredients are allowed but excluded from nutrition
- All validation is deterministic and testable

Per Step 2.1 (Ingredient Name Normalization):
- Validated ingredients include canonical_name for USDA API lookup
- Canonical name is lowercased, whitespace-normalized, descriptors removed
"""

from dataclasses import dataclass
from typing import List, Optional

from src.data_layer.models import IngredientInput, ValidatedIngredient
from src.ingestion.ingredient_normalizer import IngredientNormalizer


@dataclass
class ValidationError:
    """Structured validation error for ingredient parsing.
    
    Returns specific field and message for user correction.
    """
    field: str      # Which field failed (name, quantity, unit)
    message: str    # Human-readable error message
    value: str      # The invalid value that was provided


@dataclass
class ValidationResult:
    """Result of ingredient validation.
    
    Either is_valid=True with ingredient set,
    or is_valid=False with errors list populated.
    """
    is_valid: bool
    ingredient: Optional[ValidatedIngredient]
    errors: List[ValidationError]


class IngredientValidator:
    """Strict validator for structured ingredient inputs.
    
    Per SYSTEM_RULES.md:
    - Validates name, quantity, and unit strictly
    - Rejects ambiguous or unsupported inputs
    - Normalizes units to base units (g, ml) where applicable
    - Returns structured ValidationResult for deterministic handling
    
    Per Step 2.1 (Ingredient Name Normalization):
    - Generates canonical_name for USDA API lookup
    - Uses IngredientNormalizer to standardize names
    
    SUPPORTED UNITS:
    - Mass: g, oz, lb
    - Volume: ml, cup, tsp, tbsp
    - Count: large, scoop, serving
    - Special: "to taste" (excluded from nutrition)
    """

    # Supported units (canonical forms)
    SUPPORTED_UNITS = [
        "g", "oz", "lb",           # Mass
        "ml", "cup", "tsp", "tbsp", # Volume
        "large", "scoop", "serving", # Count/special
        "to taste"                   # Excluded from nutrition
    ]

    # Unit aliases → canonical form
    UNIT_ALIASES = {
        # Grams
        "gram": "g",
        "grams": "g",
        # Ounces
        "ounce": "oz",
        "ounces": "oz",
        # Pounds
        "pound": "lb",
        "pounds": "lb",
        # Milliliters
        "milliliter": "ml",
        "milliliters": "ml",
        # Cups
        "cups": "cup",
        # Teaspoons
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        # Tablespoons
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        # Scoops
        "scoops": "scoop",
        # Servings
        "servings": "serving",
    }

    # Unit conversions to base units
    # Mass → grams (g)
    # Volume → milliliters (ml)
    UNIT_CONVERSIONS = {
        "oz": ("g", 28.35),      # 1 oz = 28.35g
        "lb": ("g", 453.592),    # 1 lb = 453.592g
        "cup": ("ml", 240.0),    # 1 cup = 240ml
        "tsp": ("ml", 4.93),     # 1 tsp = 4.93ml
        "tbsp": ("ml", 14.79),   # 1 tbsp = 14.79ml
    }

    # Units that remain as-is (no conversion)
    SPECIAL_UNITS = ["g", "ml", "large", "scoop", "serving", "to taste"]

    def __init__(self):
        """Initialize validator with ingredient normalizer."""
        self._normalizer = IngredientNormalizer()

    def validate(self, ingredient_input: IngredientInput) -> ValidationResult:
        """Validate a structured ingredient input.
        
        Args:
            ingredient_input: IngredientInput with name, quantity, unit
            
        Returns:
            ValidationResult with either validated ingredient or errors
        """
        errors: List[ValidationError] = []

        # Validate name
        name = ingredient_input.name.strip() if ingredient_input.name else ""
        if not name:
            errors.append(ValidationError(
                field="name",
                message="Ingredient name cannot be empty",
                value=ingredient_input.name or ""
            ))

        # Validate and normalize unit first (needed for quantity validation)
        unit_raw = ingredient_input.unit.strip() if ingredient_input.unit else ""
        unit_lower = unit_raw.lower()
        
        if not unit_raw:
            errors.append(ValidationError(
                field="unit",
                message="Unit cannot be empty. Supported units: " + ", ".join(self.SUPPORTED_UNITS),
                value=""
            ))
            canonical_unit = None
        else:
            canonical_unit = self._normalize_unit(unit_lower)
            if canonical_unit is None:
                errors.append(ValidationError(
                    field="unit",
                    message=f"Unsupported unit: '{unit_raw}'. Supported units: {', '.join(self.SUPPORTED_UNITS)}",
                    value=unit_raw
                ))

        # Validate quantity
        quantity = ingredient_input.quantity
        is_to_taste = canonical_unit == "to taste" if canonical_unit else False
        
        if quantity < 0:
            errors.append(ValidationError(
                field="quantity",
                message=f"Quantity cannot be negative: {quantity}",
                value=str(quantity)
            ))
        elif quantity == 0 and not is_to_taste:
            errors.append(ValidationError(
                field="quantity",
                message="Quantity must be positive (non-zero) for measurable ingredients",
                value=str(quantity)
            ))

        # If any errors, return failure
        if errors:
            return ValidationResult(is_valid=False, ingredient=None, errors=errors)

        # Normalize quantity and unit
        normalized_quantity, normalized_unit = self._normalize_quantity_and_unit(
            quantity, canonical_unit
        )

        # For "to taste", force quantity to 0
        if is_to_taste:
            normalized_quantity = 0.0

        # Generate canonical name for USDA API lookup (Step 2.1)
        normalization_result = self._normalizer.normalize(name)
        canonical_name = normalization_result.canonical_name

        # Build validated ingredient
        validated = ValidatedIngredient(
            name=name,
            quantity=quantity,
            unit=canonical_unit,
            normalized_quantity=normalized_quantity,
            normalized_unit=normalized_unit,
            is_to_taste=is_to_taste,
            canonical_name=canonical_name
        )

        return ValidationResult(is_valid=True, ingredient=validated, errors=[])

    def _normalize_unit(self, unit_lower: str) -> Optional[str]:
        """Normalize unit to canonical form.
        
        Args:
            unit_lower: Lowercase unit string
            
        Returns:
            Canonical unit string or None if unsupported
        """
        # Check if it's already a supported unit
        if unit_lower in self.SUPPORTED_UNITS:
            return unit_lower
        
        # Check aliases
        if unit_lower in self.UNIT_ALIASES:
            return self.UNIT_ALIASES[unit_lower]
        
        # Not supported
        return None

    def _normalize_quantity_and_unit(
        self, quantity: float, unit: str
    ) -> tuple:
        """Convert quantity to base unit.
        
        Args:
            quantity: Original quantity
            unit: Canonical unit
            
        Returns:
            Tuple of (normalized_quantity, normalized_unit)
        """
        if unit in self.UNIT_CONVERSIONS:
            base_unit, factor = self.UNIT_CONVERSIONS[unit]
            return (quantity * factor, base_unit)
        
        # Special units remain as-is
        return (quantity, unit)

    def get_supported_units(self) -> List[str]:
        """Get list of supported units.
        
        Returns:
            List of supported unit strings
        """
        return self.SUPPORTED_UNITS.copy()

    def validate_batch(
        self, inputs: List[IngredientInput]
    ) -> List[ValidationResult]:
        """Validate multiple ingredients.
        
        Args:
            inputs: List of IngredientInput objects
            
        Returns:
            List of ValidationResult objects (same order as inputs)
        """
        return [self.validate(inp) for inp in inputs]
