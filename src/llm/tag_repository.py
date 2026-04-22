from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from src.llm.schemas import (
    RecipeTagsJson,
    TagMetaJson,
    ValidationFailure,
    parse_llm_json,
)

_SEED_CREATED_AT = "1970-01-01T00:00:00Z"
_SEED_TAGS: Dict[str, Dict[str, str]] = {
    "high-omega-3": {"display": "High Omega 3", "tag_type": "nutrition"},
    "high-fiber": {"display": "High Fiber", "tag_type": "nutrition"},
    "high-calcium": {"display": "High Calcium", "tag_type": "nutrition"},
}

_VALID_TAG_TYPES = {"context", "time", "nutrition", "constraint"}
_VALID_SOURCES = {"user", "llm", "system"}


@dataclass(frozen=True)
class TagRepositoryError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _normalize_slug(raw: str) -> str:
    s = str(raw).strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _load_registry_state(path: str) -> tuple[
    Dict[str, RecipeTagsJson], Dict[str, TagMetaJson], Dict[str, str]
]:
    raw = _load_tags_json(Path(path))
    tags_by_id_raw = raw.get("tags_by_id", {})
    tags_by_id: Dict[str, RecipeTagsJson] = {}
    for recipe_id, tag_raw in tags_by_id_raw.items():
        if not isinstance(tag_raw, dict):
            continue
        parsed = parse_llm_json(RecipeTagsJson, tag_raw)
        if isinstance(parsed, ValidationFailure):
            continue
        tags_by_id[str(recipe_id)] = parsed
    tag_registry = _parse_tag_registry(raw.get("tag_registry", {}))
    tag_aliases = _parse_tag_aliases(raw.get("tag_aliases", {}))
    tag_registry, tag_aliases = _ensure_seed_data(tag_registry, tag_aliases)
    return tags_by_id, tag_registry, tag_aliases


def _assert_tag_type(tag_type: str) -> str:
    normalized = str(tag_type).strip().lower()
    if normalized not in _VALID_TAG_TYPES:
        raise TagRepositoryError("TAG_INVALID", "Invalid tag type.")
    return normalized


def _assert_source(source: str) -> str:
    normalized = str(source).strip().lower()
    if normalized not in _VALID_SOURCES:
        raise TagRepositoryError("TAG_INVALID", "Invalid tag source.")
    return normalized


def _now_utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    os.replace(str(tmp_path), str(path))


