"""BE-15: HTTP contract tests for ``POST /api/v1/plan`` (failures + meal-prep metadata)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch, MealPrepBatchRepository
from src.data_layer.models import Ingredient, Recipe
from src.planning.phase0_models import Assignment, DailyTracker, PlanningBatchLock
from src.planning.phase10_reporting import MealPlanResult
_ROOT = Path(__file__).resolve().parents[2]


def _write_profile(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "nutrition_goals": {
                    "daily_calories": 2200,
                    "daily_protein_g": 140,
                    "daily_fat_g": {"min": 60, "max": 90},
                },
                "preferences": {"liked_foods": [], "disliked_foods": [], "allergies": []},
            }
        ),
        encoding="utf-8",
    )


def _dm7_tags_with_recipe(
    tmp_path: Path, monkeypatch, recipe_id: str, tag_slugs_by_type: dict
) -> Path:
    src = _ROOT / "data/recipes/recipe_tags.json"
    dst = tmp_path / "recipe_tags.json"
    shutil.copyfile(src, dst)
    data = json.loads(dst.read_text(encoding="utf-8"))
    data.setdefault("tags_by_id", {})
    data["tags_by_id"][recipe_id] = {
        "cuisine": "american",
        "cost_level": "cheap",
        "prep_time_bucket": "quick_meal",
        "dietary_flags": [],
        "tag_slugs_by_type": tag_slugs_by_type,
    }
    dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
    monkeypatch.setenv("NUTRITION_TAG_REPO_PATH", str(dst))
    return dst


def _stub_recipes_json(
    tmp_path: Path, recipe_id: str, name: str = "Contract Plan Recipe"
) -> Path:
    path = tmp_path / "recipes.json"
    payload = {
        "recipes": [
            {
                "id": recipe_id,
                "name": name,
                "ingredients": [{"name": "cream of rice", "quantity": 100, "unit": "g"}],
                "cooking_time_minutes": 5,
                "instructions": ["Prepare."],
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class _DummyProvider:
    usda_capable = True

    def resolve_all(self, _ingredient_names):
        return None

    def get_ingredient_info(self, name: str):
        return {
            "name": name,
            "per_100g": {
                "calories": 140.0,
                "protein_g": 13.0,
                "fat_g": 10.0,
                "carbs_g": 1.0,
            },
        }


class _RecipeDBPoolOne:
    """Single recipe in repo for FM-TAG-EMPTY scenario."""

    def __init__(self, *_a, **_k) -> None:
        pass

    def get_all_recipes(self):
        return [
            Recipe(
                id="r-fm-empty",
                name="Tagged Quick Meal",
                ingredients=[Ingredient("cream of rice", 100.0, "g", is_to_taste=False)],
                cooking_time_minutes=5,
                instructions=["mix"],
            )
        ]


def test_plan_fm_tag_empty_failure_shape_on_schedule_days(tmp_path, monkeypatch):
    """Pool has time-tagged recipe; slot requires ``high-fiber`` → ``FM-TAG-EMPTY`` in ``report.failures``."""
    tags_path = _dm7_tags_with_recipe(
        tmp_path,
        monkeypatch,
        "r-fm-empty",
        {"time": ["time-1"]},
    )
    recipes_path = _stub_recipes_json(tmp_path, "r-fm-empty")
    monkeypatch.setattr("src.api.server.recipes_path", str(recipes_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBPoolOne)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )
    monkeypatch.setattr(
        "src.api.server.MealPrepBatchRepository", lambda *_a, **_k: type(
            "_E", (), {"list_active": lambda self: []}
        )()
    )
    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )

    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))

    client = TestClient(app)
    resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "recipe_tags_path": str(tags_path),
            "schedule_days": [
                {
                    "day_index": 1,
                    "meals": [
                        {
                            "index": 1,
                            "busyness_level": 2,
                            "tags": ["breakfast"],
                            "required_tag_slugs": ["high-fiber"],
                        },
                    ],
                    "workouts": [],
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_status"] in ("failed", "partial")
    failures = body["report"]["failures"]
    assert failures
    hit = next((f for f in failures if f.get("code") == "FM-TAG-EMPTY"), None)
    assert hit is not None
    assert hit["day_index"] is not None
    assert hit["slot_index"] is not None
    assert hit["message"]
    assert isinstance(hit["details"], dict)
    assert hit["details"].get("missing_tag") == "high-fiber"


class _RecipeObjBatchable:
    is_meal_prep_capable = True


class _RecipeDBForMealPrepCreate:
    """``get_recipe_by_id`` for meal-prep POST validation (batch-capable flag)."""

    def __init__(self, *_a, **_k) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id == "known-recipe":
            return _RecipeObjBatchable()
        return None


class _RecipeDBWithKnown:
    def __init__(self, *_a, **_k) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id == "known-recipe":
            return object()
        return None

    def get_all_recipes(self):
        return [
            Recipe(
                id="known-recipe",
                name="Known Recipe",
                ingredients=[Ingredient("egg", 2.0, "large", is_to_taste=False)],
                cooking_time_minutes=5,
                instructions=["cook"],
            )
        ]


def test_plan_response_meal_metadata_meal_prep_batch_contract(tmp_path, monkeypatch):
    """Active batch assignment → meal row ``source``, ``batch_id``, ``slot_index``, ``servings``."""
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBWithKnown)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )

    batch = MealPrepBatch(
        id="contract-batch-1",
        recipe_id="known-recipe",
        total_servings=10,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=0, slot_index=0, servings=3.0)],
        status="planned",
    )

    class _BatchRepo:
        def list_active(self):
            return [batch]

    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", lambda *_a, **_k: _BatchRepo())

    # Deterministic planning output; metadata formatting stays live via ``format_result_json``.
    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda *_a, **_k: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[Assignment(0, 0, "known-recipe", 0)],
            daily_trackers={
                0: DailyTracker(
                    calories_consumed=100.0,
                    protein_consumed=10.0,
                    fat_consumed=5.0,
                    carbs_consumed=10.0,
                    slots_assigned=1,
                    slots_total=1,
                )
            },
            weekly_tracker=None,
            report={},
            stats=None,
        ),
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "schedule": {"08:00": 3},
        },
    )
    assert resp.status_code == 200
    meal = resp.json()["daily_plans"][0]["meals"][0]
    assert meal["source"] == "meal_prep_batch"
    assert meal["batch_id"] == "contract-batch-1"
    assert meal["slot_index"] == 0
    assert meal["servings"] == 3.0


def test_meal_prep_api_create_persists_canonical_and_plan_lock_round_trip(
    tmp_path, monkeypatch
):
    """POST batch with canonical assignments → repo → ``plan_meals`` receives matching locks."""
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))

    batches_path = tmp_path / "batches.json"

    def _repo() -> MealPrepBatchRepository:
        return MealPrepBatchRepository(str(batches_path))

    monkeypatch.setattr("src.api.meal_prep_routes.MealPrepBatchRepository", _repo)
    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", _repo)
    monkeypatch.setattr("src.api.meal_prep_routes.RecipeDB", _RecipeDBForMealPrepCreate)
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBWithKnown)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )

    locks_seen: list[list[PlanningBatchLock]] = []

    def _spy_plan(profile, pool, days):
        locks_seen.append(list(profile.batch_locks))
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[Assignment(0, 1, "known-recipe", 0)],
            daily_trackers={
                0: DailyTracker(
                    calories_consumed=100.0,
                    protein_consumed=10.0,
                    fat_consumed=5.0,
                    carbs_consumed=10.0,
                    slots_assigned=1,
                    slots_total=2,
                )
            },
            weekly_tracker=None,
            report={},
            stats=None,
        )

    monkeypatch.setattr("src.api.server.plan_meals", _spy_plan)

    client = TestClient(app)
    create = client.post(
        "/api/v1/meal_prep_batches",
        json={
            "recipe_id": "known-recipe",
            "total_servings": 3,
            "cook_date": "2026-04-27",
            "assignments": [{"day_index": 0, "slot_index": 1, "servings": 2.0}],
        },
    )
    assert create.status_code == 200
    created = create.json()
    batch_id = created["id"]
    assert created["assignments"][0]["day_index"] == 0
    assert created["assignments"][0]["slot_index"] == 1
    assert created["assignments"][0]["servings"] == 2.0

    detail = client.get(f"/api/v1/meal_prep_batches/{batch_id}")
    assert detail.status_code == 200
    assert detail.json()["assignments"][0]["slot_index"] == 1

    plan_resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
                "schedule": {"08:00": 3, "12:00": 3},
            },
        )
    assert plan_resp.status_code == 200
    assert len(locks_seen) == 1
    assert len(locks_seen[0]) == 1
    lock = locks_seen[0][0]
    assert lock.batch_id == batch_id
    assert lock.recipe_id == "known-recipe"
    assert lock.day_index == 0
    assert lock.slot_index == 1
    assert lock.servings == 2.0

    meal = plan_resp.json()["daily_plans"][0]["meals"][0]
    assert meal["source"] == "meal_prep_batch"
    assert meal["batch_id"] == batch_id
    assert meal["slot_index"] == 1
    assert meal["servings"] == 2.0


def test_plan_fm_batch_conflict_two_active_batches_same_slot(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBWithKnown)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )

    batches_path = tmp_path / "batches.json"
    batches_path.write_text(
        json.dumps(
            {
                "batches": [
                    {
                        "id": "batch-a",
                        "recipe_id": "known-recipe",
                        "total_servings": 2,
                        "cook_date": "2026-04-27",
                        "assignments": [
                            {"day_index": 0, "slot_index": 0, "servings": 1.0}
                        ],
                        "status": "planned",
                    },
                    {
                        "id": "batch-b",
                        "recipe_id": "known-recipe",
                        "total_servings": 2,
                        "cook_date": "2026-04-27",
                        "assignments": [
                            {"day_index": 0, "slot_index": 0, "servings": 1.0}
                        ],
                        "status": "planned",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.api.server.MealPrepBatchRepository",
        lambda *_a, **_k: MealPrepBatchRepository(str(batches_path)),
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "schedule": {"08:00": 3},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["plan_status"] == "failed"
    failure = next(
        f for f in body["report"]["failures"] if f.get("code") == "FM-BATCH-CONFLICT"
    )
    assert failure["message"] == "Batch locks conflict for this slot."
    assert failure["fix_hint"]
    assert isinstance(failure["details"], dict)
    assert failure["day_index"] == 0
    assert failure["slot_index"] == 0
    assert set(failure["details"]["batch_ids"]) == {"batch-a", "batch-b"}


def test_plan_response_meal_metadata_slot_index_matches_batch_assignment(tmp_path, monkeypatch):
    """Planned meal ``slot_index`` equals persisted batch assignment ``slot_index``."""
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBWithKnown)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )

    batch = MealPrepBatch(
        id="contract-batch-slot2",
        recipe_id="known-recipe",
        total_servings=10,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=0, slot_index=2, servings=4.0)],
        status="planned",
    )

    class _BatchRepo:
        def list_active(self):
            return [batch]

    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", lambda *_a, **_k: _BatchRepo())
    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda *_a, **_k: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[Assignment(0, 2, "known-recipe", 0)],
            daily_trackers={
                0: DailyTracker(
                    calories_consumed=100.0,
                    protein_consumed=10.0,
                    fat_consumed=5.0,
                    carbs_consumed=10.0,
                    slots_assigned=1,
                    slots_total=3,
                )
            },
            weekly_tracker=None,
            report={},
            stats=None,
        ),
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "schedule": {"08:00": 3, "12:00": 3, "18:00": 3},
        },
    )
    assert resp.status_code == 200
    meal = resp.json()["daily_plans"][0]["meals"][0]
    assert meal["source"] == "meal_prep_batch"
    assert meal["batch_id"] == "contract-batch-slot2"
    assert meal["slot_index"] == 2
    assert meal["servings"] == 4.0
