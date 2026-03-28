from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.llm.schemas import RecipeDraft


DEFAULT_FEEDBACK_CACHE_PATH = "data/llm/feedback_cache.json"
DEFAULT_CACHE_SCHEMA_VERSION = 1


class FeedbackCacheError(RuntimeError):
    """Deterministic feedback cache error."""


class DeterministicCacheMissError(RuntimeError):
    """Raised when strict deterministic mode is enabled and cache misses."""


def _stable_json_dumps(obj: Any) -> str:
    """Deterministic JSON serialization (stable key order + no whitespace)."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def build_feedback_cache_key(
    *,
    failure_signature: str,
    feedback_context: Dict[str, Any],
    recipes_to_generate: int,
    model_version: str,
    cache_schema_version: int = DEFAULT_CACHE_SCHEMA_VERSION,
) -> str:
    payload = {
        "cache_schema_version": int(cache_schema_version),
        "failure_signature": str(failure_signature),
        "feedback_context": feedback_context,
        "recipes_to_generate": int(recipes_to_generate),
        "model_version": str(model_version),
    }
    s = _stable_json_dumps(payload)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FeedbackCache:
    path: str
    cache_schema_version: int = DEFAULT_CACHE_SCHEMA_VERSION
    entries_by_key: Dict[str, List[Dict[str, Any]]] | None = None

    def entries(self) -> Dict[str, List[Dict[str, Any]]]:
        if self.entries_by_key is None:
            return {}
        return self.entries_by_key


def load_feedback_cache(
    path: str = DEFAULT_FEEDBACK_CACHE_PATH,
    *,
    cache_schema_version: int = DEFAULT_CACHE_SCHEMA_VERSION,
) -> FeedbackCache:
    """Load cache from disk; if schema mismatches, treat as empty."""
    if not os.path.exists(path):
        return FeedbackCache(path=path, cache_schema_version=cache_schema_version, entries_by_key={})

    try:
        raw = json.loads(open(path, "r", encoding="utf-8").read())
    except Exception as e:
        raise FeedbackCacheError(f"Failed to read feedback cache: {e}") from e

    loaded_version = int(raw.get("cache_schema_version", -1))
    if loaded_version != int(cache_schema_version):
        return FeedbackCache(
            path=path,
            cache_schema_version=cache_schema_version,
            entries_by_key={},
        )

    entries = raw.get("entries_by_key") or {}
    if not isinstance(entries, dict):
        entries = {}

    # Ensure values are lists of JSON dicts.
    safe_entries: Dict[str, List[Dict[str, Any]]] = {}
    for k, v in entries.items():
        if not isinstance(k, str):
            continue
        if not isinstance(v, list):
            continue
        safe_list: List[Dict[str, Any]] = []
        for item in v:
            if isinstance(item, dict):
                safe_list.append(item)
        safe_entries[k] = safe_list

    return FeedbackCache(
        path=path,
        cache_schema_version=cache_schema_version,
        entries_by_key=safe_entries,
    )


def get_cached_drafts(
    cache: FeedbackCache,
    cache_key: str,
) -> Optional[List[RecipeDraft]]:
    payload = cache.entries().get(cache_key)
    if not payload:
        return None

    # Re-validate cached content defensively (also protects against partial writes).
    drafts: List[RecipeDraft] = []
    for d in payload:
        drafts.append(RecipeDraft.model_validate(d))
    return drafts


def upsert_cached_drafts(
    *,
    cache_path: str,
    cache_schema_version: int,
    cache_key: str,
    drafts: List[RecipeDraft],
) -> None:
    """Upsert a cache entry with atomic write."""
    cache = load_feedback_cache(
        cache_path,
        cache_schema_version=cache_schema_version,
    )

    # Canonicalize to plain JSON objects.
    canonical_payload: List[Dict[str, Any]] = [
        d.model_dump() for d in drafts
    ]

    entries = dict(cache.entries())
    entries[cache_key] = canonical_payload

    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)

    tmp_dir = os.path.dirname(cache_path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".feedback_cache_", dir=tmp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "cache_schema_version": int(cache_schema_version),
                        "entries_by_key": entries,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
            )
        os.replace(tmp_path, cache_path)
    finally:
        # If replace failed, clean up tmp file.
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

