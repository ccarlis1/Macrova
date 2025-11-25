"""Ingredient parser for extracting quantities, units, and names from strings."""
import re
from typing import Tuple

from src.data_layer.models import Ingredient
from src.data_layer.nutrition_db import NutritionDB


class IngredientParser:
    """Parser for ingredient strings into Ingredient objects."""

    # Common unit conversions (for MVP - common cases only)
    UNIT_CONVERSIONS = {
        "oz": 28.35,  # oz to grams
        "cup": 240.0,  # cup to ml (approximate)
        "tsp": 4.93,  # tsp to ml
        "tbsp": 14.79,  # tbsp to ml
    }

    # Supported units
    SUPPORTED_UNITS = ["g", "oz", "cup", "tsp", "tbsp", "scoop", "large", "to taste", "serving"]

    def __init__(self, nutrition_db: NutritionDB):
        """Initialize parser with nutrition database for alias lookup.
        
        Args:
            nutrition_db: NutritionDB instance for ingredient name normalization
        """
        self.nutrition_db = nutrition_db

    def parse(self, ingredient_string: str) -> Ingredient:
        """Parse ingredient string into Ingredient object.
        
        Args:
            ingredient_string: Raw ingredient string (e.g., "200g cream of rice")
        
        Returns:
            Ingredient object with parsed data
        
        Raises:
            ValueError: If ingredient string is empty or cannot be parsed
        """
        if not ingredient_string or not ingredient_string.strip():
            raise ValueError("Ingredient string cannot be empty")

        ingredient_string = ingredient_string.strip()

        # Extract quantity, unit, and name
        quantity, unit, name = self.extract_quantity_and_unit(ingredient_string)

        # Detect "to taste"
        is_to_taste = self.detect_to_taste(unit)

        # Normalize ingredient name
        normalized_name = self.normalize_name(name)

        # For "to taste", set quantity to 0
        if is_to_taste:
            quantity = 0.0

        return Ingredient(
            name=normalized_name,
            quantity=quantity,
            unit=unit,
            is_to_taste=is_to_taste,
            normalized_unit=unit,  # Will be normalized later if needed
            normalized_quantity=quantity,  # Will be normalized later if needed
        )

    def normalize_name(self, name: str) -> str:
        """Normalize ingredient name using aliases from nutrition DB.
        
        Args:
            name: Raw ingredient name (e.g., "eggs")
        
        Returns:
            Normalized name (e.g., "egg") or original if not found
        """
        if not name:
            return name

        # Try to find ingredient in DB (case-insensitive)
        ingredient_info = self.nutrition_db.get_ingredient_info(name.lower())
        if ingredient_info:
            return ingredient_info["name"]

        # Return original name if not found
        return name

    def detect_to_taste(self, unit: str) -> bool:
        """Detect if ingredient is marked as 'to taste'.
        
        Args:
            unit: Unit string
        
        Returns:
            True if 'to taste', False otherwise
        """
        if not unit:
            return False
        return unit.lower() == "to taste" or "to taste" in unit.lower()

    def extract_quantity_and_unit(self, ingredient_string: str) -> Tuple[float, str, str]:
        """Extract quantity, unit, and remaining name from string.
        
        Args:
            ingredient_string: Raw ingredient string
        
        Returns:
            Tuple of (quantity: float, unit: str, name: str)
        """
        ingredient_string = ingredient_string.strip()

        # Check for "to taste" first
        if "to taste" in ingredient_string.lower():
            # Extract name (remove "to taste")
            name = re.sub(r"\s*to\s*taste\s*", "", ingredient_string, flags=re.IGNORECASE).strip()
            return (0.0, "to taste", name)

        # Pattern to match: number, unit (short), ingredient name
        # Examples: "200g cream of rice", "1 cup milk", "3 rice"
        # Try pattern with unit first: number + unit + name
        pattern_with_unit = r"^(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+(.+)$"
        match = re.match(pattern_with_unit, ingredient_string)
        
        if match:
            quantity_str = match.group(1)
            unit_str = match.group(2)
            name = match.group(3).strip()
            # Normalize multiple spaces in name
            name = re.sub(r"\s+", " ", name)
            
            quantity = float(quantity_str)
            unit = self._normalize_unit(unit_str)
            return (quantity, unit, name)

        # Try pattern without space between number and unit: "200g cream of rice"
        pattern_no_space = r"^(\d+(?:\.\d+)?)([a-zA-Z]+)\s+(.+)$"
        match = re.match(pattern_no_space, ingredient_string)
        
        if match:
            quantity_str = match.group(1)
            unit_str = match.group(2)
            name = match.group(3).strip()
            # Normalize multiple spaces in name
            name = re.sub(r"\s+", " ", name)
            
            quantity = float(quantity_str)
            unit = self._normalize_unit(unit_str)
            return (quantity, unit, name)

        # Try pattern with number only (no unit): "3 rice" or "200 cream of rice"
        pattern_number_only = r"^(\d+(?:\.\d+)?)\s+(.+)$"
        match = re.match(pattern_number_only, ingredient_string)
        
        if match:
            quantity_str = match.group(1)
            name = match.group(2).strip()
            # Normalize multiple spaces in name
            name = re.sub(r"\s+", " ", name)
            
            quantity = float(quantity_str)
            unit = "serving"  # Assume servings if no unit
            return (quantity, unit, name)

        # No match - assume entire string is name, default to 1 serving
        # Normalize multiple spaces
        name = re.sub(r"\s+", " ", ingredient_string)
        return (1.0, "serving", name)

    def _normalize_unit(self, unit_str: str) -> str:
        """Normalize unit string to standard form.
        
        Args:
            unit_str: Raw unit string
        
        Returns:
            Normalized unit string
        """
        unit_str = unit_str.strip().lower()

        # Handle common variations
        unit_mapping = {
            "gram": "g",
            "grams": "g",
            "ounce": "oz",
            "ounces": "oz",
            "teaspoon": "tsp",
            "teaspoons": "tsp",
            "tablespoon": "tbsp",
            "tablespoons": "tbsp",
            "cups": "cup",
        }

        # Check mapping first
        if unit_str in unit_mapping:
            return unit_mapping[unit_str]

        # Check if it's already a supported unit
        if unit_str in [u.lower() for u in self.SUPPORTED_UNITS]:
            return unit_str

        # If "to taste" is in the string, return "to taste"
        if "to taste" in unit_str:
            return "to taste"

        # Default to "serving" if unknown
        return "serving"

