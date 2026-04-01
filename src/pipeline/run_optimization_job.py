"""Run grocery optimization as an async job with staged progress, timeout, retries, partial results."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.models.grocery import GroceryOptimizeResponse
from src.models.optimization_job import JobStats, JobStatus, SerializedError
from src.jobs.protocols import JobStore
from src.services.grocery_meal_plan import merge_grocery_optimize_request
from src.services.grocery_optimizer import run_grocery_optimizer
from src.services.meal_plan_snapshots import MealPlanSnapshot

logger = logging.getLogger(__name__)

_DEFAULT_JOB_TIMEOUT_SEC = 300.0
_MAX_ATTEMPTS = 3
_MIN_COVERAGE_RATIO = 0.7
_SUBPROCESS_TIMEOUT_CAP_SEC = 120
_MIN_ATTEMPT_SEC = 90.0


def _coverage_ratio(result: Dict[str, Any]) -> float:
    mso = result.get("multiStoreOptimization") or {}
    per = mso.get("perIngredient")
    if isinstance(per, list) and len(per) > 0:
        satisfied = sum(1 for p in per if isinstance(p, dict) and not p.get("partial"))
        return float(satisfied) / float(len(per))
    metrics = result.get("metrics") or {}
    rate = metrics.get("coverageRate")
    if isinstance(rate, (int, float)):
        return float(rate)
    return 0.0


def _stats_from_result(result: Dict[str, Any]) -> JobStats:
    metrics = result.get("metrics") or {}
    trace = result.get("pipelineTrace")
    search_ms = 0
    if isinstance(trace, list):
        for span in trace:
            if not isinstance(span, dict):
                continue
            if span.get("stage") == "search":
                start = span.get("startedAtMs")
                end = span.get("endedAtMs")
                if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    search_ms = int(max(0.0, float(end) - float(start)))
    mso = result.get("multiStoreOptimization") or {}
    errs = mso.get("errors")
    failed_q = len(errs) if isinstance(errs, list) else 0
    cache_hits = int(metrics.get("searchCacheHits") or 0) + int(metrics.get("parseCacheHits") or 0)
    return JobStats(
        runId=str(result.get("runId") or ""),
        totalLatency=int(metrics.get("optimizationLatencyMs") or 0),
        searchLatency=search_ms,
        failedQueries=failed_q,
        cacheHits=cache_hits,
    )


def _retryable_runner_error(raw: Dict[str, Any]) -> bool:
    if raw.get("ok") is True:
        return False
    err = raw.get("error") if isinstance(raw.get("error"), dict) else {}
    msg = str(err.get("message") or "").lower()
    code = str(err.get("code") or "").upper()
    if code in {"INTERNAL_ERROR", "NO_STORES", "INVALID_REQUEST"}:
        return False
    if "timed out" in msg or "timeout" in msg:
        return True
    if any(s in msg for s in ("econnreset", "econnrefused", "socket", "network", "503", "502", "429")):
        return True
    return False


def _serialize_timeout_error() -> SerializedError:
    return SerializedError(
        message="Optimization exceeded job time budget",
        code="JOB_TIMEOUT",
        retryable=True,
    )


def evaluate_optimizer_response(raw: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[SerializedError]]:
    """
    Returns (completed_ok, result_dict, error).

    Applies partial-result policy: completed when coverage >= 70% and envelope ok with a result dict.
    """

    try:
        resp = GroceryOptimizeResponse.model_validate(raw)
    except Exception as exc:
        return False, None, SerializedError(
            message=f"Invalid optimizer response: {exc}",
            code="INVALID_RESPONSE",
            retryable=False,
        )

    if resp.ok and resp.result is not None:
        ratio = _coverage_ratio(resp.result)
        if ratio >= _MIN_COVERAGE_RATIO:
            result = dict(resp.result)
            if ratio < 1.0:
                warns: List[Any] = list(result.get("optimizationWarnings") or [])
                warns.append(
                    {
                        "code": "PARTIAL_COVERAGE",
                        "message": (
                            f"{int(round(ratio * 100))}% of ingredients are fully covered "
                            f"(minimum {_MIN_COVERAGE_RATIO:.0%} met)."
                        ),
                    }
                )
                result["optimizationWarnings"] = warns
            return True, result, None
        return False, None, SerializedError(
            message=(
                f"Insufficient ingredient coverage ({ratio:.0%}); "
                f"need at least {_MIN_COVERAGE_RATIO:.0%} for a viable cart."
            ),
            code="INSUFFICIENT_COVERAGE",
            retryable=False,
            details={"coverageRatio": ratio},
        )

    if resp.error is not None:
        ge = resp.error
        retryable = _retryable_runner_error(raw)
        return False, None, SerializedError(
            message=ge.message,
            code=ge.code,
            retryable=retryable,
        )

    return False, None, SerializedError(
        message="Optimization failed",
        code="UNKNOWN",
        retryable=False,
    )


def _merge_preferences(mode: str, max_stores: int) -> Dict[str, Any]:
    return {
        "objective": mode,
        "maxStores": max_stores,
    }


def _trim_stores(stores: List[Dict[str, Any]], max_stores: int) -> List[Dict[str, Any]]:
    if max_stores < 1:
        return stores
    return stores[:max_stores]


async def run_optimization_job(
    *,
    job_id: str,
    snapshot: MealPlanSnapshot,
    preferences_mode: str,
    max_stores: int,
    job_store: JobStore,
    job_timeout_sec: float = _DEFAULT_JOB_TIMEOUT_SEC,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Execute optimizer with staged updates; marks job completed or failed on ``job_store``."""

    def bump(progress: int, stage: str) -> None:
        # Ensure progress never regresses to keep UX monotonic across retries.
        current = job_store.get_job(job_id)
        prev = current.progress if current is not None else 0
        effective = max(prev, progress)
        job_store.update_job(job_id, progress=effective, stage=stage)
        if on_progress:
            on_progress(effective, stage)

    deadline = time.monotonic() + job_timeout_sec

    def remaining_budget() -> float:
        return max(0.1, deadline - time.monotonic())

    bump(5, "aggregating ingredients")
    await asyncio.sleep(0)

    prefs_overlay = _merge_preferences(preferences_mode, max_stores)
    stores = _trim_stores(snapshot.stores, max_stores)
    if not stores:
        job_store.update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=100,
            stage="failed",
            finished_at=time.monotonic(),
            error=SerializedError(
                message="No stores available for optimization",
                code="NO_STORES",
                retryable=False,
            ),
        )
        return

    payload = merge_grocery_optimize_request(
        snapshot.meal_plan,
        stores=stores,
        preferences=prefs_overlay,
        run_id=job_id,
    )

    bump(12, "normalizing ingredients")
    await asyncio.sleep(0)
    bump(18, "preparing product search")
    await asyncio.sleep(0)

    best_result: Optional[Dict[str, Any]] = None
    best_stats: Optional[JobStats] = None
    best_coverage: float = 0.0
    consecutive_timeouts = 0

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        if time.monotonic() >= deadline:
            break

        budget = remaining_budget()
        if budget < _MIN_ATTEMPT_SEC:
            logger.warning(
                "optimize job %s stopping retries: insufficient remaining budget (%.2fs) before attempt %s/%s",
                job_id,
                budget,
                attempt,
                _MAX_ATTEMPTS,
            )
            break

        sub_timeout = int(min(_SUBPROCESS_TIMEOUT_CAP_SEC, budget))
        bump(25, f"searching products (attempt {attempt}/{_MAX_ATTEMPTS})")

        job_store.update_job(job_id, attempts=attempt)

        # Progress heartbeat while Node runs (bounded coarse steps 25–70).
        stop_heartbeat = asyncio.Event()

        async def _heartbeat() -> None:
            p = 28
            while not stop_heartbeat.is_set():
                try:
                    await asyncio.wait_for(stop_heartbeat.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass
                if stop_heartbeat.is_set():
                    break
                p = min(70, p + 3)
                bump(p, f"searching products (attempt {attempt}/{_MAX_ATTEMPTS})")

        hb = asyncio.create_task(_heartbeat())
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(run_grocery_optimizer, payload, timeout_sec=sub_timeout),
                timeout=budget,
            )
        except asyncio.TimeoutError:
            stop_heartbeat.set()
            await hb
            consecutive_timeouts += 1
            logger.warning(
                "optimize job %s subprocess budget timeout on attempt %s/%s (budget=%.2fs, sub_timeout=%ss)",
                job_id,
                attempt,
                _MAX_ATTEMPTS,
                budget,
                sub_timeout,
            )
            if consecutive_timeouts >= 2:
                logger.warning(
                    "optimize job %s stopping after %s consecutive timeouts",
                    job_id,
                    consecutive_timeouts,
                )
                break
            continue
        finally:
            stop_heartbeat.set()
            await hb

        bump(78, "processing optimizer output")
        await asyncio.sleep(0)

        ok, result, err = evaluate_optimizer_response(raw)
        if ok and result is not None:
            stats = _stats_from_result(result)
            coverage = _coverage_ratio(result)
            if coverage > best_coverage:
                best_result = result
                best_stats = stats
                best_coverage = coverage
                job_store.update_job(job_id, result=best_result, stats=best_stats)
            if coverage >= _MIN_COVERAGE_RATIO:
                bump(95, "finalizing results")
                await asyncio.sleep(0)
                job_store.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    progress=100,
                    stage="completed",
                    finished_at=time.monotonic(),
                    result=result,
                    error=None,
                    stats=stats,
                )
                logger.info(
                    "optimize job completed job_id=%s run_id=%s total_latency_ms=%s search_latency_ms=%s "
                    "failed_queries=%s cache_hits=%s search_hits=%s search_misses=%s parse_hits=%s",
                    job_id,
                    stats.run_id,
                    stats.total_latency_ms,
                    stats.search_latency_ms,
                    stats.failed_queries,
                    stats.cache_hits,
                    int((result.get("metrics") or {}).get("searchCacheHits") or 0),
                    int((result.get("metrics") or {}).get("searchCacheMisses") or 0),
                    int((result.get("metrics") or {}).get("parseCacheHits") or 0),
                )
                return

        consecutive_timeouts = 0
        should_retry = (
            err is not None
            and err.retryable
            and attempt < _MAX_ATTEMPTS
            and remaining_budget() >= _MIN_ATTEMPT_SEC
        )
        if should_retry:
            delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            delay = min(delay, max(0.5, remaining_budget() - 1))
            bump(22, f"retrying after transient failure ({attempt}/{_MAX_ATTEMPTS})")
            logger.warning(
                "optimize job %s retry %s/%s: %s",
                job_id,
                attempt,
                _MAX_ATTEMPTS,
                err.message if err else "",
            )
            await asyncio.sleep(delay)
            continue

        break

    if best_result is not None:
        warns: List[Any] = list(best_result.get("optimizationWarnings") or [])
        warns.append(
            {
                "code": "JOB_TIMEOUT_PARTIAL",
                "message": "Optimization exceeded job time budget; returning best partial cart.",
            }
        )
        best_result["optimizationWarnings"] = warns
        stats = best_stats or _stats_from_result(best_result)
        bump(95, "finalizing partial results")
        await asyncio.sleep(0)
        job_store.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            stage="completed",
            finished_at=time.monotonic(),
            result=best_result,
            error=_serialize_timeout_error(),
            stats=stats,
        )
        logger.warning(
            "optimize job %s completed with timeout and partial result (coverage=%.3f)",
            job_id,
            best_coverage,
        )
        return

    job_store.update_job(
        job_id,
        status=JobStatus.FAILED,
        progress=100,
        stage="failed",
        finished_at=time.monotonic(),
        error=_serialize_timeout_error(),
    )
