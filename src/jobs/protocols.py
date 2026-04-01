"""Abstraction boundaries for job persistence and dispatch.

Swap implementations without changing HTTP models or route signatures:

- **Job store (Option A: in-memory, Option B: Redis hash / Postgres):** ``JobStore``
  holds authoritative job records for GET ``optimize-cart/{jobId}``.

- **Job queue (Option A: ``asyncio.Queue``, Option B: BullMQ / Redis list):** ``JobQueue``
  is the handoff from API (enqueue after persist) to worker(s) (dequeue). A remote
  worker process still consumes the same logical ``dequeue`` / ``ack`` contract;
  admission checks remain based on ``JobStore`` (e.g. per-user active counts).

- **Push channel (polling today, WebSocket/SSE later):** ``JobEventPublisher`` is
  optional. Call ``notify_job_updated`` after a successful write that affects
  observable job state so a hub can push the same payload shape as the GET
  response, without changing REST contracts.

Concrete types in this package should satisfy these protocols structurally
(``InMemoryJobStore``, ``InMemoryJobQueue``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterator, List, Optional, Protocol, runtime_checkable

from src.models.optimization_job import OptimizationJobRecord


class QueueAdmission(str, Enum):
    OK = "ok"
    QUEUE_FULL = "queue_full"
    USER_LIMIT = "user_limit"


@runtime_checkable
class JobStore(Protocol):
    """Authoritative job record storage (in-memory, Redis, etc.)."""

    def create_job(self, job: OptimizationJobRecord) -> None: ...

    def get_job(self, job_id: str) -> Optional[OptimizationJobRecord]: ...

    def update_job(self, job_id: str, **kwargs: Any) -> None: ...

    def list_stuck_jobs(self, running_before_monotonic: float) -> List[str]: ...

    def purge_expired(self) -> int: ...

    def count_active_for_user(self, user_id: str) -> int: ...

    def iter_queued_ids(self) -> Iterator[str]: ...


@runtime_checkable
class JobQueue(Protocol):
    """FIFO dispatch of job ids from API to worker(s)."""

    def check_admit(self, store: JobStore, *, user_id: Optional[str]) -> QueueAdmission: ...

    async def enqueue(self, job_id: str) -> None: ...

    async def dequeue(self) -> str: ...


class JobEventPublisher(Protocol):
    """Notify subscribers when job state changes (SSE/WebSocket, Redis pub/sub, etc.)."""

    def notify_job_updated(self, job_id: str) -> None:
        """Invoked after mutations that affect GET ``optimize-cart/{jobId}``."""
        ...


class NoOpJobEventPublisher:
    """Default publisher; replace in composition root when adding real-time delivery."""

    __slots__ = ()

    def notify_job_updated(self, job_id: str) -> None:  # noqa: ARG002
        return None
