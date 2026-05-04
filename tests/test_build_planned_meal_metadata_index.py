"""Unit tests for build_planned_meal_metadata_index."""

from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch
from src.data_layer.models import ProfilePin
from src.planning.orchestrator import build_planned_meal_metadata_index


def test_build_index_batch_and_pin_distinct_slots():
    batches = [
        MealPrepBatch(
            id="b1",
            recipe_id="r-batch",
            total_servings=4,
            cook_date="2020-01-01",
            assignments=[BatchAssignment(day_index=0, slot_index=0, servings=1.5)],
            status="planned",
        )
    ]
    pins = [ProfilePin(day_index=0, slot_index=1, recipe_id="r-pin")]
    idx = build_planned_meal_metadata_index(batches, pins)
    assert idx[(0, 0)]["kind"] == "batch"
    assert idx[(0, 0)]["recipe_id"] == "r-batch"
    assert idx[(0, 0)]["batch_id"] == "b1"
    assert idx[(0, 0)]["servings"] == 1.5
    assert idx[(0, 1)]["kind"] == "pin"
    assert idx[(0, 1)]["recipe_id"] == "r-pin"


def test_build_index_batch_wins_over_pin_same_slot():
    batches = [
        MealPrepBatch(
            id="b1",
            recipe_id="r-batch",
            total_servings=4,
            cook_date="2020-01-01",
            assignments=[BatchAssignment(day_index=0, slot_index=0, servings=2.0)],
            status="planned",
        )
    ]
    pins = [ProfilePin(day_index=0, slot_index=0, recipe_id="r-pin")]
    idx = build_planned_meal_metadata_index(batches, pins)
    assert len(idx) == 1
    assert idx[(0, 0)]["kind"] == "batch"
    assert idx[(0, 0)]["recipe_id"] == "r-batch"


def test_build_index_empty_inputs():
    assert build_planned_meal_metadata_index([], []) == {}
