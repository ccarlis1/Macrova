"""Typed contracts for the planner-failure recovery loop.

These types are the machine-checkable boundary between the deterministic planner,
the deterministic diagnosis step, the untrusted LLM proposal step, and the caller.
Nothing here calls the LLM or touches storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class RecoveryState(str, Enum):
    """Terminal state of one recovery run. Exactly one is reported per request."""

    SUCCESS = "SUCCESS"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"  # planner succeeded first time, or mode is deterministic
    UNRECOVERABLE_INFEASIBILITY = "UNRECOVERABLE_INFEASIBILITY"
    NO_USEFUL_RECOVERY_FOUND = "NO_USEFUL_RECOVERY_FOUND"
    RECOVERY_LIMIT_REACHED = "RECOVERY_LIMIT_REACHED"
    INVALID_RECOVERY_OUTPUT = "INVALID_RECOVERY_OUTPUT"
    DATA_SOURCE_FAILURE = "DATA_SOURCE_FAILURE"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass
class GapSpec:
    """What a new recipe would have to satisfy to change the planner's outcome.

    Produced deterministically from (planner result, profile, pool). This is the ONLY
    thing the LLM is shown; it is also what accepted drafts are checked against.
    """

    kind: str  # "candidate_gap" | "macro_gap" | "nutrient_gap" | "uniqueness_gap"
    failure_mode: str
    days: int
    meals_per_day: int
    # Per-meal macro envelope a useful recipe should land in (derived from daily targets / slots).
    per_meal_calories: Optional[float] = None
    per_meal_protein_g: Optional[float] = None
    per_meal_fat_g_max: Optional[float] = None
    per_meal_carbs_g: Optional[float] = None
    # Hard facts the recipe must respect.
    cook_time_cap_minutes: Optional[int] = None  # tightest cap among gap slots (None = no cap)
    excluded_ingredients: List[str] = field(default_factory=list)
    # Nutrient shortfalls (FM-4): nutrient -> minimum per-recipe contribution that would close the gap.
    nutrient_min_per_recipe: Dict[str, float] = field(default_factory=dict)
    # Which (day_index, slot_index) pairs the gap concerns (empty = whole plan).
    slots: List[List[int]] = field(default_factory=list)
    # Diversity / dedupe hints.
    existing_recipe_names: List[str] = field(default_factory=list)
    # Ingredient names the resolver is known to handle (helps the model avoid unresolvable names).
    known_ingredient_vocabulary: List[str] = field(default_factory=list)
    # Human-readable diagnosis, for logs and the LLM prompt.
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UnrecoverableReason:
    code: str  # e.g. "IMPOSSIBLE_TARGETS", "EMPTY_POOL_AFTER_FILTER", "REQUIRED_TAG_UNHELD", "PIN_OR_BATCH_CONFLICT", "SEARCH_BUDGET"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AttemptRecord:
    attempt: int
    llm_called: bool
    drafts_received: int
    drafts_after_dedupe: int
    accepted: int
    rejected: List[Dict[str, str]] = field(default_factory=list)  # [{code, message}]
    candidate_ids: List[str] = field(default_factory=list)
    planner_code_after: Optional[str] = None
    signal_before: Optional[Dict[str, Any]] = None
    signal_after: Optional[Dict[str, Any]] = None
    improved: Optional[bool] = None
    status: str = ""  # "success" | "fail" | "abort" | "error"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryOutcome:
    """Serializable summary attached to ``MealPlanResult.report['llm_recovery']``."""

    state: RecoveryState
    reason: Optional[str] = None
    gap_spec: Optional[Dict[str, Any]] = None
    unrecoverable: Optional[Dict[str, Any]] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    planner_runs: int = 1
    persisted_recipe_ids: List[str] = field(default_factory=list)
    error: Optional[Dict[str, str]] = None  # {type, code, message} for DATA_SOURCE_FAILURE / SYSTEM_ERROR
    max_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d
