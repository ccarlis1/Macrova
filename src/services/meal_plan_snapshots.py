"""In-memory snapshots of meal plans + stores for async optimize-cart (MVP)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple


@dataclass(frozen=True)
class MealPlanSnapshot:
    """Minimal data needed to build a GroceryOptimizeRequest."""

    meal_plan: Dict[str, Any]
    stores: List[Dict[str, Any]]


class MealPlanSnapshotStore:
    """Thread-safe registry with TTL for unused snapshots (demo-safe memory bound)."""

    def __init__(self, ttl_sec: float = 30 * 60) -> None:
        self._ttl_sec = ttl_sec
        self._lock = threading.RLock()
        self._by_id: Dict[str, Tuple[float, MealPlanSnapshot]] = {}

    def put(
        self,
        meal_plan_id: str,
        *,
        meal_plan: Mapping[str, Any],
        stores: List[Mapping[str, Any]],
    ) -> None:
        key = meal_plan_id.strip()
        if not key:
            return
        snap = MealPlanSnapshot(
            meal_plan=dict(meal_plan),
            stores=[dict(s) for s in stores],
        )
        with self._lock:
            self._purge_unlocked()
            self._by_id[key] = (time.monotonic(), snap)

    def get(self, meal_plan_id: str) -> Optional[MealPlanSnapshot]:
        key = meal_plan_id.strip()
        with self._lock:
            self._purge_unlocked()
            row = self._by_id.get(key)
            if row is None:
                return None
            _ts, snap = row
            return snap

    def _purge_unlocked(self) -> None:
        now = time.monotonic()
        dead: List[str] = []
        for mid, (ts, _snap) in self._by_id.items():
            if now - ts > self._ttl_sec:
                dead.append(mid)
        for mid in dead:
            self._by_id.pop(mid, None)
