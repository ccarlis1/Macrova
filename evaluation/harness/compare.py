"""Compare run_benchmark.py output with oracle labels and re-verify every returned plan.

Usage: .venv/bin/python evaluation/harness/compare.py  (writes results/compare.json)
"""
import json, os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; BENCH = REPO / "evaluation/benchmark"
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(BENCH))
from src.llm.tag_repository import (
    load_canonical_recipe_tag_slugs,
    load_hard_eligible_recipe_tag_slugs,
)
from src.planning.phase4_scoring import MEAL_ROLE_SLUGS
from oracle import COOK_CAP, carbs_target
SP = Path(__file__).parent / "results"
LIB = {r["id"]: r for r in json.load(open(BENCH / "recipes.json"))["recipes"]}
HARD = load_hard_eligible_recipe_tag_slugs(str(BENCH / "recipe_tags.json"))
CANON = load_canonical_recipe_tag_slugs(str(BENCH / "recipe_tags.json"))
ALIASES = {"batch-cook": "meal-prep"}
SC = {s["id"]: s for s in json.load(open(BENCH / "scenarios.json"))["scenarios"]}


def verify(sc, plan):
    v = []
    p = sc["profile"]; days = sc["schedule_days"]; D = len(days)
    ex = {e.strip().lower() for e in p.get("excluded_ingredients") or []}
    iex = {e.strip().lower() for e in p.get("intent_excluded_ingredients") or []}
    pins = {(x["day_index"], x["slot_index"]): x["recipe_id"] for x in sc.get("pins") or []}
    for b in sc.get("meal_prep_batches") or []:
        for a in b["assignments"]:
            pins[(a["day_index"], a["slot_index"])] = b["recipe_id"]
    ks = sorted(plan, key=int)
    if len(ks) != D: v.append(f"plan has {len(ks)} days, expected {D}")
    tot = {}
    ws = []
    for di, k in enumerate(ks):
        day = days[di]; sol = plan[k]
        w = set()
        for wo in day.get("workouts") or []:
            w |= {wo["after_meal_index"] - 1, wo["after_meal_index"]}
        ws.append(w)
        if len(sol) != len(day["meals"]): v.append(f"d{di}: {len(sol)} meals vs {len(day['meals'])} slots")
        if len(set(sol)) != len(sol): v.append(f"d{di}: HC-2 duplicate")
        k4 = [0, 0, 0, 0]
        for si, rid in enumerate(sol):
            r = LIB[rid]; slot = day["meals"][si] if si < len(day["meals"]) else None
            pinned = (di, si) in pins
            if pinned and pins[(di, si)] != rid: v.append(f"d{di}s{si}: pin/lock not honored ({pins[(di,si)]} -> {rid})")
            names = {i["name"].strip().lower() for i in r["ingredients"]}
            if names & ex: v.append(f"d{di}s{si}: HC-1 {rid}")
            if names & iex and not names & ex: v.append(f"d{di}s{si}: SAFETY(intent) {rid}")
            if slot and not pinned:
                cap = COOK_CAP[slot["busyness_level"]]
                if cap is not None and r["cooking_time_minutes"] > cap: v.append(f"d{di}s{si}: HC-3 {rid} {r['cooking_time_minutes']}>{cap}")
                req = [ALIASES.get(t, t) for t in slot.get("required_tag_slugs") or []]
                miss = [t for t in req if t not in HARD.get(rid, set())]
                if miss: v.append(f"d{di}s{si}: HC-9 {rid} lacks {miss}")
            n = r["nutrition"]
            for i, f in enumerate(("calories", "protein_g", "carbs_g", "fat_g")): k4[i] += n[f]
            for m, val in n["micronutrients"].items(): tot[m] = tot.get(m, 0) + val
        kt, pt, ct = p["daily_calories"], p["daily_protein_g"], carbs_target(p)
        for lab, val, t in (("kcal", k4[0], kt), ("protein", k4[1], pt), ("carbs", k4[2], ct)):
            if not (t * 0.9 - 1e-6 <= val <= t * 1.1 + 1e-6): v.append(f"d{di}: {lab} {val:.0f} outside ±10% of {t:.0f}")
        fl, fh = p["daily_fat_g"]["min"], p["daily_fat_g"]["max"]
        if not (fl - 1e-6 <= k4[3] <= fh + 1e-6): v.append(f"d{di}: fat {k4[3]:.1f} outside [{fl},{fh}]")
        if p.get("max_daily_calories") and k4[0] > p["max_daily_calories"] + 1e-6: v.append(f"d{di}: HC-5 {k4[0]:.0f}>{p['max_daily_calories']}")
    for di in range(1, len(ks)):
        a = {r for s, r in enumerate(plan[ks[di-1]]) if s not in ws[di-1]}
        b = {r for s, r in enumerate(plan[ks[di]]) if s not in ws[di]}
        if a & b: v.append(f"d{di-1}->d{di}: HC-8 repeat {sorted(a&b)}")
    tau = p.get("micronutrient_weekly_min_fraction", 1.0)
    for m, rdi in (p.get("micronutrient_targets") or {}).items():
        if tot.get(m, 0) < tau * rdi * D - 1e-6: v.append(f"micro {m} {tot.get(m,0):.1f} < floor {tau*rdi*D:.1f}")
    return v



