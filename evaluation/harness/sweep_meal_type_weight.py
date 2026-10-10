"""Sweep ScoringConfig.w_meal_type for §4.3 match-rate tuning.

Usage (from repo root):
  .venv/bin/python evaluation/harness/sweep_meal_type_weight.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "evaluation" / "harness"))

import run_benchmark as H  # noqa: E402
from compare import meal_type_match_stats  # noqa: E402
from src.planning import phase4_scoring as scoring  # noqa: E402

WEIGHTS = [0.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0]


def run_at_weight(w: float) -> dict:
    scoring.DEFAULT_SCORING_CONFIG = scoring.ScoringConfig(
        w_pref=scoring.DEFAULT_SCORING_CONFIG.w_pref,
        w_var=scoring.DEFAULT_SCORING_CONFIG.w_var,
        w_meal_type=w,
    )
    results = []
    for sc in H.SCEN:
        results.append(H.run(sc))
    mt = meal_type_match_stats(results)
    ok = sum(1 for r in results if r.get("code") == "OK" or r.get("success"))
    # Scorecard exactness needs oracle — approximate via success+code presence.
    from compare import SC, verify

    exact = 0
    for r in results:
        sc = SC[r["id"]]
        e = sc["expected"]
        got = r.get("code")
        exp = e["primary_failure_code"] or "OK"
        acc = set(e.get("acceptable_failure_codes") or []) | {exp}
        viol = verify(sc, r["plan"]) if r.get("plan") and r.get("success") else []
        status = "MATCH" if got == exp else ("ACCEPTABLE" if got in acc else "MISMATCH")
        if got == "OK" and viol:
            status = "INVALID_PLAN" if status != "MISMATCH" else "MISMATCH+INVALID"
        if status == "MATCH":
            exact += 1
    bfast = mt["by_meal_type"]["breakfast"]
    return {
        "w_meal_type": w,
        "exact_matches": exact,
        "n_scenarios": len(results),
        "planner_mismatch_rate": round(mt["planner_mismatch_rate"], 4),
        "breakfast_mismatch_rate": round(bfast["mismatch_rate"], 4),
        "breakfast_known": bfast["known"],
        "ok_successes": ok,
    }


def main() -> None:
    rows = []
    for w in WEIGHTS:
        print(f"running w_meal_type={w} ...", flush=True)
        row = run_at_weight(w)
        rows.append(row)
        print(row, flush=True)
    out = Path(__file__).parent / "results" / "meal_type_weight_sweep.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    # Pick smallest weight with breakfast mismatch < 10% and exact == n.
    n = rows[0]["n_scenarios"] if rows else 0
    chosen = None
    for row in rows:
        if (
            row["exact_matches"] == n
            and row["breakfast_mismatch_rate"] < 0.10
        ):
            chosen = row
            break
    if chosen is None:
        # Fall back to best breakfast rate among full-exact rows.
        exact_rows = [r for r in rows if r["exact_matches"] == n]
        if exact_rows:
            chosen = min(exact_rows, key=lambda r: r["breakfast_mismatch_rate"])
    print("chosen:", chosen)


if __name__ == "__main__":
    main()
