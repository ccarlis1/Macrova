"""Tests for Step 2.4: Nutrient Mapping.

Tests conversion of raw USDA nutrition data to internal schema.
Mapping is deterministic, no heuristics or AI inference.
"""

import pytest

from src.ingestion.nutrient_mapper import (
    NutrientMapper,
    MappedNutrition,
    USDA_NUTRIENT_MAP,
)
from src.data_layer.models import MicronutrientProfile


class TestUSDANutrientMap:
    """Tests for the static USDA nutrient ID mapping table."""

    def test_macronutrient_ids_mapped(self):
        """Test that macronutrient IDs are in the mapping."""
        # Energy (calories)
        assert 1008 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1008]["field"] == "calories"
        
        # Protein
        assert 1003 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1003]["field"] == "protein_g"
        
        # Fat
        assert 1004 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1004]["field"] == "fat_g"
        
        # Carbohydrates
        assert 1005 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1005]["field"] == "carbs_g"

    def test_vitamin_ids_mapped(self):
        """Test that vitamin IDs are in the mapping."""
        # Vitamin A
        assert 1106 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1106]["field"] == "vitamin_a_ug"
        
        # Vitamin C
        assert 1162 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1162]["field"] == "vitamin_c_mg"
        
        # Vitamin D: 1110 is the IU entry (number 324), 1114 the µg entry (328)
        assert USDA_NUTRIENT_MAP[1110]["field"] == "vitamin_d_iu"
        assert USDA_NUTRIENT_MAP[1110]["unit"] == "IU"
        assert USDA_NUTRIENT_MAP[1110].get("conversion") is None
        assert USDA_NUTRIENT_MAP[1114]["field"] == "vitamin_d_iu"
        assert USDA_NUTRIENT_MAP[1114]["unit"] == "µg"
        assert USDA_NUTRIENT_MAP[1114]["conversion"] == 40.0
        
        # Vitamin E
        assert 1109 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1109]["field"] == "vitamin_e_mg"
        
        # Vitamin K
        assert 1185 in USDA_NUTRIENT_MAP
        assert USDA_NUTRIENT_MAP[1185]["field"] == "vitamin_k_ug"
        
        # B vitamins
        assert 1165 in USDA_NUTRIENT_MAP  # B1 Thiamine
        assert 1166 in USDA_NUTRIENT_MAP  # B2 Riboflavin
        assert 1167 in USDA_NUTRIENT_MAP  # B3 Niacin
        assert 1170 in USDA_NUTRIENT_MAP  # B5 Pantothenic acid
        assert 1175 in USDA_NUTRIENT_MAP  # B6
        assert 1178 in USDA_NUTRIENT_MAP  # B12
        assert 1177 in USDA_NUTRIENT_MAP  # Folate

    def test_mineral_ids_mapped(self):
        """Test that mineral IDs are in the mapping."""
        assert 1087 in USDA_NUTRIENT_MAP  # Calcium
        assert 1098 in USDA_NUTRIENT_MAP  # Copper
        assert 1089 in USDA_NUTRIENT_MAP  # Iron
        assert 1090 in USDA_NUTRIENT_MAP  # Magnesium
        assert 1101 in USDA_NUTRIENT_MAP  # Manganese
        assert 1091 in USDA_NUTRIENT_MAP  # Phosphorus
        assert 1092 in USDA_NUTRIENT_MAP  # Potassium
        assert 1103 in USDA_NUTRIENT_MAP  # Selenium
        assert 1093 in USDA_NUTRIENT_MAP  # Sodium
        assert 1095 in USDA_NUTRIENT_MAP  # Zinc

    def test_other_nutrients_mapped(self):
        """Test that fiber and fatty acids are mapped."""
        assert 1079 in USDA_NUTRIENT_MAP  # Fiber
        assert USDA_NUTRIENT_MAP[1079]["field"] == "fiber_g"


