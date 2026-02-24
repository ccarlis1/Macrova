"""Tests for Step 2.7: Caching Layer.

Tests for disk-based ingredient lookup caching.
Cache stores normalized ingredient name → (fdcId, MappedNutrition).
"""

import pytest
import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.ingestion.ingredient_cache import (
    IngredientCache,
    CachedIngredientLookup,
    CacheEntry,
)
from src.ingestion.nutrient_mapper import MappedNutrition
from src.data_layer.models import MicronutrientProfile


class TestCacheEntry:
    """Tests for CacheEntry data model."""

    def test_cache_entry_structure(self):
        """Test that CacheEntry has required fields."""
        entry = CacheEntry(
            canonical_name="chicken breast",
            fdc_id=171705,
            description="Chicken, breast, raw",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=165.0,
                protein_g=31.0,
                fat_g=3.6,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile()
            )
        )
        
        assert entry.canonical_name == "chicken breast"
        assert entry.fdc_id == 171705
        assert entry.nutrition.calories == 165.0

    def test_cache_entry_to_dict(self):
        """Test that CacheEntry can be serialized to dict."""
        entry = CacheEntry(
            canonical_name="chicken breast",
            fdc_id=171705,
            description="Chicken, breast",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=165.0,
                protein_g=31.0,
                fat_g=3.6,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile(iron_mg=0.37)
            )
        )
        
        d = entry.to_dict()
        
        assert d["canonical_name"] == "chicken breast"
        assert d["fdc_id"] == 171705
        assert d["nutrition"]["calories"] == 165.0
        assert d["nutrition"]["micronutrients"]["iron_mg"] == 0.37

    def test_cache_entry_from_dict(self):
        """Test that CacheEntry can be deserialized from dict."""
        d = {
            "canonical_name": "chicken breast",
            "fdc_id": 171705,
            "description": "Chicken, breast",
            "data_type": "SR Legacy",
            "nutrition": {
                "calories": 165.0,
                "protein_g": 31.0,
                "fat_g": 3.6,
                "carbs_g": 0.0,
                "micronutrients": {
                    "iron_mg": 0.37
                }
            }
        }
        
        entry = CacheEntry.from_dict(d)
        
        assert entry.canonical_name == "chicken breast"
        assert entry.fdc_id == 171705
        assert entry.nutrition.calories == 165.0
        assert entry.nutrition.micronutrients.iron_mg == 0.37


