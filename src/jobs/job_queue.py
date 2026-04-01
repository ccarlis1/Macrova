"""Async FIFO queue of job ids with admission control."""

from __future__ import annotations

import asyncio
from typing import Optional

from src.jobs.protocols import JobStore, QueueAdmission


class InMemoryJobQueue:
    """Process-local implementation of :class:`src.jobs.protocols.JobQueue`."""
    def __init__(
        self,
        *,
        max_queued_depth: int = 100,
        max_active_per_user: int = 3,
    ) -> None:
        self._max_depth = max_queued_depth
        self._max_active_per_user = max_active_per_user
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    def check_admit(
        self,
        store: JobStore,
        *,
        user_id: Optional[str],
    ) -> QueueAdmission:
        if self._queue.qsize() >= self._max_depth:
            return QueueAdmission.QUEUE_FULL
        if user_id and store.count_active_for_user(user_id) >= self._max_active_per_user:
            return QueueAdmission.USER_LIMIT
        return QueueAdmission.OK

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> str:
        return await self._queue.get()
