import copy

import pytest

from src.data_layer.models import Ingredient, Recipe
from src.llm.planner_assistant import build_feedback_context
from src.llm.feedback_cache import DeterministicCacheMissError
from src.llm.schemas import RecipeDraft, RecipeIngredientDraft
from src.llm.types import ValidatedRecipeForPersistence
from src.planning.orchestrator import plan_with_llm_feedback
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult


def _make_schedule(*, days: int, slots_per_day: int) -> list[list[MealSlot]]:
    schedule: list[list[MealSlot]] = []
    for _ in range(days):
        day_slots: list[MealSlot] = []
        for _s in range(slots_per_day):
            day_slots.append(MealSlot(time="12:00", busyness_level=2, meal_type="lunch"))
        schedule.append(day_slots)
    return schedule


def _make_profile(*, days: int = 1, slots_per_day: int = 2) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=_make_schedule(days=days, slots_per_day=slots_per_day),
        excluded_ingredients=[],
        liked_foods=[],
        pinned_assignments={},
        micronutrient_targets={},
    )


def _fake_failure_result(*, failure_mode: str) -> MealPlanResult:
    return MealPlanResult(
        success=False,
        termination_code="TC-2",
        failure_mode=failure_mode,
        plan=[],
        daily_trackers={},
        weekly_tracker=None,
        report={
            "deficient_nutrients": [
                {
                    "nutrient": "iron_mg",
                    "achieved": 0.0,
                    "required": 2.0,
                    "deficit": 2.0,
                    "classification": "structural",
                }
            ],
            "failed_days": [
                {
                    "day": 0,
                    "constraint_detail": "calories",
                    "macro_violations": {
                        "constraint_detail": "calories",
                        "calories_consumed": 2500.0,
                        "protein_consumed": 90.0,
                        "fat_consumed": 40.0,
                        "carbs_consumed": 200.0,
                    },
                    "ul_violations": {},
                }
            ],
        },
        stats={"attempts": 0, "backtracks": 0},
    )


