from datetime import date, timedelta

import pytest

from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch, MealPrepBatchRepository


def _batch(
    batch_id: str = "",
    recipe_id: str = "recipe1",
    total_servings: int = 3,
    cook_date: str | None = None,
    assignments: list[BatchAssignment] | None = None,
    status: str = "planned",
) -> MealPrepBatch:
    if cook_date is None:
        cook_date = date.today().isoformat()
    if assignments is None:
        assignments = [BatchAssignment(day_index=0, slot_index=0, servings=1.0)]
    return MealPrepBatch(
        id=batch_id,
        recipe_id=recipe_id,
        total_servings=total_servings,
        cook_date=cook_date,
        assignments=assignments,
        status=status,  # type: ignore[arg-type]
    )


def test_round_trip_persistence(tmp_path):
    db_path = tmp_path / "data" / "meal_prep" / "batches.json"
    repo = MealPrepBatchRepository(str(db_path))
    created = repo.create(_batch(recipe_id="r1", total_servings=4))
    assert created is not None
    assert len(created.id) == 32

    repo2 = MealPrepBatchRepository(str(db_path))
    loaded = repo2.get(created.id)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.recipe_id == "r1"
    assert loaded.total_servings == 4
    assert len(loaded.assignments) == 1


def test_servings_remaining_math():
    batch = _batch(
        total_servings=5,
        assignments=[
            BatchAssignment(day_index=0, slot_index=0, servings=1.0),
            BatchAssignment(day_index=0, slot_index=1, servings=2.0),
        ],
    )
    assert batch.servings_remaining == 2.0


def test_assignments_for_day_filtering():
    batch = _batch(
        assignments=[
            BatchAssignment(day_index=0, slot_index=0, servings=1.0),
            BatchAssignment(day_index=1, slot_index=0, servings=1.0),
            BatchAssignment(day_index=1, slot_index=2, servings=1.0),
        ]
    )
    day1 = batch.assignments_for_day(1)
    assert len(day1) == 2
    assert {(a.day_index, a.slot_index) for a in day1} == {(1, 0), (1, 2)}


def test_multi_day_same_recipe_assignments(tmp_path):
    db_path = tmp_path / "data" / "meal_prep" / "batches.json"
    repo = MealPrepBatchRepository(str(db_path))
    batch = _batch(
        recipe_id="recipe_repeat",
        total_servings=4,
        assignments=[
            BatchAssignment(day_index=0, slot_index=0, servings=1.0),
            BatchAssignment(day_index=1, slot_index=0, servings=1.0),
            BatchAssignment(day_index=2, slot_index=1, servings=1.0),
        ],
    )
    created = repo.create(batch)
    loaded = repo.get(created.id)
    assert loaded is not None
    assert loaded.recipe_id == "recipe_repeat"
    assert {(a.day_index, a.slot_index) for a in loaded.assignments} == {
        (0, 0),
        (1, 0),
        (2, 1),
    }


def test_orphan_transition_keeps_assignments(tmp_path):
    db_path = tmp_path / "data" / "meal_prep" / "batches.json"
    repo = MealPrepBatchRepository(str(db_path))
    original_assignments = [
        BatchAssignment(day_index=0, slot_index=0, servings=1.0),
        BatchAssignment(day_index=1, slot_index=1, servings=1.0),
    ]
    created = repo.create(
        _batch(
            recipe_id="deleted-recipe",
            total_servings=3,
            assignments=original_assignments,
            status="planned",
        )
    )

    changed = repo.mark_orphaned_for_recipe("deleted-recipe")
    assert changed == 1
    updated = repo.get(created.id)
    assert updated is not None
    assert updated.status == "orphaned"
    assert [(a.day_index, a.slot_index, a.servings) for a in updated.assignments] == [
        (0, 0, 1.0),
        (1, 1, 1.0),
    ]


def test_create_validation_rules(tmp_path):
    db_path = tmp_path / "data" / "meal_prep" / "batches.json"
    repo = MealPrepBatchRepository(str(db_path))

    with pytest.raises(ValueError, match="total_servings must be >= 2"):
        repo.create(_batch(total_servings=1))

    with pytest.raises(ValueError, match="assignments count cannot exceed total_servings"):
        repo.create(
            _batch(
                total_servings=2,
                assignments=[
                    BatchAssignment(day_index=0, slot_index=0, servings=1.0),
                    BatchAssignment(day_index=0, slot_index=1, servings=1.0),
                    BatchAssignment(day_index=0, slot_index=2, servings=1.0),
                ],
            )
        )

    with pytest.raises(ValueError, match="duplicate slot address in assignments"):
        repo.create(
            _batch(
                total_servings=3,
                assignments=[
                    BatchAssignment(day_index=0, slot_index=0, servings=1.0),
                    BatchAssignment(day_index=0, slot_index=0, servings=1.0),
                ],
            )
        )

    with pytest.raises(ValueError, match="sum of assignment servings cannot exceed total_servings"):
        repo.create(
            _batch(
                total_servings=2,
                assignments=[
                    BatchAssignment(day_index=0, slot_index=0, servings=1.5),
                    BatchAssignment(day_index=0, slot_index=1, servings=1.0),
                ],
            )
        )

    with pytest.raises(ValueError, match="all assignment servings must be > 0"):
        repo.create(
            _batch(
                total_servings=2,
                assignments=[BatchAssignment(day_index=0, slot_index=0, servings=0.0)],
            )
        )


def test_status_transitions_computed_on_read(tmp_path):
    db_path = tmp_path / "data" / "meal_prep" / "batches.json"
    repo = MealPrepBatchRepository(str(db_path))
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    active = repo.create(_batch(cook_date=yesterday, total_servings=3))
    planned = repo.create(_batch(cook_date=tomorrow, total_servings=3))
    consumed = repo.create(
        _batch(
            cook_date=yesterday,
            total_servings=2,
            assignments=[
                BatchAssignment(day_index=0, slot_index=0, servings=1.0),
                BatchAssignment(day_index=0, slot_index=1, servings=1.0),
            ],
        )
    )

    assert repo.get(active.id).status == "active"
    assert repo.get(planned.id).status == "planned"
    assert repo.get(consumed.id).status == "consumed"

    active_ids = {b.id for b in repo.list_active()}
    assert active.id in active_ids
    assert planned.id in active_ids
    assert consumed.id not in active_ids
