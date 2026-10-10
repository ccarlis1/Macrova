"""Targeted probes for the fully-pinned-day defect (report cluster C3).

Each probe extends MB-099 (a fully pinned day that fits) to two days with a
free second day, then re-verifies whatever the planner returns.

Usage: .venv/bin/python evaluation/harness/probes.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_benchmark as H  # noqa: E402

from compare import verify  # noqa: E402

base = next(s for s in H.SCEN if s["id"] == "MB-099")
probes = [
    ("P1: day 0 fully pinned (fits), day 1 free", None),
    ("P2: day 0 fully pinned and misses kcal/protein/carbs, day 1 free", "bad"),
    ("P3: day 0 fully pinned (fits), fiber 30 g/day tracked", "fiber"),
]
for label, variant in probes:
    sc = copy.deepcopy(base)
    sc["id"] = "PROBE"
    sc["horizon_days"] = 2
    d2 = copy.deepcopy(sc["schedule_days"][0])
    d2["day_index"] = 2
    for m in d2["meals"]:
        m["busyness_level"] = 4
    sc["schedule_days"].append(d2)
    if variant == "bad":
        sc["pins"][2]["recipe_id"] = "sn_almonds_chocolate"
    if variant == "fiber":
        sc["profile"]["micronutrient_targets"] = {"fiber_g": 30}
    r = H.run(sc)
    violations = verify(sc, r["plan"]) if r.get("plan") and r.get("success") else None
    print(f"{label}\n  -> {r.get('code')}  plan={r.get('plan')}")
    if violations is not None:
        print(f"  independent re-check: {violations or 'valid'}")
    else:
        print(f"  report: {r.get('report_first', '')[:220]}")
