"""Nutrition scaling by quantity and unit (Step 2.5).

This module scales normalized nutrition data to reflect user-specified quantities.
Scaling is deterministic - no heuristics, density assumptions, or silent fallbacks.

DESIGN DECISIONS:
- Strict unit → gram conversion table (explicit, documented)
- Unknown units RAISE errors (no guessing)
- Volume units (cup, tbsp, tsp) require explicit weight info (no density assumptions)
- Special units (large, scoop, serving) require context or explicit weight
- Scale factor = actual_grams / base_grams

WHY SCALING IS SEPARATE FROM NUTRIENT MAPPING:
1. Mapping converts IDs → field names (schema transformation)
2. Scaling adjusts quantities (mathematical transformation)
3. Different concerns, different error modes
4. Mapping errors are data issues; scaling errors are user input issues
5. Easier to debug when each layer has single responsibility

HOW THIS AVOIDS DOWNSTREAM BUGS IN MEAL AGGREGATION:
- Explicit errors surface early (before aggregation)
- No silent fallbacks that produce incorrect totals
- Scale factor preserved for debugging
- All values numeric (no string contamination)
"""

from dataclasses import dataclass, fields
from typing import Dict, Optional

from src.ingestion.nutrient_mapper import MappedNutrition
from src.data_layer.models import NutritionProfile, MicronutrientProfile


# ============================================================================
# UNIT TO GRAM CONVERSION TABLE
# ============================================================================
#
# This is the authoritative mapping from units to grams.
# Only mass-based conversions are supported without additional context.
#
# Volume units (cup, tbsp, tsp) are NOT included because:
# - Density varies by ingredient (1 cup flour ≠ 1 cup water ≠ 1 cup oil)
# - Guessing density leads to significant errors
# - User must provide explicit weight or use mass units
# ============================================================================

UNIT_TO_GRAMS: Dict[str, float] = {
    # Mass units - direct conversion
    "g": 1.0,           # gram (base unit)
    "oz": 28.35,        # ounce
    "lb": 453.592,      # pound
    
    # Volume units with water-equivalent (for liquids only)
    # Note: These should only be used for water/water-like liquids
    "ml": 1.0,          # milliliter (1ml water ≈ 1g)
}

# Units that are NOT in UNIT_TO_GRAMS and require special handling:
# - "cup", "tbsp", "tsp": Volume units requiring density info
# - "large", "medium", "small": Count units requiring base serving weight
# - "scoop", "serving": Context-dependent, require explicit weight


# ============================================================================
# BASE SERVING WEIGHTS
# ============================================================================
#
# Common serving weights for count-based units.
# Format: unit -> {ingredient_context -> weight_in_grams}
#
# These are used when user specifies units like "2 large eggs"
# ============================================================================

BASE_SERVING_WEIGHTS: Dict[str, Dict[str, float]] = {
    "large": {
        "egg": 50.0,        # 1 large egg ≈ 50g
        "eggs": 50.0,       # Plural variant
        "banana": 118.0,    # 1 large banana ≈ 118g
        "apple": 182.0,     # 1 large apple ≈ 182g
        "orange": 184.0,    # 1 large orange ≈ 184g
        "potato": 299.0,    # 1 large potato ≈ 299g
        "tomato": 182.0,    # 1 large tomato ≈ 182g
        "avocado": 201.0,   # 1 large avocado ≈ 201g
        "onion": 150.0,     # 1 large onion ≈ 150g
    },
    "medium": {
        "egg": 44.0,        # 1 medium egg ≈ 44g
        "eggs": 44.0,
        "banana": 105.0,    # 1 medium banana ≈ 105g
        "apple": 138.0,     # 1 medium apple ≈ 138g
        "potato": 150.0,    # 1 medium potato ≈ 150g
    },
    "small": {
        "egg": 38.0,        # 1 small egg ≈ 38g
        "eggs": 38.0,
        "banana": 81.0,     # 1 small banana ≈ 81g
        "apple": 101.0,     # 1 small apple ≈ 101g
    },
    # Scoop and serving require explicit weight - no defaults
    "scoop": {},
    "serving": {},
}


