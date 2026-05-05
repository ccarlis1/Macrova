from __future__ import annotations

from datetime import date as dt_date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.error_mapping import (
    BATCH_CONFLICT,
    BATCH_INVALID,
    RECIPE_NOT_BATCHABLE,
    RECIPE_NOT_FOUND,
    ApiContractError,
    map_exception_to_api_error,
)
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch, MealPrepBatchRepository
from src.data_layer.recipe_db import RecipeDB

DEFAULT_RECIPES_PATH = "data/recipes/recipes.json"
router = APIRouter(prefix="/meal_prep_batches", tags=["meal_prep_batches"])


class AssignmentInput(BaseModel):
    """Canonical planner coordinates ``(day_index, slot_index)`` or legacy ``(date, slot_id)``.

    Legacy input is normalized at the route boundary; persistence uses only canonical fields.
    """

    model_config = ConfigDict(extra="forbid")

    day_index: Optional[int] = None
    slot_index: Optional[int] = None
    date: Optional[str] = None
    slot_id: Optional[int] = None
    servings: float = Field(default=1.0, gt=0)

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            dt_date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be ISO format YYYY-MM-DD") from exc
        return value

    @model_validator(mode="after")
    def _shape(self) -> AssignmentInput:
        has_canonical = self.day_index is not None and self.slot_index is not None
        has_legacy = self.date is not None and self.slot_id is not None
        if has_canonical and has_legacy:
            raise ValueError(
                "assignment cannot mix canonical (day_index, slot_index) with legacy (date, slot_id)"
            )
        if not has_canonical and not has_legacy:
            raise ValueError(
                "assignment requires either (day_index, slot_index) or (date, slot_id)"
            )
        if has_canonical and (self.date is not None or self.slot_id is not None):
            raise ValueError("canonical assignment must not include date or slot_id")
        if has_legacy and (self.day_index is not None or self.slot_index is not None):
            raise ValueError("legacy assignment must not include day_index or slot_index")
        return self


class CreateMealPrepBatchRequest(BaseModel):
    recipe_id: str = Field(..., min_length=1)
    total_servings: int = Field(..., ge=1)
    cook_date: str
    assignments: List[AssignmentInput] = Field(default_factory=list)

    @field_validator("recipe_id")
    @classmethod
    def _recipe_id_non_empty(cls, value: str) -> str:
        out = value.strip()
        if not out:
            raise ValueError("recipe_id must not be empty")
        return out

    @field_validator("cook_date")
    @classmethod
    def _valid_cook_date(cls, value: str) -> str:
        try:
            dt_date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("cook_date must be ISO format YYYY-MM-DD") from exc
        return value


def _assignment_input_to_batch(
    body: CreateMealPrepBatchRequest, item: AssignmentInput
) -> BatchAssignment:
    if item.day_index is not None and item.slot_index is not None:
        if int(item.day_index) < 0 or int(item.slot_index) < 0:
            raise ApiContractError(
                BATCH_INVALID, "day_index and slot_index must be >= 0"
            )
        return BatchAssignment(
            day_index=int(item.day_index),
            slot_index=int(item.slot_index),
            servings=float(item.servings),
        )
    assert item.date is not None and item.slot_id is not None
    if int(item.slot_id) < 0:
        raise ApiContractError(BATCH_INVALID, "slot_id must be >= 0")
    base = dt_date.fromisoformat(body.cook_date)
    target = dt_date.fromisoformat(item.date)
    delta = (target - base).days
    if delta < 0:
        raise ApiContractError(
            BATCH_INVALID, "assignment date must be on or after cook_date"
        )
    return BatchAssignment(
        day_index=delta,
        slot_index=int(item.slot_id),
        servings=float(item.servings),
    )


def _assignment_to_api(batch: MealPrepBatch, item: BatchAssignment) -> Dict[str, Any]:
    base = dt_date.fromisoformat(batch.cook_date)
    assignment_date = (base + timedelta(days=int(item.day_index))).isoformat()
    return {
        "day_index": int(item.day_index),
        "slot_index": int(item.slot_index),
        "servings": float(item.servings),
        "date": assignment_date,
        "slot_id": int(item.slot_index),
    }


