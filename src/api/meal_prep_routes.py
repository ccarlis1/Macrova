from __future__ import annotations

from datetime import date as dt_date, timedelta
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

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
    date: str
    slot_id: int = Field(..., ge=0)

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value: str) -> str:
        try:
            dt_date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date must be ISO format YYYY-MM-DD") from exc
        return value


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


def _assignment_to_slot(assignment_date: str, cook_date: str, slot_id: int) -> BatchAssignment:
    base = dt_date.fromisoformat(cook_date)
    target = dt_date.fromisoformat(assignment_date)
    day_index = (target - base).days + 1
    return BatchAssignment(day_index=day_index, slot_index=int(slot_id), servings=1.0)


def _assignment_to_api(batch: MealPrepBatch, item: BatchAssignment) -> Dict[str, Any]:
    base = dt_date.fromisoformat(batch.cook_date)
    assignment_date = (base + timedelta(days=int(item.day_index) - 1)).isoformat()
    return {
        "date": assignment_date,
        "slot_id": int(item.slot_index),
    }


def _batch_to_api(batch: MealPrepBatch) -> Dict[str, Any]:
    return {
        "id": batch.id,
        "recipe_id": batch.recipe_id,
        "total_servings": int(batch.total_servings),
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


def _validate_assignments(body: CreateMealPrepBatchRequest) -> None:
    if body.total_servings < 2:
        raise ApiContractError(BATCH_INVALID, "total_servings must be >= 2")
    if len(body.assignments) > body.total_servings:
        raise ApiContractError(
            BATCH_INVALID, "assignments count cannot exceed total_servings"
        )

    seen: set[Tuple[str, int]] = set()
    for item in body.assignments:
        slot = (item.date, int(item.slot_id))
        if slot in seen:
            raise ApiContractError(BATCH_INVALID, "duplicate (date, slot_id) in assignments")
        seen.add(slot)


def _validate_conflicts(body: CreateMealPrepBatchRequest, repo: MealPrepBatchRepository) -> None:
    requested_slots: set[Tuple[str, int]] = {
        (item.date, int(item.slot_id)) for item in body.assignments
    }
    for batch in repo.list_active():
        for existing in batch.assignments:
            existing_slot = (
                _assignment_to_api(batch, existing)["date"],
                int(existing.slot_index),
            )
            if existing_slot in requested_slots:
                raise ApiContractError(
                    BATCH_CONFLICT,
                    f"Slot conflict at date={existing_slot[0]!r}, slot_id={existing_slot[1]}",
                )


@router.post("")
def create_meal_prep_batch(body: CreateMealPrepBatchRequest) -> Any:
    try:
        _validate_recipe(body.recipe_id)
        _validate_assignments(body)
        repo = MealPrepBatchRepository()
        _validate_conflicts(body, repo)

        assignments = [
            _assignment_to_slot(item.date, body.cook_date, item.slot_id)
            for item in body.assignments
        ]
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
