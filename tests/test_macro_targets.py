"""Unit tests for shared macro-target validation (§4.2)."""

from __future__ import annotations

import pytest

from src.data_layer.macro_targets import MacroTargetsError, validate_macro_targets


def test_mb053_falls_back_to_fat_min():
    """D9: 2,000 kcal / 150 g protein / fat 150–170 → −10 g at the median, 12.5 g at the fat min."""
    carbs = validate_macro_targets(2000, 150, 150, 170)
    assert carbs == pytest.approx(12.5)


def test_negative_carbs_at_fat_min_rejected():
    """2,000 kcal / 150 g protein / fat 160–180 → −32.5 g at the median, still −10 g at the fat min."""
    with pytest.raises(MacroTargetsError) as exc:
        validate_macro_targets(2000, 150, 160, 180)
    assert exc.value.reason == "NEGATIVE_CARBS_DERIVED"
    assert exc.value.details["daily_carbs_g"] == pytest.approx(-10.0)
    assert exc.value.details["protein_kcal"] == pytest.approx(600.0)
    assert exc.value.details["fat_kcal_min"] == pytest.approx(1440.0)
    assert exc.value.details["fat_kcal_median"] == pytest.approx(1530.0)
    assert exc.value.details["daily_calories"] == pytest.approx(2000.0)


def test_median_used_when_non_negative():
    """The fat-min fallback only applies when the median leaves negative carbs."""
    assert validate_macro_targets(2000, 150, 60, 80) == pytest.approx((2000 - 600 - 70 * 9) / 4)


def test_mb050_low_but_non_negative_carbs_valid():
    """Crash diet: ~21.2 g derived carbs stays valid."""
    carbs = validate_macro_targets(1200, 200, 30, 40)
    assert carbs == pytest.approx(21.25)


def test_mb052_keto_macros_valid():
    """Keto: ~27.5 g derived carbs stays valid."""
    carbs = validate_macro_targets(1800, 130, 120, 140)
    assert carbs == pytest.approx(27.5)


def test_exactly_zero_derived_carbs_valid():
    """Exactly 0 g derived carbs is valid (§2.1 note)."""
    # 2000 - 100*4 - 177.777...*9 ≈ 0 when fat median = 1600/9
    fat = 1600.0 / 9.0
    carbs = validate_macro_targets(2000, 100, fat, fat)
    assert carbs == pytest.approx(0.0)


def test_fat_range_inverted_rejected():
    with pytest.raises(MacroTargetsError) as exc:
        validate_macro_targets(2000, 150, 90, 60)
    assert exc.value.reason == "FAT_RANGE_INVERTED"
    assert exc.value.details["fat_g_min"] == pytest.approx(90.0)
    assert exc.value.details["fat_g_max"] == pytest.approx(60.0)


def test_zero_calories_rejected():
    with pytest.raises(MacroTargetsError) as exc:
        validate_macro_targets(0, 150, 60, 80)
    assert exc.value.reason == "NON_POSITIVE_CALORIES"


def test_negative_protein_rejected():
    with pytest.raises(MacroTargetsError) as exc:
        validate_macro_targets(2000, -1, 60, 80)
    assert exc.value.reason == "NEGATIVE_PROTEIN"


def test_negative_fat_min_rejected():
    with pytest.raises(MacroTargetsError) as exc:
        validate_macro_targets(2000, 150, -5, 80)
    assert exc.value.reason == "NEGATIVE_FAT_MIN"