def _batch_to_api(batch: MealPrepBatch) -> Dict[str, Any]:
    assigned_servings = float(sum(item.servings for item in batch.assignments))
    remaining_servings = float(batch.servings_remaining)
    return {
        "id": batch.id,
        "recipe_id": batch.recipe_id,
        "total_servings": int(batch.total_servings),
        "assigned_servings": assigned_servings,
        "remaining_servings": remaining_servings,
        "cook_date": batch.cook_date,
        "status": batch.status,
        "assignments": [_assignment_to_api(batch, item) for item in batch.assignments],
    }


def _validate_recipe(recipe_id: str) -> None:
    recipe_db = RecipeDB(DEFAULT_RECIPES_PATH)
    recipe = recipe_db.get_recipe_by_id(recipe_id)
    if recipe is None:
        raise ApiContractError(RECIPE_NOT_FOUND, f"No recipe with id {recipe_id!r}")
    if not recipe.is_meal_prep_capable:
        raise ApiContractError(
            RECIPE_NOT_BATCHABLE,
            f"Recipe {recipe_id!r} is not meal-prep capable.",
        )


def _validate_assignments(
    total_servings: int, normalized: List[BatchAssignment]
) -> None:
    if total_servings < 2:
        raise ApiContractError(BATCH_INVALID, "total_servings must be >= 2")
    if len(normalized) > total_servings:
        raise ApiContractError(
            BATCH_INVALID, "assignments count cannot exceed total_servings"
        )

    seen: set[Tuple[int, int]] = set()
    for item in normalized:
        slot = (int(item.day_index), int(item.slot_index))
        if slot in seen:
            raise ApiContractError(
                BATCH_INVALID, "duplicate (day_index, slot_index) in assignments"
            )
        seen.add(slot)


def _validate_conflicts(
    normalized: List[BatchAssignment], repo: MealPrepBatchRepository
) -> None:
    requested_slots: set[Tuple[int, int]] = {
        (int(a.day_index), int(a.slot_index)) for a in normalized
    }
    for batch in repo.list_active():
        for existing in batch.assignments:
            key = (int(existing.day_index), int(existing.slot_index))
            if key in requested_slots:
                raise ApiContractError(
                    BATCH_CONFLICT,
                    f"Slot conflict at day_index={key[0]}, slot_index={key[1]}",
                )


@router.post("")
def create_meal_prep_batch(body: CreateMealPrepBatchRequest) -> Any:
    try:
        _validate_recipe(body.recipe_id)
        try:
            assignments = [
                _assignment_input_to_batch(body, item) for item in body.assignments
            ]
        except ApiContractError:
            raise
        except ValueError as exc:
            raise ApiContractError(BATCH_INVALID, str(exc)) from exc
        _validate_assignments(body.total_servings, assignments)
        repo = MealPrepBatchRepository()
        _validate_conflicts(assignments, repo)
        try:
            created = repo.create(
                MealPrepBatch(
                    id="",
                    recipe_id=body.recipe_id,
                    total_servings=int(body.total_servings),
                    cook_date=body.cook_date,
                    assignments=assignments,
                    status="planned",
                )
            )
        except ValueError as exc:
            raise ApiContractError(BATCH_INVALID, str(exc)) from exc
        return _batch_to_api(created)
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.get("")
def list_meal_prep_batches(
    active: bool = Query(True),  # noqa: FBT001, FBT002
) -> Any:
    try:
        repo = MealPrepBatchRepository()
        batches = repo.list_active() if active else repo.list_all()
        return {"batches": [_batch_to_api(batch) for batch in batches]}
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.get("/{batch_id}")
def get_meal_prep_batch(batch_id: str) -> Any:
    try:
        repo = MealPrepBatchRepository()
        batch = repo.get(batch_id)
        if batch is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"No meal prep batch with id {batch_id!r}",
                    }
                },
            )
        return _batch_to_api(batch)
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)


@router.delete("/{batch_id}")
def delete_meal_prep_batch(batch_id: str) -> Any:
    try:
        repo = MealPrepBatchRepository()
        cancelled = repo.cancel(batch_id)
        if not cancelled:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"No meal prep batch with id {batch_id!r}",
                    }
                },
            )
        return {"cancelled_id": batch_id}
    except Exception as exc:
        status_code, payload = map_exception_to_api_error(exc)
        return JSONResponse(status_code=status_code, content=payload)
