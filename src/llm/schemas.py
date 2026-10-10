from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, model_validator

from src.models.schedule import DaySchedule


SUPPORTED_UNITS: List[str] = [
    "g",
    "oz",
    "lb",
    "ml",
    "cup",
    "tsp",
    "tbsp",
    "large",
    "scoop",
    "serving",
    "to taste",
]


class BudgetLevel(str, Enum):
    cheap = "cheap"
    standard = "standard"
    premium = "premium"


class PrepTimeBucket(str, Enum):
    # Mirror the planner's cooking_time_max() mapping (busyness_level -> max minutes):
    snack = "snack"  # <= 5 minutes (busyness_level 1)
    quick_meal = "quick_meal"  # <= 15 minutes (busyness_level 2)
    weeknight_meal = "weeknight_meal"  # <= 30 minutes (busyness_level 3)
    meal_prep = "meal_prep"  # 30+ minutes (busyness_level 4)


class DietaryFlag(str, Enum):
    vegetarian = "vegetarian"
    vegan = "vegan"
    gluten_free = "gluten_free"
    dairy_free = "dairy_free"


def _unit_is_supported(unit: str) -> bool:
    return unit in SUPPORTED_UNITS


TagType: TypeAlias = Literal["context", "time", "nutrition", "constraint"]
TagSource: TypeAlias = Literal["user", "llm", "system"]
# Lightweight persisted recipe tag reference.
# The recipe model stores only slug/type to avoid duplicating TagMetaJson.
RecipeTagRefJson: TypeAlias = Dict[Literal["slug", "type"], StrictStr]