@contextmanager
def _exclusive_file_lock(lock_path: Path) -> Iterable[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _parse_tag_registry(raw: Any) -> Dict[str, TagMetaJson]:
    if not isinstance(raw, dict):
        return {}

    out: Dict[str, TagMetaJson] = {}
    for slug, meta_raw in raw.items():
        if not isinstance(meta_raw, dict):
            continue
        parsed = parse_llm_json(TagMetaJson, meta_raw)
        if isinstance(parsed, ValidationFailure):
            continue
        normalized_slug = _normalize_slug(slug)
        if not normalized_slug:
            continue
        meta_slug = _normalize_slug(parsed.slug)
        canonical = meta_slug or normalized_slug
        out[canonical] = parsed.model_copy(update={"slug": canonical})
    return out


def _parse_tag_aliases(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for alias_raw, canonical_raw in raw.items():
        alias = _normalize_slug(alias_raw)
        canonical = _normalize_slug(canonical_raw)
        if alias and canonical:
            out[alias] = canonical
    return out


def _ensure_seed_data(
    tag_registry: Dict[str, TagMetaJson],
    tag_aliases: Dict[str, str],
) -> Tuple[Dict[str, TagMetaJson], Dict[str, str]]:
    registry = dict(tag_registry)
    aliases = dict(tag_aliases)
    for slug, seed in _SEED_TAGS.items():
        if slug not in registry:
            registry[slug] = TagMetaJson(
                slug=slug,
                display=seed["display"],
                tag_type=seed["tag_type"],
                source="system",
                created_at=_SEED_CREATED_AT,
                aliases=[],
            )
    for meta in registry.values():
        for alias_raw in meta.aliases:
            alias = _normalize_slug(alias_raw)
            if alias:
                aliases[alias] = meta.slug
    return registry, aliases


def _load_tags_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        payload: Dict[str, Any] = {"tags_by_id": {}, "tag_registry": {}, "tag_aliases": {}}
        registry, aliases = _ensure_seed_data({}, {})
        payload["tag_registry"] = {k: v.model_dump() for k, v in registry.items()}
        payload["tag_aliases"] = dict(aliases)
        return payload
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Recipe tags file must contain a JSON object.")

    tags_by_id = data.get("tags_by_id", {})
    if not isinstance(tags_by_id, dict):
        raise ValueError('"tags_by_id" must be a JSON object.')
    tag_registry = _parse_tag_registry(data.get("tag_registry", {}))
    tag_aliases = _parse_tag_aliases(data.get("tag_aliases", {}))
    tag_registry, tag_aliases = _ensure_seed_data(tag_registry, tag_aliases)
    return {
        "tags_by_id": tags_by_id,
        "tag_registry": {k: v.model_dump() for k, v in tag_registry.items()},
        "tag_aliases": tag_aliases,
    }


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


def _write_tags_payload(
    *,
    path: str,
    tags_by_id: Dict[str, RecipeTagsJson],
    tag_registry: Dict[str, TagMetaJson],
    tag_aliases: Dict[str, str],
) -> None:
    tags_path = Path(path)
    tags_path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize payload values into plain JSON types (no Pydantic objects).
    tags_dump: Dict[str, Any] = {
        str(recipe_id): tag.model_dump(exclude_none=True)
        for recipe_id, tag in tags_by_id.items()
    }
    registry, aliases = _ensure_seed_data(tag_registry, tag_aliases)
    registry_dump: Dict[str, Any] = {
        slug: meta.model_dump() for slug, meta in registry.items()
    }
    aliases_dump: Dict[str, str] = dict(aliases)

    payload = {
        "tags_by_id": tags_dump,
        "tag_registry": registry_dump,
        "tag_aliases": aliases_dump,
    }
    tmp_path = tags_path.with_suffix(tags_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=True)

    os.replace(str(tmp_path), str(tags_path))


def upsert_recipe_tags(path: str, tags_by_id: Dict[str, RecipeTagsJson]) -> None:
    """Persist recipe tags atomically as JSON.

    - Idempotent: writing identical tags yields identical file content.
    - Stable ordering: keys are sorted for deterministic writes.
    - Atomic write: write to `*.tmp` then `os.replace`.
    """
    raw = _load_tags_json(Path(path))
    tag_registry = _parse_tag_registry(raw.get("tag_registry", {}))
    tag_aliases = _parse_tag_aliases(raw.get("tag_aliases", {}))
    _write_tags_payload(
        path=path,
        tags_by_id=tags_by_id,
        tag_registry=tag_registry,
        tag_aliases=tag_aliases,
    )


def _resolve_from_maps(
    *,
    slug_or_display: str,
    tag_registry: Dict[str, TagMetaJson],
    tag_aliases: Dict[str, str],
) -> TagMetaJson:
    token = _normalize_slug(slug_or_display)
    if not token:
        raise ValueError("Unknown tag slug/display.")

    if token in tag_registry:
        return tag_registry[token]

    canonical = tag_aliases.get(token)
    if canonical and canonical in tag_registry:
        return tag_registry[canonical]

    for meta in tag_registry.values():
        if _normalize_slug(meta.display) == token:
            return meta

    raise ValueError("Unknown tag slug/display.")


def resolve(slug_or_display: str, path: str) -> TagMetaJson:
    """Resolve a slug, alias, or display into canonical tag metadata."""
    raw = _load_tags_json(Path(path))
    tag_registry = _parse_tag_registry(raw.get("tag_registry", {}))
    tag_aliases = _parse_tag_aliases(raw.get("tag_aliases", {}))
    tag_registry, tag_aliases = _ensure_seed_data(tag_registry, tag_aliases)
    return _resolve_from_maps(
        slug_or_display=slug_or_display,
        tag_registry=tag_registry,
        tag_aliases=tag_aliases,
    )


def list_by_type(path: str, tag_type: Optional[str] = None) -> list[TagMetaJson]:
    """List canonical tags, optionally filtered by type."""
    _, tag_registry, _ = _load_registry_state(path)
    items = list(tag_registry.values())
    if tag_type is None:
        return sorted(items, key=lambda m: m.slug)
    normalized_type = _assert_tag_type(tag_type)
    return sorted(
        [meta for meta in items if meta.tag_type == normalized_type],
        key=lambda m: m.slug,
    )


def create(
    *,
    path: str,
    display: str,
    tag_type: str,
    slug: Optional[str] = None,
    source: str = "user",
) -> TagMetaJson:
    """Create a new canonical tag in the registry."""
    normalized_display = str(display).strip()
    if not normalized_display:
        raise TagRepositoryError("TAG_INVALID", "Tag display must not be empty.")
    normalized_tag_type = _assert_tag_type(tag_type)
    normalized_source = _assert_source(source)
    canonical_slug = _normalize_slug(slug if slug is not None else normalized_display)
    if not canonical_slug:
        raise TagRepositoryError("TAG_INVALID", "Invalid tag slug.")

    tags_by_id, tag_registry, tag_aliases = _load_registry_state(path)
    if canonical_slug in tag_registry or canonical_slug in tag_aliases:
        raise TagRepositoryError("TAG_CONFLICT", "Tag slug already exists.")

    meta = TagMetaJson(
        slug=canonical_slug,
        display=normalized_display,
        tag_type=normalized_tag_type,  # type: ignore[arg-type]
        source=normalized_source,  # type: ignore[arg-type]
        created_at=_now_utc_iso(),
        aliases=[],
    )
    tag_registry[canonical_slug] = meta
    _write_tags_payload(
        path=path,
        tags_by_id=tags_by_id,
        tag_registry=tag_registry,
        tag_aliases=tag_aliases,
    )
    return meta


def rename_display(*, path: str, slug: str, display: str) -> TagMetaJson:
    """Rename display field only for a canonical tag."""
    normalized_display = str(display).strip()
    if not normalized_display:
        raise TagRepositoryError("TAG_INVALID", "Tag display must not be empty.")
    _, tag_registry, tag_aliases = _load_registry_state(path)
    try:
        existing = _resolve_from_maps(
            slug_or_display=slug,
            tag_registry=tag_registry,
            tag_aliases=tag_aliases,
        )
    except ValueError as exc:
        raise TagRepositoryError("TAG_NOT_FOUND", "Tag not found.") from exc
    canonical = existing.slug
    if canonical not in tag_registry:
        raise TagRepositoryError("TAG_NOT_FOUND", "Tag not found.")
    tag_registry[canonical] = existing.model_copy(update={"display": normalized_display})
    tags_by_id = load_recipe_tags(path)
    _write_tags_payload(
        path=path,
        tags_by_id=tags_by_id,
        tag_registry=tag_registry,
        tag_aliases=tag_aliases,
    )
    return tag_registry[canonical]


def add_alias(*, path: str, slug: str, alias_slug: str) -> TagMetaJson:
    """Attach an alias slug to a canonical tag."""
    normalized_alias = _normalize_slug(alias_slug)
    if not normalized_alias:
        raise TagRepositoryError("TAG_INVALID", "Invalid alias slug.")
    _, tag_registry, tag_aliases = _load_registry_state(path)
    try:
        existing = _resolve_from_maps(
            slug_or_display=slug,
            tag_registry=tag_registry,
            tag_aliases=tag_aliases,
        )
    except ValueError as exc:
        raise TagRepositoryError("TAG_NOT_FOUND", "Tag not found.") from exc
    canonical = existing.slug
    if normalized_alias == canonical:
        raise TagRepositoryError("TAG_CONFLICT", "Alias conflicts with canonical slug.")
    if normalized_alias in tag_registry:
        raise TagRepositoryError("TAG_CONFLICT", "Alias conflicts with existing tag.")
    bound = tag_aliases.get(normalized_alias)
    if bound is not None and bound != canonical:
        raise TagRepositoryError("TAG_CONFLICT", "Alias already bound to another tag.")
    aliases = _dedupe_preserve_order(
        [a for a in [_normalize_slug(v) for v in existing.aliases] if a]
        + [normalized_alias]
    )
    tag_registry[canonical] = existing.model_copy(update={"aliases": aliases})
    tag_aliases[normalized_alias] = canonical
    tags_by_id = load_recipe_tags(path)
    _write_tags_payload(
        path=path,
        tags_by_id=tags_by_id,
        tag_registry=tag_registry,
        tag_aliases=tag_aliases,
    )
    return tag_registry[canonical]


def merge(src_slug: str, dst_slug: str, path: str) -> None:
    """Merge source slug into destination slug and update all recipe references."""
    tags_path = Path(path)
    recipes_path = tags_path.with_name("recipes.json")
    lock_path = tags_path.with_suffix(tags_path.suffix + ".merge.lock")

    with _exclusive_file_lock(lock_path):
        original_tags_bytes = tags_path.read_bytes() if tags_path.exists() else None
        original_recipes_bytes = (
            recipes_path.read_bytes() if recipes_path.exists() else None
        )
        try:
            raw = _load_tags_json(tags_path)
            tag_registry = _parse_tag_registry(raw.get("tag_registry", {}))
            tag_aliases = _parse_tag_aliases(raw.get("tag_aliases", {}))
            tag_registry, tag_aliases = _ensure_seed_data(tag_registry, tag_aliases)

            try:
                src_meta = _resolve_from_maps(
                    slug_or_display=src_slug,
                    tag_registry=tag_registry,
                    tag_aliases=tag_aliases,
                )
                dst_meta = _resolve_from_maps(
                    slug_or_display=dst_slug,
                    tag_registry=tag_registry,
                    tag_aliases=tag_aliases,
                )
            except ValueError as exc:
                raise TagRepositoryError("TAG_NOT_FOUND", "Tag not found.") from exc
            src = src_meta.slug
            dst = dst_meta.slug
            if src == dst:
                return

            tags_by_id = load_recipe_tags(path)
            updated_tags_by_id: Dict[str, RecipeTagsJson] = {}
            for recipe_id, recipe_tags in tags_by_id.items():
                tag_slugs_by_type = {
                    tag_type: list(slugs)
                    for tag_type, slugs in (recipe_tags.tag_slugs_by_type or {}).items()
                }

                for tag_type, slugs in tag_slugs_by_type.items():
                    normalized = [_normalize_slug(v) for v in slugs]
                    replaced = [dst if v == src else v for v in normalized if v]
                    tag_slugs_by_type[tag_type] = _dedupe_preserve_order(replaced)

                tag_metadata = dict(recipe_tags.tag_metadata or {})
                if src in tag_metadata:
                    tag_metadata.pop(src, None)
                    tag_metadata[dst] = dst_meta

                aliases = {
                    _normalize_slug(k): _normalize_slug(v)
                    for k, v in (recipe_tags.aliases or {}).items()
                    if _normalize_slug(k) and _normalize_slug(v)
                }
                aliases[src] = dst
                for k, v in list(aliases.items()):
                    if v == src:
                        aliases[k] = dst

                updated_tags_by_id[recipe_id] = recipe_tags.model_copy(
                    update={
                        "tag_slugs_by_type": tag_slugs_by_type,
                        "tag_metadata": tag_metadata,
                        "aliases": aliases,
                    }
                )

            tag_aliases[src] = dst
            for alias_key, canonical in list(tag_aliases.items()):
                if canonical == src:
                    tag_aliases[alias_key] = dst

            dst_aliases = [_normalize_slug(a) for a in dst_meta.aliases]
            src_aliases = [_normalize_slug(a) for a in src_meta.aliases]
            combined_aliases = _dedupe_preserve_order(
                [a for a in dst_aliases + src_aliases + [src] if a and a != dst]
            )
            tag_registry[dst] = dst_meta.model_copy(update={"aliases": combined_aliases})
            tag_registry.pop(src, None)

            if recipes_path.exists():
                from src.data_layer.recipe_db import RecipeDB

                recipe_db = RecipeDB(str(recipes_path), tag_repo_path=path)
                for recipe in recipe_db.get_all_recipes():
                    seen: set[tuple[str, str]] = set()
                    updated_tags: list[dict[str, str]] = []
                    for tag in recipe.tags:
                        if not isinstance(tag, dict):
                            continue
                        slug = str(tag.get("slug", ""))
                        tag_type = str(tag.get("type", ""))
                        if not slug or not tag_type:
                            continue
                        canonical_slug = dst if slug == src else slug
                        key = (canonical_slug, tag_type)
                        if key in seen:
                            continue
                        seen.add(key)
                        updated_tags.append({"slug": canonical_slug, "type": tag_type})
                    recipe.tags = updated_tags
                # Bulk write of all recipes.
                recipe_db.save()

            _write_tags_payload(
                path=path,
                tags_by_id=updated_tags_by_id,
                tag_registry=tag_registry,
                tag_aliases=tag_aliases,
            )
        except Exception:
            if original_recipes_bytes is None:
                if recipes_path.exists():
                    recipes_path.unlink()
            else:
                _write_bytes_atomic(recipes_path, original_recipes_bytes)
            if original_tags_bytes is None:
                if tags_path.exists():
                    tags_path.unlink()
            else:
                _write_bytes_atomic(tags_path, original_tags_bytes)
            raise

