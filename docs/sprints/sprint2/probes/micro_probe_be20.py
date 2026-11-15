"""Sprint 2 probe (BE-20 re-run of D-A): which micronutrient floors fail on the sample recipes.

Run from the repo root:  .venv/bin/python docs/sprints/sprint2/probes/micro_probe_be20.py
Optional args: days (default 7), then demographics (default: all four).

Differences from micro_probe.py (the D-A probe), as BE-20 asks:
- pool: the 18 sample recipes (data/recipes/recipes.json.example) through the MCP tool path
  (``use_sample_recipes``), not the committed 32-recipe pool;
- 7 days; MCP shorthand schedule, 3 meals at busyness 2/3/4 (D-B);
- each of the four demographics, with that demographic's daily ULs enforced;
- τ = 1.0 throughout. Macros come from config/user_profile.yaml.example.

Read-only: calls ``src.mcp_server.tools.plan_meals`` in-process; writes nothing.
The goal list under test goes in as ``targets.micronutrient_goals`` with every other
nutrient set to 0 (an empty map means no goals), so every run plans exactly that list.

Diagnostic only: ``PROBE_DROP_UL=magnesium_mg,b3_niacin_mg`` removes those daily ULs
(in memory) to show what the goal list would be without them. The reference file is
never changed.
"""
import dataclasses
import os
import sys

sys.path.insert(0, ".")
from src.data_layer.upper_limits import DEMOGRAPHICS, daily_rdis, upper_limits_for  # noqa: E402
from src.data_layer.user_profile import UserProfileLoader  # noqa: E402
from src.mcp_server import models as m  # noqa: E402
from src.mcp_server import tools  # noqa: E402
from src.mcp_server.nutrients import NUTRIENT_KEYS  # noqa: E402

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
DEMOS = sys.argv[2:] or list(DEMOGRAPHICS)

prof = UserProfileLoader("config/user_profile.yaml.example").load()
SCHEDULE = m.FullSchedule(
    days=[
        m.ScheduledDay(
            day=d,
            meals=[
                m.ScheduledMeal(meal=i + 1, busyness=b, label=label)
                for i, (b, label) in enumerate(zip((2, 3, 4), ("breakfast", "lunch", "dinner")))
            ],
        )
        for d in range(1, DAYS + 1)
    ]
)


DROP_UL = [k for k in os.environ.get("PROBE_DROP_UL", "").split(",") if k]
if DROP_UL:
    print("DIAGNOSTIC: daily ULs removed in memory:", DROP_UL)
    tools.upper_limits_for = lambda demo: dataclasses.replace(
        upper_limits_for(demo), **{k: None for k in DROP_UL}
    )


def run(demographic, goals):
    targets = m.Targets(
        daily_calories=int(prof.daily_calories),
        daily_protein_g=float(prof.daily_protein_g),
        daily_fat_g_min=float(prof.daily_fat_g[0]),
        daily_fat_g_max=float(prof.daily_fat_g[1]),
        demographic=demographic,
        # Exactly this list: every other nutrient at 0 (overrides merge onto the default).
        micronutrient_goals={k: goals.get(k, 0.0) for k in NUTRIENT_KEYS} if goals else {},
        micronutrient_weekly_min_fraction=1.0,
    )
    result, _ = tools.plan_meals(days=DAYS, targets=targets, schedule=SCHEDULE, use_sample_recipes=True)
    code = result.failure.code if result.failure else None
    return result.status, code


for demo in DEMOS:
    full = daily_rdis(demo)
    ul = upper_limits_for(demo)
    clash = {
        k: (v, getattr(ul, k)) for k, v in full.items()
        if k not in DROP_UL and getattr(ul, k, None) is not None and getattr(ul, k) < v
    }
    print(f"== {demo}: daily RDI above daily UL {clash}")
    print(f"== {demo}: none (ULs only)", run(demo, {}))
    print(f"== {demo}: all {len(full)}", run(demo, full))
    fails = []
    for key, value in full.items():
        status, code = run(demo, {key: value})
        if status != "success":
            fails.append(key)
            print(f"   {key} alone -> {status} {code}")
    print(f"== {demo}: FAIL_ALONE@1.0 {fails}")
    rest = {k: v for k, v in full.items() if k not in fails}
    together = run(demo, rest)
    print(f"== {demo}: all minus fails ({len(rest)})", together)
    sys.stdout.flush()
    if together[0] != "success":
        # Together they still fail: try dropping one more, in reference order.
        extra = [k for k in rest if run(demo, {x: v for x, v in rest.items() if x != k})[0] == "success"]
        print(f"== {demo}: dropping any ONE of {extra} as well -> success")
    sys.stdout.flush()
