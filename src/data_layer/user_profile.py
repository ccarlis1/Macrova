"""User profile loader and helpers for planning input mapping."""
import os
import sys
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.llm.schemas import BudgetLevel, PlannerConfigJson

from src.data_layer.models import MicronutrientProfile, ProfilePin, UserProfile
from src.models.legacy_schedule_migration import (
    canonical_day_to_meal_only_legacy_dict,
    legacy_schedule_dict_to_day_schedule,
    log_legacy_schedule_deprecation,
    schedule_days_to_meal_only_legacy_dict,
)
from src.models.schedule import DaySchedule
from src.planning.converters import _expand_schedule_days
from src.planning.micronutrient_policy import validate_micronutrient_weekly_min_fraction

DEFAULT_USER_PROFILE_PATH = Path("config/user_profile.yaml")


def _resolve_profile_path(yaml_path: str | Path | None = None) -> Path:
    if yaml_path is not None:
        return Path(yaml_path)
    return Path(os.environ.get("NUTRITION_USER_PROFILE_PATH", str(DEFAULT_USER_PROFILE_PATH)))


def _read_profile_yaml(target_path: Path) -> Dict[str, Any]:
    if not target_path.exists():
        return {}
    with open(target_path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("User profile YAML root must be a mapping object.")
    return dict(loaded)


def _atomic_write_profile_yaml(target_path: Path, payload: Dict[str, Any]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="user_profile.",
        dir=str(target_path.parent),
        delete=False,
        encoding="utf-8",
    ) as tmp:
        yaml.safe_dump(payload, tmp, sort_keys=False)
        temp_path = Path(tmp.name)
    temp_path.replace(target_path)


def _validate_persisted_pin_row(row: Any, index: int) -> ProfilePin:
    if not isinstance(row, dict):
        raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}] must be an object")
    for key in row.keys():
        if key not in {"day_index", "slot_index", "recipe_id"}:
            raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}].{key} is not allowed")
    if "day_index" not in row or "slot_index" not in row or "recipe_id" not in row:
        raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}] missing required fields")
    day_index = row["day_index"]
    slot_index = row["slot_index"]
    recipe_id = str(row["recipe_id"]).strip()
    if not isinstance(day_index, int) or day_index < 0:
        raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}].day_index must be int >= 0")
    if not isinstance(slot_index, int) or slot_index < 0:
        raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}].slot_index must be int >= 0")
    if not recipe_id:
        raise ValueError(f"PROFILE_PIN_INVALID: pins[{index}].recipe_id must be non-empty")
    return ProfilePin(day_index=day_index, slot_index=slot_index, recipe_id=recipe_id)


def _normalize_profile_pins(pins: List[ProfilePin]) -> List[ProfilePin]:
    # Last write wins for equivalent canonical address.
    by_key: Dict[Tuple[int, int], ProfilePin] = {}
    for pin in pins:
        by_key[(int(pin.day_index), int(pin.slot_index))] = ProfilePin(
            day_index=int(pin.day_index),
            slot_index=int(pin.slot_index),
            recipe_id=str(pin.recipe_id).strip(),
        )
    return [by_key[key] for key in sorted(by_key.keys())]


def _pins_to_storage_rows(pins: List[ProfilePin]) -> List[Dict[str, Any]]:
    return [
        {
            "day_index": int(pin.day_index),
            "slot_index": int(pin.slot_index),
            "recipe_id": str(pin.recipe_id),
        }
        for pin in _normalize_profile_pins(pins)
    ]


def _validate_pin_against_schedule(pin: ProfilePin, profile_doc: Dict[str, Any]) -> None:
    raw_days = profile_doc.get("schedule_days")
    if raw_days is None:
        return
    if not isinstance(raw_days, list):
        raise ValueError("PROFILE_PIN_INVALID: profile schedule_days must be a list")
    if pin.day_index >= len(raw_days):
        raise ValueError("PROFILE_PIN_INVALID: day_index outside persisted schedule")
    day_payload = raw_days[pin.day_index]
    if not isinstance(day_payload, dict):
        raise ValueError("PROFILE_PIN_INVALID: persisted schedule_days row must be an object")
    raw_meals = day_payload.get("meals", [])
    if not isinstance(raw_meals, list):
        raise ValueError("PROFILE_PIN_INVALID: persisted meals must be a list")
    if pin.slot_index >= len(raw_meals):
        raise ValueError("PROFILE_PIN_INVALID: slot_index outside persisted schedule day")