def test_orchestrator_retries_once_then_succeeds(monkeypatch):
    profile = _make_profile(days=2, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    success = MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={0: None},  # formatters only care that it's non-empty in this test
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure if plan_calls["count"] == 1 else success

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    # Planner assistant -> recipe drafts
    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
        assert context["failure_type"] == "FM-2"
        assert count == 1
        return [draft]

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _fake_suggest_targeted_recipe_drafts,
    )

    # Validation -> accepted recipes
    accepted_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[Ingredient(name="chicken breast", quantity=200.0, unit="g", normalized_unit="g", normalized_quantity=200.0)],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=accepted_recipe)

    def _fake_validate_recipe_drafts(*, drafts, provider):
        assert drafts == [draft]
        return [validated], []

    # Signature is validate_recipe_drafts(drafts, provider) in the real module.
    monkeypatch.setattr(
        "src.planning.orchestrator.validate_recipe_drafts",
        lambda drafts, provider: ([validated], []),
    )

    # Persistence
    monkeypatch.setattr(
        "src.planning.orchestrator.append_validated_recipes",
        lambda *, path, recipes: ["llm_recipe_1"],
    )

    # Pool update (avoid I/O + nutrition calculation in unit test)
    monkeypatch.setattr(
        "src.planning.orchestrator._append_new_recipes_to_pool",
        lambda *, recipes_path, provider, current_pool, persisted_ids: [],
    )

    dummy_client = object()  # not used due to patched suggest
    dummy_provider = type("P", (), {"usda_capable": True})()  # for assert_usda_capable_provider

    out = plan_with_llm_feedback(
        profile,
        base_pool,
        days=2,
        max_feedback_retries=3,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out.success is True
    assert plan_calls["count"] == 2
    assert out.stats is not None
    assert "llm_feedback_attempts" in out.stats
    assert isinstance(out.stats["llm_feedback_attempts"], list)


def test_orchestrator_aborts_on_repeated_failure_signature_no_progress(monkeypatch):
    profile = _make_profile(days=1, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    failure2 = copy.deepcopy(failure)

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure if plan_calls["count"] == 1 else failure2

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    # Generate drafts each attempt, but validation returns nothing => no persistence.
    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )
    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        lambda *, client, context, count: [draft],
    )

    monkeypatch.setattr(
        "src.planning.orchestrator.validate_recipe_drafts",
        lambda drafts, provider: ([], []),
    )

    monkeypatch.setattr(
        "src.planning.orchestrator.append_validated_recipes",
        lambda *, path, recipes: [],
    )

    monkeypatch.setattr(
        "src.planning.orchestrator._append_new_recipes_to_pool",
        lambda *, recipes_path, provider, current_pool, persisted_ids: [],
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()  # for assert_usda_capable_provider

    out = plan_with_llm_feedback(
        profile,
        base_pool,
        days=1,
        max_feedback_retries=3,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out.success is False
    # Initial attempt + only 1 feedback attempt (abort on repeated signature).
    assert plan_calls["count"] == 2
    assert out.stats is not None
    assert "llm_feedback_attempts" in out.stats


def test_orchestrator_feedback_cache_hit_bypasses_llm_and_is_replayable(
    monkeypatch,
    tmp_path,
):
    profile = _make_profile(days=2, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    success = MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={0: None},
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )

    suggest_calls = {"count": 0}

    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    validated_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=200.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=200.0,
            )
        ],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=validated_recipe)

    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "feedback_cache.json"))
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_SCHEMA_VERSION", "1")
    monkeypatch.setenv("LLM_DETERMINISTIC_STRICT", "false")
    monkeypatch.setenv("LLM_MODEL", "model-A")

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure if plan_calls["count"] == 1 else success

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
        suggest_calls["count"] += 1
        assert context["failure_type"] == "FM-2"
        assert count == 1
        return [draft]

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _fake_suggest_targeted_recipe_drafts,
    )

    monkeypatch.setattr(
        "src.planning.orchestrator.validate_recipe_drafts",
        lambda drafts, provider: ([validated], []),
    )

    monkeypatch.setattr(
        "src.planning.orchestrator.append_validated_recipes",
        lambda *, path, recipes: ["llm_recipe_1"],
    )

    # Avoid filesystem + nutrition calculation for incremental pool update.
    monkeypatch.setattr(
        "src.planning.orchestrator._append_new_recipes_to_pool",
        lambda *, recipes_path, provider, current_pool, persisted_ids: [],
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()

    out1 = plan_with_llm_feedback(
        profile,
        base_pool,
        days=2,
        max_feedback_retries=3,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )
    out2 = plan_with_llm_feedback(
        profile,
        base_pool,
        days=2,
        max_feedback_retries=3,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out1.success is True
    assert out2.success is True
    assert suggest_calls["count"] == 1  # second run replayed from cache

    assert out1.stats is not None
    assert out2.stats is not None
    assert out1.stats["llm_feedback_attempts"] == out2.stats["llm_feedback_attempts"]


def test_orchestrator_feedback_cache_invalidates_when_model_changes(
    monkeypatch,
    tmp_path,
):
    profile = _make_profile(days=1, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    success = MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={0: None},
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )

    suggest_calls = {"count": 0}

    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    validated_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=200.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=200.0,
            )
        ],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=validated_recipe)

    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "feedback_cache.json"))
    monkeypatch.setenv("LLM_DETERMINISTIC_STRICT", "false")

    def _run_with_model(model_version: str) -> MealPlanResult:
        monkeypatch.setenv("LLM_MODEL", model_version)

        plan_calls = {"count": 0}

        def _fake_plan_meals(*args, **kwargs):
            plan_calls["count"] += 1
            return failure if plan_calls["count"] == 1 else success

        monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

        def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
            suggest_calls["count"] += 1
            return [draft]

        monkeypatch.setattr(
            "src.planning.orchestrator.suggest_targeted_recipe_drafts",
            _fake_suggest_targeted_recipe_drafts,
        )

        monkeypatch.setattr(
            "src.planning.orchestrator.validate_recipe_drafts",
            lambda drafts, provider: ([validated], []),
        )

        monkeypatch.setattr(
            "src.planning.orchestrator.append_validated_recipes",
            lambda *, path, recipes: ["llm_recipe_1"],
        )

        monkeypatch.setattr(
            "src.planning.orchestrator._append_new_recipes_to_pool",
            lambda *, recipes_path, provider, current_pool, persisted_ids: [],
        )

        dummy_client = object()
        dummy_provider = type("P", (), {"usda_capable": True})()

        return plan_with_llm_feedback(
            profile,
            base_pool,
            days=1,
            max_feedback_retries=3,
            recipes_path="ignored.json",
            client=dummy_client,  # type: ignore[arg-type]
            provider=dummy_provider,  # type: ignore[arg-type]
            recipes_to_generate_per_attempt=1,
        )

    out1 = _run_with_model("model-A")
    out2 = _run_with_model("model-B")

    assert out1.success is True
    assert out2.success is True
    assert suggest_calls["count"] == 2  # different model => different cache keys


