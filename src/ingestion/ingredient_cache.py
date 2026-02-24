"""Disk-based caching for ingredient lookups (Step 2.7).

This module provides deterministic caching for ingredient nutrition data.
Cache stores: normalized ingredient name → (fdcId, MappedNutrition)

DESIGN DECISIONS:
- Disk-based cache (not in-memory only) for persistence across runs
- JSON format for human readability and debuggability
- Cache key is normalized ingredient name (from Step 2.1)
- Cache stores post-mapping nutrition (Step 2.4), pre-scaling
- No silent invalidation or auto-refresh

WHY CACHING OCCURS BEFORE SCALING:
1. Same ingredient (e.g., "chicken breast") always has same per-100g nutrition
2. Scaling depends on user-specified quantity (varies per recipe)
3. Caching pre-scaled data allows reuse across different quantities
4. Example: "200g chicken breast" and "150g chicken breast" both hit
   the same cache entry, then scale differently

HOW THIS STABILIZES TESTS AND PLANNER:
1. Tests don't need network access after cache is populated
2. API rate limits don't affect test runs
3. Deterministic: same input → same cached output
4. Planner behavior is consistent (not dependent on live API)
"""

import json
import os
import re
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional, Dict, Any

from src.ingestion.nutrient_mapper import MappedNutrition, NutrientMapper
from src.data_layer.models import MicronutrientProfile


@dataclass
class CacheEntry:
    """Cached ingredient lookup result.
    
    Stores the resolved ingredient data after USDA lookup and nutrient mapping.
    This is pre-scaling data (per 100g from USDA).
    
    Attributes:
        canonical_name: Normalized ingredient name (cache key)
        fdc_id: USDA FoodData Central ID
        description: Food description from USDA
        data_type: USDA data type (SR Legacy, Foundation, etc.)
        nutrition: Mapped nutrition data (per 100g)
    """
    canonical_name: str
    fdc_id: int
    description: str
    data_type: str
    nutrition: MappedNutrition
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of cache entry
        """
        return {
            "canonical_name": self.canonical_name,
            "fdc_id": self.fdc_id,
            "description": self.description,
            "data_type": self.data_type,
            "nutrition": {
                "calories": self.nutrition.calories,
                "protein_g": self.nutrition.protein_g,
                "fat_g": self.nutrition.fat_g,
                "carbs_g": self.nutrition.carbs_g,
                "micronutrients": {
                    field.name: getattr(self.nutrition.micronutrients, field.name)
                    for field in fields(self.nutrition.micronutrients)
                }
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create CacheEntry from dictionary.
        
        Args:
            data: Dictionary from JSON cache file
            
        Returns:
            CacheEntry instance
        """
        # Reconstruct MicronutrientProfile
        micro_data = data.get("nutrition", {}).get("micronutrients", {})
        micronutrients = MicronutrientProfile(**micro_data)
        
        # Reconstruct MappedNutrition
        nutrition_data = data.get("nutrition", {})
        nutrition = MappedNutrition(
            calories=nutrition_data.get("calories", 0.0),
            protein_g=nutrition_data.get("protein_g", 0.0),
            fat_g=nutrition_data.get("fat_g", 0.0),
            carbs_g=nutrition_data.get("carbs_g", 0.0),
            micronutrients=micronutrients
        )
        
        return cls(
            canonical_name=data.get("canonical_name", ""),
            fdc_id=data.get("fdc_id", 0),
            description=data.get("description", ""),
            data_type=data.get("data_type", ""),
            nutrition=nutrition
        )


