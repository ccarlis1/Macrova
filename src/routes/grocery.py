"""Grocery optimizer HTTP routes (FastAPI → Node CLI).

The request/response shape matches ``packages/grocery-optimizer`` JSON types.
To assemble ``mealPlan`` + ``recipeServings`` on the server, see
``src.services.grocery_meal_plan``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.jobs.job_queue import QueueAdmission
from src.jobs.protocols import JobQueue, JobStore
from src.models.grocery import (
    GroceryOptimizeError,
    GroceryOptimizeRequest,
    GroceryOptimizeResponse,
)
from src.models.optimization_job import (
    JobStatus,
    OptimizeCartAcceptedResponse,
    OptimizeCartJobStatusResponse,
    OptimizeCartRequestBody,
    OptimizationJobRecord,
)
from src.services.grocery_optimizer import run_grocery_optimizer
from src.services.meal_plan_snapshots import MealPlanSnapshotStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["grocery"])


def _register_meal_plan_snapshot(request: Request, body: GroceryOptimizeRequest) -> None:
    state = request.app.state
    if not hasattr(state, "meal_plan_snapshots"):
        return
    mp = body.meal_plan
    if mp.id is None:
        return
    plan_id = str(mp.id).strip()
    if not plan_id:
        return
    snap_store: MealPlanSnapshotStore = state.meal_plan_snapshots
    d = body.model_dump(mode="json", by_alias=True)
    snap_store.put(plan_id, meal_plan=d["mealPlan"], stores=d["stores"])


def _async_job_state(
    request: Request,
) -> tuple[JobStore, JobQueue, MealPlanSnapshotStore]:
    state = request.app.state
    for name in ("job_store", "job_queue", "meal_plan_snapshots"):
        if not hasattr(state, name):
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "JOB_SYSTEM_UNAVAILABLE",
                        "message": "Async job system is not initialized on this process.",
                    }
                },
            )
    return state.job_store, state.job_queue, state.meal_plan_snapshots


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
def grocery_optimize(request: Request, body: GroceryOptimizeRequest) -> GroceryOptimizeResponse:
    """Validate request, run Node stdin/stdout optimizer, return structured response."""

    mp = body.meal_plan
    logger.info(
        "grocery optimize request: meal_plan_id=%s recipe_count=%s store_count=%s",
        mp.id,
        len(mp.recipes),
        len(body.stores),
    )

    _register_meal_plan_snapshot(request, body)

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


def _user_id_from_request(request: Request) -> Optional[str]:
    return request.headers.get("X-User-Id") or request.headers.get("x-user-id")


@router.post("/api/grocery/meal-plan-snapshot")
@router.post("/api/v1/grocery/meal-plan-snapshot")
def grocery_register_meal_plan_snapshot(
    request: Request,
    body: GroceryOptimizeRequest,
) -> Any:
    """Store meal plan + stores for a later async ``optimize-cart`` (no optimizer run)."""

    _async_job_state(request)  # ensure job store / snapshots exist
    mp = body.meal_plan
    plan_id = (str(mp.id).strip() if mp.id is not None else "") or ""
    if not plan_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "MEAL_PLAN_ID_REQUIRED",
                    "message": "mealPlan.id is required to register a snapshot.",
                }
            },
        )
    _register_meal_plan_snapshot(request, body)
    logger.info(
        "meal plan snapshot registered meal_plan_id=%s recipes=%s",
        plan_id,
        len(mp.recipes),
    )
    return {"mealPlanId": plan_id}


@router.post(
    "/api/grocery/optimize-cart",
    status_code=202,
    response_model=OptimizeCartAcceptedResponse,
    response_model_by_alias=True,
)
@router.post(
    "/api/v1/grocery/optimize-cart",
    status_code=202,
    response_model=OptimizeCartAcceptedResponse,
    response_model_by_alias=True,
)
async def grocery_optimize_cart(
    request: Request,
    body: OptimizeCartRequestBody,
) -> Any:
    """Enqueue async optimization; meal plan must exist in the snapshot store (``meal-plan-snapshot`` or ``optimize``)."""

    store, queue, snap_store = _async_job_state(request)

    plan_key = body.meal_plan_id.strip()
    if snap_store.get(plan_key) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MEAL_PLAN_NOT_FOUND",
                    "message": "Unknown or expired mealPlanId.",
                }
            },
        )

    user_id = _user_id_from_request(request)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "X-User-Id header is required to start an optimization job.",
                }
            },
        )
    admission = queue.check_admit(store, user_id=user_id)
    if admission == QueueAdmission.QUEUE_FULL:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "QUEUE_FULL",
                    "message": "Too many optimization jobs queued; try again shortly.",
                }
            },
        )
    if admission == QueueAdmission.USER_LIMIT:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "CONCURRENCY_LIMIT",
                    "message": "Too many active optimization jobs for this user.",
                }
            },
        )

    job_id = str(uuid4())
    now = time.monotonic()
    record = OptimizationJobRecord(
        id=job_id,
        meal_plan_id=plan_key,
        user_id=user_id,
        status=JobStatus.QUEUED,
        progress=0,
        stage="queued",
        created_at=now,
        preferences_mode=body.preferences.mode,
        max_stores=body.preferences.max_stores,
    )
    store.create_job(record)
    await queue.enqueue(job_id)
    logger.info("grocery optimize-cart enqueued job_id=%s meal_plan_id=%s", job_id, plan_key)
    return OptimizeCartAcceptedResponse(job_id=job_id)


@router.get(
    "/api/grocery/optimize-cart/{job_id}",
    response_model=OptimizeCartJobStatusResponse,
    response_model_by_alias=True,
)
@router.get(
    "/api/v1/grocery/optimize-cart/{job_id}",
    response_model=OptimizeCartJobStatusResponse,
    response_model_by_alias=True,
)
def grocery_optimize_cart_status(
    job_id: str,
    request: Request,
) -> OptimizeCartJobStatusResponse:
    store, _queue, _snap = _async_job_state(request)
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Unknown or expired job id."}},
        )

    requester_id = _user_id_from_request(request)
    if job.user_id is not None and requester_id != job.user_id:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "You do not have access to this job."}},
        )

    status_s = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    return OptimizeCartJobStatusResponse(
        status=status_s,  # type: ignore[arg-type]
        progress=job.progress,
        stage=job.stage,
        result=job.result,
        error=job.error,
        stats=job.stats,
    )
