"""Recovery-loop contract tests (LLM overhaul Stages 1, 5, 6).

The loop is exercised end to end with the real deterministic planner, a scripted LLM client
and a USDA-capable fake provider. No monkeypatching of loop internals: the contract is what
comes back in ``report['llm_recovery']`` and what is (not) persisted on disk.
"""
from __future__ import annotations

import json

import pytest

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile
from src.llm.feedback_cache import DeterministicCacheMissError
from src.llm.recovery_types import RecoveryState
from src.planning.orchestrator import plan_with_llm_feedback
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.providers.ingredient_provider import IngredientDataProvider

TABLE = {
    "chicken breast": {"calories": 165.0, "protein_g": 31.0, "fat_g": 3.6, "carbs_g": 0.0},
    "rice": {"calories": 130.0, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28.0},
    "olive oil": {"calories": 884.0, "protein_g": 0.0, "fat_g": 100.0, "carbs_g": 0.0},
    "spinach": {"calories": 23.0, "protein_g": 2.9, "fat_g": 0.4, "carbs_g": 3.6, "iron_mg": 2.7},
    "peanut butter": {"calories": 598.0, "protein_g": 22.0, "fat_g": 51.0, "carbs_g": 22.0},
}


class Provider(IngredientDataProvider):
    usda_capable = True

    def __init__(self):
        self.resolved = []

    def get_ingredient_info(self, name):
        key = name.lower()
        if key not in TABLE:
            return None
        return {"name": key, "per_100g": TABLE[key], "provenance": {"description": key.title(), "fdc_id": 7, "method": "deterministic"}}

    def resolve_all(self, names):
        self.resolved.append(list(names))


class Client:
    _settings = None

    def __init__(self, envelopes):
        self.envelopes = list(envelopes)
        self.calls = 0
        self.contexts = []

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        self.calls += 1
        ctx = user_prompt.split("Generation context (JSON): ", 1)[1].split("\n")[0]
        self.contexts.append(json.loads(ctx))
        env = self.envelopes[min(self.calls - 1, len(self.envelopes) - 1)]
        if isinstance(env, Exception):
            raise env
        return env


def R(rid, kcal, p, f, c, t=10, ings=("rice",)):
    return PlanningRecipe(id=rid, name=rid, ingredients=[Ingredient(n, 100, "g") for n in ings], cooking_time_minutes=t,
                          nutrition=NutritionProfile(kcal, p, f, c, MicronutrientProfile()))


def profile(slots=2, kcal=1200, protein=70.0, fat=(20.0, 40.0), carbs=130.0, busy=4, excl=(), micro=None, required=None):
    busy_list = busy if isinstance(busy, list) else [busy] * slots
    return PlanningUserProfile(daily_calories=kcal, daily_protein_g=protein, daily_fat_g=fat, daily_carbs_g=carbs,
                               schedule=[[MealSlot(time="12:00", busyness_level=busy_list[i], meal_type="lunch",
                                                   required_tag_slugs=(required or {}).get(i)) for i in range(slots)]],
                               excluded_ingredients=list(excl), liked_foods=[], pinned_assignments={}, micronutrient_targets=micro or {})


# chicken 200 g + rice 250 g = 655 kcal / 68.75 p / 7.95 f / 70 c ; two such meals ~ 1310 kcal window
FIT = {"name": "Chicken and rice", "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}, {"name": "rice", "quantity": 250.0, "unit": "g"}],
       "instructions": ["Cook.", "Serve."], "cooking_time_minutes": 20}
FIT2 = {"name": "Rice and chicken plate", "ingredients": [{"name": "chicken breast", "quantity": 190.0, "unit": "g"}, {"name": "rice", "quantity": 240.0, "unit": "g"}, {"name": "olive oil", "quantity": 5.0, "unit": "g"}],
        "instructions": ["Cook.", "Serve."], "cooking_time_minutes": 15}
TINY = {"name": "Rice spoon", "ingredients": [{"name": "rice", "quantity": 30.0, "unit": "g"}], "instructions": ["Eat."], "cooking_time_minutes": 1}


def _target_for_two_fits(**kw):
    # window that FIT + FIT2 satisfies (real planner validation, ±10 %)
    return profile(slots=2, kcal=1310, protein=134.0, fat=(6.0, 22.0), carbs=136.0, **kw)


