"""Client recipe sync: upsert by id into the file-backed recipe store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, StrictInt, field_validator

from src.api.error_mapping import (
    INGREDIENT_QUANTITY_REQUIRED,
    INGREDIENT_UNRESOLVED,
    UNIT_NOT_CONVERTIBLE,
    ApiContractError,
)
from src.data_layer.exceptions import IngredientNotFoundError
from src.data_layer.recipe_db import parse_ingredient
from src.llm.recipe_tagger import CUISINE_VOCABULARY
from src.llm.schemas import BudgetLevel, DietaryFlag, PrepTimeBucket, RecipeTagsJson
from src.llm.time_bucket import deterministic_prep_time_bucket, time_bucket_slug
from src.nutrition.calculator import NutritionCalculator, is_to_taste_allowed
from src.llm.tag_repository import (
    TagRepositoryError,
    load_recipe_tags,
    resolve,
    upsert_recipe_tags,
)


class RecipeSyncIngredientLine(BaseModel):
    """One ingredient line as sent by the client."""

    name: str = Field(..., min_length=1)
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1)
    grams_per_unit: Optional[float] = Field(
        None,
        gt=0,
        description=(
            "Weight in grams of one `unit` of this line (e.g. the Ingredient Hub's cup "
            "weight). Used only when the ingredient record has no conversion for the "
            "unit; stored on the recipe line, never in the reference ingredient table."
        ),
    )

    @field_validator("name", "unit", mode="before")
    @classmethod
    def _strip_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("ingredient name must not be empty")
        return v


class RecipeSyncItem(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    ingredients: List[RecipeSyncIngredientLine] = Field(..., min_length=1)
    cooking_time_minutes: int = Field(default=0, ge=0)
    instructions: List[str] = Field(default_factory=list)
    default_servings: StrictInt = Field(default=1, ge=1)
    tag_slugs_by_type: Optional[
        Dict[Literal["context", "time", "nutrition", "constraint"], List[str]]
    ] = None
    cuisine: Optional[Literal[tuple(CUISINE_VOCABULARY)]] = Field(  # type: ignore[valid-type]
        None,
        description=(
            "Cuisine from the tagger's closed vocabulary. Omitted keeps the stored value "
            "(else \"unknown\")."
        ),
    )
    cost_level: Optional[BudgetLevel] = Field(
        None, description="Omitted keeps the stored value (else \"standard\")."
    )
    dietary_flags: Optional[List[DietaryFlag]] = Field(
        None, description="Omitted keeps the stored flags (else []); [] clears them."
    )

    @field_validator("cuisine", mode="before")
    @classmethod
    def _normalize_cuisine(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("id", "name", mode="before")
    @classmethod
    def _strip_ids(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("id", "name")
    @classmethod
    def _non_empty_after_strip(cls, v: str) -> str:
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("tag_slugs_by_type", mode="before")
    @classmethod
    def _normalize_typed_tags(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("tag_slugs_by_type must be an object.")

        out: Dict[str, List[str]] = {}
        for raw_type, raw_slugs in value.items():
            if not isinstance(raw_type, str):
                raise ValueError("tag type keys must be strings.")
            tag_type = raw_type.strip().lower()
            if tag_type not in {"context", "time", "nutrition", "constraint"}:
                raise ValueError("Invalid tag type.")
            if not isinstance(raw_slugs, list):
                raise ValueError(f"tag_slugs_by_type.{tag_type} must be a list.")
            cleaned: List[str] = []
            for raw_slug in raw_slugs:
                if not isinstance(raw_slug, str):
                    raise ValueError(f"tag_slugs_by_type.{tag_type} must contain strings.")
                slug = raw_slug.strip()
                if slug:
                    cleaned.append(slug)
            if cleaned:
                out[tag_type] = cleaned
        return out or None


class RecipeSyncRequest(BaseModel):
    recipes: List[RecipeSyncItem]


class RecipeSyncResponse(BaseModel):
    synced_ids: List[str]
    errors: List[str] = Field(default_factory=list)


def _load_recipe_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"recipes": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Recipes file must contain a JSON object.")
    recipes = data.get("recipes", [])
    if not isinstance(recipes, list):
        raise ValueError('"recipes" must be a JSON list.')
    return {"recipes": recipes}


#: Per-item save rejections. Sync reports them in ``errors`` and stores the other items;
#: single create/PUT returns them as a 400. (``INGREDIENT_QUANTITY_REQUIRED`` stays a
#: whole-request 422, as in BE-18.)
PER_ITEM_REJECTION_CODES = frozenset({UNIT_NOT_CONVERTIBLE, INGREDIENT_UNRESOLVED})


def _check_line_is_plannable(
    row: Dict[str, Any], calculator: NutritionCalculator
) -> None:
    """Reject a stored line the planner would drop: unknown name or no gram conversion.

    Uses the same parse (``parse_ingredient``) and calculator as planning, against the
    local ingredient table only: no USDA/network calls at save time.
    """
    ingredient = parse_ingredient(row)
    if ingredient.is_to_taste:
        return
    name, unit = ingredient.name, ingredient.unit
    details = {"ingredient": name, "unit": unit}
    info = calculator.provider.get_ingredient_info(name)
    if info is None:
        raise ApiContractError(
            INGREDIENT_UNRESOLVED,
            f"Ingredient {name!r} (unit {unit!r}) is not in the local ingredient table "
            "(save-time validation checks the local table only).",
            details=details,
        )
    try:
        calculator.to_grams(ingredient, info)
    except IngredientNotFoundError as exc:
        raise ApiContractError(
            UNIT_NOT_CONVERTIBLE,
            f"Ingredient {name!r} has no gram conversion for unit {unit!r}: use a mass "
            "unit or send grams_per_unit for this line.",
            details=details,
        ) from exc
    try:
        calculator.calculate_ingredient_nutrition(ingredient)
    except IngredientNotFoundError as exc:
        raise ApiContractError(
            INGREDIENT_UNRESOLVED,
            f"Ingredient {name!r} (unit {unit!r}) has no usable nutrition block in the "
            "local ingredient table.",
            details=details,
        ) from exc


def _normalize_ingredient_for_storage(
    line: RecipeSyncIngredientLine,
    calculator: Optional[NutritionCalculator] = None,
) -> Dict[str, Any]:
    """Match RecipeDB._parse_ingredient / append_validated_recipes storage shape.

    The save-time line checks live here (one loop): ``to taste`` only for seasonings
    (BE-18), then, when a ``calculator`` is given, a resolvable name and a gram
    conversion for the unit (BE-19).
    """
    unit = line.unit.strip()
    lowered = unit.lower()
    is_to_taste = lowered == "to taste" or "to taste" in lowered
    if is_to_taste and not is_to_taste_allowed(line.name):
        name = line.name.strip()
        raise ApiContractError(
            INGREDIENT_QUANTITY_REQUIRED,
            f"Ingredient {name!r} needs a quantity: only seasonings (salt, water, "
            "spices, herbs) may be 'to taste'.",
            details={"ingredient": name},
        )
    quantity = 0.0 if is_to_taste else float(line.quantity)
    out_unit = "to taste" if is_to_taste else unit
    row: Dict[str, Any] = {
        "name": line.name.strip(),
        "quantity": quantity,
        "unit": out_unit,
    }
    if line.grams_per_unit is not None and not is_to_taste:
        row["grams_per_unit"] = float(line.grams_per_unit)
    if calculator is not None:
        _check_line_is_plannable(row, calculator)
    return row


def _item_to_stored_dict(
    item: RecipeSyncItem, calculator: Optional[NutritionCalculator] = None
) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "ingredients": [
            _normalize_ingredient_for_storage(i, calculator) for i in item.ingredients
        ],
        "cooking_time_minutes": int(item.cooking_time_minutes),
        "instructions": list(item.instructions),
        "default_servings": int(item.default_servings),
    }


def _normalize_item_tags_by_type(
    item: RecipeSyncItem,
    *,
    tag_path: str,
) -> Optional[Dict[str, List[str]]]:
    if not item.tag_slugs_by_type:
        return None

    normalized: Dict[str, List[str]] = {}
    for expected_type, raw_slugs in item.tag_slugs_by_type.items():
        seen: set[str] = set()
        canonical: List[str] = []
        for raw_slug in raw_slugs:
            try:
                meta = resolve(raw_slug, tag_path)
            except ValueError as exc:
                raise TagRepositoryError("TAG_NOT_FOUND", "Tag not found.") from exc
            if meta.tag_type != expected_type:
                raise TagRepositoryError("TAG_INVALID", "Invalid tag type.")
            if meta.slug not in seen:
                seen.add(meta.slug)
                canonical.append(meta.slug)
        if canonical:
            normalized[expected_type] = canonical
    return normalized or None


def _build_updated_tags_by_id(
    *,
    tag_path: str,
    items: List[RecipeSyncItem],
) -> Dict[str, RecipeTagsJson]:
    """One ``tags_by_id`` entry per item (BE-19), to merge into the tag store.

    - ``prep_time_bucket`` and the ``time`` slug are derived from ``cooking_time_minutes``
      (``time_bucket`` helpers, the tagger's derivation); a client ``time`` slug is replaced.
    - Client ``tag_slugs_by_type`` (canonicalized) replace the other types; omitted keeps
      the stored ones.
    - ``cuisine`` / ``cost_level`` / ``dietary_flags``: sent value, else stored value, else
      ``"unknown"`` / ``"standard"`` / ``[]``.
    """
    existing = load_recipe_tags(tag_path)
    out: Dict[str, RecipeTagsJson] = {}
    for item in items:
        normalized = _normalize_item_tags_by_type(item, tag_path=tag_path)
        prior = existing.get(item.id)
        if normalized is not None:
            slugs = dict(normalized)
        else:
            slugs = dict((prior.tag_slugs_by_type or {}) if prior is not None else {})
        minutes = int(item.cooking_time_minutes)
        slugs["time"] = [resolve(time_bucket_slug(minutes), tag_path).slug]

        fields: Dict[str, Any] = {
            "prep_time_bucket": PrepTimeBucket(deterministic_prep_time_bucket(minutes)),
            "tag_slugs_by_type": slugs,
        }
        if item.cuisine is not None:
            fields["cuisine"] = item.cuisine
        if item.cost_level is not None:
            fields["cost_level"] = item.cost_level
        if item.dietary_flags is not None:
            fields["dietary_flags"] = list(item.dietary_flags)

        if prior is not None:
            out[item.id] = prior.model_copy(update=fields)
        else:
            out[item.id] = RecipeTagsJson(
                **{
                    "cuisine": "unknown",
                    "cost_level": BudgetLevel.standard,
                    "dietary_flags": [],
                    **fields,
                }
            )
    return out


def atomic_upsert_recipes_by_id(
    *,
    path: str,
    items: List[RecipeSyncItem],
    tag_path: Optional[str] = None,
    calculator: Optional[NutritionCalculator] = None,
    errors: Optional[List[str]] = None,
) -> List[str]:
    """Load JSON store, upsert each item by client id, atomic write. Returns ids in request order.

    - ``calculator``: when given, each line must resolve and convert to grams with it
      (BE-19); otherwise the item is rejected with ``UNIT_NOT_CONVERTIBLE`` /
      ``INGREDIENT_UNRESOLVED``.
    - ``errors``: when given, a rejected item is skipped (not stored, not in the returned
      ids) and ``"<recipe id>: <CODE>: <message>"`` is appended; when omitted the
      rejection is raised. Any other error rejects the whole request before any write.
    - ``tag_path``: when given, every stored item gets a ``tags_by_id`` entry, merged into
      the tag store (``upsert_recipe_tags`` merge mode).
    """
    recipes_path = Path(path)
    recipes_path.parent.mkdir(parents=True, exist_ok=True)

    accepted: List[RecipeSyncItem] = []
    blobs: List[Dict[str, Any]] = []
    for item in items:
        try:
            blob = _item_to_stored_dict(item, calculator)
        except ApiContractError as exc:
            if errors is None or exc.code not in PER_ITEM_REJECTION_CODES:
                raise
            errors.append(f"{item.id}: {exc.code}: {exc}")
            continue
        accepted.append(item)
        blobs.append(blob)

    updated_tags: Optional[Dict[str, RecipeTagsJson]] = None
    if tag_path is not None and accepted:
        # Validate/normalize tag payload before mutating recipe storage.
        updated_tags = _build_updated_tags_by_id(tag_path=tag_path, items=accepted)

    if not blobs:
        return []

    existing_data = _load_recipe_json(recipes_path)
    existing_recipes: List[Dict[str, Any]] = list(existing_data["recipes"])
    id_to_index: Dict[str, int] = {}
    for idx, row in enumerate(existing_recipes):
        rid = row.get("id")
        if isinstance(rid, str) and rid:
            id_to_index[rid] = idx

    synced_ids: List[str] = []
    for blob in blobs:
        rid = blob["id"]
        if rid in id_to_index:
            existing_recipes[id_to_index[rid]] = blob
        else:
            id_to_index[rid] = len(existing_recipes)
            existing_recipes.append(blob)
        synced_ids.append(rid)

    tmp_path = recipes_path.with_suffix(recipes_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump({"recipes": existing_recipes}, f, indent=2)
    os.replace(str(tmp_path), str(recipes_path))
    if tag_path is not None and updated_tags:
        upsert_recipe_tags(tag_path, updated_tags)
    return synced_ids