class TestNutrientMapper:
    """Tests for NutrientMapper class."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance."""
        return NutrientMapper()

    # === Macronutrient Mapping Tests ===

    def test_map_macronutrients(self, mapper):
        """Test mapping of macronutrients from USDA payload."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 165},      # Energy (kcal)
                {"nutrient": {"id": 1003}, "amount": 31.0},     # Protein (g)
                {"nutrient": {"id": 1004}, "amount": 3.6},      # Fat (g)
                {"nutrient": {"id": 1005}, "amount": 0.0},      # Carbs (g)
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.calories == 165
        assert result.protein_g == 31.0
        assert result.fat_g == 3.6
        assert result.carbs_g == 0.0

    def test_map_vitamins(self, mapper):
        """Test mapping of vitamins from USDA payload."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},      # Calories (required)
                {"nutrient": {"id": 1003}, "amount": 10},       # Protein (required)
                {"nutrient": {"id": 1004}, "amount": 5},        # Fat (required)
                {"nutrient": {"id": 1005}, "amount": 20},       # Carbs (required)
                {"nutrient": {"id": 1106}, "amount": 6.0},      # Vitamin A (µg)
                {"nutrient": {"id": 1162}, "amount": 1.6},      # Vitamin C (mg)
                {"nutrient": {"id": 1110}, "amount": 5.0},      # Vitamin D (IU)
                {"nutrient": {"id": 1109}, "amount": 0.26},     # Vitamin E (mg)
                {"nutrient": {"id": 1185}, "amount": 0.3},      # Vitamin K (µg)
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.micronutrients.vitamin_a_ug == 6.0
        assert result.micronutrients.vitamin_c_mg == 1.6
        assert result.micronutrients.vitamin_d_iu == 5.0
        assert result.micronutrients.vitamin_e_mg == 0.26
        assert result.micronutrients.vitamin_k_ug == 0.3

    def test_map_b_vitamins(self, mapper):
        """Test mapping of B vitamins from USDA payload."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 1165}, "amount": 0.073},    # B1 Thiamine (mg)
                {"nutrient": {"id": 1166}, "amount": 0.114},    # B2 Riboflavin (mg)
                {"nutrient": {"id": 1167}, "amount": 13.71},    # B3 Niacin (mg)
                {"nutrient": {"id": 1170}, "amount": 0.973},    # B5 Pantothenic (mg)
                {"nutrient": {"id": 1175}, "amount": 0.6},      # B6 (mg)
                {"nutrient": {"id": 1178}, "amount": 0.34},     # B12 (µg)
                {"nutrient": {"id": 1177}, "amount": 4.0},      # Folate (µg)
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.micronutrients.b1_thiamine_mg == 0.073
        assert result.micronutrients.b2_riboflavin_mg == 0.114
        assert result.micronutrients.b3_niacin_mg == 13.71
        assert result.micronutrients.b5_pantothenic_acid_mg == 0.973
        assert result.micronutrients.b6_pyridoxine_mg == 0.6
        assert result.micronutrients.b12_cobalamin_ug == 0.34
        assert result.micronutrients.folate_ug == 4.0

    def test_map_minerals(self, mapper):
        """Test mapping of minerals from USDA payload."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 1087}, "amount": 5.0},      # Calcium (mg)
                {"nutrient": {"id": 1098}, "amount": 0.042},    # Copper (mg)
                {"nutrient": {"id": 1089}, "amount": 0.37},     # Iron (mg)
                {"nutrient": {"id": 1090}, "amount": 29.0},     # Magnesium (mg)
                {"nutrient": {"id": 1101}, "amount": 0.017},    # Manganese (mg)
                {"nutrient": {"id": 1091}, "amount": 228.0},    # Phosphorus (mg)
                {"nutrient": {"id": 1092}, "amount": 256.0},    # Potassium (mg)
                {"nutrient": {"id": 1103}, "amount": 23.7},     # Selenium (µg)
                {"nutrient": {"id": 1093}, "amount": 74.0},     # Sodium (mg)
                {"nutrient": {"id": 1095}, "amount": 0.8},      # Zinc (mg)
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.micronutrients.calcium_mg == 5.0
        assert result.micronutrients.copper_mg == 0.042
        assert result.micronutrients.iron_mg == 0.37
        assert result.micronutrients.magnesium_mg == 29.0
        assert result.micronutrients.manganese_mg == 0.017
        assert result.micronutrients.phosphorus_mg == 228.0
        assert result.micronutrients.potassium_mg == 256.0
        assert result.micronutrients.selenium_ug == 23.7
        assert result.micronutrients.sodium_mg == 74.0
        assert result.micronutrients.zinc_mg == 0.8

    def test_map_fiber(self, mapper):
        """Test mapping of fiber from USDA payload."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 1079}, "amount": 2.4},      # Fiber (g)
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.micronutrients.fiber_g == 2.4

    # === Unknown Nutrient Tests ===

    def test_unknown_nutrients_ignored(self, mapper):
        """Test that unknown USDA nutrient IDs are ignored."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 9999}, "amount": 42.0},     # Unknown ID
                {"nutrient": {"id": 8888}, "amount": 99.0},     # Unknown ID
            ]
        }
        
        # Should not raise, unknown nutrients silently ignored
        result = mapper.map_nutrients(raw_payload)
        
        assert result.calories == 100
        assert result.protein_g == 10

    def test_nutrient_without_id_ignored(self, mapper):
        """Test that nutrients without ID field are ignored."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"name": "Unknown"}, "amount": 42.0},  # No ID
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        assert result.calories == 100

    # === Missing Nutrient Tests ===

    def test_missing_micronutrients_default_to_zero(self, mapper):
        """Test that missing micronutrients default to zero."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                # No micronutrients provided
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        # All micronutrients should default to 0.0
        assert result.micronutrients.vitamin_a_ug == 0.0
        assert result.micronutrients.vitamin_c_mg == 0.0
        assert result.micronutrients.calcium_mg == 0.0
        assert result.micronutrients.iron_mg == 0.0
        assert result.micronutrients.fiber_g == 0.0

    def test_missing_macronutrients_default_to_zero(self, mapper):
        """Test that missing macronutrients default to zero."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                # Only calories provided
                {"nutrient": {"id": 1008}, "amount": 100},
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.calories == 100
        assert result.protein_g == 0.0
        assert result.fat_g == 0.0
        assert result.carbs_g == 0.0

    def test_empty_food_nutrients(self, mapper):
        """Test handling of empty foodNutrients array."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": []
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.calories == 0.0
        assert result.protein_g == 0.0
        assert result.fat_g == 0.0
        assert result.carbs_g == 0.0

    # === Unit Conversion Tests ===

    def test_vitamin_d_mcg_to_iu_conversion(self, mapper):
        """Vitamin D only in µg (FDC id 1114, number 328): 1 µg = 40 IU."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 1114}, "amount": 0.1},  # Vitamin D in µg
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        # 0.1 µg * 40 = 4 IU
        assert result.micronutrients.vitamin_d_iu == pytest.approx(4.0)

    def test_vitamin_d_iu_direct(self, mapper):
        """Vitamin D only in IU (FDC id 1110, number 324): used as is."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
                {"nutrient": {"id": 1110}, "amount": 10.0},  # Vitamin D in IU
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.micronutrients.vitamin_d_iu == 10.0

    @pytest.mark.parametrize("order", ["iu_first", "ug_first"])
    def test_vitamin_d_both_units_uses_iu_not_x40_not_sum(self, mapper, order):
        """DATA-2 regression: FDC reports vitamin D in IU and in µg.

        Shaped like FDC 171287 (Egg, whole, raw, fresh), nutrient objects as the
        /food/{fdcId} endpoint returns them. The result must be the IU value
        (82), not IU × 40 (3280) and not IU × 40 + µg (3282, the old bug).
        """
        iu = {
            "type": "FoodNutrient",
            "nutrient": {
                "id": 1110,
                "number": "324",
                "name": "Vitamin D (D2 + D3), International Units",
                "unitName": "IU",
            },
            "amount": 82.0,
        }
        ug = {
            "type": "FoodNutrient",
            "nutrient": {
                "id": 1114,
                "number": "328",
                "name": "Vitamin D (D2 + D3)",
                "unitName": "µg",
            },
            "amount": 2.0,
        }
        d3 = {
            "type": "FoodNutrient",
            "nutrient": {
                "id": 1112,
                "number": "326",
                "name": "Vitamin D3 (cholecalciferol)",
                "unitName": "µg",
            },
            "amount": 2.0,
        }
        vitamin_d = [iu, ug, d3] if order == "iu_first" else [d3, ug, iu]
        raw_payload = {
            "fdcId": 171287,
            "dataType": "SR Legacy",
            "description": "Egg, whole, raw, fresh",
            "foodNutrients": [
                {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 143.0},
                {"nutrient": {"id": 1003, "unitName": "g"}, "amount": 12.56},
                {"nutrient": {"id": 1004, "unitName": "g"}, "amount": 9.51},
                {"nutrient": {"id": 1005, "unitName": "g"}, "amount": 0.72},
                *vitamin_d,
            ],
        }

        result = mapper.map_nutrients(raw_payload)

        assert result.micronutrients.vitamin_d_iu == 82.0

    def test_no_tracked_field_is_fed_by_two_primary_ids(self):
        """Only an explicit ``fallback`` id may share a field with another id."""
        primary_fields = [
            m["field"] for m in USDA_NUTRIENT_MAP.values() if not m.get("fallback")
        ]
        assert len(primary_fields) == len(set(primary_fields))

    # === Data Integrity Tests ===

    def test_null_amount_treated_as_zero(self, mapper):
        """Test that null/None amounts are treated as zero."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": None},     # Null amount
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.protein_g == 0.0  # Null treated as zero

    def test_missing_amount_field_treated_as_zero(self, mapper):
        """Test that missing amount field is treated as zero."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}},  # No amount field
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        assert result.protein_g == 0.0

    # === Output Structure Tests ===

    def test_output_is_deterministic(self, mapper):
        """Test that mapping is deterministic (same input → same output)."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 165},
                {"nutrient": {"id": 1003}, "amount": 31.0},
                {"nutrient": {"id": 1004}, "amount": 3.6},
                {"nutrient": {"id": 1005}, "amount": 0.0},
            ]
        }
        
        result1 = mapper.map_nutrients(raw_payload)
        result2 = mapper.map_nutrients(raw_payload)
        result3 = mapper.map_nutrients(raw_payload)
        
        assert result1.calories == result2.calories == result3.calories
        assert result1.protein_g == result2.protein_g == result3.protein_g

    def test_field_names_match_internal_schema(self, mapper):
        """Test that field names exactly match internal schema."""
        raw_payload = {
            "fdcId": 171705,
            "foodNutrients": [
                {"nutrient": {"id": 1008}, "amount": 100},
                {"nutrient": {"id": 1003}, "amount": 10},
                {"nutrient": {"id": 1004}, "amount": 5},
                {"nutrient": {"id": 1005}, "amount": 20},
            ]
        }
        
        result = mapper.map_nutrients(raw_payload)
        
        # Macronutrient fields match NutritionProfile
        assert hasattr(result, 'calories')
        assert hasattr(result, 'protein_g')
        assert hasattr(result, 'fat_g')
        assert hasattr(result, 'carbs_g')
        
        # Micronutrient fields match MicronutrientProfile
        micro = result.micronutrients
        assert hasattr(micro, 'vitamin_a_ug')
        assert hasattr(micro, 'calcium_mg')
        assert hasattr(micro, 'fiber_g')


class TestMappedNutrition:
    """Tests for MappedNutrition data model."""

    def test_mapped_nutrition_structure(self):
        """Test that MappedNutrition has required fields."""
        from src.ingestion.nutrient_mapper import MappedNutrition
        
        micro = MicronutrientProfile()
        result = MappedNutrition(
            calories=100,
            protein_g=10,
            fat_g=5,
            carbs_g=20,
            micronutrients=micro
        )
        
        assert result.calories == 100
        assert result.protein_g == 10
        assert result.fat_g == 5
        assert result.carbs_g == 20
        assert result.micronutrients == micro
