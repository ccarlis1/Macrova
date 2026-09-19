"""Run Macrova's real planner against evaluation/benchmark scenarios.

Usage (from repo root):
    .venv/bin/python evaluation/harness/run_benchmark.py [MB-001 ...]

Writes evaluation/harness/results/results.json unless OUT is set.
Counterfactual switches (environment variables):
    ALL_BATCHES=1   pass every non-orphaned batch to the planner, bypassing
                    list_active() (isolates the "fully allocated = consumed" bug)
    API_FIDELITY=1  drop max_daily_calories, as /api/v1/plan does today
    LIMIT=<n>       planner attempt_limit (default 50000)

Path mirrors /api/v1/plan (PlanRequest validation -> _build_user_profile ->
convert_profile -> tag attach -> plan_meals) but injects the benchmark's stored
per-serving nutrition via a stub calculator so the search track is not
confounded by the ingredient layer. Pins/batches go through ProfilePin and
MealPrepBatchRepository._validate_create + planning_batch_locks_from_batches.
"""
import dataclasses, json, os, sys, tempfile, time, traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "evaluation/benchmark"
sys.path.insert(0, str(REPO))
os.chdir(REPO)
os.environ["NUTRITION_TAG_REPO_PATH"] = str(BENCH / "recipe_tags.json")

from src.api import server as S
from src.data_layer.models import (Recipe, Ingredient, NutritionProfile, MicronutrientProfile, ProfilePin)
from src.data_layer.meal_prep import MealPrepBatchRepository, MealPrepBatch, BatchAssignment
from src.planning.converters import convert_profile, convert_recipes
from src.planning.orchestrator import planning_batch_locks_from_batches
from src.planning.planner import plan_meals
from src.llm.tag_repository import load_canonical_recipe_tag_slugs, load_hard_eligible_recipe_tag_slugs

TAGS = str(BENCH / "recipe_tags.json")
LIB = json.load(open(BENCH / "recipes.json"))["recipes"]
LIB_BY = {r["id"]: r for r in LIB}
SCEN = json.load(open(BENCH / "scenarios.json"))["scenarios"]
MICRO_FIELDS = {f.name for f in dataclasses.fields(MicronutrientProfile)}


class StubCalc:
    def calculate_recipe_nutrition(self, recipe):
        n = LIB_BY[recipe.id]["nutrition"]
        m = {k: v for k, v in n["micronutrients"].items() if k in MICRO_FIELDS}
        return NutritionProfile(n["calories"], n["protein_g"], n["fat_g"], n["carbs_g"], MicronutrientProfile(**m))


def data_recipe(r):
    ings = [Ingredient(name=i["name"], quantity=float(i["quantity"]), unit=i["unit"],
                       normalized_unit="g", normalized_quantity=float(i["quantity"])) for i in r["ingredients"]]
    kw = dict(id=r["id"], name=r["name"], ingredients=ings, cooking_time_minutes=r["cooking_time_minutes"], instructions=[])
    try:
        return Recipe(**kw)
    except TypeError:
        kw.pop("instructions"); return Recipe(**kw)


def run(sc):
    p = sc["profile"]
    out = {"id": sc["id"]}
    req = {
        "daily_calories": p["daily_calories"], "daily_protein_g": p["daily_protein_g"],
        "daily_fat_g_min": p["daily_fat_g"]["min"], "daily_fat_g_max": p["daily_fat_g"]["max"],
        "schedule_days": sc["schedule_days"], "days": sc["horizon_days"],
        "liked_foods": p.get("liked_foods", []), "disliked_foods": p.get("excluded_ingredients", []),
        "micronutrient_goals": p.get("micronutrient_targets") or None,
        "micronutrient_weekly_min_fraction": p.get("micronutrient_weekly_min_fraction", 1.0),
        "recipe_ids": sc["recipe_pool"]["recipe_ids"], "recipe_tags_path": TAGS,
    }
    try:
        preq = S.PlanRequest.model_validate(req)
    except Exception as e:
        out.update(code="INVALID_REQUEST", stage="input_validation", detail=str(e)[:300]); return out
    # batches
    tmp = tempfile.mkdtemp()
    repo = MealPrepBatchRepository(os.path.join(tmp, "b.json"))
    for b in sc.get("meal_prep_batches") or []:
        try:
            repo.create(MealPrepBatch(id=b["id"], recipe_id=b["recipe_id"], total_servings=b["total_servings"],
                                      cook_date=b["cook_date"], status=b.get("status", "planned"),
                                      assignments=[BatchAssignment(**a) for a in b["assignments"]]))
        except ValueError as e:
            out.update(code="BATCH_REJECTED", stage="batch_create", detail=str(e)); return out
    active = repo.list_active() if not os.environ.get("ALL_BATCHES") else [b for b in repo._batches if b.status != "orphaned"]
    out["active_batches"] = len(active)
    pins = [ProfilePin(day_index=x["day_index"], slot_index=x["slot_index"], recipe_id=x["recipe_id"]) for x in sc.get("pins") or []]
    up, _ = S._build_user_profile(preq, persisted_pins=pins)
    up.pins = pins
    # API path never sets max_daily_calories; record whether scenario needs it, then set it (planner-direct fidelity)
    out["needs_ceiling"] = p.get("max_daily_calories") is not None
    up.max_daily_calories = None if os.environ.get("API_FIDELITY") else p.get("max_daily_calories")
    recipes = S._filter_recipes_by_ids([data_recipe(r) for r in LIB], preq.recipe_ids)
    pool = convert_recipes(recipes, StubCalc())
    S._attach_canonical_recipe_tags(pool, load_canonical_recipe_tag_slugs(TAGS), load_hard_eligible_recipe_tag_slugs(TAGS))
    prof = convert_profile(up, preq.days)
    prof.batch_locks = planning_batch_locks_from_batches(active)
    t = time.time()
    try:
        res = plan_meals(prof, pool, preq.days, attempt_limit=int(os.environ.get("LIMIT", "50000")))
    except Exception as e:
        out.update(code="EXCEPTION", stage="plan", detail=f"{type(e).__name__}: {e}", tb=traceback.format_exc()[-800:]); return out
    out["secs"] = round(time.time() - t, 2)
    out["success"] = res.success
    out["tc"] = res.termination_code
    out["code"] = "OK" if res.success else res.failure_mode
    out["incomplete"] = res.plan_incomplete_reason
    out["stats"] = {k: v for k, v in (res.stats or {}).items() if k in ("attempts", "backtracks")}
    fails = (res.report or {}).get("failures") or []
    out["report_codes"] = [f.get("code") for f in fails if isinstance(f, dict)]
    out["report_first"] = json.dumps(fails[:2], default=str)[:600]
    out["warnings"] = json.dumps((res.report or {}).get("warnings"), default=str)[:400]
    if res.plan:
        plan = {}
        for a in res.plan:
            plan.setdefault(a.day_index, {})[a.slot_index] = a.recipe_id
        out["plan"] = {str(d): [plan[d][s] for s in sorted(plan[d])] for d in sorted(plan)}
    return out


if __name__ == "__main__":
    only = set(sys.argv[1:])
    results = []
    for sc in SCEN:
        if only and sc["id"] not in only:
            continue
        r = run(sc)
        results.append(r)
        print(r["id"], r.get("code"), r.get("secs"), r.get("stats"), file=sys.stderr)
    out_path = Path(os.environ.get("OUT", REPO / "evaluation/harness/results/results.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(out_path, "w"), indent=1, default=str)