class TagMetaJson(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    slug: StrictStr
    display: StrictStr
    tag_type: TagType
    source: TagSource
    created_at: StrictStr
    aliases: List[StrictStr] = Field(default_factory=list)
    #: DM-6 lifecycle state: proposed | approved | rejected.
    eligibility: Optional[StrictStr] = None
    #: DM-6 semantic class (capability, meal_role, exclusion, etc.).
    semantic_class: Optional[StrictStr] = None
    hard_filter_allowed: Optional[bool] = None
    soft_score_allowed: Optional[bool] = None
    display_only: Optional[bool] = None


class RecipeTagsJson(BaseModel):
    # Enum fields arrive from JSON as strings; allow coercion while keeping
    # "extra" forbidden and string fields strict.
    model_config = ConfigDict(extra="forbid", strict=False)

    cuisine: StrictStr
    cost_level: BudgetLevel
    prep_time_bucket: PrepTimeBucket
    dietary_flags: List[DietaryFlag] = Field(default_factory=list)
    # Additive DM-1 fields for typed slug usage and registry references.
    tag_slugs_by_type: Optional[Dict[TagType, List[StrictStr]]] = None
    tag_metadata: Optional[Dict[StrictStr, TagMetaJson]] = None
    aliases: Optional[Dict[StrictStr, StrictStr]] = None


class RecipeIngredientDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit: str

    @model_validator(mode="after")
    def _validate_unit_and_quantity(self) -> "RecipeIngredientDraft":
        if not _unit_is_supported(self.unit):
            supported = ", ".join(SUPPORTED_UNITS)
            raise ValueError(
                f"unit must be one of [{supported}]; got {self.unit!r}"
            )

        if self.unit == "to taste":
            if self.quantity != 0:
                raise ValueError("quantity must be 0 when unit is 'to taste'.")
        else:
            if self.quantity <= 0:
                raise ValueError("quantity must be > 0 for measurable ingredients.")
        return self


class RecipeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    ingredients: List[RecipeIngredientDraft] = Field(min_length=1)
    instructions: List[str] = Field(min_length=1)
    tags: Optional[RecipeTagsJson] = None
    #: Cook time claimed by the author (LLM). Generated data, recorded with provenance;
    #: validated against the slot cap when one applies. None = not claimed.
    cooking_time_minutes: Optional[int] = Field(default=None, ge=0, le=600)


class IngredientMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str
    normalized_name: str
    confidence: float = Field(ge=0.0, le=1.0)

    # Internal-only fields that later pipeline stages may add.
    canonical_name: Optional[str] = None
    validation_status: Optional[str] = None


class PlannerTargets(BaseModel):
    # strict=False: LLMs often emit JSON numbers as floats (e.g. 2000.0); coerce to int.
    model_config = ConfigDict(extra="forbid", strict=False)

    calories: int = Field(ge=0)
    protein: float = Field(ge=0)


class PlannerPreferences(BaseModel):
    # Enum fields arrive from JSON as strings; allow coercion while keeping
    # string fields strict.
    model_config = ConfigDict(extra="forbid", strict=False)

    cuisine: List[StrictStr] = Field(default_factory=list)
    budget: BudgetLevel


_MICRONUTRIENT_FIELDS = frozenset(
    (
        "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_iu", "vitamin_e_mg", "vitamin_k_ug", "b1_thiamine_mg",
        "b2_riboflavin_mg", "b3_niacin_mg", "b5_pantothenic_acid_mg", "b6_pyridoxine_mg", "b12_cobalamin_ug",
        "folate_ug", "calcium_mg", "copper_mg", "iron_mg", "magnesium_mg", "manganese_mg", "phosphorus_mg",
        "potassium_mg", "selenium_ug", "sodium_mg", "zinc_mg", "fiber_g", "omega_3_g", "omega_6_g",
    )
)

#: Field names the model may list in ``stated_fields`` (what the user explicitly said).
STATED_FIELD_NAMES = frozenset(
    (
        "days", "meals_per_day", "calories", "protein", "cuisine", "budget", "schedule_days",
        "allergies", "disliked_foods", "liked_foods", "max_daily_calories", "fat_range",
        "micronutrient_goals", "dietary_flags", "micronutrient_weekly_min_fraction",
    )
)


class PlannerConstraints(BaseModel):
    """Constraint classes the planner understands that the legacy config could not carry.

    Every field maps to an explicit planner input (see user_profile_from_planner_config);
    nothing here is interpreted by the LLM downstream.
    """

    model_config = ConfigDict(extra="forbid", strict=False)

    allergies: List[StrictStr] = Field(default_factory=list)          # -> HC-1 exclusions (safety)
    disliked_foods: List[StrictStr] = Field(default_factory=list)     # -> HC-1 exclusions
    liked_foods: List[StrictStr] = Field(default_factory=list)        # -> scoring only
    max_daily_calories: Optional[int] = Field(default=None, ge=0)     # -> HC-5 ceiling
    fat_g_min: Optional[float] = Field(default=None, ge=0)            # -> daily fat range
    fat_g_max: Optional[float] = Field(default=None, ge=0)
    micronutrient_goals: Optional[Dict[StrictStr, float]] = None      # -> daily micronutrient targets
    dietary_flags: List[DietaryFlag] = Field(default_factory=list)    # -> tag filter (dietary_flags)
    micronutrient_weekly_min_fraction: Optional[float] = Field(default=None, gt=0.0, le=1.0)  # -> tau

    @model_validator(mode="after")
    def _consistent(self) -> "PlannerConstraints":
        if self.fat_g_min is not None and self.fat_g_max is not None and self.fat_g_min > self.fat_g_max:
            raise ValueError("fat_g_min must be <= fat_g_max")
        if self.micronutrient_goals:
            unknown = sorted(k for k in self.micronutrient_goals if k not in _MICRONUTRIENT_FIELDS)
            if unknown:
                raise ValueError(f"unknown micronutrient goal keys: {unknown}")
            for k, v in self.micronutrient_goals.items():
                if v < 0:
                    raise ValueError(f"micronutrient goal {k} must be >= 0")
        return self


class PlannerConfigJson(BaseModel):
    # strict=False: allow float JSON numbers for int fields (e.g. days: 3.0).
    model_config = ConfigDict(extra="forbid", strict=False)

    days: int = Field(ge=1, le=7)
    meals_per_day: int = Field(ge=1, le=8)
    targets: PlannerTargets
    preferences: PlannerPreferences
    #: Optional explicit constraints (allergies, ceiling, fat range, micronutrients, diet flags, tau).
    constraints: Optional[PlannerConstraints] = None
    #: Names of fields the user explicitly stated (from STATED_FIELD_NAMES). Everything else
    #: the model filled with a documented default. Unknown names are dropped.
    stated_fields: List[StrictStr] = Field(default_factory=list)
    #: Optional canonical per-day meals + workouts (same contract as API ``schedule_days``).
    #: When set, ``user_profile_from_planner_config`` expands to the planning horizon
    #: and sets ``UserProfile.schedule_days``; ``meals_per_day`` should match each
    #: day's meal count when using a single template (or use one day and replicate).
    schedule_days: Optional[List[DaySchedule]] = None

    @model_validator(mode="after")
    def _schedule_days_non_empty_when_present(self) -> "PlannerConfigJson":
        if self.schedule_days is not None and len(self.schedule_days) == 0:
            raise ValueError("schedule_days must be omitted or contain at least one day")
        self.stated_fields = [f for f in dict.fromkeys(str(x).strip() for x in self.stated_fields) if f in STATED_FIELD_NAMES]
        return self

    def defaulted_fields(self) -> List[str]:
        """Fields that carry a value the user did not state (only meaningful when stated_fields is non-empty)."""
        if not self.stated_fields:
            return []
        present = {"days", "meals_per_day", "calories", "protein", "budget"}
        if self.preferences.cuisine:
            present.add("cuisine")
        if self.schedule_days:
            present.add("schedule_days")
        return sorted(present - set(self.stated_fields))


class ValidationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ok: Literal[False] = False
    error_code: str
    message: str
    field_errors: List[str] = Field(default_factory=list)


T = TypeVar("T", bound=BaseModel)


def parse_llm_json(schema_cls: type[T], raw: Dict[str, Any]) -> T | ValidationFailure:
    """Validate LLM-produced JSON against a strict schema.

    Never returns unvalidated data: either an instance of `schema_cls`,
    or a deterministic `ValidationFailure`.
    """

    if not isinstance(raw, dict):
        return ValidationFailure(
            error_code="LLM_RAW_NOT_OBJECT",
            message="LLM raw JSON was not an object.",
            field_errors=["raw must be a JSON object (dict)."],
        )

    try:
        return schema_cls.model_validate(raw)
    except ValidationError as e:
        # Produce deterministic, human-readable field error summaries.
        field_errors: List[str] = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "")
            field_errors.append(f"{loc}: {msg}".strip(": "))
        field_errors = sorted(field_errors)

        return ValidationFailure(
            error_code="LLM_SCHEMA_VALIDATION_ERROR",
            message="LLM JSON did not match the expected schema.",
            field_errors=field_errors,
        )

