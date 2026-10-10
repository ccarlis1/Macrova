"""Phase 5 + Phase 8: recovery-loop evaluation against the REAL orchestrator with a scripted LLM
and the real cache-only USDA provider (no network). Optional live sub-experiment with --live.

Usage: PYTHONPATH=. .venv/bin/python evaluation/llm_overhaul/harness/run_recovery.py [--live] [--only R-02 ...]
Writes evaluation/llm_overhaul/results/recovery_results.json. Never writes to repo data:
recipes.json, feedback cache and ingredient cache dir are all temporary copies.
"""
import argparse, copy, json, os, shutil, sys, tempfile, traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); os.chdir(REPO)
BENCH = REPO / "evaluation/benchmark"
os.environ["NUTRITION_TAG_REPO_PATH"] = str(BENCH / "recipe_tags.json")
TMP_ROOT = Path(tempfile.mkdtemp(prefix="llm_overhaul_"))
CACHE_DIR = TMP_ROOT / "cache"; shutil.copytree(REPO / ".cache/ingredients", CACHE_DIR)   # sandboxed copy
os.environ["LLM_FEEDBACK_CACHE_PATH"] = str(TMP_ROOT / "feedback_cache.json")

from src.data_layer.models import Ingredient, Recipe, ProfilePin
from src.data_layer.recipe_db import RecipeDB
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.llm.client import LLMClientError
from src.llm.recipe_generator import RecipeGenerationError
from src.llm.feedback_cache import DeterministicCacheMissError
from src.llm.tag_repository import load_canonical_recipe_tag_slugs, load_hard_eligible_recipe_tag_slugs
from src.nutrition.calculator import NutritionCalculator
from src.planning import orchestrator as O
from src.planning.converters import convert_recipes, extract_ingredient_names
from src.planning.phase0_models import MealSlot, PlanningBatchLock, PlanningUserProfile
from src.planning.planner import plan_meals
from src.providers.api_provider import APIIngredientProvider
from src.api.server import _attach_canonical_recipe_tags

LIB = {r["id"]: r for r in json.load(open(BENCH / "recipes.json"))["recipes"]}
TAGS = str(BENCH / "recipe_tags.json")


def provider():
    return APIIngredientProvider(CachedIngredientLookup(cache_dir=str(CACHE_DIR), usda_client=None))


def data_recipe(rid, cook=None):
    r = LIB[rid]
    return Recipe(id=rid, name=r["name"], ingredients=[Ingredient(i["name"], float(i["quantity"]), i["unit"]) for i in r["ingredients"]],
                  cooking_time_minutes=cook if cook is not None else r["cooking_time_minutes"], instructions=["Cook."])


def planning_pool(rids, cook_override=None):
    recs = [data_recipe(r, (cook_override or {}).get(r)) for r in rids]
    p = provider(); p.resolve_all(extract_ingredient_names(recs))
    pool = convert_recipes(recs, NutritionCalculator(p))
    _attach_canonical_recipe_tags(pool, load_canonical_recipe_tag_slugs(TAGS), load_hard_eligible_recipe_tag_slugs(TAGS))
    return pool


def draft_of(rid, instructions=("Cook.",), rename=None, cook=None):
    r = LIB[rid]
    return {"name": rename or r["name"], "ingredients": [{"name": i["name"], "quantity": float(i["quantity"]), "unit": "g"} for i in r["ingredients"]],
            "instructions": list(instructions), "cooking_time_minutes": int(cook if cook is not None else r["cooking_time_minutes"])}


def sums(pool_recipes):
    n = [r.nutrition for r in pool_recipes]
    return dict(kcal=sum(x.calories for x in n), p=sum(x.protein_g for x in n), f=sum(x.fat_g for x in n), c=sum(x.carbs_g for x in n),
                iron=sum(x.micronutrients.iron_mg for x in n))


def profile_for(day_recipes, days=1, slots=None, busyness=4, micro=None, excl=(), required=None, pins=None, carbs_override=None, kcal_override=None):
    s = sums(day_recipes); n = slots or len(day_recipes)
    sched = []
    for d in range(days):
        row = []
        for i in range(n):
            b = busyness[i] if isinstance(busyness, list) else busyness
            row.append(MealSlot(time="12:00", busyness_level=b, meal_type="lunch", required_tag_slugs=(required or {}).get(i)))
        sched.append(row)
    return PlanningUserProfile(daily_calories=int(kcal_override or round(s["kcal"])), daily_protein_g=round(s["p"], 1),
                               daily_fat_g=(round(s["f"] * 0.85, 1), round(s["f"] * 1.15, 1)),
                               daily_carbs_g=carbs_override if carbs_override is not None else round(s["c"], 1),
                               schedule=sched, excluded_ingredients=list(excl), liked_foods=[], pinned_assignments=pins or {},
                               micronutrient_targets=micro or {})


