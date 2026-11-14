"""Sprint 2 probe (BE-16): CLI-vs-API parity on config/user_profile.yaml.example.

Run from the repo root:  .venv/bin/python docs/sprints/sprint2/probes/parity_probe.py DAYS VARIANT
VARIANT: as_is | no_liked | no_micro | workout | workout_no_micro
Read-only: posts to /api/v1/plan in-process (TestClient); writes nothing.
"""
import sys
sys.path.insert(0, ".")
import json
from fastapi.testclient import TestClient
from src.api.server import app
from src.data_layer.user_profile import UserProfileLoader
from src.data_layer.recipe_db import RecipeDB
from src.planning.orchestrator import build_plan_request_from_profile
days = int(sys.argv[1]); variant = sys.argv[2] if len(sys.argv) > 2 else "as_is"
prof = UserProfileLoader("config/user_profile.yaml.example").load()
recipes = RecipeDB("data/recipes/recipes.json").get_all_recipes()
p = build_plan_request_from_profile(prof, recipes, [], None)
p.pop("active_batches", None)
p["days"] = days
p["planning_mode"] = "deterministic"
if variant == "no_liked": p["liked_foods"] = []
if variant == "no_micro": p.pop("micronutrient_goals", None)
if variant == "no_recipe_ids": p.pop("recipe_ids", None)
if variant == "workout": p["schedule"]["08:00"] = 0
if variant == "workout_no_micro": p["schedule"]["08:00"] = 0; p.pop("micronutrient_goals", None)
c = TestClient(app)
r = c.post("/api/v1/plan", json=p)
d = r.json()
print(variant, "days", days, r.status_code, d.get("success"), d.get("termination_code"),
      [(f["code"], f.get("slot_index"), f.get("details", {}).get("blocking_constraints"), f.get("cause")) for f in d.get("report", {}).get("failures", [])],
      "recipes", len(p.get("recipe_ids", [])), "tau", p["micronutrient_weekly_min_fraction"], "schedule", p["schedule"])
print("warnings keys", list((d.get("warnings") or {}).keys()))
