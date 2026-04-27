from __future__ import annotations

import json

from src.data_layer.models import NutritionProfile
from src.llm.tag_repository import (
    load_canonical_recipe_tag_slugs,
    load_hard_eligible_recipe_tag_slugs,
)
from src.planning.phase0_models import MealSlot, PlanningBatchLock, PlanningRecipe, PlanningUserProfile
from src.planning.planner import plan_meals


def _slot(
    *,
    required: list[str] | None = None,
    preferred: list[str] | None = None,
) -> MealSlot:
    return MealSlot(
        time="12:00",
        busyness_level=2,
        meal_type="lunch",
        required_tag_slugs=required,
        preferred_tag_slugs=preferred,
    )


def _recipe(
    rid: str,
    *,
    tags: set[str] | None = None,
    hard_eligible_tags: set[str] | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(
            calories=500.0,
            protein_g=50.0,
            fat_g=32.0,
            carbs_g=125.0,
        ),
        canonical_tag_slugs=set(tags or set()),
        hard_eligible_tag_slugs=set(hard_eligible_tags or set()),
    )


def _profile(
    *,
    schedule: list[list[MealSlot]],
    batch_locks: list[PlanningBatchLock] | None = None,
    pinned_assignments: dict[tuple[int, int], str] | None = None,
) -> PlanningUserProfile:
    slot_count = len(schedule[0]) if schedule and schedule[0] else 1
    daily_calories = 500 * slot_count
    daily_protein_g = 50.0 * slot_count
    daily_fat = 32.0 * slot_count
    daily_carbs_g = 125.0 * slot_count
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=(daily_fat, daily_fat),
        daily_carbs_g=daily_carbs_g,
        schedule=schedule,
        pinned_assignments=dict(pinned_assignments or {}),
        batch_locks=list(batch_locks or []),
    )


def test_required_tag_filters_candidates_per_slot():
    profile = _profile(schedule=[[_slot(required=["quick"])]])
    result = plan_meals(
        profile,
        [
            _recipe("a-non-match", tags={"slow"}, hard_eligible_tags={"slow"}),
            _recipe("z-match", tags={"quick"}, hard_eligible_tags={"quick"}),
        ],
        days=1,
    )

    assert result.success is True
    assert result.plan is not None
    assert result.plan[0].recipe_id == "z-match"


def test_no_candidate_emits_fm_tag_empty():
    profile = _profile(schedule=[[_slot(required=["portable"])]])
    result = plan_meals(
        profile,
        [
            _recipe("r1", tags={"quick"}, hard_eligible_tags={"quick"}),
            _recipe("r2", tags={"high-protein"}, hard_eligible_tags={"high-protein"}),
        ],
        days=1,
    )

    assert result.success is False
    assert result.failure_mode == "FM-TAG-EMPTY"
    slot_report = (result.report or {}).get("tag_empty_slots", [])[0]
    assert slot_report["code"] == "FM-TAG-EMPTY"
    assert slot_report["day_index"] == 0
    assert slot_report["slot_index"] == 0
    assert slot_report["required_tag_slugs"] == ["portable"]
    assert slot_report["candidate_count_before"] == 2
    assert slot_report["candidate_count_after"] == 0


def test_preferred_tags_do_not_hard_reject():
    profile = _profile(schedule=[[_slot(required=["quick"], preferred=["high-protein"])]])
    result = plan_meals(
        profile,
        [
            _recipe("only-required", tags={"quick"}, hard_eligible_tags={"quick"}),
            _recipe("non-match", tags={"slow"}, hard_eligible_tags={"slow"}),
        ],
        days=1,
    )

    assert result.success is True
    assert result.plan is not None
    assert result.plan[0].recipe_id == "only-required"


def test_lock_beats_pin_deterministically():
    profile = _profile(
        schedule=[[_slot(), _slot()]],
        batch_locks=[
            PlanningBatchLock(batch_id="batch-a", recipe_id="r-lock", day_index=0, slot_index=0),
        ],
        pinned_assignments={(1, 0): "r-pin"},
    )
    result = plan_meals(
        profile,
        [_recipe("r-lock"), _recipe("r-pin"), _recipe("r-other")],
        days=1,
    )

    assert result.success is True
    assert result.plan is not None
    by_slot = {(a.day_index, a.slot_index): a.recipe_id for a in result.plan}
    assert by_slot[(0, 0)] == "r-lock"


