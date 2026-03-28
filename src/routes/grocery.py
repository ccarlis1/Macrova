"""Grocery optimizer HTTP routes (Phase 0: FastAPI → Node CLI)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.models.grocery import (
    GroceryOptimizeError,
    GroceryOptimizeRequest,
    GroceryOptimizeResponse,
)
from src.services.grocery_optimizer import run_grocery_optimizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["grocery"])

# TODO: If runs routinely exceed HTTP timeout, introduce an async job + poll while
#  keeping the same JSON contract.


@router.post(
    "/api/grocery/optimize",
    response_model=GroceryOptimizeResponse,
    response_model_by_alias=True,
)
@router.post(
    "/api/v1/grocery/optimize",
    response_model=GroceryOptimizeResponse,
    response_model_by_alias=True,
)
def grocery_optimize(body: GroceryOptimizeRequest) -> GroceryOptimizeResponse:
    """Validate request, run Node stdin/stdout optimizer, return structured response."""

    mp = body.meal_plan
    logger.info(
        "grocery optimize request: meal_plan_id=%s recipe_count=%s store_count=%s",
        mp.id,
        len(mp.recipes),
        len(body.stores),
    )

    payload = body.model_dump(mode="json", by_alias=True)
    raw = run_grocery_optimizer(payload)

    try:
        return GroceryOptimizeResponse.model_validate(raw)
    except Exception:
        logger.exception("grocery optimize: invalid response shape from runner")
        return GroceryOptimizeResponse(
            schema_version="1.0",
            ok=False,
            result=None,
            error=GroceryOptimizeError(
                message="Invalid response shape from grocery optimizer",
            ),
        )
