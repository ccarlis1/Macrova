from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch


@dataclass
class _RecipeStub:
    id: str
    is_meal_prep_capable: bool


class _RecipeDBStub:
    def __init__(self, recipe: Optional[_RecipeStub]):
        self._recipe = recipe

    def get_recipe_by_id(self, recipe_id: str):
        if self._recipe is None:
            return None
        if self._recipe.id != recipe_id:
            return None
        return self._recipe


class _MealPrepRepoStub:
    def __init__(self):
        self._active: List[MealPrepBatch] = []
        self._by_id: dict[str, MealPrepBatch] = {}

    def list_active(self):
        return list(self._active)

    def list_all(self):
        return list(self._by_id.values())

    def get(self, batch_id: str):
        return self._by_id.get(batch_id)

    def create(self, batch: MealPrepBatch):
        created = MealPrepBatch(
            id="batch-created-1",
            recipe_id=batch.recipe_id,
            total_servings=batch.total_servings,
            cook_date=batch.cook_date,
            assignments=list(batch.assignments),
            status="planned",
        )
        self._by_id[created.id] = created
        self._active.append(created)
        return created

    def delete(self, batch_id: str):
        if batch_id not in self._by_id:
            return False
        self._by_id.pop(batch_id, None)
        self._active = [b for b in self._active if b.id != batch_id]
        return True

    def cancel(self, batch_id: str):
        if batch_id not in self._by_id:
            return False
        batch = self._by_id[batch_id]
        if len(batch.assignments) == 0:
            self.delete(batch_id)
        else:
            batch.status = "consumed"
            self._active = [b for b in self._active if b.id != batch_id]
        return True


def _client() -> TestClient:
    return TestClient(app)


def test_create_meal_prep_batch_happy_path(monkeypatch):
    repo = _MealPrepRepoStub()
    monkeypatch.setattr("src.api.meal_prep_routes.MealPrepBatchRepository", lambda: repo)
    monkeypatch.setattr(
        "src.api.meal_prep_routes.RecipeDB",
        lambda *_a, **_k: _RecipeDBStub(_RecipeStub(id="r1", is_meal_prep_capable=True)),
    )

    res = _client().post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "r1",
            "total_servings": 3,
            "cook_date": "2026-04-27",
            "assignments": [
                {"date": "2026-04-27", "slot_id": 0},
                {"date": "2026-04-28", "slot_id": 1},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "batch-created-1"
    assert body["recipe_id"] == "r1"
    assert body["status"] == "planned"
    assert body["assignments"] == [
        {"date": "2026-04-27", "slot_id": 0},
        {"date": "2026-04-28", "slot_id": 1},
    ]


def test_create_meal_prep_batch_recipe_missing(monkeypatch):
    monkeypatch.setattr(
        "src.api.meal_prep_routes.RecipeDB",
        lambda *_a, **_k: _RecipeDBStub(None),
    )
    monkeypatch.setattr(
        "src.api.meal_prep_routes.MealPrepBatchRepository", lambda: _MealPrepRepoStub()
    )
    res = _client().post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "missing",
            "total_servings": 2,
            "cook_date": "2026-04-27",
            "assignments": [],
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RECIPE_NOT_FOUND"


def test_create_meal_prep_batch_recipe_not_batchable(monkeypatch):
    monkeypatch.setattr(
        "src.api.meal_prep_routes.RecipeDB",
        lambda *_a, **_k: _RecipeDBStub(
            _RecipeStub(id="r1", is_meal_prep_capable=False)
        ),
    )
    monkeypatch.setattr(
        "src.api.meal_prep_routes.MealPrepBatchRepository", lambda: _MealPrepRepoStub()
    )
    res = _client().post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "r1",
            "total_servings": 2,
            "cook_date": "2026-04-27",
            "assignments": [],
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "RECIPE_NOT_BATCHABLE"


def test_create_meal_prep_batch_invalid_payload(monkeypatch):
    monkeypatch.setattr(
        "src.api.meal_prep_routes.RecipeDB",
        lambda *_a, **_k: _RecipeDBStub(
            _RecipeStub(id="r1", is_meal_prep_capable=True)
        ),
    )
    monkeypatch.setattr(
        "src.api.meal_prep_routes.MealPrepBatchRepository", lambda: _MealPrepRepoStub()
    )
    res = _client().post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "r1",
            "total_servings": 1,
            "cook_date": "2026-04-27",
            "assignments": [],
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BATCH_INVALID"


def test_create_meal_prep_batch_conflict(monkeypatch):
    repo = _MealPrepRepoStub()
    repo._active.append(
        MealPrepBatch(
            id="existing",
            recipe_id="r-existing",
            total_servings=2,
            cook_date="2026-04-27",
            assignments=[BatchAssignment(day_index=1, slot_index=2, servings=1.0)],
            status="planned",
        )
    )
    monkeypatch.setattr("src.api.meal_prep_routes.MealPrepBatchRepository", lambda: repo)
    monkeypatch.setattr(
        "src.api.meal_prep_routes.RecipeDB",
        lambda *_a, **_k: _RecipeDBStub(_RecipeStub(id="r1", is_meal_prep_capable=True)),
    )

    res = _client().post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "r1",
            "total_servings": 2,
            "cook_date": "2026-04-27",
            "assignments": [{"date": "2026-04-27", "slot_id": 2}],
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "BATCH_CONFLICT"


def test_list_get_delete_meal_prep_batches(monkeypatch):
    repo = _MealPrepRepoStub()
    batch = MealPrepBatch(
        id="b1",
        recipe_id="r1",
        total_servings=2,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=1, slot_index=0, servings=1.0)],
        status="planned",
    )
    repo._active.append(batch)
    repo._by_id["b1"] = batch
    monkeypatch.setattr("src.api.meal_prep_routes.MealPrepBatchRepository", lambda: repo)

    c = _client()
    list_res = c.get("/api/v1/meal_prep_batches")
    assert list_res.status_code == 200
    assert list_res.json()["batches"][0]["id"] == "b1"

    get_res = c.get("/api/v1/meal_prep_batches/b1")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == "b1"

    del_res = c.delete("/api/v1/meal_prep_batches/b1")
    assert del_res.status_code == 200
    assert del_res.json() == {"cancelled_id": "b1"}


