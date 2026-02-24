"""Nutrient mapping from USDA FoodData Central to internal schema (Step 2.4).

This module converts raw USDA nutrition data into the app's internal schema.
Mapping is deterministic - no heuristics, AI inference, or food-category assumptions.

DESIGN DECISIONS:
- Static mapping table: USDA nutrient ID → internal field name
- Unknown nutrients are silently ignored (not all USDA nutrients are tracked)
- Missing nutrients default to zero
- Unit conversions are explicit and documented
- Output exactly matches NutritionProfile/MicronutrientProfile field names

WHY MAPPING IS SEPARATE FROM RETRIEVAL:
1. Separation of concerns: retrieval handles API, mapping handles transformation
2. Testability: mapping can be tested without API mocks
3. Flexibility: mapping can change without affecting retrieval logic
4. Future extension: smarter parsing (LLM) can feed into same mapper
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from src.data_layer.models import NutritionProfile, MicronutrientProfile


# ============================================================================
# USDA NUTRIENT ID MAPPING TABLE
# ============================================================================
# 
# This is the authoritative mapping from USDA FoodData Central nutrient IDs
# to internal schema field names. Source: USDA FDC documentation.
#
# Format:
#   USDA_ID: {
#       "field": internal_field_name,
#       "category": "macro" | "micro",
#       "unit": USDA unit (for documentation),
#       "conversion": optional conversion factor
#   }
#
# Categories:
# - "macro": Maps to MappedNutrition directly (calories, protein_g, fat_g, carbs_g)
# - "micro": Maps to MicronutrientProfile field
# ============================================================================

USDA_NUTRIENT_MAP: Dict[int, Dict[str, Any]] = {
    # === MACRONUTRIENTS ===
    1008: {
        "field": "calories",
        "category": "macro",
        "unit": "kcal",
        "description": "Energy"
    },
    1003: {
        "field": "protein_g",
        "category": "macro",
        "unit": "g",
        "description": "Protein"
    },
    1004: {
        "field": "fat_g",
        "category": "macro",
        "unit": "g",
        "description": "Total lipid (fat)"
    },
    1005: {
        "field": "carbs_g",
        "category": "macro",
        "unit": "g",
        "description": "Carbohydrate, by difference"
    },
    
    # === VITAMINS ===
    # Vitamin A (RAE = Retinol Activity Equivalents)
    1106: {
        "field": "vitamin_a_ug",
        "category": "micro",
        "unit": "µg",
        "description": "Vitamin A, RAE"
    },
    # Vitamin C
    1162: {
        "field": "vitamin_c_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Vitamin C, total ascorbic acid"
    },
    # Vitamin D (IU) - some foods report in IU
    1114: {
        "field": "vitamin_d_iu",
        "category": "micro",
        "unit": "IU",
        "description": "Vitamin D (D2 + D3), International Units"
    },
    # Vitamin D (mcg) - some foods report in mcg, needs conversion
    1110: {
        "field": "vitamin_d_iu",
        "category": "micro",
        "unit": "µg",
        "description": "Vitamin D (D2 + D3)",
        "conversion": 40.0  # 1 mcg = 40 IU
    },
    # Vitamin E
    1109: {
        "field": "vitamin_e_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Vitamin E (alpha-tocopherol)"
    },
    # Vitamin K
    1185: {
        "field": "vitamin_k_ug",
        "category": "micro",
        "unit": "µg",
        "description": "Vitamin K (phylloquinone)"
    },
    
    # === B VITAMINS ===
    # B1 - Thiamine
    1165: {
        "field": "b1_thiamine_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Thiamin"
    },
    # B2 - Riboflavin
    1166: {
        "field": "b2_riboflavin_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Riboflavin"
    },
    # B3 - Niacin
    1167: {
        "field": "b3_niacin_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Niacin"
    },
    # B5 - Pantothenic acid
    1170: {
        "field": "b5_pantothenic_acid_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Pantothenic acid"
    },
    # B6 - Pyridoxine
    1175: {
        "field": "b6_pyridoxine_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Vitamin B-6"
    },
    # B12 - Cobalamin
    1178: {
        "field": "b12_cobalamin_ug",
        "category": "micro",
        "unit": "µg",
        "description": "Vitamin B-12"
    },
    # Folate
    1177: {
        "field": "folate_ug",
        "category": "micro",
        "unit": "µg",
        "description": "Folate, total"
    },
    
    # === MINERALS ===
    # Calcium
    1087: {
        "field": "calcium_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Calcium, Ca"
    },
    # Copper
    1098: {
        "field": "copper_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Copper, Cu"
    },
    # Iron
    1089: {
        "field": "iron_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Iron, Fe"
    },
    # Magnesium
    1090: {
        "field": "magnesium_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Magnesium, Mg"
    },
    # Manganese
    1101: {
        "field": "manganese_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Manganese, Mn"
    },
    # Phosphorus
    1091: {
        "field": "phosphorus_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Phosphorus, P"
    },
    # Potassium
    1092: {
        "field": "potassium_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Potassium, K"
    },
    # Selenium
    1103: {
        "field": "selenium_ug",
        "category": "micro",
        "unit": "µg",
        "description": "Selenium, Se"
    },
    # Sodium
    1093: {
        "field": "sodium_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Sodium, Na"
    },
    # Zinc
    1095: {
        "field": "zinc_mg",
        "category": "micro",
        "unit": "mg",
        "description": "Zinc, Zn"
    },
    
    # === OTHER ===
    # Fiber
    1079: {
        "field": "fiber_g",
        "category": "micro",
        "unit": "g",
        "description": "Fiber, total dietary"
    },
    # Omega-3 fatty acids (total)
    # Note: USDA may report as sum of individual fatty acids
    # 1404 is EPA+DHA, we use total polyunsaturated omega-3
    1272: {
        "field": "omega_3_g",
        "category": "micro",
        "unit": "g",
        "description": "Fatty acids, total polyunsaturated (omega-3 proxy)"
    },
    # Omega-6 fatty acids (total)
    # Note: Similar to omega-3, this may need refinement
    # Using 18:2 as linoleic acid is primary dietary omega-6
    1269: {
        "field": "omega_6_g",
        "category": "micro",
        "unit": "g",
        "description": "18:2 undifferentiated (omega-6 proxy)"
    },
}


@dataclass
class MappedNutrition:
    """Nutrition data mapped from USDA to internal schema.
    
    This is the output of NutrientMapper.map_nutrients().
    Field names exactly match NutritionProfile for easy conversion.
    
    Attributes:
        calories: Energy in kcal
        protein_g: Protein in grams
        fat_g: Total fat in grams
        carbs_g: Carbohydrates in grams
        micronutrients: MicronutrientProfile with vitamins/minerals
    """
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    micronutrients: MicronutrientProfile
    
    def to_nutrition_profile(self) -> NutritionProfile:
        """Convert to NutritionProfile for use in recipes/meals.
        
        Returns:
            NutritionProfile with macros and micronutrients
        """
        return NutritionProfile(
            calories=self.calories,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            carbs_g=self.carbs_g,
            micronutrients=self.micronutrients
        )


class NutrientMapper:
    """Maps raw USDA nutrition data to internal schema.
    
    This mapper:
    1. Iterates through USDA foodNutrients
    2. Looks up each nutrient ID in the static mapping table
    3. Applies unit conversions where needed
    4. Builds MappedNutrition with all values
    
    Unknown nutrients are ignored. Missing nutrients default to zero.
    Mapping is deterministic and testable.
    
    Usage:
        mapper = NutrientMapper()
        result = mapper.map_nutrients(raw_payload)
        
        # result.calories, result.protein_g, etc.
        # result.micronutrients.vitamin_a_ug, etc.
        
        # Convert to NutritionProfile
        profile = result.to_nutrition_profile()
    """
    
    def __init__(self):
        """Initialize mapper with default configuration."""
        # Pre-compute field → category lookup for micronutrients
        self._micro_fields = {
            v["field"] for v in USDA_NUTRIENT_MAP.values() 
            if v["category"] == "micro"
        }
    
    def map_nutrients(self, raw_payload: Dict[str, Any]) -> MappedNutrition:
        """Map raw USDA payload to internal nutrition structure.
        
        Args:
            raw_payload: Raw JSON from USDA API (FoodDetailsResult.raw_payload)
            
        Returns:
            MappedNutrition with all fields populated (missing = 0.0)
        """
        # Initialize all values to zero
        macros = {
            "calories": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "carbs_g": 0.0,
        }
        micros = {}
        
        # Extract foodNutrients array
        food_nutrients = raw_payload.get("foodNutrients", [])
        
        # Process each nutrient
        for nutrient_data in food_nutrients:
            self._process_nutrient(nutrient_data, macros, micros)
        
        # Build MicronutrientProfile with defaults
        micronutrient_profile = MicronutrientProfile(**micros)
        
        return MappedNutrition(
            calories=macros["calories"],
            protein_g=macros["protein_g"],
            fat_g=macros["fat_g"],
            carbs_g=macros["carbs_g"],
            micronutrients=micronutrient_profile
        )
    
    def _process_nutrient(
        self,
        nutrient_data: Dict[str, Any],
        macros: Dict[str, float],
        micros: Dict[str, float]
    ) -> None:
        """Process a single nutrient entry from USDA payload.
        
        Args:
            nutrient_data: Single entry from foodNutrients array
            macros: Dict to update with macronutrient values
            micros: Dict to update with micronutrient values
        """
        # Extract nutrient ID
        nutrient_info = nutrient_data.get("nutrient", {})
        nutrient_id = nutrient_info.get("id")
        
        if nutrient_id is None:
            return  # Skip if no ID
        
        # Look up in mapping table
        mapping = USDA_NUTRIENT_MAP.get(nutrient_id)
        if mapping is None:
            return  # Unknown nutrient, skip
        
        # Extract amount (default to 0 if missing or None)
        amount = nutrient_data.get("amount")
        if amount is None:
            amount = 0.0
        
        # Apply conversion if specified
        conversion = mapping.get("conversion")
        if conversion is not None:
            amount = amount * conversion
        
        # Store in appropriate dict
        field_name = mapping["field"]
        category = mapping["category"]
        
        if category == "macro":
            macros[field_name] = amount
        else:  # micro
            # Handle potential duplicate mappings (e.g., Vitamin D in IU and mcg)
            # Take the first non-zero value or sum them
            current = micros.get(field_name, 0.0)
            micros[field_name] = current + amount
    
    def get_tracked_nutrient_ids(self) -> set:
        """Get set of USDA nutrient IDs that are tracked.
        
        Useful for debugging and documentation.
        
        Returns:
            Set of USDA nutrient IDs in the mapping table
        """
        return set(USDA_NUTRIENT_MAP.keys())
    
    def get_field_for_nutrient_id(self, nutrient_id: int) -> Optional[str]:
        """Get internal field name for a USDA nutrient ID.
        
        Args:
            nutrient_id: USDA FoodData Central nutrient ID
            
        Returns:
            Internal field name or None if not tracked
        """
        mapping = USDA_NUTRIENT_MAP.get(nutrient_id)
        return mapping["field"] if mapping else None