def test_retry_succeeds_and_persists_only_used_recipes(tmp_path):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12), R("small_c", 110, 5, 3, 11)]
    client = Client([{"drafts": [FIT, FIT2, TINY]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=3)
    rec = out.report["llm_recovery"]
    assert out.success is True and rec["state"] == RecoveryState.SUCCESS.value
    assert rec["gap_spec"]["kind"] == "macro_gap"
    assert client.calls == 1 and rec["planner_runs"] == 2
    on_disk = json.load(open(tmp_path / "r.json"))["recipes"]
    assert len(on_disk) == 2 and {r["name"] for r in on_disk} == {"Chicken and rice", "Rice and chicken plate"}
    assert all(r["provenance"]["source"] == "llm_feedback" and r["provenance"]["gap_kind"] == "macro_gap" for r in on_disk)
    assert all(r["cooking_time_minutes"] in (20, 15) for r in on_disk)  # author-claimed, not fabricated
    assert rec["attempts"][0]["rejected"] == [{"code": "NOT_USEFUL", "message": rec["attempts"][0]["rejected"][0]["message"]}]
    assert set(rec["persisted_recipe_ids"]) == {r["id"] for r in on_disk}


def test_llm_receives_gap_spec_not_bare_failure_code(tmp_path):
    prof = _target_for_two_fits()
    prof.excluded_ingredients = ["peanuts"]
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    client = Client([{"drafts": [FIT, FIT2]}])
    plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                           use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    ctx = client.contexts[0]
    assert ctx["kind"] == "macro_gap" and ctx["excluded_ingredients"] == ["peanuts"]
    assert ctx["per_meal_calories"] == 655.0 and "existing_recipe_names" in ctx and ctx["attempt"] == 1


def test_failed_request_persists_nothing(tmp_path):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    client = Client([{"drafts": [FIT]}, {"drafts": [FIT]}, {"drafts": [FIT]}])  # one fitting recipe is not enough for two slots
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=1)
    assert out.success is False
    assert not (tmp_path / "r.json").exists() or json.load(open(tmp_path / "r.json"))["recipes"] == []
    rec = out.report["llm_recovery"]
    assert rec["state"] in (RecoveryState.NO_USEFUL_RECOVERY_FOUND.value, RecoveryState.RECOVERY_LIMIT_REACHED.value)
    assert rec["persisted_recipe_ids"] == []


def test_excluded_ingredient_draft_is_rejected_and_never_planned(tmp_path):
    prof = _target_for_two_fits(); prof.excluded_ingredients = ["peanuts"]
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    pb = {"name": "PB plate", "ingredients": [{"name": "peanut butter", "quantity": 100.0, "unit": "g"}, {"name": "rice", "quantity": 50.0, "unit": "g"}], "instructions": ["Mix."], "cooking_time_minutes": 2}
    client = Client([{"drafts": [pb, pb]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    rec = out.report["llm_recovery"]
    assert out.success is False
    assert rec["attempts"][0]["rejected"][0]["code"] == "EXCLUDED_INGREDIENT"
    assert rec["state"] == RecoveryState.INVALID_RECOVERY_OUTPUT.value
    assert rec["planner_runs"] == 1  # nothing accepted -> planner not re-run


def test_unrecoverable_cases_never_call_the_llm(tmp_path):
    client = Client([{"drafts": [FIT]}])
    # impossible targets
    prof = profile(carbs=-10.0)
    out = plan_with_llm_feedback(prof, [R("a", 600, 35, 10, 65), R("b", 600, 35, 10, 65)], 1, recipes_path=str(tmp_path / "r.json"),
                                 client=client, provider=Provider(), use_feedback_cache=False, force_live_generation=True)
    assert out.report["llm_recovery"]["state"] == RecoveryState.UNRECOVERABLE_INFEASIBILITY.value
    assert out.report["llm_recovery"]["reason"] == "IMPOSSIBLE_TARGETS"
    # empty pool
    out2 = plan_with_llm_feedback(_target_for_two_fits(), [], 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                  use_feedback_cache=False, force_live_generation=True)
    assert out2.report["llm_recovery"]["reason"] == "EMPTY_POOL"
    # required tag nobody holds
    prof3 = _target_for_two_fits(required={1: ["post-workout"]})
    out3 = plan_with_llm_feedback(prof3, [R("a", 600, 35, 10, 65), R("b", 600, 35, 10, 65)], 1, recipes_path=str(tmp_path / "r.json"),
                                  client=client, provider=Provider(), use_feedback_cache=False, force_live_generation=True)
    assert out3.report["llm_recovery"]["reason"] == "REQUIRED_TAG_UNHELD"
    assert client.calls == 0


def test_cook_time_cap_gap_and_claimed_time(tmp_path):
    prof = _target_for_two_fits(busy=[1, 4])  # slot 0: <= 5 min
    pool = [R("a", 655, 68.75, 7.95, 70, t=20), R("b", 655, 68.75, 7.95, 70, t=20)]
    quick = {"name": "Quick chicken rice", "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}, {"name": "rice", "quantity": 250.0, "unit": "g"}], "instructions": ["Microwave."], "cooking_time_minutes": 4}
    slow_claim = {"name": "Slow chicken rice", "ingredients": [{"name": "chicken breast", "quantity": 200.0, "unit": "g"}, {"name": "rice", "quantity": 250.0, "unit": "g"}], "instructions": ["Roast."], "cooking_time_minutes": 40}
    client = Client([{"drafts": [slow_claim, quick]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    rec = out.report["llm_recovery"]
    assert rec["gap_spec"]["kind"] == "candidate_gap" and rec["gap_spec"]["cook_time_cap_minutes"] == 5
    assert [r["code"] for r in rec["attempts"][0]["rejected"]] == ["COOK_TIME_EXCEEDS_CAP"]
    assert out.success is True and rec["state"] == RecoveryState.SUCCESS.value
    assert json.load(open(tmp_path / "r.json"))["recipes"][0]["cooking_time_minutes"] == 4


def test_rejections_are_fed_back_on_the_next_attempt(tmp_path):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    client = Client([{"drafts": [TINY, TINY]}, {"drafts": [FIT, FIT2]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    assert client.calls == 2
    assert client.contexts[1]["previous_attempt_rejections"][0]["code"] == "NOT_USEFUL"
    assert out.success is True


def test_feedback_cache_replays_and_model_change_invalidates(tmp_path, monkeypatch):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "fc.json"))
    monkeypatch.setenv("LLM_MODEL", "model-A")
    c1 = Client([{"drafts": [FIT, FIT2]}])
    out1 = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r1.json"), client=c1, provider=Provider(), recipes_to_generate_per_attempt=2)
    c2 = Client([{"drafts": [FIT, FIT2]}])
    out2 = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r2.json"), client=c2, provider=Provider(), recipes_to_generate_per_attempt=2)
    assert out1.success and out2.success and c1.calls == 1 and c2.calls == 0
    monkeypatch.setenv("LLM_MODEL", "model-B")
    c3 = Client([{"drafts": [FIT, FIT2]}])
    plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r3.json"), client=c3, provider=Provider(), recipes_to_generate_per_attempt=2)
    assert c3.calls == 1


def test_strict_mode_raises_on_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_FEEDBACK_CACHE_PATH", str(tmp_path / "fc.json"))
    client = Client([{"drafts": [FIT]}])
    with pytest.raises(DeterministicCacheMissError):
        plan_with_llm_feedback(_target_for_two_fits(), [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)], 1,
                               recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(), deterministic_strict_override=True)
    assert client.calls == 0


def test_duplicate_drafts_within_and_across_attempts_are_filtered(tmp_path):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    client = Client([{"drafts": [FIT, FIT]}, {"drafts": [FIT, FIT]}, {"drafts": [FIT, FIT]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    rec = out.report["llm_recovery"]
    assert rec["attempts"][0]["drafts_received"] == 2 and rec["attempts"][0]["recipes_generated"] == 1
    assert rec["attempts"][1]["recipes_generated"] == 0  # fingerprint already seen
    assert out.success is False and rec["persisted_recipe_ids"] == []


def test_pool_update_failure_is_typed_and_never_rebuilds_pool(tmp_path, monkeypatch):
    prof = _target_for_two_fits()
    pool = [R("small_a", 100, 5, 2, 10), R("small_b", 120, 6, 2, 12)]
    monkeypatch.setattr("src.planning.orchestrator._candidate_planning_recipe", lambda recipe, provider: (_ for _ in ()).throw(RuntimeError("incremental update failed")))
    client = Client([{"drafts": [FIT, FIT2]}])
    out = plan_with_llm_feedback(prof, pool, 1, recipes_path=str(tmp_path / "r.json"), client=client, provider=Provider(),
                                 use_feedback_cache=False, force_live_generation=True, recipes_to_generate_per_attempt=2)
    rec = out.report["llm_recovery"]
    assert out.success is False and rec["state"] == RecoveryState.SYSTEM_ERROR.value and rec["reason"] == "pool_update_failed"
    assert rec["planner_runs"] == 1
