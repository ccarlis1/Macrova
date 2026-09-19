"""Phase 7: tagging evaluation. Offline gate checks + LIVE LLM tagging of 6 library recipes (twice).
Usage: PYTHONPATH=. .venv/bin/python evaluation/llm_overhaul/harness/tag_eval.py [--no-live]
Writes evaluation/llm_overhaul/results/tag_eval.json. Uses temp copies; never writes repo tag data.
"""
import argparse, json, os, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(REPO)); os.chdir(REPO)
BENCH = REPO / "evaluation/benchmark"
TMP = Path(tempfile.mkdtemp()); TAGS = TMP / "recipe_tags.json"; shutil.copy(BENCH / "recipe_tags.json", TAGS)
os.environ["NUTRITION_TAG_REPO_PATH"] = str(TAGS)
from src.data_layer.models import Ingredient, Recipe
from src.llm import tag_repository as TR
from src.llm.time_bucket import time_bucket
from src.llm.schemas import RecipeTagsJson, PrepTimeBucket
from src.models.schedule import MealSlot

LIB = {r["id"]: r for r in json.load(open(BENCH / "recipes.json"))["recipes"]}
out = {"offline": {}, "live": None}

# T-01 unknown slug rejected
try:
    MealSlot(index=1, busyness_level=2, required_tag_slugs=["unicorn-friendly"]); out["offline"]["T-01_unknown_slug_rejected"] = False
except Exception as e:
    out["offline"]["T-01_unknown_slug_rejected"] = True
# T-02 proposed LLM tags excluded from hard eligibility (benchmark fixture has proposed tags)
canon = TR.load_canonical_recipe_tag_slugs(str(TAGS)); hard = TR.load_hard_eligible_recipe_tag_slugs(str(TAGS))
raw = json.load(open(TAGS))["tags_by_id"]
proposed = {rid: [s for s, m in (t.get("tag_metadata") or {}).items() if m.get("source") == "llm" and m.get("eligibility") == "proposed"] for rid, t in raw.items()}
proposed = {k: v for k, v in proposed.items() if v}
leak = [(rid, s) for rid, slugs in proposed.items() for s in slugs if s in hard.get(rid, set())]
out["offline"]["T-02_proposed_tags_in_fixture"] = sum(len(v) for v in proposed.values()); out["offline"]["T-02_proposed_leaked_into_hard"] = leak
# T-03 alias
out["offline"]["T-03_alias_batch_cook"] = TR.resolve("batch-cook", str(TAGS)).slug
# T-04 destructive upsert
before = set(TR.load_recipe_tags(str(TAGS)).keys())
TR.upsert_recipe_tags(str(TAGS), {"llm_new": RecipeTagsJson(cuisine="anything", cost_level="cheap", prep_time_bucket="snack", dietary_flags=[])})
after = set(TR.load_recipe_tags(str(TAGS)).keys())
out["offline"]["T-04_entries_before_after"] = [len(before), len(after)]; out["offline"]["T-04_curated_entries_lost"] = len(before - after)
shutil.copy(BENCH / "recipe_tags.json", TAGS)  # restore temp copy for live part
# free-string cuisine accepted by schema
out["offline"]["T-07_free_cuisine_schema_accepts"] = RecipeTagsJson(cuisine="martian fusion 2000", cost_level="cheap", prep_time_bucket="snack", dietary_flags=[]).cuisine

MEAT = ("beef", "chicken", "turkey", "salami", "tuna", "salmon", "tilapia", "roast beef", "burger", "thigh")
DAIRY = ("yogurt", "cheese", "milk", "cottage", "whey", "feta", "parmesan", "cheddar", "butter")
GLUTEN = ("bread", "pasta", "sourdough", "krispies", "tortillas")
def det_bucket(minutes):
    return "snack" if minutes <= 5 else "quick_meal" if minutes <= 15 else "weeknight_meal" if minutes <= 30 else "meal_prep"
def contradictions(rid, flags):
    names = " ".join(i["name"] for i in LIB[rid]["ingredients"]); c = []
    if "vegan" in flags and (any(k in names for k in MEAT) or any(k in names for k in DAIRY)): c.append("vegan_with_animal_products")
    if "vegetarian" in flags and any(k in names for k in MEAT): c.append("vegetarian_with_meat")
    if "dairy_free" in flags and any(k in names for k in DAIRY): c.append("dairy_free_with_dairy")
    if "gluten_free" in flags and any(k in names for k in GLUTEN): c.append("gluten_free_with_gluten_source")
    return c

ap = argparse.ArgumentParser(); ap.add_argument("--no-live", action="store_true"); a = ap.parse_args()
if not a.no_live:
    for line in (REPO / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    from src.config.llm_settings import load_llm_settings; from src.llm.client import LLMClient; from src.llm.recipe_tagger import tag_recipes
    client = LLMClient(load_llm_settings())
    ids = ["bk_tofu_scramble", "ln_turkey_sandwich", "dn_salmon_potatoes", "sn_yogurt_honey", "dn_bean_quesadilla", "hc_mass_gainer"]
    recs = [Recipe(id=r, name=LIB[r]["name"], ingredients=[Ingredient(i["name"], float(i["quantity"]), "g") for i in LIB[r]["ingredients"]], cooking_time_minutes=LIB[r]["cooking_time_minutes"], instructions=["Cook."]) for r in ids]
    runs = [tag_recipes(client, recs, tag_repo_path=str(TAGS)), tag_recipes(client, recs, tag_repo_path=str(TAGS))]
    live = {"tagged_count": [len(r) for r in runs], "per_recipe": {}}
    agree = 0; bucket_ok = 0; contra = 0; cuisines = set()
    for r in recs:
        t1 = runs[0].get(r.id); t2 = runs[1].get(r.id)
        if t1 is None: live["per_recipe"][r.id] = "dropped"; continue
        flags = [f.value for f in t1.dietary_flags]; cz = contradictions(r.id, flags); contra += len(cz)
        bk = t1.prep_time_bucket.value; ok = bk == det_bucket(r.cooking_time_minutes); bucket_ok += int(ok); cuisines.add(t1.cuisine)
        same = (t2 is not None and t1.model_dump() == t2.model_dump()); agree += int(same)
        proposed = {s: (m.source, m.eligibility) for s, m in (t1.tag_metadata or {}).items()}
        live["per_recipe"][r.id] = {"cook_min": r.cooking_time_minutes, "bucket": bk, "deterministic_bucket": det_bucket(r.cooking_time_minutes), "bucket_ok": ok, "cuisine": t1.cuisine, "cost": t1.cost_level.value, "flags": flags, "contradictions": cz, "run2_same": same, "run2_cuisine": t2.cuisine if t2 else None, "slugs_by_type": t1.tag_slugs_by_type, "proposed_metadata": proposed}
    from src.llm.recipe_tagger import CUISINE_VOCABULARY
    live.update(T05_bucket_agreement=f"{bucket_ok}/{len(recs)}", T06_contradictions=contra, T07_distinct_cuisine_strings=sorted(cuisines),
                T07_all_in_vocabulary=all(c in CUISINE_VOCABULARY for c in cuisines), T08_determinism=f"{agree}/{len(recs)}",
                proposed_slugs_all_quarantined=all(v == ("llm", "proposed") for r in live["per_recipe"].values() if isinstance(r, dict) for v in r["proposed_metadata"].values()))
    out["live"] = live
json.dump(out, open(REPO / f"evaluation/llm_overhaul/results/tag_eval{os.environ.get('SUFFIX', '')}.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)); shutil.rmtree(TMP, ignore_errors=True)
