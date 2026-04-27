"""Meal prep batch entities and JSON-backed repository."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from uuid import uuid4


SlotAddress = Tuple[int, int]


@dataclass
class BatchAssignment:
    day_index: int
    slot_index: int
    servings: float = 1.0

    @property
    def slot_address(self) -> SlotAddress:
        return (self.day_index, self.slot_index)


@dataclass
class MealPrepBatch:
    id: str
    recipe_id: str
    total_servings: int
    cook_date: str
    assignments: List[BatchAssignment]
    status: Literal["planned", "active", "consumed", "orphaned"]

    @property
    def servings_remaining(self) -> float:
        return self.total_servings - sum(a.servings for a in self.assignments)

    def assignments_for_day(self, day_index: int) -> List[BatchAssignment]:
        return [a for a in self.assignments if a.day_index == day_index]


class MealPrepBatchRepository:
    """JSON-backed repository for meal prep batches."""

    def __init__(self, json_path: str = "data/meal_prep/batches.json"):
        self.json_path = Path(json_path)
        self._batches: List[MealPrepBatch] = []
        self._ensure_storage_parent_exists()
        self._load()

    def _ensure_storage_parent_exists(self) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_storage_file_exists(self) -> None:
        self._ensure_storage_parent_exists()
        if not self.json_path.exists():
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump({"batches": []}, f, indent=2)

    def _load(self) -> None:
        if not self.json_path.exists():
            self._batches = []
            return
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._batches = [self._parse_batch(raw) for raw in data.get("batches", [])]

    def _save(self) -> None:
        self._ensure_storage_file_exists()
        payload = {"batches": [self._batch_to_dict(b) for b in self._batches]}
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _parse_batch(self, raw: Dict[str, object]) -> MealPrepBatch:
        assignments_raw = raw.get("assignments", [])
        assignments = [
            BatchAssignment(
                day_index=int(item["day_index"]),
                slot_index=int(item["slot_index"]),
                servings=float(item.get("servings", 1.0)),
            )
            for item in assignments_raw
        ]
        return MealPrepBatch(
            id=str(raw["id"]),
            recipe_id=str(raw["recipe_id"]),
            total_servings=int(raw["total_servings"]),
            cook_date=str(raw["cook_date"]),
            assignments=assignments,
            status=str(raw["status"]),  # type: ignore[arg-type]
        )

    def _batch_to_dict(self, batch: MealPrepBatch) -> Dict[str, object]:
        # Persist only canonical status to avoid storing stale active transitions.
        persisted_status: Literal["planned", "consumed", "orphaned"]
        if batch.status == "orphaned":
            persisted_status = "orphaned"
        elif batch.status == "consumed":
            persisted_status = "consumed"
        else:
            persisted_status = "planned"
        return {
            "id": batch.id,
            "recipe_id": batch.recipe_id,
            "total_servings": batch.total_servings,
            "cook_date": batch.cook_date,
            "assignments": [
                {
                    "day_index": a.day_index,
                    "slot_index": a.slot_index,
                    "servings": a.servings,
                }
                for a in batch.assignments
            ],
            "status": persisted_status,
        }

    def _effective_status(self, batch: MealPrepBatch) -> Literal["planned", "active", "consumed", "orphaned"]:
        if batch.status == "orphaned":
            return "orphaned"
        if batch.status == "consumed":
            return "consumed"
        if batch.servings_remaining == 0:
            return "consumed"
        if batch.cook_date <= date.today().isoformat():
            return "active"
        return "planned"

    def _with_effective_status(self, batch: MealPrepBatch) -> MealPrepBatch:
        return MealPrepBatch(
            id=batch.id,
            recipe_id=batch.recipe_id,
            total_servings=batch.total_servings,
            cook_date=batch.cook_date,
            assignments=[
                BatchAssignment(
                    day_index=a.day_index,
                    slot_index=a.slot_index,
                    servings=a.servings,
                )
                for a in batch.assignments
            ],
            status=self._effective_status(batch),
        )

    def _validate_create(self, batch: MealPrepBatch) -> None:
        if batch.total_servings < 2:
            raise ValueError("total_servings must be >= 2")
        if len(batch.assignments) > batch.total_servings:
            raise ValueError("assignments count cannot exceed total_servings")
        if any(a.servings <= 0 for a in batch.assignments):
            raise ValueError("all assignment servings must be > 0")

        seen: set[SlotAddress] = set()
        for assignment in batch.assignments:
            slot: SlotAddress = assignment.slot_address
            if slot in seen:
                raise ValueError("duplicate slot address in assignments")
            seen.add(slot)

        if sum(a.servings for a in batch.assignments) > batch.total_servings:
            raise ValueError("sum of assignment servings cannot exceed total_servings")

    def list_active(self) -> List[MealPrepBatch]:
        return [
            self._with_effective_status(batch)
            for batch in self._batches
            if self._effective_status(batch) in {"planned", "active"}
        ]

    def list_all(self) -> List[MealPrepBatch]:
        return [self._with_effective_status(batch) for batch in self._batches]

    def get(self, batch_id: str) -> Optional[MealPrepBatch]:
        for batch in self._batches:
            if batch.id == batch_id:
                return self._with_effective_status(batch)
        return None

    def create(self, batch: MealPrepBatch) -> MealPrepBatch:
        self._validate_create(batch)
        batch_id = batch.id.strip() if batch.id else ""
        if not batch_id:
            batch_id = uuid4().hex
        persisted_status: Literal["planned", "consumed", "orphaned"]
        if batch.status == "orphaned":
            persisted_status = "orphaned"
        elif batch.status == "consumed":
            persisted_status = "consumed"
        else:
            persisted_status = "planned"
        batch = MealPrepBatch(
            id=batch_id,
            recipe_id=batch.recipe_id,
            total_servings=batch.total_servings,
            cook_date=batch.cook_date,
            assignments=[
                BatchAssignment(
                    day_index=a.day_index,
                    slot_index=a.slot_index,
                    servings=a.servings,
                )
                for a in batch.assignments
            ],
            status=persisted_status,
        )
        if any(existing.id == batch.id for existing in self._batches):
            raise ValueError(f"batch id already exists: {batch.id}")
        self._batches.append(batch)
        self._save()
        return self._with_effective_status(batch)

    def delete(self, batch_id: str) -> bool:
        initial_len = len(self._batches)
        self._batches = [b for b in self._batches if b.id != batch_id]
        deleted = len(self._batches) != initial_len
        if deleted:
            self._save()
        return deleted

    def cancel(self, batch_id: str) -> bool:
        for index, batch in enumerate(self._batches):
            if batch.id != batch_id:
                continue
            if len(batch.assignments) == 0:
                self._batches.pop(index)
            else:
                batch.status = "consumed"
            self._save()
            return True
        return False

    def mark_orphaned_for_recipe(self, recipe_id: str) -> int:
        changed = 0
        for batch in self._batches:
            if batch.recipe_id == recipe_id and batch.status != "orphaned":
                batch.status = "orphaned"
                changed += 1
        if changed > 0:
            self._save()
        return changed