def test_orchestrator_feedback_strict_mode_aborts_on_cache_miss(
    monkeypatch,
    tmp_path,
):
    profile = _make_profile(days=1, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")

    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "feedback_cache.json"))
    monkeypatch.setenv("LLM_DETERMINISTIC_STRICT", "true")
    monkeypatch.setenv("LLM_MODEL", "model-A")

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", lambda *args, **kwargs: failure)

    def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
        raise AssertionError("LLM draft generation should not run in strict mode on cache miss.")

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _fake_suggest_targeted_recipe_drafts,
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()

    with pytest.raises(DeterministicCacheMissError):
        plan_with_llm_feedback(
            profile,
            base_pool,
            days=1,
            max_feedback_retries=3,
            recipes_path="ignored.json",
            client=dummy_client,  # type: ignore[arg-type]
            provider=dummy_provider,  # type: ignore[arg-type]
            recipes_to_generate_per_attempt=1,
        )


def test_orchestrator_pre_validation_dedupes_within_attempt(monkeypatch):
    """
    When the LLM returns duplicate drafts in a single attempt, the orchestrator
    should de-dupe before `validate_recipe_drafts()` runs.
    """
    profile = _make_profile(days=2, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    success = MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={0: None},
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure if plan_calls["count"] == 1 else success

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
        assert context["failure_type"] == "FM-2"
        assert count == 1
        # Duplicate drafts in the same attempt; orchestrator should de-dupe.
        return [draft, draft]

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _fake_suggest_targeted_recipe_drafts,
    )

    accepted_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=200.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=200.0,
            )
        ],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=accepted_recipe)

    validate_calls = {"count": 0}

    def _fake_validate_recipe_drafts(drafts, provider):
        validate_calls["count"] += 1
        assert drafts == [draft]  # within-attempt de-dupe
        return [validated], []

    monkeypatch.setattr("src.planning.orchestrator.validate_recipe_drafts", _fake_validate_recipe_drafts)

    monkeypatch.setattr(
        "src.planning.orchestrator.append_validated_recipes",
        lambda *, path, recipes: ["llm_recipe_1"],
    )
    monkeypatch.setattr(
        "src.planning.orchestrator._append_new_recipes_to_pool",
        lambda *, recipes_path, provider, current_pool, persisted_ids: [],
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()

    out = plan_with_llm_feedback(
        profile,
        base_pool,
        days=2,
        max_feedback_retries=2,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out.success is True
    assert plan_calls["count"] == 2
    assert validate_calls["count"] == 1
    assert out.stats is not None
    attempts = out.stats.get("llm_feedback_attempts") or []
    assert len(attempts) == 1
    assert attempts[0]["recipes_generated"] == 1
    assert attempts[0]["accepted"] == 1
    assert attempts[0]["status"] == "fail"


def test_orchestrator_pre_validation_dedupes_already_accepted_on_retry(monkeypatch):
    """
    When the orchestrator has already persisted a draft fingerprint from a
    previous attempt, subsequent retries that re-suggest the same draft
    should be filtered out before validation, leading to an abort when the
    planner repeats the same failure signature without new persistence.
    """
    profile = _make_profile(days=1, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    suggest_calls = {"count": 0}

    def _fake_suggest_targeted_recipe_drafts(*, client, context, count):
        suggest_calls["count"] += 1
        # Two feedback attempts (max_feedback_retries=2).
        return [draft]  # re-suggest same draft on both attempts

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        _fake_suggest_targeted_recipe_drafts,
    )

    accepted_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=200.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=200.0,
            )
        ],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=accepted_recipe)

    validate_calls = {"count": 0}

    def _fake_validate_recipe_drafts(drafts, provider):
        validate_calls["count"] += 1
        if validate_calls["count"] == 1:
            assert drafts == [draft]
            return [validated], []
        # Second attempt: draft fingerprint already accepted -> filtered out.
        assert drafts == []
        return [], []

    monkeypatch.setattr("src.planning.orchestrator.validate_recipe_drafts", _fake_validate_recipe_drafts)

    append_calls = {"count": 0}

    def _fake_append_validated_recipes(*, path, recipes):
        append_calls["count"] += 1
        return ["llm_recipe_1"]

    monkeypatch.setattr("src.planning.orchestrator.append_validated_recipes", _fake_append_validated_recipes)

    monkeypatch.setattr(
        "src.planning.orchestrator._append_new_recipes_to_pool",
        lambda *, recipes_path, provider, current_pool, persisted_ids: [],
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()

    out = plan_with_llm_feedback(
        profile,
        base_pool,
        days=1,
        max_feedback_retries=2,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out.success is False
    assert plan_calls["count"] == 3  # initial + 2 feedback attempts
    assert validate_calls["count"] == 2
    assert append_calls["count"] == 1  # second attempt persisted nothing

    assert out.stats is not None
    attempts = out.stats.get("llm_feedback_attempts") or []
    assert len(attempts) == 2
    assert attempts[0]["status"] == "fail"
    assert attempts[0]["recipes_generated"] == 1
    assert attempts[0]["accepted"] == 1
    assert attempts[1]["status"] == "abort"
    assert attempts[1]["recipes_generated"] == 0
    assert attempts[1]["accepted"] == 0


def test_orchestrator_fallback_observability_on_incremental_failure(monkeypatch, capsys):
    profile = _make_profile(days=1, slots_per_day=2)
    base_pool: list[PlanningRecipe] = []

    failure = _fake_failure_result(failure_mode="FM-2")
    success = MealPlanResult(
        success=True,
        termination_code="TC-1",
        plan=[],
        daily_trackers={0: None},
        weekly_tracker=None,
        report={},
        stats={"attempts": 1, "backtracks": 0},
    )

    plan_calls = {"count": 0}

    def _fake_plan_meals(*args, **kwargs):
        plan_calls["count"] += 1
        return failure if plan_calls["count"] == 1 else success

    monkeypatch.setattr("src.planning.orchestrator.plan_meals", _fake_plan_meals)

    draft = RecipeDraft(
        name="Generated",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    monkeypatch.setattr(
        "src.planning.orchestrator.suggest_targeted_recipe_drafts",
        lambda *, client, context, count: [draft],
    )

    accepted_recipe = Recipe(
        id="",
        name="Accepted",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=200.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=200.0,
            )
        ],
        cooking_time_minutes=10,
        instructions=["Cook it."],
    )
    validated = ValidatedRecipeForPersistence(recipe=accepted_recipe)

    monkeypatch.setattr(
        "src.planning.orchestrator.validate_recipe_drafts",
        lambda drafts, provider: ([validated], []),
    )

    # Persist at least one draft so the incremental expansion path runs.
    monkeypatch.setattr(
        "src.planning.orchestrator.append_validated_recipes",
        lambda *, path, recipes: ["llm_recipe_1"],
    )

    def _raise_incremental(*args, **kwargs):
        raise RuntimeError("incremental update failed")

    monkeypatch.setattr("src.planning.orchestrator._append_new_recipes_to_pool", _raise_incremental)
    monkeypatch.setattr(
        "src.planning.orchestrator._rebuild_recipe_pool",
        lambda *, recipes_path, provider: [],
    )

    dummy_client = object()
    dummy_provider = type("P", (), {"usda_capable": True})()

    out = plan_with_llm_feedback(
        profile,
        base_pool,
        days=1,
        max_feedback_retries=2,
        recipes_path="ignored.json",
        client=dummy_client,  # type: ignore[arg-type]
        provider=dummy_provider,  # type: ignore[arg-type]
        recipes_to_generate_per_attempt=1,
    )

    assert out.success is True
    captured = capsys.readouterr()
    assert '"fallback_triggered": true' in captured.err
    assert '"reason": "incremental_update_failed"' in captured.err

