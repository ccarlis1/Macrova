from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.error_mapping import map_exception_to_api_error
from src.llm import tag_repository
from src.llm.tag_repository import TagRepositoryError

DEFAULT_TAG_PATH = "data/recipes/recipe_tags.json"

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreateRequest(BaseModel):
    slug: Optional[str] = None
    display: str = Field(..., min_length=1)
    type: Literal["context", "time", "nutrition", "constraint"]


class TagRenameRequest(BaseModel):
    display: str = Field(..., min_length=1)


class TagAliasRequest(BaseModel):
    alias_slug: str = Field(..., min_length=1)

def _to_payload(meta: Any, recipe_count: int) -> Dict[str, Any]:
    return {
        "slug": meta.slug,
        "display": meta.display,
        "type": meta.tag_type,
        "source": meta.source,
        "created_at": meta.created_at,
        "aliases": list(meta.aliases),
        "recipe_count": recipe_count,
    }


def _compute_recipe_counts() -> Dict[str, int]:
    return tag_repository.compute_recipe_tag_counts(DEFAULT_TAG_PATH)


def _log_mutation(action: str, payload: Dict[str, Any]) -> None:
    print(
        json.dumps({"action": action, **payload}, sort_keys=True, ensure_ascii=True),
        file=sys.stderr,
    )


@router.get("")
def list_tags_endpoint(
    type: Optional[Literal["context", "time", "nutrition", "constraint"]] = Query(  # noqa: A002
        default=None
    ),
) -> Any:
    try:
        tags = tag_repository.list_by_type(DEFAULT_TAG_PATH, type)
        counts = _compute_recipe_counts()
        return {"tags": [_to_payload(meta, counts.get(meta.slug, 0)) for meta in tags]}
    except TagRepositoryError as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("")
def create_tag_endpoint(body: TagCreateRequest) -> Any:
    try:
        meta = tag_repository.create(
            path=DEFAULT_TAG_PATH,
            slug=body.slug,
            display=body.display,
            tag_type=body.type,
            source="user",
        )
        _log_mutation("create_tag", {"slug": meta.slug})
        return {"tag": _to_payload(meta, 0)}
    except TagRepositoryError as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.patch("/{slug}")
def rename_tag_endpoint(slug: str, body: TagRenameRequest) -> Any:
    try:
        meta = tag_repository.rename_display(
            path=DEFAULT_TAG_PATH,
            slug=slug,
            display=body.display,
        )
        counts = _compute_recipe_counts()
        _log_mutation("rename_tag", {"slug": meta.slug})
        return {"tag": _to_payload(meta, counts.get(meta.slug, 0))}
    except TagRepositoryError as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("/{slug}/alias")
def add_alias_endpoint(slug: str, body: TagAliasRequest) -> Any:
    try:
        meta = tag_repository.add_alias(
            path=DEFAULT_TAG_PATH,
            slug=slug,
            alias_slug=body.alias_slug,
        )
        counts = _compute_recipe_counts()
        _log_mutation("add_alias", {"slug": meta.slug, "alias_slug": body.alias_slug})
        return {"tag": _to_payload(meta, counts.get(meta.slug, 0))}
    except TagRepositoryError as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("/{src_slug}/merge_into/{dst_slug}")
def merge_tag_endpoint(src_slug: str, dst_slug: str) -> Any:
    try:
        tag_repository.merge(src_slug, dst_slug, DEFAULT_TAG_PATH)
        merged = tag_repository.resolve(dst_slug, DEFAULT_TAG_PATH)
        counts = _compute_recipe_counts()
        _log_mutation("merge_tag", {"src_slug": src_slug, "dst_slug": dst_slug})
        return {"tag": _to_payload(merged, counts.get(merged.slug, 0))}
    except TagRepositoryError as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)
