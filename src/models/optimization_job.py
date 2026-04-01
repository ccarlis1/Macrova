"""Job status models for async grocery cart optimization."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SerializedError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    code: Optional[str] = None
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class JobStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    total_latency_ms: int = Field(alias="totalLatency", ge=0)
    search_latency_ms: int = Field(default=0, alias="searchLatency", ge=0)
    failed_queries: int = Field(default=0, alias="failedQueries", ge=0)
    cache_hits: int = Field(default=0, alias="cacheHits", ge=0)


class OptimizeCartJobStatusResponse(BaseModel):
    """GET /api/v1/grocery/optimize-cart/{jobId} body."""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["queued", "running", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    stage: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[SerializedError] = None
    stats: Optional[JobStats] = None


class OptimizeCartAcceptedResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId")


class OptimizeCartPreferences(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["balanced", "min_cost", "min_waste"]
    max_stores: int = Field(alias="maxStores", ge=1, le=50)


class OptimizeCartRequestBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meal_plan_id: str = Field(alias="mealPlanId", min_length=1)
    preferences: OptimizeCartPreferences


class OptimizationJobRecord(BaseModel):
    """Mutable job snapshot persisted in the in-memory store."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    meal_plan_id: str
    user_id: Optional[str] = None
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    attempts: int = Field(default=0, ge=0)
    result: Optional[Dict[str, Any]] = None
    error: Optional[SerializedError] = None
    stats: Optional[JobStats] = None
    preferences_mode: str = "balanced"
    max_stores: int = Field(default=4, ge=1)
