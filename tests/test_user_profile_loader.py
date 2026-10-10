"""Tests for src/data_layer/user_profile.py — YAML profile loading contract."""

import pytest
import yaml

from src.data_layer.user_profile import UserProfileLoader


def _write_profile(tmp_path, data):
    path = tmp_path / "user_profile.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def _base_profile(**overrides):
    data = {
        "nutrition_goals": {
            "daily_calories": 2000,
            "daily_protein_g": 150,
            "daily_fat_g": {"min": 50, "max": 70},
        },
        "preferences": {
            "liked_foods": ["salmon"],
            "disliked_foods": ["liver"],
            "allergies": ["peanut"],
        },
        "schedule_days": [
            {
                "day_index": 1,
                "meals": [
                    {"index": 1, "busyness_level": 2},
                    {"index": 2, "busyness_level": 3},
                ],
            }
        ],
    }
    data.update(overrides)
    return data


def test_loads_macros_and_derives_carbs_from_median_fat(tmp_path):
    profile = UserProfileLoader(_write_profile(tmp_path, _base_profile())).load()

    assert profile.daily_calories == 2000
    assert profile.daily_protein_g == 150.0
    assert profile.daily_fat_g == (50.0, 70.0)
    # carbs = (calories - protein*4 - median_fat*9) / 4 with median fat 60 g
    assert profile.daily_carbs_g == pytest.approx((2000 - 150 * 4 - 60 * 9) / 4)


def test_canonical_schedule_days_are_parsed(tmp_path):
    profile = UserProfileLoader(_write_profile(tmp_path, _base_profile())).load()

    assert profile.schedule_days is not None
    assert len(profile.schedule_days) == 1
    assert [m.index for m in profile.schedule_days[0].meals] == [1, 2]


def test_preferences_are_stringified_lists(tmp_path):
    profile = UserProfileLoader(_write_profile(tmp_path, _base_profile())).load()

    assert profile.liked_foods == ["salmon"]
    assert profile.disliked_foods == ["liver"]
    assert profile.allergies == ["peanut"]


def test_tau_defaults_to_strict_1_0(tmp_path):
    profile = UserProfileLoader(_write_profile(tmp_path, _base_profile())).load()
    assert profile.micronutrient_weekly_min_fraction == 1.0


def test_unknown_micronutrient_goals_are_skipped_and_valid_ones_kept(tmp_path, capsys):
    data = _base_profile(
        micronutrient_goals={"iron_mg": 8, "unobtainium_mg": 999},
    )
    profile = UserProfileLoader(_write_profile(tmp_path, data)).load()

    assert profile.daily_micronutrient_targets == {"iron_mg": 8.0}
    assert "unobtainium_mg" in capsys.readouterr().err


def test_missing_schedule_raises_key_error(tmp_path):
    data = _base_profile()
    del data["schedule_days"]

    with pytest.raises(KeyError):
        UserProfileLoader(_write_profile(tmp_path, data)).load()


def test_legacy_schedule_dict_is_migrated_to_one_canonical_day(tmp_path):
    data = _base_profile()
    del data["schedule_days"]
    data["schedule"] = {"08:00": 2, "12:30": 3}

    profile = UserProfileLoader(_write_profile(tmp_path, data)).load()

    assert profile.schedule_days is not None
    assert len(profile.schedule_days) == 1
    assert len(profile.schedule_days[0].meals) == 2