def test_pin_beats_required_tags():
    profile = _profile(
        schedule=[[_slot(required=["high-protein"])]],
        pinned_assignments={(1, 0): "r-pin"},
    )
    result = plan_meals(
        profile,
        [
            _recipe("r-pin", tags={"quick"}, hard_eligible_tags={"quick"}),
            _recipe("r-other", tags={"high-protein"}, hard_eligible_tags={"high-protein"}),
        ],
        days=1,
    )

    assert result.plan is not None
    assert result.plan[0].recipe_id == "r-pin"


def test_proposed_llm_tag_excluded_from_hard_matching():
    profile = _profile(schedule=[[_slot(required=["high-protein"])]])
    result = plan_meals(
        profile,
        [
            # Would win by tie-break id if not excluded from hard matching.
            _recipe(
                "a-proposed-tag",
                tags={"high-protein"},
                hard_eligible_tags=set(),
            ),
            _recipe(
                "z-approved-tag",
                tags={"high-protein"},
                hard_eligible_tags={"high-protein"},
            ),
        ],
        days=1,
    )

    assert result.success is True
    assert result.plan is not None
    assert result.plan[0].recipe_id == "z-approved-tag"


def test_repository_hard_eligible_tags_exclude_proposed_llm_tags(tmp_path):
    tag_path = tmp_path / "recipe_tags.json"
    tag_path.write_text(
        json.dumps(
            {
                "tags_by_id": {
                    "a-proposed-tag": {
                        "cuisine": "shared",
                        "cost_level": "cheap",
                        "prep_time_bucket": "quick_meal",
                        "dietary_flags": [],
                        "tag_slugs_by_type": {"constraint": ["high-protein"]},
                        "tag_metadata": {
                            "high-protein": {
                                "slug": "high-protein",
                                "display": "High Protein",
                                "tag_type": "constraint",
                                "source": "llm",
                                "created_at": "2026-01-01T00:00:00Z",
                                "aliases": [],
                                "eligibility": "proposed",
                            }
                        },
                    },
                    "z-approved-tag": {
                        "cuisine": "shared",
                        "cost_level": "cheap",
                        "prep_time_bucket": "quick_meal",
                        "dietary_flags": [],
                        "tag_slugs_by_type": {"constraint": ["high-protein"]},
                        "tag_metadata": {
                            "high-protein": {
                                "slug": "high-protein",
                                "display": "High Protein",
                                "tag_type": "constraint",
                                "source": "llm",
                                "created_at": "2026-01-01T00:00:00Z",
                                "aliases": [],
                                "eligibility": "approved",
                            }
                        },
                    },
                },
                "tag_registry": {},
                "tag_aliases": {},
            }
        ),
        encoding="utf-8",
    )
    canonical_by_id = load_canonical_recipe_tag_slugs(str(tag_path))
    hard_eligible_by_id = load_hard_eligible_recipe_tag_slugs(str(tag_path))
    recipes = [
        _recipe(
            rid,
            tags=canonical_by_id.get(rid, set()),
            hard_eligible_tags=hard_eligible_by_id.get(rid, set()),
        )
        for rid in ["a-proposed-tag", "z-approved-tag"]
    ]
    result = plan_meals(_profile(schedule=[[_slot(required=["high-protein"])]]), recipes, days=1)

    assert hard_eligible_by_id["a-proposed-tag"] == set()
    assert hard_eligible_by_id["z-approved-tag"] == {"high-protein"}
    assert result.success is True
    assert result.plan is not None
    assert result.plan[0].recipe_id == "z-approved-tag"


def test_equal_seed_deterministic_outcome():
    profile = _profile(schedule=[[_slot(required=["quick"])], [_slot(required=["slow"])]])
    recipes = [
        _recipe("a-quick", tags={"quick"}, hard_eligible_tags={"quick"}),
        _recipe("b-slow", tags={"slow"}, hard_eligible_tags={"slow"}),
    ]

    result_a = plan_meals(profile, recipes, days=2)
    result_b = plan_meals(profile, recipes, days=2)

    assert result_a.success == result_b.success
    assert result_a.failure_mode == result_b.failure_mode
    assert result_a.termination_code == result_b.termination_code
    assert result_a.plan == result_b.plan