class ScriptedLLM:
    """Returns the scripted draft list per call; pads/truncates to the requested count. Records contexts."""
    _settings = None
    def __init__(self, per_call):
        self.per_call = list(per_call); self.calls = []
    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        ctx = user_prompt.split("Generation context (JSON): ", 1)[1].split("\n")[0] if "Generation context" in user_prompt else ""
        count = int(user_prompt.split("generate exactly ")[1].split(" ")[0])
        drafts = self.per_call[min(len(self.calls), len(self.per_call) - 1)] if self.per_call else []
        self.calls.append({"count": count, "context": json.loads(ctx) if ctx else None})
        if drafts == "GARBAGE":
            return {"drafts": []}
        drafts = list(drafts)
        while drafts and len(drafts) < count: drafts.append(drafts[-1])
        return {"drafts": drafts[:count]}


FIT = ["bk_yogurt_berry_bowl", "ln_chickpea_salad", "dn_tilapia_rice"]      # forms a valid day by construction
DISTRACT = ["sn_whey_water", "sn_chia_seed_water", "sn_edamame_cup", "sn_carrots_almond_butter"]   # small snacks: cannot reach the FIT day window


def unheld_tag(pool_ids):
    hard = load_hard_eligible_recipe_tag_slugs(TAGS)
    held = set().union(*(hard.get(r, set()) for r in pool_ids))
    for cand in ("post-workout", "kid-friendly", "reheats-well", "portable", "low-carb"):
        if cand not in held: return cand
    raise RuntimeError("no unheld tag")


