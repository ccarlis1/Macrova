"""User profile loader and helpers for planning input mapping."""
import sys
import yaml
from pathlib import Path
from typing import Dict, List

from src.llm.schemas import BudgetLevel, PlannerConfigJson

from src.data_layer.models import MicronutrientProfile, UserProfile


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
        schedule = data["schedule"]
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

        # Convert schedule times to integers
        schedule_dict = {str(k): int(v) for k, v in schedule.items()}

        # Extract preferences
        liked_foods = [str(food) for food in preferences.get("liked_foods", [])]
        disliked_foods = [str(food) for food in preferences.get("disliked_foods", [])]
        allergies = [str(allergen) for allergen in preferences.get("allergies", [])]

        # Extract optional max_daily_calories (Calorie Deficit Mode)
        max_daily_calories = nutrition_goals.get("max_daily_calories")
        if max_daily_calories is not None:
            max_daily_calories = int(max_daily_calories)

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
    - meals_per_day -> schedule dict (times + busyness_level=4)
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
    return UserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=(float(fat_g_min), float(fat_g_max)),
        daily_carbs_g=float(daily_carbs_g),
        schedule=_schedule_dict_from_meals_per_day(cfg.meals_per_day),
        liked_foods=cuisine,
        disliked_foods=[],
        allergies=[],
        max_daily_calories=None,
        daily_micronutrient_targets=None,
    )