class IngredientCache:
    """Disk-based cache for ingredient nutrition data.
    
    Stores cached entries as JSON files in a configurable directory.
    Each ingredient gets its own file for easy inspection and debugging.
    
    Usage:
        cache = IngredientCache(cache_dir="./cache/ingredients")
        
        # Write to cache
        cache.write(entry)
        
        # Read from cache
        entry = cache.read("chicken breast")
        
        # Check if cached
        if cache.has("chicken breast"):
            ...
    """
    
    DEFAULT_CACHE_DIR = ".cache/ingredients"
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache with directory path.
        
        Args:
            cache_dir: Directory for cache files (created if not exists)
        """
        self.cache_dir = Path(cache_dir or self.DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def write(self, entry: CacheEntry) -> None:
        """Write entry to cache.
        
        Args:
            entry: CacheEntry to cache
        """
        file_path = self._get_file_path(entry.canonical_name)
        
        with open(file_path, 'w') as f:
            json.dump(entry.to_dict(), f, indent=2)
    
    def read(self, canonical_name: str) -> Optional[CacheEntry]:
        """Read entry from cache.
        
        Args:
            canonical_name: Normalized ingredient name
            
        Returns:
            CacheEntry if found, None otherwise
        """
        file_path = self._get_file_path(canonical_name)
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            # Corrupted cache file - treat as miss
            return None
    
    def has(self, canonical_name: str) -> bool:
        """Check if ingredient is cached.
        
        Args:
            canonical_name: Normalized ingredient name
            
        Returns:
            True if cached, False otherwise
        """
        file_path = self._get_file_path(canonical_name)
        return file_path.exists()
    
    def _get_file_path(self, canonical_name: str) -> Path:
        """Get file path for cache entry.
        
        Args:
            canonical_name: Normalized ingredient name
            
        Returns:
            Path to cache file
        """
        # Convert name to safe filename
        safe_name = self._to_safe_filename(canonical_name)
        return self.cache_dir / f"{safe_name}.json"
    
    def _to_safe_filename(self, name: str) -> str:
        """Convert ingredient name to safe filename.
        
        Args:
            name: Ingredient name
            
        Returns:
            Filesystem-safe filename (without extension)
        """
        # Replace spaces and special chars with underscores
        safe = re.sub(r'[^\w\-]', '_', name.lower())
        # Collapse multiple underscores
        safe = re.sub(r'_+', '_', safe)
        # Remove leading/trailing underscores
        safe = safe.strip('_')
        return safe or "unnamed"


class CachedIngredientLookup:
    """High-level service for cached ingredient lookups.
    
    Combines cache with USDA API client for transparent caching:
    - Cache hit → return cached nutrition
    - Cache miss → call API, map nutrients, cache result, return
    
    Usage:
        from src.ingestion import USDAClient
        
        client = USDAClient.from_env()
        lookup = CachedIngredientLookup(
            cache_dir="./cache/ingredients",
            usda_client=client
        )
        
        # Transparent caching
        result = lookup.lookup("chicken breast")
        # result.fdc_id, result.nutrition available
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        usda_client = None
    ):
        """Initialize cached lookup service.
        
        Args:
            cache_dir: Directory for cache files
            usda_client: USDAClient instance for API calls
        """
        self.cache = IngredientCache(cache_dir=cache_dir)
        self.client = usda_client
        self.mapper = NutrientMapper()
    
    def lookup(self, canonical_name: str) -> Optional[CacheEntry]:
        """Look up ingredient with caching.
        
        Args:
            canonical_name: Normalized ingredient name
            
        Returns:
            CacheEntry with fdc_id and nutrition, or None if not found
        """
        # Check cache first
        cached = self.cache.read(canonical_name)
        if cached is not None:
            return cached
        
        # Cache miss - call API
        if self.client is None:
            return None
        
        # Step 2.2: Search for ingredient
        lookup_result = self.client.lookup(canonical_name)
        if not lookup_result.success:
            return None
        
        # Step 2.3: Get nutrition data
        details = self.client.get_food_details(lookup_result.fdc_id)
        if not details.success:
            return None
        
        # Step 2.4: Map nutrients
        nutrition = self.mapper.map_nutrients(details.raw_payload)
        
        # Get data type
        data_type = ""
        if hasattr(lookup_result, 'data_type') and lookup_result.data_type:
            data_type = lookup_result.data_type.value if hasattr(lookup_result.data_type, 'value') else str(lookup_result.data_type)
        
        # Create cache entry
        entry = CacheEntry(
            canonical_name=canonical_name,
            fdc_id=lookup_result.fdc_id,
            description=lookup_result.description or "",
            data_type=data_type,
            nutrition=nutrition
        )
        
        # Write to cache
        self.cache.write(entry)
        
        return entry
    
    def lookup_and_scale(
        self,
        canonical_name: str,
        quantity: float,
        unit: str,
        ingredient_context: Optional[str] = None,
        serving_weight_grams: Optional[float] = None
    ):
        """Look up ingredient and scale to quantity.
        
        Convenience method that combines caching with scaling.
        
        Args:
            canonical_name: Normalized ingredient name
            quantity: User-specified quantity
            unit: User-specified unit
            ingredient_context: Optional context for count units
            serving_weight_grams: Optional explicit serving weight
            
        Returns:
            ScaledNutrition or None if lookup fails
        """
        from src.ingestion.nutrition_scaler import NutritionScaler
        
        entry = self.lookup(canonical_name)
        if entry is None:
            return None
        
        scaler = NutritionScaler()
        return scaler.scale(
            nutrition=entry.nutrition,
            quantity=quantity,
            unit=unit,
            base_grams=100.0,  # USDA data is per 100g
            ingredient_context=ingredient_context,
            serving_weight_grams=serving_weight_grams
        )
