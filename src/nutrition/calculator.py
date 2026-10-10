"""Nutrition calculator for computing nutrition values for ingredients and recipes."""
from dataclasses import replace
from typing import Dict, Any, Optional, List

from src.data_layer.models import Ingredient, Recipe, NutritionProfile, MicronutrientProfile
from src.data_layer.exceptions import IngredientNotFoundError
from src.providers.ingredient_provider import IngredientDataProvider
from src.ingestion.nutrition_scaler import BASE_SERVING_WEIGHTS


class NutritionCalculator:
    """Calculator for nutrition values of ingredients and recipes.

    Quantities are converted to grams once via ``to_grams`` (using the
    ingredient record's ``grams_per_unit`` and explicit serving weights).
    Pool builders call ``normalize_ingredient`` once per ingredient, which
    stores the grams in ``normalized_quantity`` (``normalized_unit="g"``);
    nutrition is then computed from that value. The authored
    ``quantity``/``unit`` stay for display.
    Nutrition is then scaled from ``per_100g`` (or an equivalent per-unit
    block with a known gram size). Unknown units raise
    ``IngredientNotFoundError`` so the recipe leaves the planning pool
    with ``warnings.nutrition`` — never silent zeros or density guesses.
    """

    # Mass-only conversion; volume needs per-ingredient grams_per_unit.
    OZ_TO_GRAMS = 28.35

    UNIT_ALIASES = {
        "gram": "g",
        "grams": "g",
        "ounce": "oz",
        "ounces": "oz",
        "cups": "cup",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "milliliter": "ml",
        "milliliters": "ml",
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
            IngredientNotFoundError: If ingredient not found, or quantity
                cannot be converted to grams, or no nutrition block exists
            ValueError: If ingredient is marked as "to taste"
        """
        if ingredient.is_to_taste:
            raise ValueError("Cannot calculate nutrition for 'to taste' ingredients")

        # Get ingredient info from provider
        ingredient_info = self.provider.get_ingredient_info(ingredient.name)
        if ingredient_info is None:
            raise IngredientNotFoundError(ingredient.name)

        grams = self._grams(ingredient, ingredient_info)
        nutrition_data, unit_size_g = self._nutrition_block_for_grams(ingredient_info)
        if nutrition_data is None or unit_size_g is None:
            raise IngredientNotFoundError(
                f"{ingredient.name} (no matching nutrition unit found)"
            )

        multiplier = grams / unit_size_g
        calories = nutrition_data.get("calories", 0.0) * multiplier
        protein_g = nutrition_data.get("protein_g", 0.0) * multiplier
        fat_g = nutrition_data.get("fat_g", 0.0) * multiplier
        carbs_g = nutrition_data.get("carbs_g", 0.0) * multiplier
        micronutrients = self._calculate_micronutrients(nutrition_data, multiplier)

        return NutritionProfile(
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            micronutrients=micronutrients,
        )

    def unresolved_ingredient_names(self, recipe: Recipe) -> List[str]:
        """Return sorted unique names of non-to-taste ingredients that cannot be resolved.

        Used by ``convert_recipes`` to drop incomplete recipes from the pool
        (§4.4: no silent zeros). Does not mutate state.

        Conversion failures include the unit in ``IngredientNotFoundError.ingredient_name``
        (e.g. ``"quinoa (no gram conversion for 'cup')"``) so warnings name both.
        """
        missing: set[str] = set()
        for ingredient in recipe.ingredients:
            if ingredient.is_to_taste:
                continue
            try:
                self.calculate_ingredient_nutrition(ingredient)
            except IngredientNotFoundError as exc:
                missing.add(exc.ingredient_name)
            except RuntimeError:
                # API provider: name not pre-resolved via resolve_all
                missing.add(ingredient.name)
        return sorted(missing)

    def calculate_recipe_nutrition(self, recipe: Recipe) -> NutritionProfile:
        """Calculate total nutrition for a recipe.

        Sums resolved ingredients only. Callers that build a planning pool
        must use ``unresolved_ingredient_names`` / ``convert_recipes(..., drop_unresolved=True)``
        so recipes with gaps never enter search with understated macros.

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
                # Partial totals only — pool builders must drop the recipe (§4.4).
                continue

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            micronutrients=MicronutrientProfile(**total_micros),
        )

    def normalize_ingredient(self, ingredient: Ingredient) -> Ingredient:
        """Return a copy with ``normalized_quantity`` in grams (``normalized_unit="g"``).

        The single conversion step of the grams-first design: ``convert_recipes``
        calls it once per ingredient when it builds the planning pool, after
        provider resolution. "To taste" ingredients are returned unchanged.

        Raises:
            IngredientNotFoundError: If the ingredient is unknown or its unit
                has no gram conversion.
        """
        if ingredient.is_to_taste:
            return ingredient
        ingredient_info = self.provider.get_ingredient_info(ingredient.name)
        if ingredient_info is None:
            raise IngredientNotFoundError(ingredient.name)
        grams = self.to_grams(ingredient, ingredient_info)
        return replace(ingredient, normalized_unit="g", normalized_quantity=grams)

    def _grams(self, ingredient: Ingredient, ingredient_info: Dict[str, Any]) -> float:
        """Grams for an ingredient: its normalized value, or ``to_grams`` if not normalized yet."""
        if ingredient.normalized_unit == "g":
            return float(ingredient.normalized_quantity)
        return self.to_grams(ingredient, ingredient_info)

    def to_grams(
        self, ingredient: Ingredient, ingredient_info: Dict[str, Any]
    ) -> float:
        """Convert an ingredient quantity to grams using explicit weights only.

        Order:
          1. ``g`` / ``gram`` / ``grams`` → quantity
          2. ``grams_per_unit[unit]`` (plus ``scoop_size_g`` / ``large_size_g`` on the record)
          3. ``oz`` → 28.35 (mass, safe for any ingredient)
          4. ``BASE_SERVING_WEIGHTS`` for count units with a named entry
          5. otherwise ``IngredientNotFoundError`` (no density guesses)
        """
        quantity = float(ingredient.quantity)
        raw_unit = (ingredient.unit or "").lower().strip()
        unit = self.UNIT_ALIASES.get(raw_unit, raw_unit)
        name_lower = (ingredient.name or "").lower().strip()

        if unit == "g":
            return quantity

        gpu = dict(ingredient_info.get("grams_per_unit") or {})
        # Explicit size fields on the record are the same kind of data as grams_per_unit.
        if "scoop" not in gpu and ingredient_info.get("scoop_size_g") is not None:
            gpu["scoop"] = float(ingredient_info["scoop_size_g"])
        if "large" not in gpu and ingredient_info.get("large_size_g") is not None:
            gpu["large"] = float(ingredient_info["large_size_g"])
        if unit in gpu:
            return quantity * float(gpu[unit])

        if unit == "oz":
            return quantity * self.OZ_TO_GRAMS

        weights = BASE_SERVING_WEIGHTS.get(unit, {})
        weight_per = weights.get(name_lower) or weights.get(name_lower.rstrip("s"))
        if weight_per is not None:
            return quantity * float(weight_per)

        raise IngredientNotFoundError(
            f"{ingredient.name} (no gram conversion for '{ingredient.unit}')"
        )

    def _nutrition_block_for_grams(
        self, ingredient_info: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[float]]:
        """Return (nutrition_dict, grams_per_block) for scaling by grams.

        Prefers ``per_100g``. Falls back to ``per_scoop`` / ``per_large`` when
        those blocks have an explicit gram size on the record.
        """
        if "per_100g" in ingredient_info and ingredient_info["per_100g"] is not None:
            return ingredient_info["per_100g"], 100.0

        if "per_scoop" in ingredient_info and ingredient_info["per_scoop"] is not None:
            scoop_g = ingredient_info.get("scoop_size_g")
            if scoop_g is not None:
                return ingredient_info["per_scoop"], float(scoop_g)

        if "per_large" in ingredient_info and ingredient_info["per_large"] is not None:
            large_g = ingredient_info.get("large_size_g")
            if large_g is not None:
                return ingredient_info["per_large"], float(large_g)
            # Count-weight table may still define the size for a named ingredient.
            # Without a size, we cannot scale from grams — caller raises.

        return None, None

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