def cases():
    C = []
    def add(id, title, expect, help_label, build):
        C.append(dict(id=id, title=title, expected_terminal=expect, recipes_could_help=help_label, build=build))

    add("R-01", "fitting pool, no gap", "SUCCESS", "n/a", lambda: dict(pool_ids=FIT + DISTRACT, day=FIT, drafts=[[draft_of("sn_banana_pb")]]))
    add("R-02", "one recipe missing; LLM supplies it (resolvable)", "SUCCESS", "yes",
        lambda: dict(pool_ids=FIT[:2] + DISTRACT, day=FIT, drafts=[[draft_of("dn_tilapia_rice")]]))
    add("R-03", "one missing; LLM names unresolvable ingredients", "INVALID_RECOVERY_OUTPUT", "yes",
        lambda: dict(pool_ids=FIT[:2] + DISTRACT, day=FIT, drafts=[[{"name": "Dragonfruit tilapia", "ingredients": [{"name": "tilapia", "quantity": 150.0, "unit": "g"}, {"name": "dragonfruit granola", "quantity": 200.0, "unit": "g"}, {"name": "moon salt", "quantity": 5.0, "unit": "g"}], "instructions": ["Cook."]}]]))
    add("R-04", "one recipe, three slots (HC-2); LLM supplies two", "SUCCESS", "yes",
        lambda: dict(pool_ids=FIT[:1] + DISTRACT, day=FIT, drafts=[[draft_of("ln_chickpea_salad"), draft_of("dn_tilapia_rice")]]))
    add("R-05", "negative derived carbs (infeasible by construction)", "UNRECOVERABLE_INFEASIBILITY", "no",
        lambda: dict(pool_ids=FIT + DISTRACT, day=FIT, carbs=-10.0, drafts=[[draft_of("dn_tilapia_rice"), draft_of("sn_banana_pb")]]))
    add("R-06", "pool emptied by a user tag filter; LLM drafts fit", "UNRECOVERABLE_INFEASIBILITY", "no (would bypass filter)",
        lambda: dict(pool_ids=[], day=FIT, drafts=[[draft_of(r) for r in FIT]]))
    add("R-07", "required tag 'vegan' on slot 1; pool lacks it; drafts untagged", "UNRECOVERABLE_INFEASIBILITY", "no (needs tag, not recipe)",
        lambda: dict(pool_ids=FIT + DISTRACT, day=FIT, required={1: [unheld_tag(FIT + DISTRACT)]}, drafts=[[draft_of("dn_tofu_stir_fry")], [draft_of("ln_tofu_quinoa_salad")], [draft_of("bk_tofu_scramble")]]))
    add("R-08", "micronutrient (iron) structural gap; LLM supplies iron-rich fitting recipe", "SUCCESS", "yes",
        lambda: dict(pool_ids=["bk_yogurt_berry_bowl", "sn_yogurt_honey"] + ["sn_whey_water", "sn_chia_seed_water"], day=["bk_yogurt_berry_bowl", "sn_yogurt_honey", "ln_tofu_quinoa_salad"], iron_from_day=True, drafts=[[draft_of("ln_tofu_quinoa_salad")]]))
    add("R-09", "slot 0 needs <=5 min; pool all slow; LLM draft claims its real 3-minute time", "SUCCESS", "yes (only with a real quick recipe)",
        lambda: dict(pool_ids=FIT[1:] + DISTRACT, day=FIT, busyness=[1, 3, 3], cook_override={r: 20 for r in FIT[1:] + DISTRACT}, drafts=[[draft_of("bk_yogurt_berry_bowl", instructions=["Mix."])]]))
    add("R-10", "batch lock recipe exceeds slot cook time", "UNRECOVERABLE_INFEASIBILITY", "no",
        lambda: dict(pool_ids=FIT + DISTRACT, day=FIT, busyness=[1, 2, 2], cook_override={"bk_yogurt_berry_bowl": 20}, batch_lock=("bk_yogurt_berry_bowl", 0, 0), drafts=[[draft_of("sn_banana_pb")]]))
    add("R-11", "feasible instance hits attempt cap (FM-5)", "UNRECOVERABLE_INFEASIBILITY", "no",
        lambda: dict(pool_ids=FIT + DISTRACT, day=FIT, attempt_limit=1, drafts=[[draft_of("sn_banana_pb")]]))
    add("R-12", "LLM returns garbage", "DATA_SOURCE_FAILURE", "n/a",
        lambda: dict(pool_ids=FIT[:2] + DISTRACT, day=FIT, drafts=["GARBAGE"]))
    add("R-13", "'peanuts' excluded; draft with peanut butter fits", "INVALID_RECOVERY_OUTPUT", "yes (with a safe recipe)",
        lambda: dict(pool_ids=["bk_yogurt_berry_bowl", "ln_chickpea_salad"] + DISTRACT, day=["bk_yogurt_berry_bowl", "ln_chickpea_salad", "sn_banana_pb"], excl=["peanuts"], drafts=[[draft_of("sn_banana_pb")]]))
    add("R-14", "LLM re-proposes the same non-fitting draft", "INVALID_RECOVERY_OUTPUT", "no (as offered)",
        lambda: dict(pool_ids=FIT[:2] + DISTRACT, day=FIT, drafts=[[draft_of("sn_krispie_banana")], [draft_of("sn_krispie_banana")], [draft_of("sn_krispie_banana")]]))
    add("R-15", "candidate conversion fails -> typed error, pool untouched", "SYSTEM_ERROR", "yes",
        lambda: dict(pool_ids=FIT[:2] + DISTRACT, day=FIT, drafts=[[draft_of("dn_tilapia_rice")]], force_fallback=True, disk_has_all=True))
    return C


def classify(rec):
    if rec.get("outcome") and rec["outcome"].get("state"):
        st = rec["outcome"]["state"]
        return "UNRECOVERABLE_INFEASIBILITY (typed: %s)" % rec["outcome"].get("reason") if st == "UNRECOVERABLE_INFEASIBILITY" else st
    if rec.get("exception"):
        et = rec["exception"]["type"]
        return "DATA_SOURCE_FAILURE" if et in ("RecipeGenerationError", "LLMClientError", "LLMResponseFormatError", "LLMInternalError", "DeterministicCacheMissError") else "SYSTEM_ERROR"
    if rec["final_success"]:
        return "SUCCESS"
    if rec["llm_calls"] == 0:
        return "UNRECOVERABLE_INFEASIBILITY (code-declared)"
    hist = rec["history"]
    if hist and hist[-1]["status"] == "abort":
        return "NO_USEFUL_RECOVERY_FOUND" if any(h["accepted"] for h in hist) else "INVALID_RECOVERY_OUTPUT"
    if not any(h["accepted"] for h in hist):
        return "INVALID_RECOVERY_OUTPUT"
    return "RECOVERY_LIMIT_REACHED"