class UnsupportedUnitError(Exception):
    """Raised when a unit cannot be converted to grams.
    
    This error is raised when:
    - Unit is not in the conversion table
    - Volume unit used without density information
    - Count unit used without serving weight context
    
    Attributes:
        unit: The unsupported unit string
        message: Human-readable error message
    """
    def __init__(self, unit: str, message: str):
        self.unit = unit
        self.message = message
        super().__init__(f"Unsupported unit '{unit}': {message}")


@dataclass
class ScaledNutrition:
    """Nutrition data scaled to actual ingredient quantity.
    
    This is the output of NutritionScaler.scale().
    Includes the scale factor and actual grams for debugging/auditing.
    
    Attributes:
        calories: Scaled calories
        protein_g: Scaled protein in grams
        fat_g: Scaled fat in grams
        carbs_g: Scaled carbs in grams
        micronutrients: Scaled MicronutrientProfile
        scale_factor: Factor used for scaling (actual_grams / base_grams)
        actual_grams: Resolved weight in grams
    """
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    micronutrients: MicronutrientProfile
    scale_factor: float
    actual_grams: float
    
    def to_nutrition_profile(self) -> NutritionProfile:
        """Convert to NutritionProfile for use in recipes/meals.
        
        Returns:
            NutritionProfile with scaled values
        """
        return NutritionProfile(
            calories=self.calories,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            carbs_g=self.carbs_g,
            micronutrients=self.micronutrients
        )