def _slot_meal_type(meal: dict, slot_index: int, n_meals: int) -> str:
    """Resolve slot meal type the same way converters._meal_type_from_canonical does."""
    for t in meal.get("tags") or []:
        tl = str(t).strip().lower()
        if tl in MEAL_ROLE_SLUGS:
            return tl
    explicit = str(meal.get("meal_type") or "").strip().lower()
    if explicit in MEAL_ROLE_SLUGS:
        return explicit
    order = ("breakfast", "lunch", "dinner", "snack")
    if n_meals >= 3 and slot_index == 0:
        return "breakfast"
    if n_meals >= 3 and slot_index == n_meals - 1:
        return "dinner"
    if n_meals >= 3 and slot_index == n_meals // 2:
        return "lunch"
    return order[min(slot_index, 3)]


def meal_type_match_stats(results):
    """§4.3 metric: mismatch rates for planner-chosen slots with a known meal_type.

    Pins and meal-prep locks are excluded (assigned before scoring).
    """
    by_type = {m: {"known": 0, "mismatch": 0} for m in sorted(MEAL_ROLE_SLUGS)}
    known = mismatch = 0
    for r in results:
        if not r.get("success") or not r.get("plan"):
            continue
        sc = SC[r["id"]]
        pins = {(x["day_index"], x["slot_index"]) for x in sc.get("pins") or []}
        for b in sc.get("meal_prep_batches") or []:
            for a in b["assignments"]:
                pins.add((a["day_index"], a["slot_index"]))
        plan = r["plan"]
        days = sc["schedule_days"]
        for di_str, rids in plan.items():
            di = int(di_str)
            if di >= len(days):
                continue
            meals = days[di]["meals"]
            n = len(meals)
            for si, rid in enumerate(rids):
                if (di, si) in pins:
                    continue
                if si >= n:
                    continue
                mt = _slot_meal_type(meals[si], si, n)
                if mt not in MEAL_ROLE_SLUGS:
                    continue
                tags = {str(t).strip().lower() for t in CANON.get(rid, set())}
                known += 1
                by_type[mt]["known"] += 1
                if mt not in tags:
                    mismatch += 1
                    by_type[mt]["mismatch"] += 1
    out = {
        "planner_slots_known": known,
        "planner_slots_mismatched": mismatch,
        "planner_mismatch_rate": (mismatch / known) if known else 0.0,
        "by_meal_type": {
            mt: {
                "known": stats["known"],
                "mismatched": stats["mismatch"],
                "mismatch_rate": (
                    stats["mismatch"] / stats["known"] if stats["known"] else 0.0
                ),
            }
            for mt, stats in by_type.items()
        },
    }
    return out


def main():
    RES = json.load(open(SP / "results.json"))
    rows = []
    for r in RES:
        sc = SC[r["id"]]; e = sc["expected"]
        got = r.get("code")
        acc = set(e.get("acceptable_failure_codes") or []) | {e["primary_failure_code"] or "OK"}
        viol = verify(sc, r["plan"]) if r.get("plan") and r.get("success") else []
        exp = e["primary_failure_code"] or "OK"
        status = ("MATCH" if got == exp else "ACCEPTABLE" if got in acc else "MISMATCH")
        if got == "OK" and viol: status = "INVALID_PLAN" if status != "MISMATCH" else "MISMATCH+INVALID"
        rows.append(dict(id=r["id"], title=sc["title"], cats=sc["categories"], cls=e["class"], expected=exp, acceptable=sorted(acc),
                         got=got, status=status, viol=viol, tc=r.get("tc"), incomplete=r.get("incomplete"),
                         report_codes=r.get("report_codes"), report_first=r.get("report_first"), detail=r.get("detail"),
                         stage_exp=e["failure_stage"], oracle={k: v for k, v in (e.get("oracle") or {}).items() if k != "witness_plan"},
                         spec_notes=sc.get("spec_notes"), n_days=len(sc["schedule_days"]),
                         micro=bool(sc["profile"].get("micronutrient_targets")), pins=len(sc.get("pins") or []),
                         batches=len(sc.get("meal_prep_batches") or []), safety=sc.get("safety_expectation")))
    mt_stats = meal_type_match_stats(RES)
    # Keep compare.json as a list for backward compatibility with diff_results.py;
    # write meal-type stats alongside as meal_type_match.json.
    json.dump(rows, open(SP / "compare.json", "w"), indent=1)
    json.dump(mt_stats, open(SP / "meal_type_match.json", "w"), indent=1)
    from collections import Counter
    print(Counter(x["status"] for x in rows))
    bfast = mt_stats["by_meal_type"].get("breakfast", {})
    print(
        "meal_type_match: overall={:.1%} breakfast={:.1%} (n_bfast={})".format(
            mt_stats["planner_mismatch_rate"],
            bfast.get("mismatch_rate", 0.0),
            bfast.get("known", 0),
        )
    )
    for x in rows:
        if x["status"] not in ("MATCH", "ACCEPTABLE") or x["viol"]:
            print(f"{x['id']} [{x['cls']}] exp={x['expected']} got={x['got']} tc={x['tc']} {x['status']} cats={','.join(x['cats'])} D={x['n_days']} micro={x['micro']} pins={x['pins']} b={x['batches']}")
            for s in x["viol"][:4]: print("    V:", s)


if __name__ == "__main__":
    main()
