"""API: τ (micronutrient_weekly_min_fraction) on PlanRequest maps into UserProfile."""

from src.api.server import PlanRequest, _build_user_profile
from src.planning.converters import convert_profile


def test_plan_request_default_tau_strict():
    req = PlanRequest(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g_min=50.0,
        daily_fat_g_max=80.0,
        schedule={"12:00": 2},
    )
    assert req.micronutrient_weekly_min_fraction == 1.0


def test_build_user_profile_passes_tau_to_data_layer():
    req = PlanRequest(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g_min=50.0,
        daily_fat_g_max=80.0,
        schedule={"12:00": 2},
        micronutrient_weekly_min_fraction=0.9,
    )
    profile, _ = _build_user_profile(req)
    assert profile.micronutrient_weekly_min_fraction == 0.9
    planning = convert_profile(profile, days=3)
    assert planning.micronutrient_weekly_min_fraction == 0.9