class NutritionScaler:
    """Scales nutrition data to reflect user-specified quantities.
    
    This scaler:
    1. Converts user unit to grams
    2. Computes scale factor (actual_grams / base_grams)
    3. Multiplies all nutrition values by scale factor
    
    Unknown units raise UnsupportedUnitError - no silent fallbacks.
    
    Usage:
        scaler = NutritionScaler()
        
        # Scale 200g of chicken (base is 100g from USDA)
        result = scaler.scale(
            nutrition=mapped_nutrition,
            quantity=200.0,
            unit="g",
            base_grams=100.0
        )
        
        # Scale 2 large eggs
        result = scaler.scale(
            nutrition=egg_nutrition,
            quantity=2.0,
            unit="large",
            base_grams=100.0,
            ingredient_context="egg"
        )
    """
    
    def scale(
        self,
        nutrition: MappedNutrition,
        quantity: float,
        unit: str,
        base_grams: float,
        ingredient_context: Optional[str] = None,
        serving_weight_grams: Optional[float] = None
    ) -> ScaledNutrition:
        """Scale nutrition data to actual quantity.
        
        Args:
            nutrition: Mapped nutrition per base_grams
            quantity: User-specified quantity
            unit: User-specified unit (g, oz, lb, large, etc.)
            base_grams: Base weight for nutrition data (usually 100g from USDA)
            ingredient_context: Optional ingredient name for count units (e.g., "egg")
            serving_weight_grams: Optional explicit serving weight in grams
            
        Returns:
            ScaledNutrition with all values adjusted
            
        Raises:
            UnsupportedUnitError: If unit cannot be converted
            ValueError: If quantity or base_grams are invalid
        """
        # Validate inputs
        if quantity < 0:
            raise ValueError(f"Invalid quantity: {quantity}. Must be non-negative.")
        if base_grams <= 0:
            raise ValueError(f"Invalid base_grams: {base_grams}. Must be positive.")
        
        # Handle zero quantity (edge case)
        if quantity == 0:
            return self._create_zero_result()
        
        # Convert unit to grams
        actual_grams = self._resolve_grams(
            quantity=quantity,
            unit=unit,
            ingredient_context=ingredient_context,
            serving_weight_grams=serving_weight_grams
        )
        
        # Compute scale factor
        scale_factor = actual_grams / base_grams
        
        # Scale macronutrients
        scaled_calories = nutrition.calories * scale_factor
        scaled_protein = nutrition.protein_g * scale_factor
        scaled_fat = nutrition.fat_g * scale_factor
        scaled_carbs = nutrition.carbs_g * scale_factor
        
        # Scale micronutrients
        scaled_micros = self._scale_micronutrients(
            nutrition.micronutrients,
            scale_factor
        )
        
        return ScaledNutrition(
            calories=scaled_calories,
            protein_g=scaled_protein,
            fat_g=scaled_fat,
            carbs_g=scaled_carbs,
            micronutrients=scaled_micros,
            scale_factor=scale_factor,
            actual_grams=actual_grams
        )
    
    def _resolve_grams(
        self,
        quantity: float,
        unit: str,
        ingredient_context: Optional[str],
        serving_weight_grams: Optional[float]
    ) -> float:
        """Convert quantity + unit to total grams.
        
        Args:
            quantity: Numeric quantity
            unit: Unit string
            ingredient_context: Optional ingredient name
            serving_weight_grams: Optional explicit serving weight
            
        Returns:
            Total weight in grams
            
        Raises:
            UnsupportedUnitError: If conversion not possible
        """
        unit_lower = unit.lower()
        
        # Check direct mass conversions first
        if unit_lower in UNIT_TO_GRAMS:
            return quantity * UNIT_TO_GRAMS[unit_lower]
        
        # Check if explicit serving weight provided
        if serving_weight_grams is not None:
            return quantity * serving_weight_grams
        
        # Check count-based units with context
        if unit_lower in BASE_SERVING_WEIGHTS:
            return self._resolve_count_unit(
                quantity=quantity,
                unit=unit_lower,
                ingredient_context=ingredient_context
            )
        
        # Check volume units (require density info)
        if unit_lower in ("cup", "cups", "tbsp", "tablespoon", "tsp", "teaspoon"):
            raise UnsupportedUnitError(
                unit=unit,
                message="Volume units require explicit weight (serving_weight_grams). "
                        "Density varies by ingredient."
            )
        
        # Unknown unit
        raise UnsupportedUnitError(
            unit=unit,
            message=f"Unit not in conversion table. Supported mass units: {list(UNIT_TO_GRAMS.keys())}"
        )
    
    def _resolve_count_unit(
        self,
        quantity: float,
        unit: str,
        ingredient_context: Optional[str]
    ) -> float:
        """Resolve count-based units (large, medium, small, etc.) to grams.
        
        Args:
            quantity: Number of items
            unit: Size descriptor (large, medium, small)
            ingredient_context: Ingredient name to look up weight
            
        Returns:
            Total weight in grams
            
        Raises:
            UnsupportedUnitError: If context not provided or ingredient unknown
        """
        if ingredient_context is None:
            raise UnsupportedUnitError(
                unit=unit,
                message=f"Count unit '{unit}' requires ingredient_context "
                        f"(e.g., ingredient_context='egg')"
            )
        
        context_lower = ingredient_context.lower()
        serving_weights = BASE_SERVING_WEIGHTS.get(unit, {})
        
        # Look up weight for this ingredient
        if context_lower in serving_weights:
            weight_per_item = serving_weights[context_lower]
            return quantity * weight_per_item
        
        # Ingredient not in serving weight table
        raise UnsupportedUnitError(
            unit=unit,
            message=f"No serving weight defined for '{ingredient_context}' with unit '{unit}'. "
                    f"Known ingredients for '{unit}': {list(serving_weights.keys())}"
        )
    
    def _scale_micronutrients(
        self,
        micronutrients: MicronutrientProfile,
        scale_factor: float
    ) -> MicronutrientProfile:
        """Scale all micronutrient values.
        
        Args:
            micronutrients: Original MicronutrientProfile
            scale_factor: Factor to multiply by
            
        Returns:
            New MicronutrientProfile with scaled values
        """
        # Get all field values and scale them
        scaled_values = {}
        for field in fields(micronutrients):
            original_value = getattr(micronutrients, field.name)
            scaled_values[field.name] = original_value * scale_factor
        
        return MicronutrientProfile(**scaled_values)
    
    def _create_zero_result(self) -> ScaledNutrition:
        """Create a result with all zeros (for zero quantity).
        
        Returns:
            ScaledNutrition with all values at 0.0
        """
        return ScaledNutrition(
            calories=0.0,
            protein_g=0.0,
            fat_g=0.0,
            carbs_g=0.0,
            micronutrients=MicronutrientProfile(),
            scale_factor=0.0,
            actual_grams=0.0
        )
    
    def get_supported_mass_units(self) -> list:
        """Get list of directly supported mass units.
        
        Returns:
            List of unit strings that can be converted without context
        """
        return list(UNIT_TO_GRAMS.keys())
    
    def get_supported_count_units(self) -> list:
        """Get list of count-based units (require ingredient context).
        
        Returns:
            List of count unit strings
        """
        return list(BASE_SERVING_WEIGHTS.keys())
