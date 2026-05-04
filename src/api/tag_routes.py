from __future__ import annotations

import sys
from collections import Counter
from typing import Callable, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.error_mapping import map_exception_to_api_error
from src.data_layer.recipe_db import RecipeDB
from src.llm.schemas import TagMeta, TagType
from src.llm.tag_repository import (
    TagRegistry,
    load_recipe_tag_slugs,
)

router = APIRouter()

_tag_path_getter: Callable[[], str] = lambda: "data/recipes/recipe_tags.json"
_recipes_path_getter: Callable[[], str] = lambda: "data/recipes/recipes.json"


def configure_tag_routes(
    *,
    tag_path_getter: Callable[[], str],
    recipes_path_getter: Callable[[], str],
) -> None:
    global _tag_path_getter, _recipes_path_getter
    _tag_path_getter = tag_path_getter
    _recipes_path_getter = recipes_path_getter


class TagCreateRequest(BaseModel):
    display: str
    type: TagType
    slug: Optional[str] = None


class TagRenameRequest(BaseModel):
    display: str


class TagAliasRequest(BaseModel):
    alias_slug: str


class TagResponse(BaseModel):
    slug: str
    display: str
    type: TagType
    source: str
    created_at: str
    aliases: List[str]
    eligibility: str
    recipe_count: int = 0


def _registry() -> TagRegistry:
    return TagRegistry(_tag_path_getter())


def _tag_response(tag: TagMeta, *, recipe_count: int = 0) -> TagResponse:
    return TagResponse(
        slug=tag.slug,
        display=tag.display,
        type=tag.type,
        source=tag.source,
        created_at=tag.created_at,
        aliases=list(tag.aliases),
        eligibility=tag.eligibility,
        recipe_count=recipe_count,
    )


def _recipe_counts_by_slug() -> Counter[str]:
    try:
        recipe_ids = {
            recipe.id for recipe in RecipeDB(_recipes_path_getter()).get_all_recipes()
        }
    except FileNotFoundError:
        recipe_ids = set()

    slugs_by_id = load_recipe_tag_slugs(_tag_path_getter())
    counts: Counter[str] = Counter()
    for recipe_id, slugs in slugs_by_id.items():
        if recipe_id not in recipe_ids:
            continue
        counts.update(set(slugs))
    return counts


def _log_mutation(action: str, slug: str) -> None:
    print(f"tag_mutation action={action} slug={slug}", file=sys.stderr)


@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    type: Optional[TagType] = Query(default=None),
) -> List[TagResponse] | JSONResponse:
    try:
        counts = _recipe_counts_by_slug()
        return [
            _tag_response(tag, recipe_count=counts.get(tag.slug, 0))
            for tag in _registry().list_by_type(type)
        ]
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("/tags", response_model=TagResponse)
def create_tag(body: TagCreateRequest) -> TagResponse | JSONResponse:
    try:
        tag = _registry().create(
            display=body.display,
            type=body.type,
            slug=body.slug,
            source="user",
        )
        _log_mutation("create", tag.slug)
        return _tag_response(tag)
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.patch("/tags/{slug}", response_model=TagResponse)
def rename_tag(slug: str, body: TagRenameRequest) -> TagResponse | JSONResponse:
    try:
        tag = _registry().rename_display(slug, body.display)
        _log_mutation("rename", tag.slug)
        return _tag_response(tag)
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("/tags/{slug}/alias", response_model=TagResponse)
def add_tag_alias(slug: str, body: TagAliasRequest) -> TagResponse | JSONResponse:
    try:
        tag = _registry().add_alias(slug, body.alias_slug)
        _log_mutation("alias", tag.slug)
        return _tag_response(tag)
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.post("/tags/{src_slug}/merge_into/{dst_slug}", response_model=None)
def merge_tag(src_slug: str, dst_slug: str):
    try:
        _registry().merge(src_slug, dst_slug)
        _log_mutation("merge", src_slug)
        return {"merged": src_slug, "into": dst_slug}
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)
