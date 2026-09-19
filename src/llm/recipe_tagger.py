from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.data_layer.models import Recipe
from src.llm import tag_repository
from src.llm.client import LLMClient
from src.llm.schemas import PrepTimeBucket, RecipeTagsJson, TagMetaJson, ValidationFailure, parse_llm_json
from src.llm.time_bucket import time_bucket

_DEFAULT_TAG_REPO_PATH = "data/recipes/recipe_tags.json"

# Closed cuisine vocabulary for the legacy `cuisine` field (identity_hint; display/soft only).
CUISINE_VOCABULARY: List[str] = [
    "american", "mexican", "italian", "mediterranean", "middle-eastern", "indian", "chinese", "japanese",
    "korean", "thai", "vietnamese", "french", "greek", "spanish", "latin-american", "african", "caribbean",
    "british", "german", "eastern-european", "fusion", "unknown",
]

# Only the LLM-facing part of the schema (the model never emits tag_metadata/aliases).
_LLM_TAG_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cuisine", "cost_level", "prep_time_bucket", "dietary_flags"],
    "properties": {
        "cuisine": {"type": "string", "enum": CUISINE_VOCABULARY},
        "cost_level": {"type": "string", "enum": ["cheap", "standard", "premium"]},
        "prep_time_bucket": {"type": "string", "enum": ["snack", "quick_meal", "weeknight_meal", "meal_prep"]},
        "dietary_flags": {"type": "array", "items": {"type": "string", "enum": ["vegetarian", "vegan", "gluten_free", "dairy_free"]}},
        "tag_slugs_by_type": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "context": {"type": "array", "items": {"type": "string"}},
                "nutrition": {"type": "array", "items": {"type": "string"}},
                "constraint": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


class RecipeTaggingError(Exception):
    """Deterministic error raised when recipe tagging fails."""

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


def _recipe_for_prompt(recipe: Recipe) -> Dict[str, Any]:
    # Keep prompting deterministic and compact; we don't include recipe `id`
    # because it would bias the model toward echoing it.
    return {
        "name": recipe.name,
        "ingredients": [
            {
                "name": ing.name,
                "quantity": float(ing.quantity),
                "unit": ing.unit,
                "is_to_taste": bool(ing.is_to_taste),
            }
            for ing in recipe.ingredients
        ],
        "instructions": list(recipe.instructions),
        "cooking_time_minutes": int(recipe.cooking_time_minutes),
    }


def deterministic_prep_time_bucket(cooking_time_minutes: int) -> str:
    """Effort bucket derived from the known cook time (mirrors planner busyness caps)."""
    m = int(cooking_time_minutes)
    if m <= 5:
        return "snack"
    if m <= 15:
        return "quick_meal"
    if m <= 30:
        return "weeknight_meal"
    return "meal_prep"


def _registry_slugs_by_type(tag_repo_path: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"context": [], "nutrition": [], "constraint": []}
    for meta in tag_repository.list_by_type(tag_repo_path):
        if meta.tag_type in out:
            out[meta.tag_type].append(meta.slug)
    return {k: sorted(v) for k, v in out.items()}


def _quarantined_metadata(slugs: List[str], tag_repo_path: str) -> Dict[str, TagMetaJson]:
    """Per-recipe metadata marking LLM-proposed slugs as `llm` / `proposed` (never hard-eligible)."""
    out: Dict[str, TagMetaJson] = {}
    for slug in slugs:
        try:
            meta = tag_repository.resolve(slug, tag_repo_path)
        except ValueError:
            continue
        out[meta.slug] = tag_repository.enrich_tag_meta(
            meta.model_copy(update={"source": "llm", "eligibility": "proposed"})
        )
    return out


def tag_recipes(
    client: LLMClient,
    recipes: List[Recipe],
    *,
    tag_repo_path: Optional[str] = None,
) -> Dict[str, RecipeTagsJson]:
    """Propose tags for recipes with the LLM, then normalize deterministically.

    Contract (LLM overhaul Stage 7):
    - the prompt embeds the JSON schema and the registry's canonical slugs, so the model
      cannot invent a shape or a slug;
    - `prep_time_bucket` is overwritten by the deterministic bucket of `cooking_time_minutes`
      (a known fact is never guessed);
    - proposed registry slugs are recorded with `source="llm"`, `eligibility="proposed"` so
      the planner never treats them as hard constraints until curated;
    - `time-*` effort slugs are derived, not proposed;
    - a recipe whose output fails the schema is omitted (never written).
    """
    repo_path = tag_repo_path or os.environ.get("NUTRITION_TAG_REPO_PATH", _DEFAULT_TAG_REPO_PATH)
    allowed = _registry_slugs_by_type(repo_path)

    system_prompt = (
        "You are a strict recipe tagging engine. Return ONLY valid JSON matching the schema; no commentary. "
        "Use ONLY the enum values shown. For tag_slugs_by_type use ONLY slugs from the allowed lists "
        "(omit a type when nothing applies; never invent slugs; never emit time-* slugs). "
        "dietary_flags must be justified by the ingredient list (e.g. no 'vegan' when the recipe contains dairy or meat).\n"
        f"JSON schema: {json.dumps(_LLM_TAG_SCHEMA, separators=(',', ':'))}\n"
        f"Allowed tag_slugs_by_type: {json.dumps(allowed, separators=(',', ':'))}"
    )

    out: Dict[str, RecipeTagsJson] = {}
    for recipe in recipes:
        user_prompt = json.dumps({"recipe": _recipe_for_prompt(recipe)}, sort_keys=True, ensure_ascii=True)
        raw = client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, schema_name="RecipeTagsJson", temperature=0.0)
        if not isinstance(raw, dict):
            continue
        raw = dict(raw)
        raw.pop("tag_metadata", None)
        raw.pop("aliases", None)
        parsed = parse_llm_json(RecipeTagsJson, raw)
        if isinstance(parsed, ValidationFailure):
            continue

        # Deterministic normalization of the accepted proposal.
        slugs_by_type: Dict[str, List[str]] = {}
        proposed: List[str] = []
        for tag_type, slugs in (parsed.tag_slugs_by_type or {}).items():
            if tag_type == "time":
                continue
            keep: List[str] = []
            for slug in slugs:
                try:
                    canonical = tag_repository.resolve(slug, repo_path).slug
                except ValueError:
                    continue
                if canonical in allowed.get(tag_type, []) and canonical not in keep:
                    keep.append(canonical)
            if keep:
                slugs_by_type[tag_type] = keep
                proposed.extend(keep)
        try:
            slugs_by_type["time"] = [time_bucket(int(recipe.cooking_time_minutes))]
        except Exception:
            pass

        cuisine = str(parsed.cuisine).strip().lower()
        if cuisine not in CUISINE_VOCABULARY:
            cuisine = "unknown"

        out[recipe.id] = parsed.model_copy(
            update={
                "cuisine": cuisine,
                "prep_time_bucket": PrepTimeBucket(deterministic_prep_time_bucket(recipe.cooking_time_minutes)),
                "tag_slugs_by_type": slugs_by_type or None,
                "tag_metadata": _quarantined_metadata(proposed, repo_path) or None,
            }
        )

    return out
