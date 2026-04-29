"""Client recipe sync: upsert by id into the file-backed recipe store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, StrictInt, field_validator

from src.llm.schemas import RecipeTagsJson
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


def _normalize_ingredient_for_storage(line: RecipeSyncIngredientLine) -> Dict[str, Any]:
    """Match RecipeDB._parse_ingredient / append_validated_recipes storage shape."""
    unit = line.unit.strip()
    lowered = unit.lower()
    is_to_taste = lowered == "to taste" or "to taste" in lowered
    quantity = 0.0 if is_to_taste else float(line.quantity)
    out_unit = "to taste" if is_to_taste else unit
    return {
        "name": line.name.strip(),
        "quantity": quantity,
        "unit": out_unit,
    }


def _item_to_stored_dict(item: RecipeSyncItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "ingredients": [_normalize_ingredient_for_storage(i) for i in item.ingredients],
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
) -> Optional[Dict[str, RecipeTagsJson]]:
    if not items:
        return None

    existing = load_recipe_tags(tag_path)
    updated = dict(existing)
    changed = False
    for item in items:
        normalized = _normalize_item_tags_by_type(item, tag_path=tag_path)
        if normalized is None:
            continue
        changed = True
        prior = existing.get(item.id)
        if prior is not None:
            updated[item.id] = prior.model_copy(update={"tag_slugs_by_type": normalized})
        else:
            updated[item.id] = RecipeTagsJson(
                cuisine="unknown",
                cost_level="standard",
                prep_time_bucket="weeknight_meal",
                dietary_flags=[],
                tag_slugs_by_type=normalized,
            )
    if not changed:
        return None
    return updated


def atomic_upsert_recipes_by_id(
    *,
    path: str,
    items: List[RecipeSyncItem],
    tag_path: Optional[str] = None,
) -> List[str]:
    """Load JSON store, upsert each item by client id, atomic write. Returns ids in request order."""
    recipes_path = Path(path)
    recipes_path.parent.mkdir(parents=True, exist_ok=True)
    updated_tags: Optional[Dict[str, RecipeTagsJson]] = None
    if tag_path is not None:
        # Validate/normalize tag payload before mutating recipe storage.
        updated_tags = _build_updated_tags_by_id(tag_path=tag_path, items=items)

    existing_data = _load_recipe_json(recipes_path)
    existing_recipes: List[Dict[str, Any]] = list(existing_data["recipes"])
    id_to_index: Dict[str, int] = {}
    for idx, row in enumerate(existing_recipes):
        rid = row.get("id")
        if isinstance(rid, str) and rid:
            id_to_index[rid] = idx

    synced_ids: List[str] = []
    for item in items:
        blob = _item_to_stored_dict(item)
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
    if tag_path is not None and updated_tags is not None:
        upsert_recipe_tags(tag_path, updated_tags)
    return synced_ids
