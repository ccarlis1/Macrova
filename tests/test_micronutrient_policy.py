"""Unit tests for τ-scaled weekly micronutrient policy helpers."""

import pytest

from src.planning.micronutrient_policy import (
    MICRONUTRIENT_EPSILON,
    cumulative_minimum_total,
    is_below_weekly_minimum,
    sodium_weekly_advisory_max_mg,
    validate_micronutrient_weekly_min_fraction,
    weekly_deficit_to_minimum,
    weekly_minimum_total,
)


def test_weekly_minimum_total_tau_one():
    assert weekly_minimum_total(100.0, 7, 1.0) == 700.0


def test_weekly_minimum_total_relaxed():
    assert weekly_minimum_total(100.0, 7, 0.9) == 630.0


def test_cumulative_matches_weekly_when_full_horizon():
    daily = 50.0
    D = 5
    tau = 0.9
    assert cumulative_minimum_total(daily, D, tau) == weekly_minimum_total(daily, D, tau)


def test_boundary_is_not_below_at_exact_minimum():
    target = weekly_minimum_total(10.0, 3, 1.0)
    assert not is_below_weekly_minimum(target, 10.0, 3, 1.0)
    assert is_below_weekly_minimum(
        target - 2 * MICRONUTRIENT_EPSILON, 10.0, 3, 1.0
    )


def test_weekly_deficit_to_minimum_sign():
    assert weekly_deficit_to_minimum(700.0, 100.0, 7, 1.0) == 0.0
    assert weekly_deficit_to_minimum(650.0, 100.0, 7, 1.0) == 50.0


def test_sodium_advisory_not_scaled_by_tau():
    assert sodium_weekly_advisory_max_mg(100.0, 7) == 2.0 * 700.0


def test_validate_tau_accepts_open_closed_interval():
    assert validate_micronutrient_weekly_min_fraction(1.0) == 1.0
    assert validate_micronutrient_weekly_min_fraction(0.9) == 0.9
    x = validate_micronutrient_weekly_min_fraction(1e-12)
    assert x == pytest.approx(1e-12)


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.01, 2.0])
def test_validate_tau_rejects_out_of_range(bad: float):
    with pytest.raises(ValueError):
        validate_micronutrient_weekly_min_fraction(bad)