def run_case(c, live_client=None):
    spec = c["build"](); rec = {"id": c["id"], "title": c["title"], "expected_terminal": c["expected_terminal"], "recipes_could_help": c["recipes_could_help"]}
    tmp = Path(tempfile.mkdtemp(dir=TMP_ROOT)); recipes_path = tmp / "recipes.json"
    os.environ["LLM_FEEDBACK_CACHE_PATH"] = str(tmp / "feedback_cache.json")   # isolate the feedback cache per case
    disk_ids = [r for r in LIB if r not in ("dn_tilapia_rice",)] if spec.get("disk_has_all") else spec["pool_ids"]
    json.dump({"recipes": [{"id": r, "name": LIB[r]["name"], "ingredients": [{"name": i["name"], "quantity": i["quantity"], "unit": "g"} for i in LIB[r]["ingredients"]], "cooking_time_minutes": LIB[r]["cooking_time_minutes"], "instructions": ["Cook."]} for r in disk_ids]}, open(recipes_path, "w"))
    pool = planning_pool(spec["pool_ids"], spec.get("cook_override"))
    day_pool = planning_pool(spec["day"], spec.get("cook_override"))
    micro = None
    if spec.get("iron_from_day"):
        micro = {"iron_mg": round(sums(day_pool)["iron"] * 0.95, 2)}
    prof = profile_for(day_pool, busyness=spec.get("busyness", 4), micro=micro, excl=spec.get("excl", ()), required=spec.get("required"), carbs_override=spec.get("carbs"))
    if spec.get("batch_lock"):
        rid, d, s = spec["batch_lock"]; prof.batch_locks = [PlanningBatchLock(batch_id="b1", recipe_id=rid, day_index=d, slot_index=s, servings=1.0)]
    llm = ScriptedLLM(spec["drafts"])
    planner_runs = []; real_plan = O.plan_meals
    def traced_plan(profile, recipe_pool, days, **kw):
        r = real_plan(profile, recipe_pool, days, attempt_limit=spec.get("attempt_limit", 50000))
        planner_runs.append({"pool_size": len(recipe_pool), "pool_ids": sorted(x.id for x in recipe_pool), "code": "OK" if r.success else r.failure_mode,
                             "tagged": sum(1 for x in recipe_pool if x.canonical_tag_slugs), "hard_attr": sum(1 for x in recipe_pool if x.hard_eligible_tag_slugs is not None)})
        return r
    O.plan_meals = traced_plan
    orig_append = getattr(O, "_candidate_planning_recipe", None)
    if spec.get("force_fallback") and orig_append is not None:
        O._candidate_planning_recipe = lambda recipe, provider: (_ for _ in ()).throw(RuntimeError("forced"))
    cache_before = len(list(CACHE_DIR.glob("*.json")))
    try:
        result = O.plan_with_llm_feedback(prof, pool, 1, recipes_path=str(recipes_path), client=llm, provider=provider(), use_feedback_cache=True, force_live_generation=False)
        rec["exception"] = None; rec["final_success"] = result.success; rec["final_code"] = "OK" if result.success else result.failure_mode
        rec["history"] = (result.stats or {}).get("llm_feedback_attempts", [])
        rec["outcome"] = (result.report or {}).get("llm_recovery")
        rec["plan"] = [a.recipe_id for a in (result.plan or [])] if result.success else None
    except Exception as e:
        rec["exception"] = {"type": type(e).__name__, "msg": str(e)[:200]}; rec["final_success"] = False; rec["final_code"] = None; rec["history"] = []; rec["plan"] = None
    finally:
        O.plan_meals = real_plan
        if orig_append is not None: O._candidate_planning_recipe = orig_append
    rec["initial_code"] = planner_runs[0]["code"] if planner_runs else None
    rec["planner_runs"] = len(planner_runs); rec["llm_calls"] = len(llm.calls); rec["llm_contexts"] = [x["context"] for x in llm.calls]
    rec["pool_trace"] = planner_runs
    persisted = [r for r in json.load(open(recipes_path))["recipes"] if r["id"].startswith("llm_")]
    rec["persisted_llm_recipes"] = [(r["id"], r["name"], r["cooking_time_minutes"], [i["name"] for i in r["ingredients"] if i["unit"] == "to taste"]) for r in persisted]
    rec["persisted_provenance"] = [r.get("provenance", {}).get("source") for r in persisted]
    rec["cache_files_written"] = len(list(CACHE_DIR.glob("*.json"))) - cache_before
    rec["feedback_cache_keys"] = len(json.load(open(os.environ["LLM_FEEDBACK_CACHE_PATH"])).get("entries_by_key", {})) if Path(os.environ["LLM_FEEDBACK_CACHE_PATH"]).exists() else 0
    flags = []
    if rec["plan"] and spec.get("excl"):
        for rid in rec["plan"]:
            names = [i["name"] for i in LIB[rid]["ingredients"]] if rid in LIB else [i["name"] for r in persisted if r["id"] == rid for i in r["ingredients"]]
            if any(any(e in n for n in names) for e in [x.rstrip("s") for x in spec["excl"]]): flags.append(f"plan contains excluded-class ingredient via {rid}")
    if rec["plan"] and c["id"] == "R-06": flags.append("success bypassed the user's tag filter")
    if rec["plan"] and c["id"] == "R-09":
        for p in persisted:
            lib = next((LIB[k]["cooking_time_minutes"] for k in LIB if LIB[k]["name"] == p["name"]), None)
            if lib is not None and p["cooking_time_minutes"] != lib and p.get("provenance", {}).get("cooking_time_source") != "llm_claimed":
                flags.append("success relies on fabricated cook time")
    if c["id"] == "R-15" and len(planner_runs) > 1 and planner_runs[-1]["pool_size"] > len(spec["pool_ids"]) + 1: flags.append(f"retry pool grew to {planner_runs[-1]['pool_size']} (requested subset {len(spec['pool_ids'])})")
    if len(planner_runs) > 1 and planner_runs[0]["hard_attr"] and planner_runs[-1]["hard_attr"] < planner_runs[-1]["pool_size"]: flags.append("retry pool lost hard-eligible tag attributes on some recipes")
    if persisted and not rec["final_success"]: flags.append(f"{len(persisted)} recipe(s) persisted although the request failed")
    if any(t for _, _, _, t in rec["persisted_llm_recipes"]): flags.append("persisted recipe has demoted (to-taste) ingredients")
    rec["intent_violations"] = flags
    rec["observed_terminal"] = classify(rec)
    if live_client is not None and c["id"] in ("R-02", "R-05", "R-07", "R-08", "R-13") and llm.calls:
        rec["live"] = live_probe(live_client, llm.calls[0]["context"], spec)
    return rec


