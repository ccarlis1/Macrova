"""Tests for ingredient parser."""
import pytest
from tempfile import NamedTemporaryFile
import json

from src.ingestion.ingredient_parser import IngredientParser
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.models import Ingredient


class TestIngredientParser:
    """Tests for IngredientParser."""

    @pytest.fixture
    def nutrition_db(self):
        """Create a test nutrition database."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["cream of rice", "rice cereal"],
                },
                {
                    "name": "egg",
                    "per_large": {
                        "calories": 72,
                        "protein_g": 6.3,
                        "fat_g": 4.8,
                        "carbs_g": 0.4,
                    },
                    "large_size_g": 50,
                    "aliases": ["eggs", "egg", "large egg"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        db = NutritionDB(temp_path)
        yield db
        import os
        os.unlink(temp_path)

    @pytest.fixture
    def parser(self, nutrition_db):
        """Create an IngredientParser instance."""
        return IngredientParser(nutrition_db)

    def test_parse_basic(self, parser):
        """Test basic ingredient parsing."""
        ingredient = parser.parse("200g cream of rice")
        assert ingredient.name == "cream of rice"
        assert ingredient.quantity == 200.0
        assert ingredient.unit == "g"
        assert ingredient.is_to_taste is False

    def test_parse_to_taste(self, parser):
        """Test parsing 'to taste' ingredients."""
        ingredient = parser.parse("salt to taste")
        assert ingredient.name == "salt"
        assert ingredient.quantity == 0.0
        assert ingredient.unit == "to taste"
        assert ingredient.is_to_taste is True

    def test_parse_to_taste_in_name(self, parser):
        """Test parsing when 'to taste' appears in the name."""
        ingredient = parser.parse("salsa to taste")
        assert ingredient.name == "salsa"
        assert ingredient.unit == "to taste"
        assert ingredient.is_to_taste is True

    def test_parse_name_normalization(self, parser):
        """Test ingredient name normalization via aliases."""
        ingredient = parser.parse("5 large eggs")
        assert ingredient.name == "egg"  # Normalized via alias
        assert ingredient.quantity == 5.0
        assert ingredient.unit == "large"

    def test_parse_various_units(self, parser):
        """Test parsing with various units."""
        test_cases = [
            ("200g cream of rice", 200.0, "g"),
            ("1 oz cheese", 1.0, "oz"),
            ("1 cup milk", 1.0, "cup"),
            ("1 tsp salt", 1.0, "tsp"),
            ("1 tbsp oil", 1.0, "tbsp"),
            ("1 scoop protein", 1.0, "scoop"),
            ("2 large eggs", 2.0, "large"),
        ]

        for input_str, expected_qty, expected_unit in test_cases:
            ingredient = parser.parse(input_str)
            assert ingredient.quantity == expected_qty
            assert ingredient.unit == expected_unit

    def test_parse_missing_quantity(self, parser):
        """Test parsing when quantity is missing - should default to 1 serving."""
        ingredient = parser.parse("cream of rice")
        assert ingredient.quantity == 1.0
        assert ingredient.unit == "serving"
        assert ingredient.name == "cream of rice"

    def test_parse_number_without_unit(self, parser):
        """Test parsing number without unit - should assume servings."""
        ingredient = parser.parse("3 rice")
        assert ingredient.quantity == 3.0
        assert ingredient.unit == "serving"
        assert ingredient.name == "rice"

    def test_parse_missing_unit_with_number(self, parser):
        """Test parsing number without explicit unit - should default to serving."""
        ingredient = parser.parse("200 cream of rice")
        assert ingredient.quantity == 200.0
        assert ingredient.unit == "serving"

    def test_parse_unknown_ingredient(self, parser):
        """Test parsing unknown ingredient - should return original name."""
        ingredient = parser.parse("200g unknown_ingredient")
        assert ingredient.name == "unknown_ingredient"  # Not normalized
        assert ingredient.quantity == 200.0
        assert ingredient.unit == "g"

    def test_parse_empty_string(self, parser):
        """Test parsing empty string - should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parser.parse("")

    def test_parse_whitespace_handling(self, parser):
        """Test parsing with multiple spaces."""
        ingredient = parser.parse("200  g  cream  of  rice")
        assert ingredient.quantity == 200.0
        assert ingredient.unit == "g"
        assert ingredient.name == "cream of rice"

    def test_parse_case_insensitive(self, parser):
        """Test parsing is case-insensitive for normalization."""
        ingredient = parser.parse("EGGS")
        assert ingredient.name == "egg"  # Normalized via alias (case-insensitive)

    def test_detect_to_taste(self, parser):
        """Test 'to taste' detection."""
        assert parser.detect_to_taste("to taste") is True
        assert parser.detect_to_taste("To Taste") is True
        assert parser.detect_to_taste("g") is False
        assert parser.detect_to_taste("") is False

    def test_normalize_name(self, parser):
        """Test name normalization."""
        assert parser.normalize_name("eggs") == "egg"  # Via alias
        assert parser.normalize_name("cream of rice") == "cream of rice"  # Direct match
        assert parser.normalize_name("unknown") == "unknown"  # Not found

