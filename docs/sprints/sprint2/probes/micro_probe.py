"""Sprint 2 probe (D-A / BE-20): which micronutrient floors make plans fail.

Run from the repo root:  .venv/bin/python docs/sprints/sprint2/probes/micro_probe.py
Uses config/user_profile.yaml.example macros and data/recipes/recipes.json, 3 days, deterministic.
Read-only: posts to /api/v1/plan in-process (TestClient); writes nothing.
"""
import json, sys, time
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from src.api.server import app
from src.data_layer.user_profile import UserProfileLoader
from src.data_layer.recipe_db import RecipeDB
from src.planning.orchestrator import build_plan_request_from_profile
prof = UserProfileLoader("config/user_profile.yaml.example").load()
recipes = RecipeDB("data/recipes/recipes.json").get_all_recipes()
base = build_plan_request_from_profile(prof, recipes, [], None)
base.pop("active_batches", None)
goals = base.pop("micronutrient_goals")
c = TestClient(app)
def run(g, tau, days=3):
    p = dict(base, days=days, planning_mode="deterministic", micronutrient_weekly_min_fraction=tau)
    if g: p["micronutrient_goals"] = g
    d = c.post("/api/v1/plan", json=p).json()
    return d.get("termination_code"), [f["code"] for f in d.get("report", {}).get("failures", [])]
t=time.time(); print("none", run(None, 1.0), round(time.time()-t,1)); sys.stdout.flush()
fails = []
for k, v in goals.items():
    r = run({k: v}, 1.0)
    if r[1]: fails.append(k)
    print(k, r); sys.stdout.flush()
print("FAIL_ALONE@1.0", fails)
ok = {k: v for k, v in goals.items() if k not in fails}
print("all-minus-fails @1.0", run(ok, 1.0))
for tau in (0.8, 0.7, 0.5):
    print("all25 tau", tau, run(goals, tau))
