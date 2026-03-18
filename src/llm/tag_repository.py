from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from src.llm.schemas import RecipeTagsJson, parse_llm_json, ValidationFailure


def _load_tags_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"tags_by_id": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Recipe tags file must contain a JSON object.")
    tags_by_id = data.get("tags_by_id", {})
    if not isinstance(tags_by_id, dict):
        raise ValueError('"tags_by_id" must be a JSON object.')
    return {"tags_by_id": tags_by_id}


def load_recipe_tags(path: str) -> Dict[str, RecipeTagsJson]:
    """Load validated recipe tags from disk.

    Invalid tag entries are skipped (never returned as unvalidated data).
    """

    tags_path = Path(path)
    raw = _load_tags_json(tags_path)
    tags_by_id_raw = raw["tags_by_id"]

    out: Dict[str, RecipeTagsJson] = {}
    for recipe_id, tag_raw in tags_by_id_raw.items():
        if not isinstance(tag_raw, dict):
            continue
        parsed = parse_llm_json(RecipeTagsJson, tag_raw)
        if isinstance(parsed, ValidationFailure):
            continue
        out[str(recipe_id)] = parsed
    return out


def upsert_recipe_tags(path: str, tags_by_id: Dict[str, RecipeTagsJson]) -> None:
    """Persist recipe tags atomically as JSON.

    - Idempotent: writing identical tags yields identical file content.
    - Stable ordering: keys are sorted for deterministic writes.
    - Atomic write: write to `*.tmp` then `os.replace`.
    """

    tags_path = Path(path)
    tags_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize payload values into plain JSON types (no Pydantic objects).
    tags_dump: Dict[str, Any] = {
        str(recipe_id): tag.model_dump() for recipe_id, tag in tags_by_id.items()
    }

    payload = {"tags_by_id": tags_dump}
    tmp_path = tags_path.with_suffix(tags_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=True)

    os.replace(str(tmp_path), str(tags_path))

