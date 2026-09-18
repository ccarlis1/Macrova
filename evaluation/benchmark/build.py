"""Build the Macrova planning benchmark.

    python3 evaluation/benchmark/build.py            # write outputs
    python3 evaluation/benchmark/build.py --check    # verify only, exit 1 on label mismatch

Outputs (evaluation/benchmark/):
    recipes.json        benchmark recipe library with nutrition computed from .cache/ingredients
    recipe_tags.json    tag registry + tags_by_id fixture (recipe_tags.json shape)
    scenarios.json      150 scenarios with oracle-verified expected outcomes
    scenarios_index.md  one-line-per-scenario summary table

Pure standard library; does not import src/.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from library import (  # noqa: E402
    KNOWN_SLUGS, QUARANTINED_INGREDIENTS, TAG_ALIASES, all_tags, build_library, build_tag_fixture, hard_eligible_tags,
)
from oracle import Oracle, carbs_target  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402

BORDERLINE_MAX_MEAL_SETS = 12  # feasible, but the tightest day has <= this many distinct recipe sets
BORDERLINE_MAX_TOLERANCE = 0.15  # infeasible, but becomes feasible at <= +-15%


def classify(res: dict) -> str:
    code = res["failure_code"]
    det = res["details"]
    if code is None:
        per_day = det.get("distinct_meal_sets_per_day") or [10**9]
        capped = det.get("day_enumeration_capped") or [False] * len(per_day)
        tight = min(10**9 if cap else c for c, cap in zip(per_day, capped))
        return "borderline" if tight <= BORDERLINE_MAX_MEAL_SETS else "feasible"
    if code in ("FM-2", "FM-3") and det.get("min_tolerance_for_feasibility") is not None \
            and det["min_tolerance_for_feasibility"] <= BORDERLINE_MAX_TOLERANCE:
        return "borderline"
    return "infeasible"


def acceptable_codes(res: dict, sc: dict) -> list:
    """Failure codes a conforming implementation may legitimately emit."""
    code = res["failure_code"]
    if code is None:
        return ["OK"]
    acc = [code]
    if code in ("FM-2", "FM-3", "FM-4", "FM-1") and res["stage"] == "search":
        acc.append("FM-5")  # budget exhaustion is permitted when the instance is infeasible
    if code in ("FM-1", "FM-2") and sc["profile"].get("micronutrient_targets"):
        acc.append("FM-4")  # structural micronutrient pre-check may fire first (reconciliation 2.3)
    if code == "FM-3" and res["stage"] == "search":
        acc.append("FM-2")  # downstream pin infeasibility is reported as FM-3 or FM-2
    return sorted(set(acc))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    library = build_library()
    oracle = Oracle(library, hard_eligible_tags, all_tags, TAG_ALIASES, KNOWN_SLUGS)
    lib_ids = {r["id"] for r in library}

    # Exclusion strings must hit a real canonical ingredient name, except the
    # deliberately class-level entries used by the exclusion-semantics scenarios.
    names = {i["name"].strip().lower() for r in library for i in r["ingredients"]}
    deliberate = {"peanuts", "egg", "dairy", "eggs"}
    for sc in SCENARIOS:
        for key in ("excluded_ingredients", "intent_excluded_ingredients"):
            for e in sc["profile"].get(key, []):
                if e.strip().lower() not in names and e not in deliberate:
                    raise SystemExit(f"{sc['id']}: {key} entry {e!r} matches no ingredient name")

    mismatches = []
    out = []
    for sc in SCENARIOS:
        missing = [r for r in sc["recipe_pool"]["recipe_ids"] if r not in lib_ids]
        if missing:
            raise SystemExit(f"{sc['id']}: unknown recipe ids {missing}")
        res = oracle.evaluate(sc)
        cls = classify(res)
        expected = {
            "class": cls,
            "outcome": "success" if res["failure_code"] is None else "failure",
            "primary_failure_code": res["failure_code"],
            "acceptable_failure_codes": acceptable_codes(res, sc),
            "failure_stage": res["stage"],
            "derived_daily_carbs_g": round(carbs_target(sc["profile"]), 1),
            "oracle": res["details"],
        }
        if "intent_excluded_ingredients" in sc["profile"]:
            ires = oracle.evaluate(sc, excluded_key="intent_excluded_ingredients")
            expected["intent_outcome"] = {
                "outcome": "success" if ires["failure_code"] is None else "failure",
                "primary_failure_code": ires["failure_code"],
                "note": "outcome if exclusions matched the user's intent (allergen class), not exact names",
            }
        if cls != sc["intended_class"]:
            mismatches.append((sc["id"], sc["title"], sc["intended_class"], cls, res["failure_code"],
                               {k: v for k, v in res["details"].items() if k != "witness_plan"}))
        rec = dict(sc)
        rec["expected"] = expected
        out.append(rec)

    for m in mismatches:
        print("MISMATCH", *m)
    print(f"{len(out)} scenarios; {len(mismatches)} mismatches")
    print("classes:", dict(Counter(r["expected"]["class"] for r in out)))
    print("codes:", dict(Counter(str(r["expected"]["primary_failure_code"]) for r in out)))
    if args.check:
        return 1 if mismatches else 0

    (HERE / "recipes.json").write_text(json.dumps({
        "source": ".cache/ingredients (per-100 g USDA values), quantities in grams per single serving",
        "quarantined_cache_entries": QUARANTINED_INGREDIENTS,
        "recipes": library,
    }, indent=2) + "\n")
    (HERE / "recipe_tags.json").write_text(json.dumps(build_tag_fixture(library), indent=2, sort_keys=True) + "\n")
    (HERE / "scenarios.json").write_text(json.dumps({
        "benchmark": "macrova-planning-v1",
        "spec": "docs/planner/mealplan-specification-v3.md",
        "scenario_count": len(out),
        "scenarios": out,
    }, indent=2) + "\n")
    write_index(out)
    return 1 if mismatches else 0


def write_index(out):
    lines = [
        "# Scenario index",
        "",
        "Generated by `build.py`; do not edit by hand. `class` and `code` are oracle-computed.",
        "",
        "| ID | Title | Categories | D | Slots/day | Pool | Pins | Batches | Class | Expected code |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in out:
        slots = sorted({len(d["meals"]) for d in r["schedule_days"]})
        lines.append(
            f"| {r['id']} | {r['title']} | {', '.join(r['categories'])} | {r['horizon_days']} | "
            f"{'/'.join(map(str, slots))} | {r['recipe_pool']['size']} | {len(r['pins'])} | "
            f"{len(r['meal_prep_batches'])} | {r['expected']['class']} | "
            f"{r['expected']['primary_failure_code'] or 'OK'} |"
        )
    (HERE / "scenarios_index.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
