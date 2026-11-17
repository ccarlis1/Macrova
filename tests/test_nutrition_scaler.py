"""Tests for the named serving weights used to convert count units to grams."""

from src.ingestion.nutrition_scaler import (
    BASE_SERVING_WEIGHTS,
)


class TestBaseServingWeights:
    """Tests for base serving weight definitions."""

    def test_large_egg_defined(self):
        """Test that large egg has a defined weight."""
        assert "large" in BASE_SERVING_WEIGHTS
        # 1 large egg ≈ 50g
        assert BASE_SERVING_WEIGHTS["large"]["egg"] == 50.0

    def test_scoop_requires_context(self):
        """Test that scoop is in serving weights."""
        assert "scoop" in BASE_SERVING_WEIGHTS
