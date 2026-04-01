"""Background worker loop: dequeue optimization jobs and run the pipeline."""

from __future__ import annotations

import asyncio
import logging
import time
import traceback

from fastapi import FastAPI

from src.jobs.protocols import JobQueue, JobStore
from src.models.optimization_job import JobStatus, SerializedError
from src.pipeline.run_optimization_job import run_optimization_job
from src.services.meal_plan_snapshots import MealPlanSnapshotStore

logger = logging.getLogger(__name__)


async def job_worker_loop(app: FastAPI) -> None:
    store: JobStore = app.state.job_store
    queue: JobQueue = app.state.job_queue
    snapshots: MealPlanSnapshotStore = app.state.meal_plan_snapshots

    try:
        while True:
            job_id = await queue.dequeue()
            await _process_one_job(store, snapshots, job_id)
    except asyncio.CancelledError:
        logger.info("job_worker_loop cancelled")
    except Exception:
        logger.exception("job_worker_loop crashed; exiting")
        raise


async def supervised_job_worker_loop(app: FastAPI) -> None:
    """Supervisor that restarts the worker loop after crashes with a short backoff."""

    backoff_sec = 3.0
    while True:
        try:
            await job_worker_loop(app)
            # Normal exit (e.g., application shutdown) — break instead of hot-looping.
            break
        except asyncio.CancelledError:
            logger.info("supervised_job_worker_loop cancelled")
            raise
        except Exception:
            logger.exception("job_worker_loop crashed; restarting in %ss", backoff_sec)
            try:
                await asyncio.sleep(backoff_sec)
            except asyncio.CancelledError:
                logger.info("supervised_job_worker_loop cancelled during backoff")
                raise


async def _process_one_job(
    store: JobStore,
    snapshots: MealPlanSnapshotStore,
    job_id: str,
) -> None:
    job = store.get_job(job_id)
    if job is None:
        return
    if job.status != JobStatus.QUEUED:
        return

    store.update_job(
        job_id,
        status=JobStatus.RUNNING,
        started_at=time.monotonic(),
        progress=max(job.progress, 3),
        stage="starting optimizer",
    )

    snap = snapshots.get(job.meal_plan_id)
    if snap is None:
        store.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=100,
            stage="failed",
            finished_at=time.monotonic(),
            error=SerializedError(
                message="Meal plan snapshot expired or not found",
                code="MEAL_PLAN_GONE",
                retryable=False,
            ),
        )
        return

    try:
        await run_optimization_job(
            job_id=job_id,
            snapshot=snap,
            preferences_mode=job.preferences_mode,
            max_stores=job.max_stores,
            job_store=store,
        )
    except asyncio.CancelledError:
        store.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=100,
            stage="failed",
            finished_at=time.monotonic(),
            error=SerializedError(
                message="Job cancelled",
                code="CANCELLED",
                retryable=True,
            ),
        )
        raise
    except Exception as exc:
        logger.exception("job_worker: unhandled error for job %s", job_id)
        store.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=100,
            stage="failed",
            finished_at=time.monotonic(),
            error=SerializedError(
                message=str(exc) or type(exc).__name__,
                code="WORKER_ERROR",
                retryable=True,
                details={"traceback": traceback.format_exc()},
            ),
        )
