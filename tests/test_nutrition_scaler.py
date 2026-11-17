"""Tests for Step 2.5: Quantity & Unit Scaling.

Tests scaling of normalized nutrition data to reflect user-specified quantities.
Scaling is deterministic - no heuristics, density assumptions, or silent fallbacks.
"""

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