def load_profile_pins(*, yaml_path: str | Path | None = None) -> List[ProfilePin]:
    target_path = _resolve_profile_path(yaml_path)
    profile_doc = _read_profile_yaml(target_path)
    raw_pins = profile_doc.get("pins", [])
    if raw_pins is None:
        return []
    if not isinstance(raw_pins, list):
        raise ValueError("PROFILE_PIN_INVALID: pins must be a list")
    parsed = [_validate_persisted_pin_row(row, idx) for idx, row in enumerate(raw_pins)]
    return _normalize_profile_pins(parsed)


def upsert_profile_pin(
    *,
    day_index: int,
    slot_index: int,
    recipe_id: str,
    yaml_path: str | Path | None = None,
) -> ProfilePin:
    target_path = _resolve_profile_path(yaml_path)
    profile_doc = _read_profile_yaml(target_path)
    existing_pins = load_profile_pins(yaml_path=target_path)
    updated_pin = ProfilePin(day_index=int(day_index), slot_index=int(slot_index), recipe_id=str(recipe_id).strip())
    _validate_pin_against_schedule(updated_pin, profile_doc)
    normalized = _normalize_profile_pins(existing_pins + [updated_pin])
    profile_doc["pins"] = _pins_to_storage_rows(normalized)
    _atomic_write_profile_yaml(target_path, profile_doc)
    return next(
        pin for pin in normalized if pin.day_index == updated_pin.day_index and pin.slot_index == updated_pin.slot_index
    )


def clear_profile_pin(
    *,
    day_index: int,
    slot_index: int,
    yaml_path: str | Path | None = None,
) -> Tuple[bool, Optional[ProfilePin]]:
    target_path = _resolve_profile_path(yaml_path)
    profile_doc = _read_profile_yaml(target_path)
    existing_pins = load_profile_pins(yaml_path=target_path)
    removed: Optional[ProfilePin] = None
    kept: List[ProfilePin] = []
    for pin in existing_pins:
        if pin.day_index == day_index and pin.slot_index == slot_index:
            removed = pin
            continue
        kept.append(pin)
    profile_doc["pins"] = _pins_to_storage_rows(kept)
    _atomic_write_profile_yaml(target_path, profile_doc)
    return removed is not None, removed


def clear_all_profile_pins(*, yaml_path: str | Path | None = None) -> int:
    target_path = _resolve_profile_path(yaml_path)
    profile_doc = _read_profile_yaml(target_path)
    existing = load_profile_pins(yaml_path=target_path)
    count = len(existing)
    profile_doc["pins"] = []
    _atomic_write_profile_yaml(target_path, profile_doc)
    return count