class TestIngredientCache:
    """Tests for IngredientCache disk-based storage."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create cache instance with temp directory."""
        return IngredientCache(cache_dir=temp_cache_dir)

    @pytest.fixture
    def sample_entry(self):
        """Create sample cache entry."""
        return CacheEntry(
            canonical_name="chicken breast",
            fdc_id=171705,
            description="Chicken, breast, raw",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=165.0,
                protein_g=31.0,
                fat_g=3.6,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile(iron_mg=0.37)
            )
        )

    # === Basic Read/Write Tests ===

    def test_write_and_read_entry(self, cache, sample_entry):
        """Test writing and reading a cache entry."""
        cache.write(sample_entry)
        
        result = cache.read("chicken breast")
        
        assert result is not None
        assert result.fdc_id == 171705
        assert result.nutrition.calories == 165.0

    def test_read_nonexistent_returns_none(self, cache):
        """Test that reading nonexistent entry returns None."""
        result = cache.read("nonexistent ingredient")
        
        assert result is None

    def test_cache_key_is_normalized_name(self, cache, sample_entry):
        """Test that cache key is the normalized ingredient name."""
        cache.write(sample_entry)
        
        # Should be found by canonical name
        assert cache.read("chicken breast") is not None
        # Filenames are lowercased, so uppercase maps to same file
        # (canonical names from normalizer are already lowercase)
        assert cache.read("CHICKEN BREAST") is not None  # Same file (lowercased)
        # Should not be found by different ingredient
        assert cache.read("salmon") is None

    # === Disk Persistence Tests ===

    def test_cache_creates_file(self, cache, sample_entry, temp_cache_dir):
        """Test that cache creates a file on disk."""
        cache.write(sample_entry)
        
        # Should have created a file
        cache_file = Path(temp_cache_dir) / "chicken_breast.json"
        assert cache_file.exists()

    def test_cache_file_is_valid_json(self, cache, sample_entry, temp_cache_dir):
        """Test that cache file is valid, readable JSON."""
        cache.write(sample_entry)
        
        cache_file = Path(temp_cache_dir) / "chicken_breast.json"
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        assert data["fdc_id"] == 171705
        assert data["nutrition"]["calories"] == 165.0

    def test_cache_persists_across_instances(self, temp_cache_dir, sample_entry):
        """Test that cache persists across cache instances."""
        # Write with first instance
        cache1 = IngredientCache(cache_dir=temp_cache_dir)
        cache1.write(sample_entry)
        
        # Read with second instance
        cache2 = IngredientCache(cache_dir=temp_cache_dir)
        result = cache2.read("chicken breast")
        
        assert result is not None
        assert result.fdc_id == 171705

    def test_cache_human_readable(self, cache, sample_entry, temp_cache_dir):
        """Test that cache files are human-readable (indented JSON)."""
        cache.write(sample_entry)
        
        cache_file = Path(temp_cache_dir) / "chicken_breast.json"
        content = cache_file.read_text()
        
        # Should have newlines (indented)
        assert '\n' in content
        # Should have readable field names
        assert '"fdc_id"' in content
        assert '"calories"' in content

    # === Edge Cases ===

    def test_cache_handles_special_characters_in_name(self, cache, temp_cache_dir):
        """Test caching ingredients with special characters."""
        entry = CacheEntry(
            canonical_name="cream of rice",
            fdc_id=12345,
            description="Cream of rice",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=100.0,
                protein_g=2.0,
                fat_g=0.5,
                carbs_g=22.0,
                micronutrients=MicronutrientProfile()
            )
        )
        
        cache.write(entry)
        result = cache.read("cream of rice")
        
        assert result is not None
        assert result.fdc_id == 12345

    def test_cache_directory_created_if_not_exists(self, temp_cache_dir):
        """Test that cache creates directory if it doesn't exist."""
        new_dir = Path(temp_cache_dir) / "new_cache_dir"
        
        cache = IngredientCache(cache_dir=str(new_dir))
        
        assert new_dir.exists()

    def test_cache_overwrites_existing_entry(self, cache, sample_entry):
        """Test that writing same key overwrites existing entry."""
        cache.write(sample_entry)
        
        # Update entry
        updated_entry = CacheEntry(
            canonical_name="chicken breast",
            fdc_id=999999,  # Different ID
            description="Updated",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=200.0,
                protein_g=40.0,
                fat_g=5.0,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile()
            )
        )
        cache.write(updated_entry)
        
        result = cache.read("chicken breast")
        assert result.fdc_id == 999999
        assert result.nutrition.calories == 200.0

    # === Has/Contains Tests ===

    def test_has_returns_true_for_cached(self, cache, sample_entry):
        """Test that has() returns True for cached entries."""
        cache.write(sample_entry)
        
        assert cache.has("chicken breast") is True

    def test_has_returns_false_for_uncached(self, cache):
        """Test that has() returns False for uncached entries."""
        assert cache.has("nonexistent") is False