def live_probe(client, context, spec):
    from src.llm.recipe_generator import generate_recipe_drafts
    out = {"context_sent": context}
    try:
        drafts = generate_recipe_drafts(client, context=context, count=3)
    except Exception as e:
        return {**out, "error": f"{type(e).__name__}: {e}"[:200], "details": getattr(e, "details", None), "raw": (getattr(client, "_last_model_content_text", "") or "")[:1200]}
    p = provider(); names = []
    for d in drafts:
        for i in d.ingredients:
            if i.unit != "to taste": names.append(i.name)
    resolvable = 0
    for n in set(names):
        try:
            p.resolve_all([n]); resolvable += 1
        except Exception:
            pass
    excl = [x.rstrip("s") for x in spec.get("excl", ())]
    out.update(drafts=[{"name": d.name, "ingredients": [i.name for i in d.ingredients], "n_instructions": len(d.instructions)} for d in drafts],
               distinct_ingredient_names=len(set(names)), offline_resolvable=resolvable,
               excluded_hits=[n for n in names if any(e in n for e in excl)] if excl else [])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--only", nargs="*"); a = ap.parse_args()
    live_client = None
    if a.live:
        for line in (REPO / ".env").read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        from src.config.llm_settings import load_llm_settings; from src.llm.client import LLMClient
        live_client = LLMClient(load_llm_settings())
    results = []
    for c in cases():
        if a.only and c["id"] not in a.only: continue
        try:
            r = run_case(c, live_client)
        except Exception as e:
            r = {"id": c["id"], "harness_error": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1200:]}
        results.append(r)
        print(r["id"], r.get("initial_code"), "->", r.get("final_code"), "|", r.get("observed_terminal"), "| llm", r.get("llm_calls"), "| flags", r.get("intent_violations"), r.get("harness_error", ""), file=sys.stderr)
    json.dump(results, open(REPO / f"evaluation/llm_overhaul/results/recovery_results{os.environ.get('SUFFIX', '')}.json", "w"), indent=1, default=str)
    print(json.dumps([{k: r.get(k) for k in ("id", "initial_code", "final_code", "expected_terminal", "observed_terminal", "llm_calls", "planner_runs", "persisted_llm_recipes", "persisted_provenance", "cache_files_written", "intent_violations")} for r in results], indent=1, default=str))
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
