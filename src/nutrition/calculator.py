"""Nutrition calculator for computing nutrition values for ingredients and recipes."""
from typing import Dict, Any, Optional, List

from src.data_layer.models import Ingredient, Recipe, NutritionProfile, MicronutrientProfile
from src.data_layer.exceptions import IngredientNotFoundError
from src.providers.ingredient_provider import IngredientDataProvider


class NutritionCalculator:
    """Calculator for nutrition values of ingredients and recipes."""

    # Common unit conversions (for MVP - common cases only)
    UNIT_CONVERSIONS = {
        "oz": 28.35,  # oz to grams
        "cup": 240.0,  # cup to ml (approximate)
        "tsp": 4.93,  # tsp to ml
        "tbsp": 14.79,  # tbsp to ml
    }

    # Micronutrient field names that match MicronutrientProfile attributes
    # These are the keys we look for in ingredient nutrition data
    MICRONUTRIENT_FIELDS: List[str] = [
        # Vitamins
        "vitamin_a_ug",
        "vitamin_c_mg",
        "vitamin_d_iu",
        "vitamin_e_mg",
        "vitamin_k_ug",
        "b1_thiamine_mg",
        "b2_riboflavin_mg",
        "b3_niacin_mg",
        "b5_pantothenic_acid_mg",
        "b6_pyridoxine_mg",
        "b12_cobalamin_ug",
        "folate_ug",
        # Minerals
        "calcium_mg",
        "copper_mg",
        "iron_mg",
        "magnesium_mg",
        "manganese_mg",
        "phosphorus_mg",
        "potassium_mg",
        "selenium_ug",
        "sodium_mg",
        "zinc_mg",
        # Other
        "fiber_g",
        "omega_3_g",
        "omega_6_g",
    ]

    def __init__(self, provider: IngredientDataProvider):
        """Initialize calculator with ingredient data provider.
        
        Args:
            provider: IngredientDataProvider instance for nutrition data lookup
        """
        self.provider = provider

    def calculate_ingredient_nutrition(
        self, ingredient: Ingredient
    ) -> NutritionProfile:
        """Calculate nutrition for a single ingredient.
        
        Args:
            ingredient: Ingredient object (must not be "to taste")
        
        Returns:
            NutritionProfile with calculated nutrition
        
        Raises:
            IngredientNotFoundError: If ingredient not found in database
            ValueError: If ingredient is marked as "to taste"
        """
        if ingredient.is_to_taste:
            raise ValueError("Cannot calculate nutrition for 'to taste' ingredients")

        # Get ingredient info from provider
        ingredient_info = self.provider.get_ingredient_info(ingredient.name)
        if ingredient_info is None:
            raise IngredientNotFoundError(ingredient.name)

        # Find appropriate unit key for nutrition lookup
        unit_key = self._find_nutrition_unit_key(ingredient, ingredient_info)
        if unit_key is None:
            raise IngredientNotFoundError(
                f"{ingredient.name} (no matching nutrition unit found)"
            )

        # Get nutrition data for the unit
        nutrition_data = ingredient_info.get(unit_key)
        if nutrition_data is None:
            raise IngredientNotFoundError(
                f"{ingredient.name} (no nutrition data for {unit_key})"
            )

        # Get unit size for calculation
        unit_size = self._get_unit_size(unit_key, ingredient_info)

        # For per_scoop and per_large, quantity is already in the right unit
        # For per_100g, we need to convert quantity to grams
        if unit_key == "per_100g":
            # Convert quantity to grams
            converted_quantity = self._convert_quantity_to_grams(ingredient)
            # Calculate: (nutrition_per_100g * converted_quantity_g) / 100
            calories = (nutrition_data.get("calories", 0.0) * converted_quantity) / 100.0
            protein_g = (nutrition_data.get("protein_g", 0.0) * converted_quantity) / 100.0
            fat_g = (nutrition_data.get("fat_g", 0.0) * converted_quantity) / 100.0
            carbs_g = (nutrition_data.get("carbs_g", 0.0) * converted_quantity) / 100.0
            # Calculate micronutrients with same scaling
            micronutrients = self._calculate_micronutrients(
                nutrition_data, converted_quantity / 100.0
            )
        else:
            # For per_scoop or per_large, quantity is already in the right unit
            # Calculate: nutrition_per_unit * quantity
            calories = nutrition_data.get("calories", 0.0) * ingredient.quantity
            protein_g = nutrition_data.get("protein_g", 0.0) * ingredient.quantity
            fat_g = nutrition_data.get("fat_g", 0.0) * ingredient.quantity
            carbs_g = nutrition_data.get("carbs_g", 0.0) * ingredient.quantity
            # Calculate micronutrients with same scaling
            micronutrients = self._calculate_micronutrients(
                nutrition_data, ingredient.quantity
            )

        return NutritionProfile(
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            micronutrients=micronutrients,
        )

    def calculate_recipe_nutrition(self, recipe: Recipe) -> NutritionProfile:
        """Calculate total nutrition for a recipe.
        
        Args:
            recipe: Recipe object with ingredients
        
        Returns:
            NutritionProfile with summed nutrition (excludes "to taste" ingredients)
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        # Initialize micronutrient totals
        total_micros: Dict[str, float] = {field: 0.0 for field in self.MICRONUTRIENT_FIELDS}

        # Filter out "to taste" ingredients
        for ingredient in recipe.ingredients:
            if ingredient.is_to_taste:
                continue

            try:
                ingredient_nutrition = self.calculate_ingredient_nutrition(ingredient)
                total_calories += ingredient_nutrition.calories
                total_protein += ingredient_nutrition.protein_g
                total_fat += ingredient_nutrition.fat_g
                total_carbs += ingredient_nutrition.carbs_g
                # Aggregate micronutrients
                if ingredient_nutrition.micronutrients is not None:
                    self._add_micronutrients(total_micros, ingredient_nutrition.micronutrients)
            except IngredientNotFoundError:
                # Log warning but continue with other ingredients
                # In MVP, we'll skip missing ingredients
                continue

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            micronutrients=MicronutrientProfile(**total_micros),
        )

    def _find_nutrition_unit_key(
        self, ingredient: Ingredient, ingredient_info: Dict[str, Any]
    ) -> Optional[str]:
        """Find appropriate unit key for nutrition lookup.
        
        Args:
            ingredient: Ingredient object
            ingredient_info: Full ingredient info from provider
        
        Returns:
            Unit key (e.g., "per_100g", "per_scoop", "per_large") or None
        """
        unit = ingredient.unit.lower()

        # Map ingredient units to nutrition DB keys
        unit_mapping = {
            "g": "per_100g",
            "gram": "per_100g",
            "grams": "per_100g",
            "oz": "per_100g",  # Will convert oz to g
            "ounce": "per_100g",
            "ounces": "per_100g",
            "scoop": "per_scoop",
            "large": "per_large",
            "serving": "per_100g",  # Default to per_100g for servings
        }

        # Try direct mapping first
        if unit in unit_mapping:
            key = unit_mapping[unit]
            # Check if this key exists in ingredient_info
            if key in ingredient_info:
                return key

        # Try to find any matching key
        # Priority: per_scoop, per_large, per_100g
        for key in ["per_scoop", "per_large", "per_100g"]:
            if key in ingredient_info:
                return key

        return None

    def _convert_quantity_to_grams(self, ingredient: Ingredient) -> float:
        """Convert ingredient quantity to grams.
        
        Args:
            ingredient: Ingredient object
        
        Returns:
            Quantity in grams
        """
        quantity = ingredient.quantity
        unit = ingredient.unit.lower()

        if unit == "g" or unit == "gram" or unit == "grams":
            return quantity
        elif unit == "oz" or unit == "ounce" or unit == "ounces":
            # Convert oz to grams
            return quantity * self.UNIT_CONVERSIONS["oz"]
        elif unit == "serving":
            # For servings, assume 1 serving = 100g (default)
            # This is a simplification for MVP
            return quantity * 100.0
        else:
            # Default: assume grams
            return quantity

    def _get_unit_size(self, unit_key: str, ingredient_info: Dict[str, Any]) -> float:
        """Get the size of the unit for nutrition calculation.
        
        Args:
            unit_key: Nutrition unit key (e.g., "per_100g")
            ingredient_info: Full ingredient info
        
        Returns:
            Unit size (e.g., 100.0 for "per_100g")
        """
        if unit_key == "per_100g":
            return 100.0
        elif unit_key == "per_scoop":
            # Get scoop size from ingredient_info if available
            return ingredient_info.get("scoop_size_g", 30.0)  # Default 30g
        elif unit_key == "per_large":
            # Get large size from ingredient_info if available
            return ingredient_info.get("large_size_g", 50.0)  # Default 50g
        else:
            return 1.0  # Default to 1

    def _calculate_micronutrients(
        self, nutrition_data: Dict[str, Any], multiplier: float
    ) -> MicronutrientProfile:
        """Calculate micronutrient values from nutrition data.
        
        Args:
            nutrition_data: Dict containing nutrition values (may include micronutrients)
            multiplier: Scaling factor based on quantity (e.g., 2.0 for 200g when per_100g)
        
        Returns:
            MicronutrientProfile with calculated values (zeros for missing data)
        """
        micro_values: Dict[str, float] = {}
        
        for field in self.MICRONUTRIENT_FIELDS:
            # Get value from nutrition data, default to 0.0 if not present
            base_value = nutrition_data.get(field, 0.0)
            micro_values[field] = base_value * multiplier
        
        return MicronutrientProfile(**micro_values)

    def _add_micronutrients(
        self, totals: Dict[str, float], micros: MicronutrientProfile
    ) -> None:
        """Add micronutrient values to running totals.
        
        Args:
            totals: Dict of running micronutrient totals (modified in place)
            micros: MicronutrientProfile to add
        """
        for field in self.MICRONUTRIENT_FIELDS:
            totals[field] += getattr(micros, field, 0.0)

