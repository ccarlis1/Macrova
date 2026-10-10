"""Phase 4: natural-language -> PlannerConfigJson benchmark (LIVE LLM).

Usage (repo root):  PYTHONPATH=. .venv/bin/python evaluation/llm_overhaul/harness/run_nl_benchmark.py [--runs 2]
Writes evaluation/llm_overhaul/results/nl_results.json and prints a metric summary.
"""
import argparse, json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); os.chdir(REPO)
for line in (REPO / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("="); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.config.llm_settings import load_llm_settings
from src.llm.client import LLMClient
from src.llm.constraint_parser import parse_nl_config, PlannerConfigParsingError
from src.data_layer.user_profile import user_profile_from_planner_config, PlannerConfigMappingError

HERE = Path(__file__).resolve().parent
SPEC = json.load(open(HERE / "nl_cases.json"))
DEFAULTS = SPEC["documented_defaults"]
# After Stage 8 every constraint class is representable; keep the pre-overhaul set to report structural omissions
# under the OLD schema for comparison, but score against the NEW schema.
UNREPRESENTABLE_BEFORE = {"allergies", "dislikes", "max_calories", "micronutrients", "fat_min", "fat_max", "diet", "liked", "tau"}
UNREPRESENTABLE = set()
REPRESENTABLE = {"days", "meals_per_day", "calories", "protein", "cuisine", "budget", "workouts", "busyness", "meals_by_day", "required_tags",
                 "allergies", "dislikes", "max_calories", "micronutrients", "fat_min", "fat_max", "diet", "liked", "tau"}


def close(a, b, tol=0.02):
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
    except Exception:
        return False


def _norm_list(xs):
    return sorted({" ".join(w.rstrip("s") for w in str(x).lower().split()) for x in (xs or [])})


def extract(cfg):
    d = cfg.model_dump(mode="json")
    out = {"days": d["days"], "meals_per_day": d["meals_per_day"], "calories": d["targets"]["calories"],
           "protein": d["targets"]["protein"], "cuisine": [c.lower() for c in d["preferences"]["cuisine"]],
           "budget": d["preferences"]["budget"], "schedule_days": d.get("schedule_days"),
           "stated_fields": d.get("stated_fields") or []}
    c = d.get("constraints") or {}
    out["allergies"] = _norm_list(c.get("allergies")); out["dislikes"] = _norm_list(c.get("disliked_foods")); out["liked"] = _norm_list(c.get("liked_foods"))
    out["max_calories"] = c.get("max_daily_calories"); out["fat_min"] = c.get("fat_g_min"); out["fat_max"] = c.get("fat_g_max")
    out["micronutrients"] = c.get("micronutrient_goals") or None; out["diet"] = _norm_list(c.get("dietary_flags")); out["tau"] = c.get("micronutrient_weekly_min_fraction")
    sd = d.get("schedule_days") or []
    if sd:
        out["workouts"] = sorted(w["after_meal_index"] for w in sd[0].get("workouts", []))
        out["busyness"] = [m["busyness_level"] for m in sd[0]["meals"]]
        out["meals_by_day"] = [len(x["meals"]) for x in sd]
        out["required_tags"] = {str(m["index"]): m.get("required_tag_slugs") for m in sd[0]["meals"] if m.get("required_tag_slugs")}
    return out


def score(case, parsed, err):
    stated = case["stated"]; s = {"id": case["id"], "cat": case["cat"], "error": err}
    if err is not None:
        s["invalid"] = True; s["expected_invalid"] = bool(case.get("expect_invalid"))
        return s
    s["invalid"] = False; s["expected_invalid"] = bool(case.get("expect_invalid"))
    got = parsed
    field_ok, omitted_model, omitted_struct, misplaced = {}, [], [], []
    for k, v in stated.items():
        if k in UNREPRESENTABLE:
            omitted_struct.append(k)
            # did the model smuggle it into cuisine?
            words = []
            if isinstance(v, list): words = [str(x).lower() for x in v]
            elif isinstance(v, dict): words = [str(x).lower() for x in v]
            elif k == "diet": words = [str(v).lower()]
            if any(any(w.split()[0] in c for c in got["cuisine"]) for w in words if w):
                misplaced.append(k)
            continue
        if k in ("calories", "protein", "max_calories", "fat_min", "fat_max", "tau"):
            field_ok[k] = close(got.get(k), v) if got.get(k) is not None else False
            if got.get(k) is None: omitted_model.append(k)
        elif k in ("allergies", "dislikes", "liked", "diet"):
            exp = _norm_list(v if k != "diet" else [x.replace("_", " ").replace("-", " ") for x in v])
            gotv = _norm_list([x.replace("_", " ").replace("-", " ") for x in got.get(k, [])])
            field_ok[k] = (exp == gotv)
            if not gotv: omitted_model.append(k)
        elif k == "micronutrients":
            field_ok[k] = (got.get(k) or {}) == {kk: float(vv) for kk, vv in v.items()}
            if not got.get(k): omitted_model.append(k)
        elif k == "cuisine":
            field_ok[k] = set(x.lower() for x in v) == set(got["cuisine"])
        elif k in ("workouts", "busyness", "meals_by_day", "required_tags"):
            field_ok[k] = (got.get(k) == v)
            if got.get(k) is None: omitted_model.append(k)
        else:
            field_ok[k] = (got.get(k) == v)
    # invented / defaulted (model-reported stated_fields, when present, is the arbiter)
    invented, defaulted = [], []
    reported = got.get("stated_fields") or []
    sf_map = {"days": "days", "meals_per_day": "meals_per_day", "calories": "calories", "protein": "protein", "budget": "budget", "cuisine": "cuisine"}
    s["stated_fields_reported"] = bool(reported)
    s["stated_fields_precision"] = None
    if reported:
        truth = set()
        for k in stated:
            truth.add({"dislikes": "disliked_foods", "liked": "liked_foods", "max_calories": "max_daily_calories", "micronutrients": "micronutrient_goals",
                       "fat_min": "fat_range", "fat_max": "fat_range", "diet": "dietary_flags", "tau": "micronutrient_weekly_min_fraction",
                       "workouts": "schedule_days", "busyness": "schedule_days", "meals_by_day": "schedule_days", "required_tags": "schedule_days"}.get(k, k))
        rep = set(reported)
        s["stated_fields_precision"] = round(len(rep & truth) / max(1, len(rep)), 2)
        s["stated_fields_recall"] = round(len(rep & truth) / max(1, len(truth)), 2)
    s["schedule_dropped_by_mapping"] = bool(got.get("schedule_days")) and bool(reported) and "schedule_days" not in reported
    for k in ("days", "calories", "protein", "budget", "cuisine"):
        if k in stated or k in case.get("ambiguous", []):
            continue
        val = got.get(k)
        if k == "cuisine":
            if val: invented.append(k)
        elif val == DEFAULTS[k]:
            defaulted.append(k)
        else:
            invented.append(f"{k}={val}")
    if "meals_per_day" not in stated and "meals_by_day" not in stated and "meals_per_day" not in case.get("ambiguous", []):
        (defaulted if got["meals_per_day"] in (1, 3) else invented).append(f"meals_per_day={got['meals_per_day']}")
    if got.get("schedule_days") and not any(k in stated for k in ("workouts", "busyness", "meals_by_day", "required_tags")):
        invented.append("schedule_days" + (" (dropped by mapping)" if s["schedule_dropped_by_mapping"] else " (KEPT)"))
    # hard/soft at system level
    hs = []
    # After Stage 8: NL cuisine is never a hard filter; budget only stands in for fat when fat is unstated.
    if "fat_min" in stated and not (got.get("fat_min") is not None or got.get("fat_max") is not None):
        hs.append("stated fat range not captured -> budget-derived range used")
    if "diet" in stated and any(d in got["cuisine"] for d in _norm_list(v for v in stated["diet"])):
        hs.append("diet placed in cuisine (soft) instead of dietary_flags (hard)")
    s.update(field_ok=field_ok, omitted_model=omitted_model, omitted_structural=omitted_struct, misplaced=misplaced,
             invented=invented, defaulted=defaulted, hard_soft=hs, ambiguous_values={k: got.get(k) for k in case.get("ambiguous", [])})
    return s


def run_once(client, cases):
    out = []
    for c in cases:
        t = time.time(); err = None; parsed = None; raw = None; mapping = None
        try:
            cfg = parse_nl_config(client, c["prompt"]); raw = cfg.model_dump(mode="json"); parsed = extract(cfg)
            try:
                p = user_profile_from_planner_config(cfg)
                mapping = {"fat": list(p.daily_fat_g), "carbs": p.daily_carbs_g, "allergies": p.allergies, "dislikes": p.disliked_foods,
                           "max_calories": p.max_daily_calories, "micro": p.daily_micronutrient_targets, "tau": p.micronutrient_weekly_min_fraction,
                           "schedule": p.schedule, "schedule_days_kept": p.schedule_days is not None}
            except PlannerConfigMappingError as e:
                err = f"MAPPING:{e.error_code}"
        except PlannerConfigParsingError as e:
            err = f"PARSE:{e.error_code}:{e.details.get('field_errors', '')[:3]}"
        except Exception as e:
            err = f"OTHER:{type(e).__name__}:{e}"
        sc = score(c, parsed, err); sc["raw"] = raw; sc["mapping"] = mapping; sc["secs"] = round(time.time() - t, 2)
        out.append(sc); print(c["id"], "ERR" if err else "ok", err or "", file=sys.stderr)
    return out


def summarize(runs):
    r = runs[0]; n = len(r)
    valid = [x for x in r if not x["invalid"]]
    fields = {}
    for x in valid:
        for k, ok in x["field_ok"].items():
            fields.setdefault(k, [0, 0]); fields[k][0] += int(ok); fields[k][1] += 1
    summ = {
        "n_cases": n,
        "field_accuracy": {k: f"{a}/{b}" for k, (a, b) in sorted(fields.items())},
        "cases_with_structural_omission": sum(1 for x in valid if x["omitted_structural"]),
        "structural_omissions_total": sum(len(x["omitted_structural"]) for x in valid),
        "model_omissions_total": sum(len(x["omitted_model"]) for x in valid),
        "misplaced_into_cuisine": [(x["id"], x["misplaced"]) for x in valid if x["misplaced"]],
        "cases_with_invented_nondefault": [(x["id"], x["invented"]) for x in valid if x["invented"]],
        "cases_with_documented_defaults": sum(1 for x in valid if x["defaulted"]),
        "hard_soft_misclassifications": sum(len(x["hard_soft"]) for x in valid),
        "structural_omissions_under_old_schema": sum(1 for x in valid for k in SPEC["cases"][[c["id"] for c in SPEC["cases"]].index(x["id"])]["stated"] if k in UNREPRESENTABLE_BEFORE),
        "stated_fields_reported_rate": f"{sum(1 for x in valid if x.get('stated_fields_reported'))}/{len(valid)}",
        "stated_fields_precision_mean": round(sum(x['stated_fields_precision'] for x in valid if x.get('stated_fields_precision') is not None) / max(1, sum(1 for x in valid if x.get('stated_fields_precision') is not None)), 2),
        "stated_fields_recall_mean": round(sum(x.get('stated_fields_recall', 0) for x in valid if x.get('stated_fields_precision') is not None) / max(1, sum(1 for x in valid if x.get('stated_fields_precision') is not None)), 2),
        "invented_schedule_kept_after_mapping": sum(1 for x in valid if any(i.endswith("(KEPT)") for i in x["invented"])),
        "allergies_reaching_profile": f"{sum(1 for x in valid if x['mapping'] and x['mapping'].get('allergies'))}/{sum(1 for x in valid if 'allergies' in SPEC['cases'][[c['id'] for c in SPEC['cases']].index(x['id'])]['stated'])}",
        "invalid_expected": [x["id"] for x in r if x["invalid"] and x["expected_invalid"]],
        "invalid_unexpected": [(x["id"], x["error"]) for x in r if x["invalid"] and not x["expected_invalid"]],
        "expected_invalid_but_accepted": [x["id"] for x in r if x["expected_invalid"] and not x["invalid"]],
        "ambiguous_values": {x["id"]: x["ambiguous_values"] for x in valid if x["ambiguous_values"]},
    }
    if len(runs) > 1:
        agree = sum(1 for a, b in zip(runs[0], runs[1]) if a["raw"] == b["raw"] and a["error"] == b["error"])
        summ["determinism_agreement"] = f"{agree}/{n}"
        summ["nondeterministic_cases"] = [a["id"] for a, b in zip(runs[0], runs[1]) if not (a["raw"] == b["raw"] and a["error"] == b["error"])]
    return summ


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--runs", type=int, default=2); ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    cases = [c for c in SPEC["cases"] if not a.only or c["id"] in a.only]
    client = LLMClient(load_llm_settings())
    runs = [run_once(client, cases) for _ in range(a.runs)]
    summ = summarize(runs)
    out = {"model": load_llm_settings().model, "summary": summ, "runs": runs}
    Path(REPO / "evaluation/llm_overhaul/results").mkdir(parents=True, exist_ok=True)
    json.dump(out, open(REPO / f"evaluation/llm_overhaul/results/nl_results{os.environ.get('SUFFIX', '')}.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))