def _normalize_schedule_days_for_storage(
    schedule_days: List[DaySchedule],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for day in sorted(schedule_days, key=lambda d: d.day_index):
        day_payload = day.model_dump(mode="json", exclude_none=True)
        day_payload["meals"] = sorted(day_payload.get("meals", []), key=lambda m: m["index"])
        day_payload["workouts"] = sorted(
            day_payload.get("workouts", []),
            key=lambda w: (w["after_meal_index"], w["type"]),
        )
        normalized.append(day_payload)
    return normalized


def persist_profile_schedule_days(
    schedule_days: List[DaySchedule],
    *,
    yaml_path: str | Path | None = None,
) -> List[Dict[str, Any]]:
    """Persist canonical schedule_days into the existing profile YAML document."""
    target_path = _resolve_profile_path(yaml_path)
    existing = _read_profile_yaml(target_path)

    normalized_days = _normalize_schedule_days_for_storage(schedule_days)
    existing["schedule_days"] = normalized_days
    # Remove legacy schedule to avoid conflicting representations.
    existing.pop("schedule", None)

    _atomic_write_profile_yaml(target_path, existing)
    return normalized_days


class UserProfileLoader:
    """Loader for user profile configuration from YAML."""

    def __init__(self, yaml_path: str):
        """Initialize user profile loader from YAML file.

        Args:
            yaml_path: Path to YAML file containing user profile
        """
        self.yaml_path = Path(yaml_path)

    def load(self) -> UserProfile:
        """Load user profile from YAML file.

        Returns:
            UserProfile object

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            KeyError: If required fields are missing
        """
        with open(self.yaml_path, "r") as f:
            data = yaml.safe_load(f)

        nutrition_goals = data["nutrition_goals"]
        preferences = data["preferences"]

        # Extract nutrition goals
        daily_calories = int(nutrition_goals["daily_calories"])
        daily_protein_g = float(nutrition_goals["daily_protein_g"])
        fat_range = nutrition_goals["daily_fat_g"]
        daily_fat_g = (float(fat_range["min"]), float(fat_range["max"]))

        # Calculate carbs from remaining calories
        # Use median fat (average of min and max) for calculation
        median_fat_g = (daily_fat_g[0] + daily_fat_g[1]) / 2
        # Carbs = (calories - protein*4 - fat*9) / 4
        daily_carbs_g = (daily_calories - daily_protein_g * 4 - median_fat_g * 9) / 4

        schedule_days: list[DaySchedule] | None = None
        schedule_dict: dict[str, int]
        if data.get("schedule_days") is not None:
            raw_days = data["schedule_days"]
            if not isinstance(raw_days, list):
                raise ValueError("schedule_days must be a list")
            schedule_days = [DaySchedule.model_validate(d) for d in raw_days]
            schedule_dict, cw = schedule_days_to_meal_only_legacy_dict(schedule_days)
            for msg in cw:
                print(f"Warning: {msg}", file=sys.stderr)
        elif "schedule" in data:
            log_legacy_schedule_deprecation("yaml")
            schedule = data["schedule"]
            legacy_dict = {str(k): int(v) for k, v in schedule.items()}
            day, mw = legacy_schedule_dict_to_day_schedule(legacy_dict, day_index=1)
            for msg in mw:
                print(f"Warning: {msg}", file=sys.stderr)
            schedule_days = [day]
            schedule_dict = canonical_day_to_meal_only_legacy_dict(day)
        else:
            raise KeyError("Provide 'schedule' (legacy) or 'schedule_days' in profile YAML")

        # Extract preferences
        liked_foods = [str(food) for food in preferences.get("liked_foods", [])]
        disliked_foods = [str(food) for food in preferences.get("disliked_foods", [])]
        allergies = [str(allergen) for allergen in preferences.get("allergies", [])]

        # Extract optional max_daily_calories (Calorie Deficit Mode)
        max_daily_calories = nutrition_goals.get("max_daily_calories")
        if max_daily_calories is not None:
            max_daily_calories = int(max_daily_calories)

        tau_raw = nutrition_goals.get("micronutrient_weekly_min_fraction", 1.0)
        micronutrient_weekly_min_fraction = validate_micronutrient_weekly_min_fraction(float(tau_raw))
        if micronutrient_weekly_min_fraction < 0.85:
            print(
                "Warning: micronutrient_weekly_min_fraction (τ) below 0.85 relaxes weekly micronutrient floors substantially.",
                file=sys.stderr,
            )

        # Extract micronutrient_goals (daily RDIs); validate keys against MicronutrientProfile
        micro_goals = data.get("micronutrient_goals", {})
        valid_fields = set(MicronutrientProfile.__dataclass_fields__.keys())
        daily_micro = {}
        for key, val in micro_goals.items():
            if key not in valid_fields:
                print(
                    f"Warning: unknown micronutrient goal '{key}', skipping",
                    file=sys.stderr,
                )
                continue
            daily_micro[key] = float(val)

        return UserProfile(
            daily_calories=daily_calories,
            daily_protein_g=daily_protein_g,
            daily_fat_g=daily_fat_g,
            daily_carbs_g=daily_carbs_g,
            schedule=schedule_dict,
            liked_foods=liked_foods,
            disliked_foods=disliked_foods,
            allergies=allergies,
            max_daily_calories=max_daily_calories,
            daily_micronutrient_targets=daily_micro or None,
            micronutrient_weekly_min_fraction=micronutrient_weekly_min_fraction,
            schedule_days=schedule_days,
            pins=load_profile_pins(yaml_path=self.yaml_path),
        )


class PlannerConfigMappingError(Exception):
    """Raised when mapping PlannerConfigJson into UserProfile is impossible."""

    def __init__(self, *, error_code: str, message: str, details: Dict[str, float] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:  # pragma: no cover (mostly surfaced via API)
        if not self.details:
            return f"{self.error_code}: {super().__str__()}"
        return f"{self.error_code}: {super().__str__()} ({sorted(self.details.items())})"


def _schedule_dict_from_meals_per_day(meals_per_day: int) -> Dict[str, int]:
    """Create a deterministic schedule dict (time -> busyness_level).

    Planner uses schedule[time] busyness level to set cooking-time constraints.
    We use busyness_level=4 (no cooking-time upper bound) for robustness.
    """
    times = [
        "07:00",
        "12:00",
        "18:00",
        "19:00",
        "20:00",
        "21:00",
        "22:00",
        "23:00",
    ]
    if meals_per_day < 1 or meals_per_day > len(times):
        # Defensive: schema validation should prevent this, but keep deterministic behavior.
        raise PlannerConfigMappingError(
            error_code="INVALID_MEALS_PER_DAY",
            message=f"meals_per_day out of supported range: {meals_per_day}",
        )
    return {t: 4 for t in times[:meals_per_day]}


def _default_fat_ratio_bounds(budget: BudgetLevel) -> tuple[float, float]:
    """Return (fat_ratio_min, fat_ratio_max) over remaining calories after protein.

    The planner uses fat min/max and derived carbs for macro feasibility/scoring.
    Since PlannerConfigJson does not include explicit fat targets, we deterministically
    assume a fat share based on budget preference.
    """
    if budget == BudgetLevel.cheap:
        return (0.25, 0.30)
    if budget == BudgetLevel.standard:
        return (0.28, 0.35)
    if budget == BudgetLevel.premium:
        return (0.30, 0.40)
    # Defensive fallback (should be unreachable due to enum typing).
    return (0.28, 0.35)


def user_profile_from_planner_config(cfg: PlannerConfigJson) -> UserProfile:
    """Map strict PlannerConfigJson into a UserProfile usable by `convert_profile()`.

    Deterministic mapping:
    - If ``schedule_days`` is set: expand to ``cfg.days`` (single-day templates replicate),
      populate ``UserProfile.schedule_days`` and derived legacy ``schedule`` dict.
    - Else: ``meals_per_day`` -> schedule dict (times + busyness_level=4)
    - preferences.cuisine -> liked_foods
    - targets.calories + targets.protein -> daily_calories/daily_protein_g
    - derived fat range + carbs computed from deterministic budget-based fat ratio bounds
    """
    daily_calories = int(cfg.targets.calories)
    daily_protein_g = float(cfg.targets.protein)

    remaining_after_protein_cal = daily_calories - daily_protein_g * 4.0
    if remaining_after_protein_cal < 0:
        raise PlannerConfigMappingError(
            error_code="NEGATIVE_REMAINING_AFTER_PROTEIN",
            message="Protein calories exceed daily calories, cannot derive fat/carbs.",
            details={"remaining_after_protein_cal": remaining_after_protein_cal},
        )

    fat_ratio_min, fat_ratio_max = _default_fat_ratio_bounds(cfg.preferences.budget)
    fat_cal_min = remaining_after_protein_cal * fat_ratio_min
    fat_cal_max = remaining_after_protein_cal * fat_ratio_max
    fat_g_min = fat_cal_min / 9.0
    fat_g_max = fat_cal_max / 9.0

    median_fat_g = (fat_g_min + fat_g_max) / 2.0
    daily_carbs_g = (
        daily_calories - daily_protein_g * 4.0 - median_fat_g * 9.0
    ) / 4.0
    if daily_carbs_g < 0:
        raise PlannerConfigMappingError(
            error_code="NEGATIVE_CARBS_DERIVED",
            message="Derived carbs was negative; mapping is impossible with these targets.",
            details={
                "daily_calories": float(daily_calories),
                "daily_protein_g": daily_protein_g,
                "fat_g_min": fat_g_min,
                "fat_g_max": fat_g_max,
                "median_fat_g": median_fat_g,
                "daily_carbs_g": daily_carbs_g,
            },
        )

    cuisine = [str(c).strip() for c in cfg.preferences.cuisine or [] if str(c).strip()]

    if cfg.schedule_days is not None:
        expanded = _expand_schedule_days(list(cfg.schedule_days), cfg.days)
        schedule_dict, _ = schedule_days_to_meal_only_legacy_dict(expanded)
    else:
        expanded = None
        schedule_dict = _schedule_dict_from_meals_per_day(cfg.meals_per_day)

    return UserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=(float(fat_g_min), float(fat_g_max)),
        daily_carbs_g=float(daily_carbs_g),
        schedule={str(k): int(v) for k, v in schedule_dict.items()},
        liked_foods=cuisine,
        disliked_foods=[],
        allergies=[],
        max_daily_calories=None,
        daily_micronutrient_targets=None,
        micronutrient_weekly_min_fraction=1.0,
        schedule_days=expanded,
        pins=None,
    )

