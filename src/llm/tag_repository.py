from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.llm.schemas import (
    RecipeTagsJson,
    TagMeta,
    TagSource,
    TagType,
    parse_llm_json,
    ValidationFailure,
)


class TagRepositoryError(Exception):
    """Base error for deterministic tag repository failures."""

    error_code = "TAG_INVALID"
    status_code = 422


class TagNotFoundError(TagRepositoryError):
    error_code = "TAG_NOT_FOUND"
    status_code = 404


class TagConflictError(TagRepositoryError):
    error_code = "TAG_CONFLICT"
    status_code = 409


class TagInvalidError(TagRepositoryError):
    error_code = "TAG_INVALID"
    status_code = 422


TAG_TYPES = {"context", "time", "nutrition", "constraint"}
TAG_SOURCES = {"user", "llm", "system"}

SEED_TAGS: List[Dict[str, str]] = [
    {"slug": "high-omega-3", "display": "High Omega 3", "type": "nutrition"},
    {"slug": "high-fiber", "display": "High Fiber", "type": "nutrition"},
    {"slug": "high-calcium", "display": "High Calcium", "type": "nutrition"},
    {"slug": "time-0", "display": "0 minutes", "type": "time"},
    {"slug": "time-1", "display": "1 to 5 minutes", "type": "time"},
    {"slug": "time-2", "display": "6 to 15 minutes", "type": "time"},
    {"slug": "time-3", "display": "16 to 30 minutes", "type": "time"},
    {"slug": "time-4", "display": "31 plus minutes", "type": "time"},
]


def normalize_slug(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise TagInvalidError("Tag slug cannot be empty after normalization.")
    return normalized


def _created_at() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_tags_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"tags_by_id": {}, "registry": {}, "recipe_tag_slugs_by_id": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Recipe tags file must contain a JSON object.")
    tags_by_id = data.get("tags_by_id", {})
    if not isinstance(tags_by_id, dict):
        raise ValueError('"tags_by_id" must be a JSON object.')
    registry = data.get("registry", {})
    if not isinstance(registry, dict):
        raise ValueError('"registry" must be a JSON object.')
    recipe_tag_slugs_by_id = data.get("recipe_tag_slugs_by_id", {})
    if not isinstance(recipe_tag_slugs_by_id, dict):
        raise ValueError('"recipe_tag_slugs_by_id" must be a JSON object.')
    return {
        "tags_by_id": tags_by_id,
        "registry": registry,
        "recipe_tag_slugs_by_id": recipe_tag_slugs_by_id,
    }


def _write_tags_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=True)
    os.replace(str(tmp_path), str(path))


def _tag_meta_from_raw(raw: Any) -> Optional[TagMeta]:
    if not isinstance(raw, dict):
        return None
    parsed = parse_llm_json(TagMeta, raw)
    if isinstance(parsed, ValidationFailure):
        return None
    return parsed


def _tag_to_json(tag: TagMeta) -> Dict[str, Any]:
    return tag.model_dump()


def _validate_tag_type(tag_type: str) -> TagType:
    if tag_type not in TAG_TYPES:
        raise TagInvalidError(f"Invalid tag type: {tag_type}")
    return tag_type  # type: ignore[return-value]


def _validate_tag_source(source: str) -> TagSource:
    if source not in TAG_SOURCES:
        raise TagInvalidError(f"Invalid tag source: {source}")
    return source  # type: ignore[return-value]


def _default_eligibility(source: TagSource) -> str:
    return "proposed" if source == "llm" else "approved"


def _seed_registry(payload: Dict[str, Any]) -> bool:
    registry = payload["registry"]
    changed = False
    for seed in SEED_TAGS:
        slug = seed["slug"]
        if slug in registry:
            continue
        tag = TagMeta(
            slug=slug,
            display=seed["display"],
            type=_validate_tag_type(seed["type"]),
            source="system",
            created_at=_created_at(),
            aliases=[],
            eligibility="approved",
        )
        registry[slug] = _tag_to_json(tag)
        changed = True
    return changed


def load_recipe_tag_slugs(path: str) -> Dict[str, List[str]]:
    raw = _load_tags_json(Path(path))
    out: Dict[str, List[str]] = {}
    for recipe_id, slugs in raw["recipe_tag_slugs_by_id"].items():
        if not isinstance(slugs, list):
            continue
        out[str(recipe_id)] = [normalize_slug(str(slug)) for slug in slugs]
    return out


def upsert_recipe_tag_slugs(
    path: str, recipe_tag_slugs_by_id: Dict[str, List[str]]
) -> None:
    tags_path = Path(path)
    payload = _load_tags_json(tags_path)
    payload["recipe_tag_slugs_by_id"] = {
        str(recipe_id): sorted({normalize_slug(slug) for slug in slugs})
        for recipe_id, slugs in recipe_tag_slugs_by_id.items()
    }
    _seed_registry(payload)
    _write_tags_json(tags_path, payload)


