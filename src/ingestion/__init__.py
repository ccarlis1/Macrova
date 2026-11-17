"""Ingestion layer for parsing and retrieving data."""

from src.ingestion.ingredient_validator import (
    IngredientValidator,
    ValidationError,
    ValidationResult,
)

from src.ingestion.ingredient_normalizer import (
    IngredientNormalizer,
    NormalizationResult,
    CONTROLLED_DESCRIPTORS,
)

from src.ingestion.usda_client import (
    USDAClient,
    USDALookupResult,
    USDALookupError,
    FoodDetailsResult,
    DataType,
)

from src.ingestion.nutrient_mapper import (
    NutrientMapper,
    MappedNutrition,
    USDA_NUTRIENT_MAP,
)

from src.ingestion.nutrition_scaler import (
    BASE_SERVING_WEIGHTS,
)

from src.ingestion.ingredient_cache import (
    IngredientCache,
    CachedIngredientLookup,
    CacheEntry,
)

__all__ = [
    # Ingredient validation
    "IngredientValidator",
    "ValidationError",
    "ValidationResult",
    # Ingredient name normalization
    "IngredientNormalizer",
    "NormalizationResult",
    "CONTROLLED_DESCRIPTORS",
    # USDA API client
    "USDAClient",
    "USDALookupResult",
    "USDALookupError",
    "FoodDetailsResult",
    "DataType",
    # Nutrient mapping
    "NutrientMapper",
    "MappedNutrition",
    "USDA_NUTRIENT_MAP",
    # Nutrition scaling
    "BASE_SERVING_WEIGHTS",
    # Ingredient caching
    "IngredientCache",
    "CachedIngredientLookup",
    "CacheEntry",
]
