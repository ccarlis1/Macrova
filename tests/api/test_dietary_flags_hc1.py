"""F9: dietary_flags on PlanRequest reach HC-1 exclusions over HTTP.

Regression: ``str(DietaryFlag.gluten_free)`` is ``"DietaryFlag.gluten_free"``,
which mapped to no exclusions, so the flag was silently dropped on the API path.
"""

from __future__ import annotations

import pytest

from src.api.server import PlanRequest, _build_user_profile
from src.llm.schemas import DietaryFlag
from src.planning.allergens import dietary_flag_violations, exclusions_for_dietary_flags
from src.planning.converters import convert_profile


def _request(**overrides) -> PlanRequest:
    kw = dict(
        daily_calories=2000,
        daily_protein_g=120.0,
        daily_fat_g_min=55.0,
        daily_fat_g_max=85.0,
        schedule={"07:30": 3, "12:30": 3, "18:30": 4},
        days=1,
    )
    kw.update(overrides)
    return PlanRequest(**kw)


@pytest.mark.parametrize(
    "flag, must_exclude",
    [
        ("gluten_free", {"pasta", "sourdough bread", "soy sauce"}),
        ("dairy_free", {"milk", "butter"}),
        ("vegetarian", {"chicken breast", "salmon"}),
        ("vegan", {"eggs", "chicken breast", "honey"}),
    ],
)
def test_plan_request_flag_becomes_hc1_exclusion(flag, must_exclude):
    user_profile, _ = _build_user_profile(_request(dietary_flags=[flag]))
    assert user_profile.dietary_flags == [flag]
    planning = convert_profile(user_profile, days=1)
    assert must_exclude <= set(planning.excluded_ingredients)


def test_flags_append_after_allergies_without_duplicates():
    user_profile, _ = _build_user_profile(
        _request(allergies=["gluten"], dietary_flags=["gluten_free"])
    )
    excluded = convert_profile(user_profile, days=1).excluded_ingredients
    assert len(excluded) == len(set(excluded))
    assert "sourdough bread" in excluded


def test_enum_members_and_strings_map_the_same():
    assert exclusions_for_dietary_flags([DietaryFlag.gluten_free]) == exclusions_for_dietary_flags(
        ["gluten_free"]
    )
    assert dietary_flag_violations(DietaryFlag.gluten_free, ["sourdough bread"]) == ["sourdough bread"]


def test_unknown_flag_raises_instead_of_dropping():
    with pytest.raises(ValueError, match="unknown dietary flag"):
        exclusions_for_dietary_flags(["DietaryFlag.gluten_free"])
