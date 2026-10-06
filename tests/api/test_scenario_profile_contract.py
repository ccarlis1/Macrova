"""Contract: every benchmark scenario ``profile`` key maps to PlanRequest or an allow-list.

Keeps evaluation/benchmark/scenarios.json from drifting away from the HTTP
``PlanRequest`` surface without an explicit reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.api.server import PlanRequest

_REPO = Path(__file__).resolve().parents[2]
_SCENARIOS = _REPO / "evaluation" / "benchmark" / "scenarios.json"

# Nested scenario profile keys -> PlanRequest field(s).
# Values may be a single field name or a pipe-joined set of alternatives
# (any one of which satisfies the mapping).
_PROFILE_TO_PLAN_REQUEST: dict[str, str] = {
    "daily_calories": "daily_calories",
    "daily_protein_g": "daily_protein_g",
    "daily_fat_g.min": "daily_fat_g_min",
    "daily_fat_g.max": "daily_fat_g_max",
    "max_daily_calories": "max_daily_calories",
    "liked_foods": "liked_foods",
    "excluded_ingredients": "allergies|disliked_foods",
    "micronutrient_targets": "micronutrient_goals",
    "micronutrient_weekly_min_fraction": "micronutrient_weekly_min_fraction",
    "dietary_flags": "dietary_flags",
}

# Keys that intentionally do not map to PlanRequest.
_ALLOWLIST: dict[str, str] = {
    "demographic": "not wired: ULs not enforced over HTTP",
    "intent_excluded_ingredients": "oracle-only metadata",
}


def _flatten_profile_keys(profile: dict) -> set[str]:
    keys: set[str] = set()
    for key, value in profile.items():
        if key == "daily_fat_g" and isinstance(value, dict):
            for nested in value:
                keys.add(f"daily_fat_g.{nested}")
        else:
            keys.add(key)
    return keys


def test_every_scenario_profile_key_maps_or_is_allowlisted():
    plan_fields = set(PlanRequest.model_fields)
    data = json.loads(_SCENARIOS.read_text())
    scenarios = data["scenarios"] if isinstance(data, dict) else data

    unknown: list[str] = []
    for sc in scenarios:
        sid = sc["id"]
        for key in sorted(_flatten_profile_keys(sc.get("profile") or {})):
            if key in _ALLOWLIST:
                continue
            mapping = _PROFILE_TO_PLAN_REQUEST.get(key)
            if mapping is None:
                unknown.append(f"{sid}: {key} (no map, no allow-list)")
                continue
            targets = mapping.split("|")
            if not any(t in plan_fields for t in targets):
                unknown.append(
                    f"{sid}: {key} -> {mapping} but none are PlanRequest fields"
                )

    assert not unknown, "Unmapped scenario profile keys:\n" + "\n".join(unknown)


def test_mapped_plan_request_fields_exist():
    plan_fields = set(PlanRequest.model_fields)
    for profile_key, mapping in _PROFILE_TO_PLAN_REQUEST.items():
        targets = mapping.split("|")
        assert any(t in plan_fields for t in targets), (
            f"{profile_key} maps to {mapping}, but none exist on PlanRequest"
        )


def test_allowlist_reasons_are_nonempty():
    for key, reason in _ALLOWLIST.items():
        assert reason.strip(), f"allow-list entry {key!r} needs a reason"
