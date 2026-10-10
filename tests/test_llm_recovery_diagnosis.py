"""Stage 3: deterministic diagnosis decides whether recipes can help, before any LLM call."""
from __future__ import annotations

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile
from src.llm.recovery_diagnosis import diagnose, feasibility_signal, improved, slot_candidate_counts
from src.llm.recovery_types import GapSpec, UnrecoverableReason
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult


def R(rid, kcal=600, p=40, f=20, c=60, ings=("x",), t=10, iron=1.0, tags=None):
    return PlanningRecipe(id=rid, name=rid, ingredients=[Ingredient(n, 100, "g") for n in ings], cooking_time_minutes=t,
                          nutrition=NutritionProfile(kcal, p, f, c, MicronutrientProfile(iron_mg=iron)),
                          canonical_tag_slugs=set(tags or []), hard_eligible_tag_slugs=set(tags or []))


def P(slots=3, busy=4, excl=(), micro=None, carbs=200.0, required=None, kcal=1800, ceiling=None):
    sched = [[MealSlot(time="12:00", busyness_level=busy if isinstance(busy, int) else busy[i], meal_type="lunch",
                       required_tag_slugs=(required or {}).get(i)) for i in range(slots)]]
    return PlanningUserProfile(daily_calories=kcal, daily_protein_g=120.0, daily_fat_g=(50.0, 70.0), daily_carbs_g=carbs,
                               schedule=sched, excluded_ingredients=list(excl), liked_foods=[], pinned_assignments={},
                               micronutrient_targets=micro or {}, max_daily_calories=ceiling)


def F(code="FM-1", report=None, stats=None):
    return MealPlanResult(success=False, termination_code="TC-2", failure_mode=code, report=report or {}, stats=stats or {})


def test_pin_and_batch_failures_are_unrecoverable():
    for code in ("FM-3", "FM-BATCH-CONFLICT"):
        out = diagnose(F(code), P(), [R("a"), R("b"), R("c")], 1)
        assert isinstance(out, UnrecoverableReason) and out.code == "PIN_OR_BATCH_CONFLICT"


def test_impossible_targets_are_unrecoverable_before_any_llm_call():
    out = diagnose(F("FM-1"), P(carbs=-10.0), [R("a"), R("b"), R("c")], 1)
    assert isinstance(out, UnrecoverableReason) and out.code == "IMPOSSIBLE_TARGETS" and "carbs" in out.details
    out2 = diagnose(F("FM-1"), P(ceiling=1000), [R("a"), R("b"), R("c")], 1)
    assert isinstance(out2, UnrecoverableReason) and "calorie_ceiling" in out2.details


def test_empty_pool_is_unrecoverable():
    out = diagnose(F("FM-1"), P(), [], 1)
    assert isinstance(out, UnrecoverableReason) and out.code == "EMPTY_POOL"


def test_required_tag_held_by_no_recipe_is_unrecoverable():
    out = diagnose(F("FM-1"), P(required={1: ["post-workout"]}), [R("a"), R("b"), R("c")], 1)
    assert isinstance(out, UnrecoverableReason) and out.code == "REQUIRED_TAG_UNHELD"
    ok = diagnose(F("FM-1"), P(required={1: ["post-workout"]}, excl=["x"]), [R("a", tags=["post-workout"]), R("b"), R("c")], 1)
    assert isinstance(ok, GapSpec)  # tag is held; exclusions empty the slots -> candidate gap


def test_search_budget_is_not_an_inventory_gap():
    out = diagnose(F("FM-5", stats={"attempts": 50000}), P(), [R("a"), R("b"), R("c")], 1)
    assert isinstance(out, UnrecoverableReason) and out.code == "SEARCH_BUDGET"


def test_candidate_gap_names_slots_cap_and_exclusions():
    pool = [R("a", t=20), R("b", t=25), R("c", t=30)]
    out = diagnose(F("FM-1"), P(busy=[1, 4, 4], excl=["peanuts"]), pool, 1)
    assert isinstance(out, GapSpec) and out.kind == "candidate_gap"
    assert out.slots == [[0, 0]] and out.cook_time_cap_minutes == 5 and out.excluded_ingredients == ["peanuts"]
    assert out.per_meal_calories == 600.0


def test_uniqueness_gap_when_pool_smaller_than_slots():
    out = diagnose(F("FM-1"), P(slots=3), [R("a"), R("b")], 1)
    assert isinstance(out, GapSpec) and out.kind == "uniqueness_gap"


def test_nutrient_gap_reports_per_recipe_minimum():
    pool = [R("a", iron=1.0), R("b", iron=1.0), R("c", iron=1.0), R("d", iron=1.0)]
    out = diagnose(F("FM-4"), P(micro={"iron_mg": 18.0}), pool, 1)
    assert isinstance(out, GapSpec) and out.kind == "nutrient_gap"
    assert out.nutrient_min_per_recipe["iron_mg"] == 15.0  # 18 required - 3 reachable


def test_macro_gap_when_every_slot_has_candidates():
    pool = [R("a", kcal=300), R("b", kcal=300), R("c", kcal=300), R("d", kcal=300)]
    out = diagnose(F("FM-1"), P(), pool, 1)
    assert isinstance(out, GapSpec) and out.kind == "macro_gap"


def test_feasibility_signal_improves_only_in_gap_dimension():
    prof = P(busy=[1, 4, 4])
    pool = [R("a", t=20), R("b", t=25), R("c", t=30)]
    gap = diagnose(F("FM-1"), prof, pool, 1)
    before = feasibility_signal(prof, pool, gap, 1)
    assert before["min_gap_slot_candidates"] == 0
    after = feasibility_signal(prof, pool + [R("quick", t=5)], gap, 1)
    assert improved(before, after, gap)
    after_wrong = feasibility_signal(prof, pool + [R("slow", t=40)], gap, 1)
    assert not improved(before, after_wrong, gap)
    assert slot_candidate_counts(prof, pool + [R("quick", t=5)])["0:0"] == 1
