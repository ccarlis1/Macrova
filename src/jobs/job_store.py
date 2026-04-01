"""Thread-safe in-memory job store with post-completion TTL."""

from __future__ import annotations

import threading
import time
from typing import Iterator, List, Optional

from src.models.optimization_job import JobStatus, OptimizationJobRecord


class InMemoryJobStore:
    """Process-local implementation of :class:`src.jobs.protocols.JobStore`."""
    def __init__(self, ttl_after_done_sec: float = 30 * 60) -> None:
        self._ttl = ttl_after_done_sec
        self._lock = threading.RLock()
        self._jobs: dict[str, OptimizationJobRecord] = {}

    def create_job(self, job: OptimizationJobRecord) -> None:
        with self._lock:
            self._purge_expired_unlocked()
            self._jobs[job.id] = job

    def get_job(self, job_id: str) -> Optional[OptimizationJobRecord]:
        with self._lock:
            self._purge_expired_unlocked()
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if self._is_expired(job):
                self._jobs.pop(job_id, None)
                return None
            return job

    def update_job(self, job_id: str, **kwargs) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            self._jobs[job_id] = job.model_copy(update=kwargs)

    def list_stuck_jobs(self, running_before_monotonic: float) -> List[str]:
        """Job ids in ``running`` with ``started_at`` monotonic timestamp older than threshold."""

        with self._lock:
            out: List[str] = []
            for jid, j in self._jobs.items():
                if j.status != JobStatus.RUNNING or j.started_at is None:
                    continue
                if j.started_at < running_before_monotonic:
                    out.append(jid)
            return out

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_expired_unlocked()

    def count_active_for_user(self, user_id: str) -> int:
        with self._lock:
            n = 0
            for j in self._jobs.values():
                if j.user_id != user_id:
                    continue
                if j.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                    n += 1
            return n

    def iter_queued_ids(self) -> Iterator[str]:
        with self._lock:
            for jid, j in self._jobs.items():
                if j.status == JobStatus.QUEUED:
                    yield jid

    def _is_expired(self, job: OptimizationJobRecord) -> bool:
        if job.finished_at is None:
            return False
        return (time.monotonic() - job.finished_at) > self._ttl

    def _purge_expired_unlocked(self) -> int:
        dead = [jid for jid, j in self._jobs.items() if self._is_expired(j)]
        for jid in dead:
            self._jobs.pop(jid, None)
        return len(dead)
