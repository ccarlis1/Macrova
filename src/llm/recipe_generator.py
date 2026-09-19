from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from src.llm.client import LLMClient
from src.llm.schemas import RecipeDraft, ValidationFailure, parse_llm_json


class RecipeGenerationError(Exception):
    """Deterministic error raised when recipe generation fails."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


def _estimate_context_snippet(context: Dict[str, Any]) -> str:
    # Deterministic prompt string for the LLM (stable key ordering).
    return json.dumps(context, sort_keys=True, ensure_ascii=True)


def _type_name(v: Any) -> str:
    return type(v).__name__


def _normalize_recipe_draft_raw(
    draft_raw: Any, *, draft_index: int
) -> Tuple[Any, bool, List[str]]:
    """Normalize common LLM output alias variants into `RecipeDraft` shape.

    Determinism:
    - Only transforms fields with well-known, predictable alias patterns.
    - Never attempts "best guess" coercions beyond the explicit rules below.

    Hard-fail (do not guess):
    - both `name` and `title` missing
    - ingredient item not coercible to an object with required fields
    - non-numeric `amount` / `quantity`
    """

    normalization_actions: List[str] = []
    normalization_applied = False

    if not isinstance(draft_raw, dict):
        # Let strict schema validation surface the type issue deterministically.
        return draft_raw, False, normalization_actions

    draft: Dict[str, Any] = dict(draft_raw)  # shallow copy for deterministic edits

    # Enforce name/title presence deterministically before parsing.
    has_name = "name" in draft
    has_title = "title" in draft
    if not has_name and not has_title:
        raise RecipeGenerationError(
            error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
            message="Draft normalization failed: missing both `name` and `title`.",
            details={"draft_index": draft_index},
        )

    # Draft-level aliases:
    # - title -> name only when name is missing
    # - forbid/remove recurring alias keys so `extra="forbid"` won't trip later
    if "title" in draft:
        title_val = draft.get("title")
        if not has_name and isinstance(title_val, str):
            draft["name"] = title_val
            normalization_applied = True
            normalization_actions.append("remap draft.title->draft.name")
        elif not has_name:
            raise RecipeGenerationError(
                error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
                message="Draft normalization failed: `title` exists but is not a string.",
                details={"draft_index": draft_index, "title_type": _type_name(title_val)},
            )

        # Always remove forbidden alias key.
        draft.pop("title", None)
        normalization_applied = True
        normalization_actions.append("drop draft.title")

    # Cook-time aliases: keep the author's claim under the schema key (integer minutes only).
    for alias in ("cook_time", "cooking_time", "cook_time_minutes", "total_time_minutes"):
        if alias in draft and "cooking_time_minutes" not in draft:
            val = draft.get(alias)
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                draft.pop(alias, None)
                normalization_applied = True
                normalization_actions.append(f"drop draft.{alias} (non-numeric)")
                continue
            draft["cooking_time_minutes"] = int(round(float(val)))
            normalization_applied = True
            normalization_actions.append(f"remap draft.{alias}->draft.cooking_time_minutes")
        if alias in draft:
            draft.pop(alias, None)
            normalization_applied = True
            normalization_actions.append(f"drop draft.{alias}")
    if "cooking_time_minutes" in draft and isinstance(draft["cooking_time_minutes"], float):
        draft["cooking_time_minutes"] = int(round(draft["cooking_time_minutes"]))

    # Drop known non-schema metadata keys (they are forbidden by schema).
    for forbidden_key in ("servings", "prep_time"):
        if forbidden_key in draft:
            draft.pop(forbidden_key, None)
            normalization_applied = True
            normalization_actions.append(f"drop draft.{forbidden_key}")

    # Instructions: accept a single string.
    if "instructions" in draft and isinstance(draft.get("instructions"), str):
        draft["instructions"] = [draft["instructions"]]
        normalization_applied = True
        normalization_actions.append("coerce instructions string->list")

    # Ingredients: accept amount alias, drop extras, keep only name/quantity/unit.
    if "ingredients" in draft and isinstance(draft.get("ingredients"), list):
        ingredients_raw = draft["ingredients"]
        normalized_ingredients: List[Dict[str, Any]] = []

        for ing_index, ing_raw in enumerate(ingredients_raw):
            if not isinstance(ing_raw, dict):
                raise RecipeGenerationError(
                    error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
                    message="Draft normalization failed: ingredient item is not an object.",
                    details={"draft_index": draft_index, "ingredient_index": ing_index},
                )

            ing = dict(ing_raw)  # shallow copy

            # remap amount -> quantity only if quantity missing
            if "amount" in ing and "quantity" not in ing:
                amount_val = ing.get("amount")
                if isinstance(amount_val, bool) or not isinstance(amount_val, (int, float)):
                    raise RecipeGenerationError(
                        error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
                        message="Draft normalization failed: non-numeric ingredient amount.",
                        details={
                            "draft_index": draft_index,
                            "ingredient_index": ing_index,
                            "amount_type": _type_name(amount_val),
                        },
                    )
                ing["quantity"] = float(amount_val)
                normalization_applied = True
                normalization_actions.append(
                    f"remap ingredient[{ing_index}].amount->ingredient[{ing_index}].quantity"
                )

            # Drop forbidden ingredient alias key.
            if "amount" in ing:
                ing.pop("amount", None)
                normalization_applied = True
                normalization_actions.append(f"drop ingredient[{ing_index}].amount")

            # Hard-fail if required fields are missing (do not guess).
            missing_required = [k for k in ("name", "quantity", "unit") if k not in ing]
            if missing_required:
                raise RecipeGenerationError(
                    error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
                    message="Draft normalization failed: ingredient missing required fields.",
                    details={
                        "draft_index": draft_index,
                        "ingredient_index": ing_index,
                        "missing_required": missing_required,
                    },
                )

            quantity_val = ing.get("quantity")
            if isinstance(quantity_val, bool) or not isinstance(quantity_val, (int, float)):
                raise RecipeGenerationError(
                    error_code="LLM_DRAFT_NORMALIZATION_HARDFAIL",
                    message="Draft normalization failed: non-numeric ingredient quantity.",
                    details={
                        "draft_index": draft_index,
                        "ingredient_index": ing_index,
                        "quantity_type": _type_name(quantity_val),
                    },
                )

            # Keep only schema keys.
            dropped_extras = sorted(
                set(ing_raw.keys()) - {"name", "quantity", "unit", "amount"}
            )
            if dropped_extras:
                normalization_applied = True
                normalization_actions.append(
                    f"ingredient[{ing_index}].drop_extras:{','.join(dropped_extras)}"
                )

            normalized_ingredients.append(
                {"name": ing["name"], "quantity": float(quantity_val), "unit": ing["unit"]}
            )

        draft["ingredients"] = normalized_ingredients

    return draft, normalization_applied, normalization_actions


def generate_recipe_drafts(
    client: LLMClient,
    *,
    context: dict,
    count: int,
) -> List[RecipeDraft]:
    """Generate strict `RecipeDraft` objects from an LLM.

    Notes:
    - `LLMClient` guarantees the top-level return is a JSON object (dict), not a list.
    - We therefore expect an envelope: `{ "drafts": [ ... ] }`.
    - Ordering from the LLM is preserved to keep determinism across retries.
    """

    if count < 1:
        raise RecipeGenerationError(
            error_code="INVALID_COUNT",
            message="count must be >= 1.",
            details={"count": count},
        )

    system_prompt = (
        "You generate candidate meal recipes for nutrition agents. "
        "Return ONLY valid JSON. Do not include commentary. "
        'The JSON must be an object with exactly one key: "drafts". '
        "The value of `drafts` must be an array of recipe draft objects. "
        "\n\nRecipeDraft contract (each draft object):\n"
        '- Required keys: "name" (string), "ingredients" (array of objects), "instructions" (array of strings), "cooking_time_minutes" (integer, total active+passive minutes)\n'
        '- Optional key: "tags"\n'
        '- Ingredients objects (each ingredient): required keys "name", "quantity", "unit"\n'
        '- Ingredients objects must NOT include extra keys\n'
        "\nAllowed ingredient unit tokens (unit must match one of these exactly):\n"
        'g, oz, lb, ml, cup, tsp, tbsp, large, scoop, serving, to taste\n'
        "- Exact-match rule: unit must match one of these tokens exactly (no other unit strings).\n"
        "- Quantity coupling rule:\n"
        '  - if unit == "to taste" then quantity = 0\n'
        "  - otherwise quantity > 0\n"
        "- Spices/tiny-count items: represent as {\"unit\": \"to taste\", \"quantity\": 0} (do NOT put count words like 'cloves' into the `unit` field).\n"
        "\nForbidden keys/aliases (must not appear):\n"
        '- Draft: "title", "servings", "prep_time", "cook_time" (use "cooking_time_minutes")\n'
        "\nGeneration context rules (the context JSON is a GapSpec from a deterministic planner):\n"
        "- excluded_ingredients: NEVER use these or any product made from them (e.g. 'peanuts' excludes peanut butter).\n"
        "- cook_time_cap_minutes: cooking_time_minutes must be <= this value when present.\n"
        "- per_meal_calories / per_meal_protein_g / per_meal_fat_g_max / per_meal_carbs_g: aim each draft at these per-serving amounts.\n"
        "- nutrient_min_per_recipe: each draft must supply at least these amounts per serving of the listed nutrients.\n"
        "- known_ingredient_vocabulary: prefer ingredient names from this list; use plain generic USDA-style names otherwise.\n"
        "- existing_recipe_names: do not propose these or trivial variations of them.\n"
        "- Ingredient alias: do NOT output `ingredients[].amount`; use `ingredients[].quantity` instead\n"
        "\nJSON template (example):\n"
        "{\n"
        '  "drafts": [\n'
        "    {\n"
        '      "name": "Example Recipe",\n'
        '      "ingredients": [\n'
        '        {"name": "chicken breast", "quantity": 200.0, "unit": "g"},\n'
        '        {"name": "salt", "quantity": 0.0, "unit": "to taste"}\n'
        "      ],\n"
        '      "instructions": ["Cook it."],\n'
        '      "cooking_time_minutes": 20\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    user_prompt = (
        f"Request: generate exactly {count} recipe drafts.\n"
        f"Generation context (JSON): {_estimate_context_snippet(context)}\n"
        "Each draft must follow the RecipeDraft contract exactly (required keys only; no forbidden keys)."
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="RecipeDraftEnvelope",
        temperature=0.0,
    )

    if not isinstance(raw, dict):
        raise RecipeGenerationError(
            error_code="LLM_RAW_NOT_DICT",
            message="LLM response was not a JSON object.",
        )

    allowed_keys = {"drafts"}
    raw_keys = set(raw.keys())
    if raw_keys != allowed_keys:
        raise RecipeGenerationError(
            error_code="LLM_ENVELOPE_INVALID_KEYS",
            message="LLM response envelope keys were not exactly ['drafts'].",
            details={"raw_keys": sorted(raw_keys)},
        )

    drafts_raw = raw.get("drafts")
    if not isinstance(drafts_raw, list):
        raise RecipeGenerationError(
            error_code="LLM_DRAFTS_NOT_LIST",
            message="LLM response field `drafts` was not a list.",
        )

    if len(drafts_raw) != count:
        raise RecipeGenerationError(
            error_code="LLM_WRONG_DRAFT_COUNT",
            message="LLM returned the wrong number of drafts.",
            details={"expected": count, "received": len(drafts_raw)},
        )

    parsed: List[RecipeDraft] = []
    first_failure: Dict[str, Any] | None = None
    for idx, draft_raw in enumerate(drafts_raw):
        try:
            normalized_draft_raw, normalization_applied, normalization_actions = (
                _normalize_recipe_draft_raw(draft_raw, draft_index=idx)
            )
        except RecipeGenerationError as exc:
            # Per-draft rejection: one malformed draft must not discard its siblings.
            if first_failure is None:
                first_failure = {"draft_index": idx, "error_code": exc.error_code, "details": exc.details}
            continue

        parsed_or_failure = parse_llm_json(RecipeDraft, normalized_draft_raw)
        if isinstance(parsed_or_failure, ValidationFailure):
            if first_failure is None:
                first_failure = {
                    "draft_index": idx,
                    "validation_failure": parsed_or_failure.model_dump(),
                    "normalization_applied": normalization_applied,
                    "normalization_actions": normalization_actions,
                }
            continue
        parsed.append(parsed_or_failure)

    if not parsed:
        details = dict(first_failure or {"draft_index": 0})
        code = details.pop("error_code", "LLM_DRAFT_SCHEMA_VALIDATION_FAILED")
        raise RecipeGenerationError(
            error_code=code,
            message="A generated draft failed strict schema validation." if code == "LLM_DRAFT_SCHEMA_VALIDATION_FAILED" else "Draft normalization failed.",
            details=details if "details" not in details else details["details"],
        )

    return parsed