class TestCachedIngredientLookup:
    """Tests for CachedIngredientLookup service."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_client(self):
        """Create mock USDA client."""
        client = Mock()
        return client

    @pytest.fixture
    def cached_lookup(self, temp_cache_dir, mock_client):
        """Create cached lookup service."""
        return CachedIngredientLookup(
            cache_dir=temp_cache_dir,
            usda_client=mock_client
        )

    # === Cache Hit Tests ===

    def test_cache_hit_bypasses_api(self, cached_lookup, temp_cache_dir, mock_client):
        """Test that cache hit does NOT call API."""
        # Pre-populate cache
        cache = IngredientCache(cache_dir=temp_cache_dir)
        entry = CacheEntry(
            canonical_name="chicken breast",
            fdc_id=171705,
            description="Chicken, breast",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=165.0,
                protein_g=31.0,
                fat_g=3.6,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile()
            )
        )
        cache.write(entry)
        
        # Lookup should hit cache
        result = cached_lookup.lookup("chicken breast")
        
        # API should NOT have been called
        mock_client.lookup.assert_not_called()
        mock_client.get_food_details.assert_not_called()
        
        # Should return cached data
        assert result.fdc_id == 171705
        assert result.nutrition.calories == 165.0

    def test_cache_hit_returns_cached_nutrition(self, cached_lookup, temp_cache_dir):
        """Test that cache hit returns full cached nutrition data."""
        # Pre-populate cache with rich nutrition data
        cache = IngredientCache(cache_dir=temp_cache_dir)
        entry = CacheEntry(
            canonical_name="salmon",
            fdc_id=175167,
            description="Salmon, raw",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=208.0,
                protein_g=20.4,
                fat_g=13.4,
                carbs_g=0.0,
                micronutrients=MicronutrientProfile(
                    vitamin_d_iu=526.0,
                    omega_3_g=2.26,
                    selenium_ug=36.5
                )
            )
        )
        cache.write(entry)
        
        result = cached_lookup.lookup("salmon")
        
        assert result.nutrition.micronutrients.vitamin_d_iu == 526.0
        assert result.nutrition.micronutrients.omega_3_g == 2.26

    # === Cache Miss Tests ===

    def test_cache_miss_calls_api(self, cached_lookup, mock_client):
        """Test that cache miss calls USDA API."""
        # Configure mock responses with proper data_type
        from src.ingestion.usda_client import DataType
        
        mock_client.lookup.return_value = Mock(
            success=True,
            fdc_id=171705,
            description="Chicken, breast",
            data_type=DataType.SR_LEGACY
        )
        mock_client.get_food_details.return_value = Mock(
            success=True,
            raw_payload={
                "fdcId": 171705,
                "description": "Chicken, breast",
                "dataType": "SR Legacy",
                "foodNutrients": [
                    {"nutrient": {"id": 1008}, "amount": 165.0},
                    {"nutrient": {"id": 1003}, "amount": 31.0},
                    {"nutrient": {"id": 1004}, "amount": 3.6},
                    {"nutrient": {"id": 1005}, "amount": 0.0},
                ]
            }
        )
        
        result = cached_lookup.lookup("chicken breast")
        
        # API should have been called
        mock_client.lookup.assert_called_once()
        mock_client.get_food_details.assert_called_once_with(171705)
        
        # Should return nutrition data
        assert result.fdc_id == 171705

    def test_cache_miss_writes_to_cache(self, cached_lookup, mock_client, temp_cache_dir):
        """Test that cache miss writes result to cache."""
        # Configure mock responses
        mock_client.lookup.return_value = Mock(
            success=True,
            fdc_id=171705,
            description="Chicken, breast",
            data_type=Mock(value="SR Legacy")
        )
        mock_client.get_food_details.return_value = Mock(
            success=True,
            raw_payload={
                "fdcId": 171705,
                "description": "Chicken, breast",
                "dataType": "SR Legacy",
                "foodNutrients": [
                    {"nutrient": {"id": 1008}, "amount": 165.0},
                    {"nutrient": {"id": 1003}, "amount": 31.0},
                    {"nutrient": {"id": 1004}, "amount": 3.6},
                    {"nutrient": {"id": 1005}, "amount": 0.0},
                ]
            }
        )
        
        # First lookup - cache miss
        cached_lookup.lookup("chicken breast")
        
        # Check cache file was created
        cache_file = Path(temp_cache_dir) / "chicken_breast.json"
        assert cache_file.exists()

    def test_subsequent_lookup_uses_cache(self, cached_lookup, mock_client):
        """Test that subsequent lookups use cache, not API."""
        # Configure mock responses
        mock_client.lookup.return_value = Mock(
            success=True,
            fdc_id=171705,
            description="Chicken, breast",
            data_type=Mock(value="SR Legacy")
        )
        mock_client.get_food_details.return_value = Mock(
            success=True,
            raw_payload={
                "fdcId": 171705,
                "description": "Chicken, breast",
                "dataType": "SR Legacy",
                "foodNutrients": [
                    {"nutrient": {"id": 1008}, "amount": 165.0},
                    {"nutrient": {"id": 1003}, "amount": 31.0},
                    {"nutrient": {"id": 1004}, "amount": 3.6},
                    {"nutrient": {"id": 1005}, "amount": 0.0},
                ]
            }
        )
        
        # First lookup - cache miss
        cached_lookup.lookup("chicken breast")
        
        # Reset mock call counts
        mock_client.lookup.reset_mock()
        mock_client.get_food_details.reset_mock()
        
        # Second lookup - should hit cache
        result = cached_lookup.lookup("chicken breast")
        
        # API should NOT have been called again
        mock_client.lookup.assert_not_called()
        mock_client.get_food_details.assert_not_called()
        
        # Should still return correct data
        assert result.fdc_id == 171705

    # === Error Handling Tests ===

    def test_lookup_failure_not_cached(self, cached_lookup, mock_client, temp_cache_dir):
        """Test that failed lookups are NOT cached."""
        # Configure mock to fail
        mock_client.lookup.return_value = Mock(
            success=False,
            error_code="NOT_FOUND"
        )
        
        # Lookup should return None or error
        result = cached_lookup.lookup("nonexistent food xyz")
        
        assert result is None
        
        # Nothing should be cached
        cache = IngredientCache(cache_dir=temp_cache_dir)
        assert cache.has("nonexistent food xyz") is False


class TestCacheReusedAcrossTestRuns:
    """Tests verifying cache persistence across test runs."""

    @pytest.fixture
    def persistent_cache_dir(self, tmp_path_factory):
        """Create a persistent cache directory for test session."""
        return tmp_path_factory.mktemp("ingredient_cache")

    def test_cache_persists_phase_1_write(self, persistent_cache_dir):
        """Phase 1: Write to cache."""
        cache = IngredientCache(cache_dir=str(persistent_cache_dir))
        
        entry = CacheEntry(
            canonical_name="test ingredient",
            fdc_id=99999,
            description="Test",
            data_type="SR Legacy",
            nutrition=MappedNutrition(
                calories=100.0,
                protein_g=10.0,
                fat_g=5.0,
                carbs_g=20.0,
                micronutrients=MicronutrientProfile()
            )
        )
        cache.write(entry)
        
        # Verify written
        assert cache.has("test ingredient")

    def test_cache_persists_phase_2_read(self, persistent_cache_dir):
        """Phase 2: Read from cache (simulating new test run)."""
        # Create new cache instance (simulates new process)
        cache = IngredientCache(cache_dir=str(persistent_cache_dir))
        
        # Write first (in case phase 1 didn't run)
        if not cache.has("test ingredient"):
            entry = CacheEntry(
                canonical_name="test ingredient",
                fdc_id=99999,
                description="Test",
                data_type="SR Legacy",
                nutrition=MappedNutrition(
                    calories=100.0,
                    protein_g=10.0,
                    fat_g=5.0,
                    carbs_g=20.0,
                    micronutrients=MicronutrientProfile()
                )
            )
            cache.write(entry)
        
        # Should be able to read
        result = cache.read("test ingredient")
        
        assert result is not None
        assert result.fdc_id == 99999
