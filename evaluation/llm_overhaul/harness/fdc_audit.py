"""Phase 6: FoodData Central pipeline audit (offline, read-only).
Usage: PYTHONPATH=. .venv/bin/python evaluation/llm_overhaul/harness/fdc_audit.py
Writes evaluation/llm_overhaul/results/fdc_audit.json and prints a table for adjudication.
"""
import json, os, re, sys
from pathlib import Path
from collections import Counter
REPO = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(REPO)); os.chdir(REPO)
from src.ingestion.ingredient_ranker import _COMPOUND_PRODUCT_KEYWORDS
from src.ingestion.ingredient_normalizer import IngredientNormalizer
from src.providers.api_provider import APIIngredientProvider
from src.ingestion.ingredient_cache import CachedIngredientLookup

rows = []
for f in sorted((REPO / ".cache/ingredients").glob("*.json")):
    e = json.load(open(f)); n = e["nutrition"]; m = n["micronutrients"]; q = e["canonical_name"]; d = e["description"]
    first = re.sub(r"[^a-z ]", "", q.lower()).split()[0] if q.strip() else ""
    flags = []
    if n["calories"] == 0 and (n["protein_g"] + n["fat_g"] + n["carbs_g"]) > 0: flags.append("zero_kcal_with_macros")
    if m.get("vitamin_d_iu", 0) > 500: flags.append("vitamin_d_outlier")
    if e["data_type"] == "Branded": flags.append("branded")
    if any(k in d.lower() for k in _COMPOUND_PRODUCT_KEYWORDS): flags.append("compound_keyword")
    if first and first.rstrip("s") not in d.lower().replace(",", " "): flags.append("first_token_missing_in_description")
    rows.append({"query": q, "file": f.name, "description": d, "data_type": e["data_type"], "kcal": n["calories"], "fat": n["fat_g"], "protein": n["protein_g"], "carbs": n["carbs_g"], "vitd": m.get("vitamin_d_iu", 0), "flags": flags})

# duplicate identities under name variants
norm = IngredientNormalizer(); stems = Counter()
for r in rows:
    s = re.sub(r"\b(\w+?)s\b", r"\1", norm.get_canonical_name(r["query"]))
    s = re.sub(r"\b(drained|unsalted|in unsalted water|raw|plain|nonfat|reduced fat|\d+% fat|lowfat|low fat)\b", "", s).strip()
    stems[s.split(",")[0].strip()] += 1
dups = {k: v for k, v in stems.items() if v > 1}

# provenance: what does the provider expose?
p = APIIngredientProvider(CachedIngredientLookup(cache_dir=".cache/ingredients", usda_client=None))
p.resolve_all(["oats"]); info = p.get_ingredient_info("oats")
provenance_keys = sorted(info.keys())

# volume units in persisted recipes (treated as grams by the calculator)
rec = json.load(open("data/recipes/recipes.json"))["recipes"]
vol = [(r["id"], i["name"], i["quantity"], i["unit"]) for r in rec for i in r["ingredients"] if i["unit"] in ("ml", "cup", "tbsp", "tsp")]

out = {"n_entries": len(rows), "data_types": dict(Counter(r["data_type"] for r in rows)),
       "flag_counts": dict(Counter(f for r in rows for f in r["flags"])),
       "flagged": [r for r in rows if r["flags"]], "duplicate_identities": dups,
       "provider_dict_keys": provenance_keys, "fdc_id_visible_past_provider": "fdc_id" in provenance_keys,
       "volume_unit_lines_in_recipes": len(vol), "volume_unit_examples": vol[:8], "rows": rows}
json.dump(out, open(REPO / "evaluation/llm_overhaul/results/fdc_audit.json", "w"), indent=1)
print(f"{'query':32} {'description':52} {'type':14} kcal   flags")
for r in rows:
    print(f"{r['query'][:32]:32} {r['description'][:52]:52} {r['data_type'][:14]:14} {r['kcal']:6.0f} {','.join(r['flags'])}")
print("\nflag counts:", out["flag_counts"]); print("data types:", out["data_types"]); print("duplicate identities:", dups)
print("provider dict keys:", provenance_keys, "| fdc_id visible:", out["fdc_id_visible_past_provider"])
print("volume-unit ingredient lines in recipes.json:", len(vol), vol[:5])
