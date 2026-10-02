"""Shared validation for daily macro targets (§2.1 / §4.2).

Carbs are never an input: they are derived as
``(daily_calories - protein_g * 4 - median_fat_g * 9) / 4``.
A profile with negative derived carbs (or other inconsistent targets) is
rejected before planning.
"""

from __future__ import annotations

from typing import Any, Dict


class MacroTargetsError(ValueError):
    """Raised when daily macro targets are invalid before planning."""

    def __init__(self, reason: str, message: str, details: Dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if not self.details:
            return f"{self.reason}: {self.message}"
        return f"{self.reason}: {self.message} ({sorted(self.details.items())})"


def validate_macro_targets(
    calories: float,
    protein_g: float,
    fat_min: float,
    fat_max: float,
) -> float:
    """Validate macro targets and return derived ``daily_carbs_g``.

    Raises:
        MacroTargetsError: when targets are inconsistent / non-physical.
    """
    calories_f = float(calories)
    protein_f = float(protein_g)
    fat_min_f = float(fat_min)
    fat_max_f = float(fat_max)

    if calories_f <= 0:
        raise MacroTargetsError(
            reason="NON_POSITIVE_CALORIES",
            message="daily_calories must be greater than zero.",
            details={"daily_calories": calories_f},
        )
    if protein_f < 0:
        raise MacroTargetsError(
            reason="NEGATIVE_PROTEIN",
            message="daily_protein_g must not be negative.",
            details={"daily_protein_g": protein_f},
        )
    if fat_min_f < 0:
        raise MacroTargetsError(
            reason="NEGATIVE_FAT_MIN",
            message="daily_fat_g.min must not be negative.",
            details={"fat_g_min": fat_min_f},
        )
    if fat_min_f > fat_max_f:
        raise MacroTargetsError(
            reason="FAT_RANGE_INVERTED",
            message="daily_fat_g.min must not exceed daily_fat_g.max.",
            details={"fat_g_min": fat_min_f, "fat_g_max": fat_max_f},
        )

    median_fat_g = (fat_min_f + fat_max_f) / 2.0
    protein_kcal = protein_f * 4.0
    fat_kcal_median = median_fat_g * 9.0
    daily_carbs_g = (calories_f - protein_kcal - fat_kcal_median) / 4.0

    if daily_carbs_g < 0:
        raise MacroTargetsError(
            reason="NEGATIVE_CARBS_DERIVED",
            message=(
                "Derived carbs are negative: protein and fat use more calories "
                "than the daily calorie target."
            ),
            details={
                "daily_carbs_g": daily_carbs_g,
                "protein_kcal": protein_kcal,
                "fat_kcal_median": fat_kcal_median,
                "daily_calories": calories_f,
            },
        )

    return daily_carbs_g