def test_list_meal_prep_batches_active_false_includes_inactive(monkeypatch):
    repo = _MealPrepRepoStub()
    active = MealPrepBatch(
        id="active",
        recipe_id="r1",
        total_servings=2,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=1, slot_index=0, servings=1.0)],
        status="planned",
    )
    consumed = MealPrepBatch(
        id="consumed",
        recipe_id="r1",
        total_servings=2,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=1, slot_index=1, servings=1.0)],
        status="consumed",
    )
    repo._active.append(active)
    repo._by_id[active.id] = active
    repo._by_id[consumed.id] = consumed
    monkeypatch.setattr("src.api.meal_prep_routes.MealPrepBatchRepository", lambda: repo)

    res = _client().get("/api/v1/meal_prep_batches", params={"active": "false"})

    assert res.status_code == 200
    assert {item["id"] for item in res.json()["batches"]} == {"active", "consumed"}


def test_recipe_delete_endpoint_orphans_batches(monkeypatch):
    class _ServerRecipe:
        def __init__(self, rid: str):
            self.id = rid

    class _ServerRecipeDB:
        def __init__(self, *_a, **_k):
            self._recipes = [_ServerRecipe("r1"), _ServerRecipe("r2")]

        def get_recipe_by_id(self, recipe_id: str):
            for recipe in self._recipes:
                if recipe.id == recipe_id:
                    return recipe
            return None

        def save(self):
            return None

    class _ServerMealPrepRepo:
        def mark_orphaned_for_recipe(self, recipe_id: str) -> int:
            assert recipe_id == "r1"
            return 3

    monkeypatch.setattr("src.api.server.RecipeDB", _ServerRecipeDB)
    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", lambda: _ServerMealPrepRepo())

    res = _client().delete("/api/v1/recipes/r1")
    assert res.status_code == 200
    assert res.json() == {"deleted_id": "r1", "orphaned_batches": 3}


def test_recipe_delete_endpoint_returns_404(monkeypatch):
    class _ServerRecipeDB:
        def __init__(self, *_a, **_k):
            self._recipes = []

        def get_recipe_by_id(self, _recipe_id: str):
            return None

        def save(self):
            return None

    monkeypatch.setattr("src.api.server.RecipeDB", _ServerRecipeDB)
    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", lambda: object())

    res = _client().delete("/api/v1/recipes/missing")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RECIPE_NOT_FOUND"
