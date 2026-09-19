from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict

from src.llm.client import LLMClient
from src.llm.schemas import PlannerConfigJson, ValidationFailure, parse_llm_json

logger = logging.getLogger(__name__)

# Embedded so the model cannot invent alternate keys (e.g. numberOfMeals).
_PLANNER_CONFIG_JSON_SCHEMA_COMPACT = json.dumps(
    PlannerConfigJson.model_json_schema(),
    separators=(",", ":"),
    ensure_ascii=True,
)


@dataclass(frozen=True)
class PlannerConfigParsingError(Exception):
    """Raised when NL->JSON parsing or strict schema validation fails."""

    error_code: str
    message: str
    details: Dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover (covered indirectly via API tests)
        return f"{self.error_code}: {self.message}"


def parse_nl_config(client: LLMClient, text: str) -> PlannerConfigJson:
    """Convert natural language into a strict PlannerConfigJson.

    Invariants:
    - LLM output is untrusted.
    - We validate via strict Pydantic schema parsing only.
    - We never return partially-valid configs: either valid PlannerConfigJson
      or a deterministic PlannerConfigParsingError.
    """
    if not isinstance(text, str) or not text.strip():
        raise PlannerConfigParsingError(
            error_code="INVALID_NL_INPUT",
            message="prompt text must be a non-empty string.",
            details={"text_type": str(type(text)), "text_empty": True},
        )

    system_prompt = (
        "You are a nutrition-agent planning assistant. "
        "Convert user natural language into a JSON object that matches the "
        "PlannerConfigJson schema below exactly. "
        "Return ONLY JSON (no markdown, no prose). "
        "Use ONLY the property names from the schema — for example map "
        "'N meals per day' to integer field meals_per_day (not numberOfMeals "
        "or total_meals). "
        "If the user does not specify days, calories, protein, cuisine, or "
        "budget, choose sensible defaults: days=1, targets suitable for a "
        "typical adult (e.g. 2000 calories, 120g protein), cuisine=[], "
        "budget=standard.\n"
        "Scheduling constraints (optional field schedule_days): When the user "
        "mentions workouts, which meal is before/after training, prep/cook time "
        "limits, or different effort per meal, populate schedule_days. "
        "Each day has meals with contiguous index 1..N and busyness_level 1-4 "
        "(1=very quick/snack, 2=~15min, 3=~30min, 4=no tight cap). "
        "Workouts are NOT meals: use workouts[] with after_meal_index meaning the "
        "gap after that meal (1 <= after_meal_index < N). At most 2 workouts per day; "
        "no duplicate gap. workout type is one of AM, PM, general; intensity optional "
        "low|moderate|high. "
        "If schedule_days is omitted, only meals_per_day is used (uniform high "
        "busyness defaults downstream). "
        "For multi-day horizons you may send one template day (day_index=1) and it "
        "will be replicated for all days. "
        "Only emit schedule_days when the user actually describes per-meal effort, time "
        "limits or workouts; otherwise omit it.\n"
        "Constraints (field `constraints`, emit it whenever any apply): allergies and "
        "intolerances -> constraints.allergies; foods to avoid -> constraints.disliked_foods; "
        "favourite foods -> constraints.liked_foods; 'under/at most/no more than N calories' -> "
        "constraints.max_daily_calories=N (and targets.calories=N if no other calorie target is "
        "given); an explicit fat range -> fat_g_min/fat_g_max; per-day micronutrient goals -> "
        "constraints.micronutrient_goals keyed by the internal field names (e.g. fiber_g, iron_mg, "
        "calcium_mg, vitamin_c_mg, potassium_mg, magnesium_mg, sodium_mg, omega_3_g); vegan / "
        "vegetarian / gluten-free / dairy-free -> constraints.dietary_flags (NOT cuisine); a stated "
        "weekly micronutrient fraction -> constraints.micronutrient_weekly_min_fraction. "
        "Never place allergies, diets or liked foods in preferences.cuisine or in tag slugs.\n"
        "Units: convert kJ to kcal (divide by 4.184); convert protein given per kg or per lb of "
        "bodyweight into grams; percent-of-calories protein into grams (kcal*pct/4).\n"
        "stated_fields: list exactly the field names the user explicitly stated, from: "
        "days, meals_per_day, calories, protein, cuisine, budget, schedule_days, allergies, "
        "disliked_foods, liked_foods, max_daily_calories, fat_range, micronutrient_goals, "
        "dietary_flags, micronutrient_weekly_min_fraction. Fields you defaulted must NOT be listed.\n"
        "Never clamp or 'fix' invalid values: if the user asks for 0 days or 10 meals, output "
        "that number and let validation reject it."
    )
    user_prompt = (
        "User request (natural language):\n"
        f"{text}\n\n"
        "PlannerConfigJson JSON Schema (additionalProperties false at each "
        f"object; obey exactly):\n{_PLANNER_CONFIG_JSON_SCHEMA_COMPACT}\n"
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="PlannerConfigJson",
        temperature=0.0,
    )

    parsed_or_failure = parse_llm_json(PlannerConfigJson, raw)
    if isinstance(parsed_or_failure, ValidationFailure):
        raw_text = getattr(client, "_last_model_content_text", None)
        logger.warning(
            "planner_config_json_validation_failed prompt_len=%d field_errors=%s "
            "parsed_object=%s raw_model_content=%s",
            len(text),
            parsed_or_failure.field_errors,
            json.dumps(raw, sort_keys=True, ensure_ascii=True),
            raw_text if raw_text is None else repr(raw_text),
        )
        raise PlannerConfigParsingError(
            error_code=parsed_or_failure.error_code,
            message=parsed_or_failure.message,
            details={"field_errors": parsed_or_failure.field_errors},
        )

    return parsed_or_failure

