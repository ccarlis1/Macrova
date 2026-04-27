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
    eligibility: Optional[StrictStr] = None
    hard_filter_allowed: Optional[bool] = None
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


class PlannerConfigJson(BaseModel):
    # strict=False: allow float JSON numbers for int fields (e.g. days: 3.0).
    model_config = ConfigDict(extra="forbid", strict=False)

    days: int = Field(ge=1, le=7)
    meals_per_day: int = Field(ge=1, le=8)
    targets: PlannerTargets
    preferences: PlannerPreferences
    #: Optional canonical per-day meals + workouts (same contract as API ``schedule_days``).
    #: When set, ``user_profile_from_planner_config`` expands to the planning horizon
    #: and sets ``UserProfile.schedule_days``; ``meals_per_day`` should match each
    #: day's meal count when using a single template (or use one day and replicate).
    schedule_days: Optional[List[DaySchedule]] = None

    @model_validator(mode="after")
    def _schedule_days_non_empty_when_present(self) -> "PlannerConfigJson":
        if self.schedule_days is not None and len(self.schedule_days) == 0:
            raise ValueError("schedule_days must be omitted or contain at least one day")
        return self


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