class TagRegistry:
    def __init__(self, path: str):
        self.path = Path(path)
        payload = _load_tags_json(self.path)
        if _seed_registry(payload):
            _write_tags_json(self.path, payload)

    def _load(self) -> Dict[str, Any]:
        payload = _load_tags_json(self.path)
        if _seed_registry(payload):
            _write_tags_json(self.path, payload)
            payload = _load_tags_json(self.path)
        return payload

    def _save(self, payload: Dict[str, Any]) -> None:
        _write_tags_json(self.path, payload)

    def _all_tags(self, payload: Dict[str, Any]) -> Dict[str, TagMeta]:
        out: Dict[str, TagMeta] = {}
        for slug, raw in payload["registry"].items():
            parsed = _tag_meta_from_raw(raw)
            if parsed is not None:
                out[str(slug)] = parsed
        return out

    def resolve(self, slug_or_display: str) -> TagMeta:
        lookup = normalize_slug(slug_or_display)
        payload = self._load()
        tags = self._all_tags(payload)
        if lookup in tags:
            return tags[lookup]

        for tag in tags.values():
            aliases = {normalize_slug(alias) for alias in tag.aliases}
            if lookup in aliases or lookup == normalize_slug(tag.display):
                return tag

        raise TagNotFoundError(f"Tag not found: {slug_or_display}")

    def create(
        self,
        *,
        display: str,
        type: TagType,
        slug: Optional[str] = None,
        source: TagSource = "user",
    ) -> TagMeta:
        tag_type = _validate_tag_type(type)
        tag_source = _validate_tag_source(source)
        normalized_slug = normalize_slug(slug or display)

        payload = self._load()
        tags = self._all_tags(payload)
        if normalized_slug in tags:
            raise TagConflictError(f"Tag already exists: {normalized_slug}")

        for existing in tags.values():
            aliases = {normalize_slug(alias) for alias in existing.aliases}
            if normalized_slug in aliases:
                raise TagConflictError(f"Tag alias already exists: {normalized_slug}")

        tag = TagMeta(
            slug=normalized_slug,
            display=display.strip(),
            type=tag_type,
            source=tag_source,
            created_at=_created_at(),
            aliases=[],
            eligibility=_default_eligibility(tag_source),  # type: ignore[arg-type]
        )
        payload["registry"][normalized_slug] = _tag_to_json(tag)
        self._save(payload)
        return tag

    def list_by_type(self, type: Optional[TagType] = None) -> List[TagMeta]:
        payload = self._load()
        tag_type = _validate_tag_type(type) if type is not None else None
        tags = list(self._all_tags(payload).values())
        if tag_type is not None:
            tags = [tag for tag in tags if tag.type == tag_type]
        return sorted(tags, key=lambda tag: tag.slug)

    def rename_display(self, slug: str, display: str) -> TagMeta:
        normalized_slug = normalize_slug(slug)
        payload = self._load()
        tag = self._all_tags(payload).get(normalized_slug)
        if tag is None:
            raise TagNotFoundError(f"Tag not found: {slug}")
        tag.display = display.strip()
        payload["registry"][normalized_slug] = _tag_to_json(tag)
        self._save(payload)
        return tag

    def add_alias(self, slug: str, alias_slug: str) -> TagMeta:
        normalized_slug = normalize_slug(slug)
        normalized_alias = normalize_slug(alias_slug)
        payload = self._load()
        tags = self._all_tags(payload)
        tag = tags.get(normalized_slug)
        if tag is None:
            raise TagNotFoundError(f"Tag not found: {slug}")
        if normalized_alias in tags and normalized_alias != normalized_slug:
            raise TagConflictError(f"Tag already exists: {normalized_alias}")
        for existing in tags.values():
            aliases = {normalize_slug(alias) for alias in existing.aliases}
            if normalized_alias in aliases and existing.slug != normalized_slug:
                raise TagConflictError(f"Tag alias already exists: {normalized_alias}")
        if normalized_alias != normalized_slug and normalized_alias not in tag.aliases:
            tag.aliases.append(normalized_alias)
            tag.aliases = sorted({normalize_slug(alias) for alias in tag.aliases})
            payload["registry"][normalized_slug] = _tag_to_json(tag)
            self._save(payload)
        return tag

    def merge(self, src_slug: str, dst_slug: str) -> None:
        normalized_src = normalize_slug(src_slug)
        normalized_dst = normalize_slug(dst_slug)
        if normalized_src == normalized_dst:
            raise TagInvalidError("Cannot merge a tag into itself.")

        payload = self._load()
        tags = self._all_tags(payload)
        src = tags.get(normalized_src)
        dst = tags.get(normalized_dst)
        if src is None:
            raise TagNotFoundError(f"Tag not found: {src_slug}")
        if dst is None:
            raise TagNotFoundError(f"Tag not found: {dst_slug}")
        if src.type != dst.type:
            raise TagInvalidError("Cannot merge tags with different types.")

        rewritten: Dict[str, List[str]] = {}
        for recipe_id, slugs in payload["recipe_tag_slugs_by_id"].items():
            if not isinstance(slugs, list):
                continue
            next_slugs = [
                (
                    normalized_dst
                    if normalize_slug(str(slug)) == normalized_src
                    else normalize_slug(str(slug))
                )
                for slug in slugs
            ]
            rewritten[str(recipe_id)] = sorted(set(next_slugs))
        payload["recipe_tag_slugs_by_id"] = rewritten

        dst_aliases = {normalize_slug(alias) for alias in dst.aliases}
        dst_aliases.add(normalized_src)
        dst_aliases.update(normalize_slug(alias) for alias in src.aliases)
        dst.aliases = sorted(dst_aliases)
        payload["registry"][normalized_dst] = _tag_to_json(dst)
        payload["registry"].pop(normalized_src, None)
        self._save(payload)


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

    # Normalize payload values into plain JSON types (no Pydantic objects).
    tags_dump: Dict[str, Any] = {
        str(recipe_id): tag.model_dump() for recipe_id, tag in tags_by_id.items()
    }

    payload = _load_tags_json(tags_path)
    payload["tags_by_id"] = tags_dump
    _seed_registry(payload)
    _write_tags_json(tags_path, payload)
