"""Canonical τ-scaled weekly micronutrient minimums (prorated RDI × horizon).

Planning phases must use these helpers for any comparison against the weekly or
cumulative micronutrient *floor* instead of inlining ``daily_rdi * D`` or
``tau * daily_rdi * D``. Upper-limit (UL) validation must not depend on this
module — τ applies only to RDI minimum paths.

See MEALPLAN_SPECIFICATION_v1 (micronutrient_weekly_min_fraction τ).
"""

from __future__ import annotations

from typing import Any

# Tolerance for floating-point boundaries (matches legacy phase7 normalization).
MICRONUTRIENT_EPSILON = 1e-9


def validate_micronutrient_weekly_min_fraction(tau: float) -> float:
    """τ must lie in (0, 1]. Used at YAML / API profile load time."""
    t = float(tau)
    if t <= 0.0 or t > 1.0:
        raise ValueError(
            f"micronutrient_weekly_min_fraction (τ) must be in (0, 1]; got {tau!r}"
        )
    return t


def weekly_minimum_total(daily_rdi: float, D: int, tau: float) -> float:
    """Horizon floor: τ × daily_rdi × D (acceptance / structural / FC-4 target)."""
    return tau * daily_rdi * D


def cumulative_minimum_total(daily_rdi: float, days_completed: int, tau: float) -> float:
    """Cumulative floor after k completed days: τ × daily_rdi × k (carryover)."""
    return tau * daily_rdi * days_completed


def weekly_deficit_to_minimum(
    consumed: float,
    daily_rdi: float,
    D: int,
    tau: float,
) -> float:
    """Signed shortfall vs τ-weekly minimum (positive ⇒ need more to reach floor)."""
    return weekly_minimum_total(daily_rdi, D, tau) - consumed


def is_below_weekly_minimum(
    consumed: float,
    daily_rdi: float,
    D: int,
    tau: float,
) -> bool:
    """True if consumed is strictly below the τ-weekly minimum beyond FP tolerance."""
    return consumed < weekly_minimum_total(daily_rdi, D, tau) - MICRONUTRIENT_EPSILON


def tau_from_profile(profile: Any) -> float:
    """Read τ from a planning profile; default 1.0 until the field exists everywhere."""
    return float(getattr(profile, "micronutrient_weekly_min_fraction", 1.0))


def sodium_weekly_advisory_max_mg(daily_rdi: float, D: int) -> float:
    """2.0 × full prorated sodium RDI (not scaled by τ). Spec 6.6 advisory only."""
    return 2.0 * weekly_minimum_total(daily_rdi, D, 1.0)
