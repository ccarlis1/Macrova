from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

from src.data_layer.models import Ingredient, Recipe


def _normalized_ingredient_for_fingerprint(ing: Ingredient) -> Dict[str, Any]:
    # To keep the fingerprint stable across presentation differences:
    # - ignore ingredient name ordering (we sort later)
    # - ignore recipe name/id/instructions
    # - treat "to taste" ingredients as non-contributing to fingerprint
    if ing.is_to_taste or ing.unit.lower() == "to taste":
        return {}

    # Quantities are floats; normalize to a stable decimal precision.
    qty = round(float(ing.quantity), 6)
    return {
        "name": str(ing.name).strip().lower(),
        "quantity": qty,
        "unit": str(ing.unit).strip().lower(),
    }


def compute_recipe_fingerprint(recipe: Recipe) -> str:
    """Compute a stable fingerprint ignoring ingredient ordering.

    Based only on measurable ingredients (name/quantity/unit), with stable
    float rounding.
    """
    normalized: List[Dict[str, Any]] = []
    for ing in recipe.ingredients:
        d = _normalized_ingredient_for_fingerprint(ing)
        if d:
            normalized.append(d)

    normalized.sort(key=lambda d: (d["name"], d["unit"], d["quantity"]))
    payload = {"ingredients": normalized}
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def generate_deterministic_recipe_id(recipe: Recipe, existing_ids: Set[str]) -> str:
    """Generate a collision-safe deterministic ID for `recipe`.

    If the primary candidate is already present, suffix deterministically.
    """
    fingerprint = compute_recipe_fingerprint(recipe)
    base = f"llm_{fingerprint[:16]}"

    if base not in existing_ids:
        return base

    # Collision-safe suffixing (deterministic but should almost never happen).
    for i in range(1, 10000):
        candidate = f"{base}_{i}"
        if candidate not in existing_ids:
            return candidate

    # Extremely unlikely; surface a clear error.
    raise RuntimeError("Failed to generate collision-free recipe id.")


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


def append_validated_recipes(
    *,
    path: str,
    recipes: List[Recipe],
) -> List[str]:
    """Append validated recipes to the JSON store.

    - Deduplicates by fingerprint (ingredient content).
    - Uses deterministic, collision-safe IDs.
    - Preserves existing ordering; appends new recipes in input order.
    - Performs atomic write to avoid partial file corruption.
    """
    recipes_path = Path(path)
    recipes_path.parent.mkdir(parents=True, exist_ok=True)

    existing_data = _load_recipe_json(recipes_path)
    existing_recipes: List[Dict[str, Any]] = existing_data["recipes"]

    existing_ids: Set[str] = set()
    existing_fingerprints: Set[str] = set()
    fingerprint_to_id: Dict[str, str] = {}
    from src.data_layer.recipe_db import RecipeDB

    if existing_recipes:
        # Use RecipeDB parsing to avoid duplicating parsing logic.
        # (It depends on the same JSON shape we write.)
        db = RecipeDB(str(recipes_path))
        for r in db.get_all_recipes():
            existing_ids.add(r.id)
            fp = compute_recipe_fingerprint(r)
            existing_fingerprints.add(fp)
            fingerprint_to_id[fp] = r.id

    appended_ids: List[str] = []

    for recipe in recipes:
        fp = compute_recipe_fingerprint(recipe)
        if fp in existing_fingerprints:
            continue  # Deduplicate by content.

        recipe.id = generate_deterministic_recipe_id(recipe, existing_ids)
        existing_ids.add(recipe.id)
        existing_fingerprints.add(fp)
        fingerprint_to_id[fp] = recipe.id
        appended_ids.append(recipe.id)

        existing_recipes.append(
            {
                "id": recipe.id,
                "name": recipe.name,
                "ingredients": [
                    {
                        "name": ing.name,
                        "quantity": float(ing.quantity if not ing.is_to_taste else 0.0),
                        "unit": "to taste" if ing.is_to_taste or ing.unit.lower() == "to taste" else ing.unit,
                    }
                    for ing in recipe.ingredients
                ],
                "cooking_time_minutes": int(recipe.cooking_time_minutes),
                "instructions": list(recipe.instructions),
            }
        )

    tmp_path = recipes_path.with_suffix(recipes_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump({"recipes": existing_recipes}, f, indent=2)

    os.replace(str(tmp_path), str(recipes_path))
    return appended_ids

