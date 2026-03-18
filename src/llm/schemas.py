from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


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
    quick = "quick"
    medium = "medium"
    slow = "slow"


class DietaryFlag(str, Enum):
    vegetarian = "vegetarian"
    vegan = "vegan"
    gluten_free = "gluten_free"
    dairy_free = "dairy_free"


def _unit_is_supported(unit: str) -> bool:
    return unit in SUPPORTED_UNITS


class RecipeTagsJson(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cuisine: str
    cost_level: BudgetLevel
    prep_time_bucket: PrepTimeBucket
    dietary_flags: List[DietaryFlag] = Field(default_factory=list)


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
    model_config = ConfigDict(extra="forbid", strict=True)

    calories: int = Field(ge=0)
    protein: float = Field(ge=0)


class PlannerPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cuisine: List[str] = Field(default_factory=list)
    budget: BudgetLevel


class PlannerConfigJson(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    days: int = Field(ge=1, le=7)
    meals_per_day: int = Field(ge=1, le=8)
    targets: PlannerTargets
    preferences: PlannerPreferences


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

