"""Client recipe sync: upsert by id into the file-backed recipe store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


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
    }


def atomic_upsert_recipes_by_id(*, path: str, items: List[RecipeSyncItem]) -> List[str]:
    """Load JSON store, upsert each item by client id, atomic write. Returns ids in request order."""
    recipes_path = Path(path)
    recipes_path.parent.mkdir(parents=True, exist_ok=True)

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
    return synced_ids
