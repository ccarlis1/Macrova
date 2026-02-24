"""NutritionProfile construction from pipeline outputs (Step 2.6).

This module builds clean NutritionProfile instances from scaled nutrition data.
NutritionProfile is the BOUNDARY between external data (USDA) and internal logic.

DESIGN DECISIONS:
- NutritionProfile contains ONLY internal schema fields
- No USDA IDs, raw payloads, or external metadata
- All values are numeric (no None, no strings)
- Missing nutrients default to zero
- Output is safe for aggregation, scoring, and tracking

WHY NutritionProfile IS THE BOUNDARY:
1. External data (USDA) has different schemas, IDs, and field names
2. Internal logic (scoring, planning) needs consistent, predictable data
3. Decoupling means USDA changes don't break internal algorithms
4. Testing internal logic doesn't require USDA mocks

HOW THIS SIMPLIFIES MEAL PLANNER:
1. Meal planner receives NutritionProfile, not raw API data
2. All fields guaranteed to exist and be numeric
3. No need for null checks or type coercion in planner
4. Aggregation is simple addition (profile1.calories + profile2.calories)
5. Scoring can trust data consistency
"""

from dataclasses import fields
from typing import Union

from src.data_layer.models import NutritionProfile, MicronutrientProfile
from src.ingestion.nutrition_scaler import ScaledNutrition
from src.ingestion.nutrient_mapper import MappedNutrition


class NutritionProfileBuilder:
    """Builds clean NutritionProfile instances from pipeline outputs.
    
    This builder ensures:
    - All required fields are present
    - Field names exactly match internal schema
    - No USDA-specific metadata leaks through
    - Missing nutrients default to zero
    - Output is safe for aggregation and scoring
    
    Usage:
        builder = NutritionProfileBuilder()
        
        # From scaled nutrition (after quantity scaling)
        profile = builder.build(scaled_nutrition)
        
        # From mapped nutrition (per-100g, no scaling)
        profile = builder.build_from_mapped(mapped_nutrition)
    """
    
    def build(self, scaled: ScaledNutrition) -> NutritionProfile:
        """Build NutritionProfile from ScaledNutrition.
        
        This is the primary method for constructing profiles after
        the full pipeline (lookup → map → scale).
        
        Args:
            scaled: ScaledNutrition from NutritionScaler
            
        Returns:
            Clean NutritionProfile for internal use
        """
        # Create a fresh MicronutrientProfile to ensure independence
        micronutrients = self._copy_micronutrients(scaled.micronutrients)
        
        return NutritionProfile(
            calories=float(scaled.calories),
            protein_g=float(scaled.protein_g),
            fat_g=float(scaled.fat_g),
            carbs_g=float(scaled.carbs_g),
            micronutrients=micronutrients
        )
    
    def build_from_mapped(self, mapped: MappedNutrition) -> NutritionProfile:
        """Build NutritionProfile from MappedNutrition (no scaling).
        
        Use this when you want the per-100g values without scaling,
        or when scaling has been applied elsewhere.
        
        Args:
            mapped: MappedNutrition from NutrientMapper
            
        Returns:
            Clean NutritionProfile for internal use
        """
        # Create a fresh MicronutrientProfile to ensure independence
        micronutrients = self._copy_micronutrients(mapped.micronutrients)
        
        return NutritionProfile(
            calories=float(mapped.calories),
            protein_g=float(mapped.protein_g),
            fat_g=float(mapped.fat_g),
            carbs_g=float(mapped.carbs_g),
            micronutrients=micronutrients
        )
    
    def _copy_micronutrients(
        self, source: MicronutrientProfile
    ) -> MicronutrientProfile:
        """Create an independent copy of MicronutrientProfile.
        
        Ensures no shared references between input and output.
        
        Args:
            source: Original MicronutrientProfile
            
        Returns:
            New MicronutrientProfile with same values
        """
        # Copy all field values
        values = {}
        for field in fields(source):
            value = getattr(source, field.name)
            # Ensure numeric and default to 0.0 if None
            values[field.name] = float(value) if value is not None else 0.0
        
        return MicronutrientProfile(**values)


def build_nutrition_profile(
    nutrition: Union[ScaledNutrition, MappedNutrition]
) -> NutritionProfile:
    """Convenience function to build NutritionProfile from pipeline output.
    
    Automatically detects input type and builds appropriately.
    
    Args:
        nutrition: Either ScaledNutrition or MappedNutrition
        
    Returns:
        Clean NutritionProfile for internal use
        
    Example:
        # Full pipeline
        lookup = client.lookup("chicken breast")
        details = client.get_food_details(lookup.fdc_id)
        mapped = mapper.map_nutrients(details.raw_payload)
        scaled = scaler.scale(mapped, 200.0, "g", 100.0)
        profile = build_nutrition_profile(scaled)
        
        # No scaling needed
        profile = build_nutrition_profile(mapped)
    """
    builder = NutritionProfileBuilder()
    
    if isinstance(nutrition, ScaledNutrition):
        return builder.build(nutrition)
    elif isinstance(nutrition, MappedNutrition):
        return builder.build_from_mapped(nutrition)
    else:
        raise TypeError(
            f"Expected ScaledNutrition or MappedNutrition, got {type(nutrition).__name__}"
        )
