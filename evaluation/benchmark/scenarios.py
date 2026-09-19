"""150 Macrova meal-planning benchmark scenarios.

Each scenario is authored with an *intended* class. The oracle (oracle.py)
independently computes the spec-v3 outcome; build.py records both and fails if
they disagree, so every label in scenarios.json is oracle-verified.

Index conventions (match the code, not older prose):
- ``schedule_days[i].day_index`` is 1-based (PlanRequest contract).
- ``pins[*]`` and ``meal_prep_batches[*].assignments[*]`` use canonical
  zero-based ``(day_index, slot_index)``.
"""

from __future__ import annotations

from typing import List, Optional

from library import RECIPES, DATA_HAZARD_RECIPES

SCENARIOS: List[dict] = []

CORE = [r["id"] for r in RECIPES if not r["id"].startswith("dup_")]
_BY_ID = {r["id"]: r for r in RECIPES + DATA_HAZARD_RECIPES}


def pool(*require, base=None, drop=(), add=()):
    base = CORE if base is None else base
    ids = [i for i in base if all(t in _BY_ID[i]["tags"] for t in require) and i not in drop]
    return ids + [a for a in add if a not in ids]


def quick(max_minutes, base=None):
    base = CORE if base is None else base
    return [i for i in base if _BY_ID[i]["cooking_time_minutes"] <= max_minutes]


# ------------------------------------------------------------------ builders
def M(time, busy, label, req=None, pref=None):
    return {"time": time, "busy": busy, "label": label, "req": req, "pref": pref}


def W(after, kind="general", intensity="moderate"):
    return {"after_meal_index": after, "type": kind, "intensity": intensity}


def day(meals, workouts=()):
    return {"meals": meals, "workouts": list(workouts)}


def std3(b=(2, 3, 3), t=("07:30", "12:30", "18:30"), req=(None, None, None), pref=(None, None, None)):
    labels = ("breakfast", "lunch", "dinner")
    return [M(t[i], b[i], labels[i], req[i], pref[i]) for i in range(3)]


def std4(b=(2, 3, 1, 3), t=("07:00", "12:00", "15:30", "19:00")):
    labels = ("breakfast", "lunch", "snack", "dinner")
    return [M(t[i], b[i], labels[i]) for i in range(4)]


def five(b=(2, 1, 3, 1, 3), t=("06:30", "10:00", "13:00", "16:00", "19:30")):
    labels = ("breakfast", "snack", "lunch", "snack", "dinner")
    return [M(t[i], b[i], labels[i]) for i in range(5)]


def P(kcal, protein, fmin, fmax, *, excluded=(), liked=(), ceiling=None, micros=None, tau=1.0,
      intent_excluded=None, demographic="adult_male"):
    p = {
        "daily_calories": kcal,
        "daily_protein_g": protein,
        "daily_fat_g": {"min": fmin, "max": fmax},
        "max_daily_calories": ceiling,
        "excluded_ingredients": list(excluded),
        "liked_foods": list(liked),
        "demographic": demographic,
        "micronutrient_targets": dict(micros or {}),
        "micronutrient_weekly_min_fraction": tau,
    }
    if intent_excluded is not None:
        p["intent_excluded_ingredients"] = list(intent_excluded)
    return p


_CLASS_WORDS = {"feasible", "infeasible", "borderline"}


def S(title, request, *, cats, intended, profile, days, pool_ids, pool_note, pins=(), batches=(),
      prefs_note="", spec_notes=(), safety=None):
    """Register a scenario. ``days`` is a list of day() dicts (one per horizon day)."""
    sid = f"MB-{len(SCENARIOS) + 1:03d}"
    sched = []
    for i, d in enumerate(days):
        sched.append({
            "day_index": i + 1,
            "meals": [
                {k: v for k, v in {
                    "index": j + 1,
                    "busyness_level": m["busy"],
                    "tags": [m["label"]],
                    "preferred_time": m["time"],
                    "required_tag_slugs": m["req"],
                    "preferred_tag_slugs": m["pref"],
                }.items() if v is not None}
                for j, m in enumerate(d["meals"])
            ],
            "workouts": d["workouts"],
        })
    SCENARIOS.append({
        "id": sid,
        "title": title,
        "user_request": request,
        # Outcome class lives in intended_class / expected.class; categories are thematic only.
        "categories": [c for c in cats if c not in _CLASS_WORDS] or ["baseline"],
        "intended_class": intended,
        "profile": profile,
        "horizon_days": len(days),
        "schedule_days": sched,
        "pins": [{"day_index": d, "slot_index": s, "recipe_id": r} for d, s, r in pins],
        "meal_prep_batches": list(batches),
        "recipe_pool": {"recipe_ids": list(pool_ids), "size": len(pool_ids), "description": pool_note},
        "preferences_note": prefs_note,
        "spec_notes": list(spec_notes),
        "safety_expectation": safety,
    })


def B(bid, recipe, servings, assigns, cook_date="2026-09-20"):
    return {"id": bid, "recipe_id": recipe, "total_servings": servings, "cook_date": cook_date,
            "assignments": [{"day_index": d, "slot_index": s, "servings": 1.0} for d, s in assigns],
            "status": "planned"}


def rep(d, n):
    return [d for _ in range(n)]


FULL = "full local library (core recipes, no duplicates)"

# ======================================================================
# A. Clearly feasible everyday requests
# ======================================================================
S("Office worker, simple 3 meals",
  "I want 2,100 calories and about 140 g protein a day, fat 55-80 g. Breakfast before work, lunch at my desk, normal dinner. Just one day for now.",
  cats=["feasible"], intended="feasible",
  profile=P(2100, 140, 55, 80, liked=["salmon", "rice"]),
  days=[day(std3())], pool_ids=CORE, pool_note=FULL)

S("Maintenance with afternoon snack",
  "Plan tomorrow: 2,200 kcal, 130 g protein, 60-85 g fat. Three meals plus a quick snack mid-afternoon.",
  cats=["feasible"], intended="feasible",
  profile=P(2200, 130, 60, 85),
  days=[day(std4())], pool_ids=CORE, pool_note=FULL)

S("Three-day lean bulk",
  "Lean bulk: 2,800 kcal, 170 g protein, 70-100 g fat. Four meals a day for the next 3 days. I lift after lunch.",
  cats=["feasible", "multi-day"], intended="feasible",
  profile=P(2800, 170, 70, 100, liked=["beef", "rice"]),
  days=rep(day(std4(b=(2, 3, 1, 4)), [W(2, "PM", "high")]), 3), pool_ids=CORE, pool_note=FULL)

S("Moderate cut, 5 days, 3 meals",
  "I'm cutting. 1,900 calories, 150 g protein, fat between 45 and 70. Plan Monday to Friday, three meals.",
  cats=["feasible", "multi-day"], intended="feasible",
  profile=P(1900, 150, 45, 70),
  days=rep(day(std3()), 5), pool_ids=CORE, pool_note=FULL)

S("Vegetarian week-lite",
  "Vegetarian, 2,000 kcal, 100 g protein, fat 55-85. Three days, three meals, nothing fancy on weekdays.",
  cats=["feasible", "multi-day"], intended="feasible",
  profile=P(2000, 100, 55, 85, liked=["yogurt", "pasta"]),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian")

S("Pescatarian two-meal day",
  "I eat fish but no other meat. 1,300 kcal, 90 g protein, 30-50 g fat, lunch and dinner plus an evening snack today.",
  cats=["feasible"], intended="feasible",
  profile=P(1300, 90, 30, 50),
  days=[day([M("12:30", 3, "lunch"), M("19:00", 4, "dinner"), M("21:30", 1, "snack")])],
  pool_ids=pool("pescatarian") + pool("vegetarian"), pool_note="pescatarian + vegetarian recipes")

S("Endurance athlete, morning run",
  "I run at 6:30am most days. 2,700 kcal, 120 g protein, 60-90 g fat. Pre-run snack, breakfast after, lunch and dinner. Two days.",
  cats=["feasible", "meal-timing", "multi-day"], intended="feasible",
  profile=P(2700, 120, 60, 90, liked=["banana", "oats"]),
  days=rep(day([M("05:45", 1, "snack"), M("08:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("19:00", 4, "dinner")],
               [W(1, "AM", "high")]), 2),
  pool_ids=CORE, pool_note=FULL)

S("Busy parent, quick meals",
  "Everything has to be 15 minutes or less. 2,000 kcal, 120 g protein, fat 50-80. Three meals and a snack tomorrow.",
  cats=["feasible", "cook-time"], intended="feasible",
  profile=P(2000, 120, 50, 80),
  days=[day(std4(b=(2, 2, 1, 2)))], pool_ids=CORE, pool_note=FULL)

S("Dairy-free three meals",
  "I'm lactose intolerant, so dairy-free please. 2,100 kcal, 130 g protein, fat 55-85, three meals, one day.",
  cats=["feasible", "preferences"], intended="feasible",
  profile=P(2100, 130, 55, 85),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=pool("dairy-free"), pool_note="recipes tagged dairy-free")

S("Gluten-free, 2 days",
  "Celiac. 2,000 kcal, 130 g protein, 55-80 g fat. Two days of three meals.",
  cats=["feasible", "preferences", "multi-day"], intended="feasible",
  profile=P(2000, 130, 55, 80),
  days=rep(day(std3(b=(3, 3, 4))), 2), pool_ids=pool("gluten-free"), pool_note="recipes tagged gluten-free")

S("High-protein cut with shake",
  "Cutting hard: 2,000 kcal, 170 g protein, 45-70 g fat. Breakfast, lunch, a post-gym shake at 5pm, dinner. One day.",
  cats=["feasible", "meal-timing"], intended="feasible",
  profile=P(2000, 170, 45, 70),
  days=[day([M("07:00", 2, "breakfast"), M("12:00", 3, "lunch"), M("17:00", 1, "snack"), M("19:30", 4, "dinner")],
            [W(2, "PM", "high")])],
  pool_ids=CORE, pool_note=FULL)

S("Shift worker, late schedule",
  "I work 2pm to 11pm. First meal at 11am, lunch break at 5pm, then a meal when I get home at midnight-ish (23:30). 2,300 kcal, 140 g protein, 60-90 g fat.",
  cats=["feasible", "meal-timing"], intended="feasible",
  profile=P(2300, 140, 60, 90),
  days=[day([M("11:00", 4, "breakfast"), M("17:00", 1, "lunch"), M("23:30", 2, "dinner")])],
  pool_ids=CORE, pool_note=FULL)

S("Intermittent fasting 16:8",
  "I do 16:8, eating window noon to 8pm. Two big meals, 2,000 kcal, 140 g protein, 60-90 g fat.",
  cats=["borderline", "meal-timing"], intended="borderline",
  spec_notes=["Two atomic recipes must jointly land four +-10% windows; no pair does, one does at +-12% (no portion variable, OR review 2.1)."],
  profile=P(2000, 140, 60, 90),
  days=[day([M("12:00", 3, "lunch"), M("19:30", 4, "dinner")])],
  pool_ids=CORE, pool_note=FULL)

S("Liked foods steer choice",
  "2,200 kcal, 140 g protein, 55-85 g fat, three meals. I love salmon, potatoes and yogurt, would be great to see them.",
  cats=["feasible", "preferences"], intended="feasible",
  profile=P(2200, 140, 55, 85, liked=["salmon", "potatoes", "greek yogurt"]),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  prefs_note="liked_foods is a tie-break signal only (spec 7.1); plan validity must not depend on it")

S("Older adult, smaller appetite",
  "My doctor wants me at 1,700 calories with 90 g of protein, fat 45-70. I prefer four smaller meals.",
  cats=["feasible"], intended="feasible",
  profile=P(1700, 90, 45, 70, demographic="adult_female"),
  days=[day(std4(b=(3, 3, 1, 3), t=("08:00", "12:00", "15:00", "18:00")))], pool_ids=CORE, pool_note=FULL)

S("Five meals bodybuilding",
  "Bodybuilding, 3,000 kcal, 200 g protein, 70-100 g fat. Five meals. Train after the 10am snack.",
  cats=["feasible", "meal-timing"], intended="feasible",
  profile=P(3000, 200, 70, 100),
  days=[day(five(), [W(2, "AM", "high")])], pool_ids=CORE, pool_note=FULL)

S("Four-day vegetarian with snacks",
  "Vegetarian, 2,100 kcal, 110 g protein, 55-85 g fat. Four days, breakfast/lunch/snack/dinner.",
  cats=["feasible", "multi-day"], intended="feasible",
  profile=P(2100, 110, 55, 85),
  days=rep(day(std4()), 4), pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian")

S("Nut allergy, simple",
  "Tree nut and peanut allergy. 2,000 kcal, 130 g protein, 50-80 g fat. Three meals, one day.",
  cats=["feasible", "preferences"], intended="feasible",
  profile=P(2000, 130, 50, 80, excluded=["almonds", "almond butter unsalted", "peanut butter"]),
  days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  safety={"must_not_contain_cache_keys": ["almonds", "almond_butter_unsalted", "peanut_butter"]})

S("Calorie ceiling with slack",
  "Target 1,800 kcal but never go above 1,900. 140 g protein, 45-65 g fat. Three meals.",
  cats=["feasible", "calorie-ceiling"], intended="feasible",
  profile=P(1800, 140, 45, 65, ceiling=1900),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Week plan, 3 meals, large pool",
  "Give me a full week, 2,200 kcal, 140 g protein, 55-85 g fat, three meals every day.",
  cats=["feasible", "multi-day"], intended="feasible",
  profile=P(2200, 140, 55, 85),
  days=rep(day(std3(b=(2, 3, 4))), 7), pool_ids=CORE, pool_note=FULL)

S("Fiber goal, 3 days",
  "I'm trying to hit 30 g of fiber a day. 2,100 kcal, 120 g protein, 55-85 g fat, three meals, three days.",
  cats=["feasible", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2100, 120, 55, 85, micros={"fiber_g": 30}),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL)

S("Iron and calcium tracking, relaxed tau",
  "Track iron (18 mg) and calcium (1,000 mg). 90% of target over the plan is fine. 2,000 kcal, 110 g protein, 55-80 g fat, 4 meals, 3 days.",
  cats=["feasible", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2000, 110, 55, 80, micros={"iron_mg": 18, "calcium_mg": 1000}, tau=0.9, demographic="adult_female"),
  days=rep(day(std4()), 3), pool_ids=CORE, pool_note=FULL)

S("Pinned favorite breakfast",
  "Always overnight oats for breakfast. 2,200 kcal, 120 g protein, 55-85 g fat, three meals, two days.",
  cats=["feasible", "pins", "multi-day"], intended="feasible",
  profile=P(2200, 120, 55, 85),
  days=rep(day(std3()), 2), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_overnight_oats")],
  spec_notes=["Only day 0 is pinned; pinning the same non-workout breakfast on day 1 would violate HC-8 (see pin-conflict scenarios)."])

S("Pinned dinner out",
  "I'm having the salmon and potatoes at my mom's for dinner, plan the rest. 2,100 kcal, 140 g protein, 50-80 g fat. Weeknight, so dinner is normally a 30-minute slot.",
  cats=["pin-conflict", "cook-time"], intended="infeasible",
  spec_notes=["Someone else cooks, but HC-3 pre-validation still rejects a 35-min pinned recipe in a busyness-3 (<=30 min) slot -> FM-3. Pins cannot express 'not cooked by me'."],
  profile=P(2100, 140, 50, 80),
  days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_salmon_potatoes")])

S("Preferred tags only",
  "I'd like breakfast to be high-protein if possible and dinner something that reheats well, but not a big deal. 2,100 kcal, 140 g protein, 55-80 g fat.",
  cats=["feasible", "tags"], intended="feasible",
  profile=P(2100, 140, 55, 80),
  days=[day(std3(pref=(["high-protein"], None, ["reheats-well"])))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["preferred_tag_slugs are soft (HC-9 excludes them); a nutrition_claim tag is allowed as a preference."])

S("Required breakfast tag, satisfiable",
  "Make sure the first meal is actually a breakfast food and dinner is a real dinner. 2,100 kcal, 130 g protein, 55-80 g fat.",
  cats=["feasible", "tags"], intended="feasible",
  profile=P(2100, 130, 55, 80),
  days=[day(std3(req=(["breakfast"], None, ["dinner"])))], pool_ids=CORE, pool_note=FULL)

S("Portable lunch requirement",
  "Lunch has to be something I can take to the job site, no microwave. 2,400 kcal, 150 g protein, 60-90 g fat. Two days.",
  cats=["tag-conflict", "multi-day-conflict"], intended="infeasible",
  profile=P(2400, 150, 60, 90),
  spec_notes=["Each day is feasible alone, but every valid day uses the same portable lunch in a non-workout slot, so HC-8 blocks day 2 (FM-1 per spec 11: 'eligible recipes were used in non-workout slots yesterday')."],
  days=rep(day(std3(req=(None, ["portable", "no-cook"], None))), 2), pool_ids=CORE, pool_note=FULL)

S("Meal prep across non-consecutive days",
  "Sunday I'll make a big chickpea salad and take it for lunch Monday and Wednesday. 2,100 kcal, 130 g protein, 55-80 g fat, Monday-Wednesday.",
  cats=["borderline", "meal-prep", "multi-day"], intended="borderline",
  profile=P(2100, 130, 55, 80),
  days=rep(day(std3(b=(2, 2, 3))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chickpea_mw", "ln_chickpea_salad", 2, [(0, 1), (2, 1)])],
  spec_notes=["Non-consecutive days, so HC-8 does not fire; 10-minute recipe fits the busyness-2 lunch cap."])

S("Workout-slot shake repeats daily",
  "Same post-workout shake every day at 6pm is fine by me. 2,500 kcal, 170 g protein, 60-90 g fat, three days.",
  cats=["feasible", "multi-day", "meal-timing"], intended="feasible",
  profile=P(2500, 170, 60, 90),
  days=rep(day([M("07:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("18:00", 1, "snack"), M("20:00", 4, "dinner")],
               [W(2, "PM", "high")]), 3),
  pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "sn_protein_shake"), (1, 2, "sn_protein_shake"), (2, 2, "sn_protein_shake")],
  spec_notes=["Slot 2 is post-workout (workout after meal 2), so HC-8 exempts the repeated shake."])

# ======================================================================
# B. Borderline requests (feasible-but-scarce, or near-miss at +-10%)
# ======================================================================
S("16:8 with bigger target",
  "Still doing 16:8 but bumping to 2,400 kcal and 160 g protein, fat 65-95. Two meals only.",
  cats=["infeasible", "meal-timing"], intended="infeasible",
  profile=P(2400, 160, 65, 95),
  days=[day([M("12:00", 3, "lunch"), M("19:30", 4, "dinner")])], pool_ids=CORE, pool_note=FULL)

S("Small cut, 1,500 kcal",
  "Petite and cutting: 1,400 kcal, 115 g protein, fat 35-48 g, three meals.",
  cats=["feasible"], intended="feasible",
  profile=P(1400, 115, 35, 48, demographic="adult_female"),
  days=[day(std3())], pool_ids=CORE, pool_note=FULL)

S("Vegan high protein",
  "Vegan, trying to build muscle. 2,300 kcal, 130 g protein, 60-85 g fat, three meals and a snack.",
  cats=["borderline", "nutrition-conflict"], intended="borderline",
  profile=P(2300, 130, 60, 85),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=pool("vegan"), pool_note="recipes tagged vegan")

S("Big bulk, four meals",
  "Bulking hard: 3,500 kcal, 200 g protein, 90-130 g fat, four meals.",
  cats=["feasible"], intended="feasible",
  profile=P(3500, 200, 90, 130),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=CORE, pool_note=FULL)

S("Narrow fat window",
  "My coach gave me exact numbers: 2,200 kcal, 160 g protein, fat 62-64 g. Three meals.",
  cats=["borderline", "nutrition-conflict"], intended="borderline",
  profile=P(2200, 160, 62, 64),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Ceiling equals target",
  "1,800 kcal and I mean it: never over 1,800. 130 g protein, 45-65 g fat, three meals.",
  cats=["borderline", "calorie-ceiling"], intended="feasible",
  profile=P(1800, 130, 45, 65, ceiling=1800),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["Effective kcal window becomes [1620, 1800] (lower -10% bound, ceiling as upper)."])

S("Everything under five minutes",
  "No cooking at all this week, max 5 minutes per meal. 2,300 kcal, 140 g protein, 50-80 g fat, three meals, one day to start.",
  cats=["borderline", "cook-time"], intended="borderline",
  profile=P(2300, 140, 50, 80),
  days=[day(std3(b=(1, 1, 1)))], pool_ids=CORE, pool_note=FULL)

S("Gluten-free and dairy-free",
  "Celiac and lactose intolerant. 2,000 kcal, 120 g protein, 55-80 g fat, three meals.",
  cats=["borderline", "preferences"], intended="borderline",
  profile=P(2000, 120, 55, 80),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=pool("gluten-free", "dairy-free"), pool_note="gluten-free AND dairy-free recipes")

S("Pescatarian four days",
  "Pescatarian (fish + vegetarian), 2,000 kcal, 120 g protein, 50-75 g fat, four days of three meals.",
  cats=["borderline", "multi-day"], intended="feasible",
  profile=P(2000, 120, 50, 75),
  days=rep(day(std3(b=(2, 3, 4))), 4), pool_ids=pool("pescatarian") + pool("vegetarian"),
  pool_note="pescatarian + vegetarian recipes")

S("Vegetarian full week",
  "Vegetarian, 2,100 kcal, 100 g protein, 60-85 g fat, three meals, all seven days.",
  cats=["borderline", "multi-day"], intended="feasible",
  profile=P(2100, 100, 60, 85),
  days=rep(day(std3(b=(2, 3, 4))), 7), pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian")

S("Fiber 38 g strict, 3 days",
  "I want the full 38 g fiber, every gram of it averaged over three days. 2,300 kcal, 130 g protein, 55-85 g fat, three meals.",
  cats=["borderline", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2300, 130, 55, 85, micros={"fiber_g": 38}),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL)

S("Potassium 3,400 mg, 2 days",
  "Blood pressure: aim for 3,400 mg potassium. 2,000 kcal, 120 g protein, 50-75 g fat, three meals, two days.",
  cats=["borderline", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2000, 120, 50, 75, micros={"potassium_mg": 3400}),
  days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL)

S("Magnesium with tau 0.9",
  "Track magnesium at 400 mg, 90% is fine. 2,200 kcal, 130 g protein, 55-80 g fat, three meals, three days.",
  cats=["borderline", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2200, 130, 55, 80, micros={"magnesium_mg": 400}, tau=0.9),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL)

S("Low-fat heart diet",
  "Cardiologist says low fat: 2,000 kcal, 140 g protein, 22-32 g fat, three meals and a snack.",
  cats=["borderline", "nutrition-conflict"], intended="borderline",
  profile=P(2000, 140, 22, 32),
  days=[day(std4())], pool_ids=CORE, pool_note=FULL)

S("Curated 10-recipe list, 3 days",
  "Only use these 10 recipes I actually like. 2,100 kcal, 140 g protein, 55-80 g fat, three meals, three days.",
  cats=["recipe-inventory", "multi-day-conflict"], intended="infeasible",
  profile=P(2100, 140, 55, 80),
  days=rep(day(std3(b=(2, 3, 4))), 3),
  pool_ids=["bk_yogurt_berry_bowl", "bk_protein_oats", "bk_salmon_toast", "ln_turkey_sandwich", "ln_tuna_poke",
            "ln_chickpea_salad", "dn_beef_rice_bowl", "dn_thigh_sheet_pan", "dn_tilapia_rice", "dn_burger_bowl"],
  pool_note="user-curated 10 recipes",
  spec_notes=["Exactly one valid day exists; HC-8 forbids repeating its non-workout meals on day 2 -> FM-1."])

S("Two-a-day training",
  "I train twice: 7am and 5pm. 3,000 kcal, 180 g protein, 70-100 g fat, five meals.",
  cats=["borderline", "meal-timing"], intended="feasible",
  profile=P(3000, 180, 70, 100),
  days=[day([M("06:15", 1, "snack"), M("08:30", 2, "breakfast"), M("12:30", 3, "lunch"), M("18:30", 1, "snack"),
             M("20:00", 4, "dinner")], [W(1, "AM", "high"), W(3, "PM", "moderate")])],
  pool_ids=CORE, pool_note=FULL)

S("High-carb endurance",
  "Marathon block: 3,200 kcal, 120 g protein, 50-70 g fat so carbs are high. Four meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(3200, 120, 50, 70),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=CORE, pool_note=FULL)

S("Six small meals",
  "I graze. Six small meals, 2,200 kcal, 140 g protein, 60-85 g fat.",
  cats=["borderline", "meal-timing"], intended="feasible",
  profile=P(2200, 140, 60, 85),
  days=[day([M("07:00", 2, "breakfast"), M("09:30", 1, "snack"), M("12:00", 3, "lunch"), M("15:00", 1, "snack"),
             M("18:00", 3, "dinner"), M("21:00", 1, "snack")])],
  pool_ids=CORE, pool_note=FULL)

S("Pinned lunch with tight remaining budget",
  "Work is catering the tuna poke lunch. I'm at 1,500 kcal, 135 g protein, 35-45 g fat, three meals.",
  cats=["borderline", "pins"], intended="borderline",
  profile=P(1500, 135, 35, 45),
  days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 1, "ln_tuna_poke")])

S("Quick lunches, relaxed dinners, 5 days",
  "Weekdays: lunch at my desk is 5 minutes max, dinner I have time. 2,200 kcal, 140 g protein, 55-85 g fat, three meals, Monday-Friday.",
  cats=["borderline", "cook-time", "multi-day"], intended="feasible",
  profile=P(2200, 140, 55, 85),
  days=rep(day(std3(b=(2, 1, 4))), 5), pool_ids=CORE, pool_note=FULL)

# ======================================================================
# C. Clearly infeasible requests
# ======================================================================
S("Crash diet with very high protein",
  "1,200 calories but 200 g protein, fat 30-40 g. Three meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(1200, 200, 30, 40),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("5,000 kcal in two meals",
  "Strongman season: 5,000 kcal, 250 g protein, 120-170 g fat, but I only have time for two meals.",
  cats=["infeasible", "meal-timing"], intended="infeasible",
  profile=P(5000, 250, 120, 170),
  days=[day([M("11:00", 4, "lunch"), M("19:00", 4, "dinner")])], pool_ids=CORE, pool_note=FULL)

S("Keto macros",
  "Keto: 1,800 kcal, 130 g protein, 120-140 g fat, which leaves ~28 g carbs. Three meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(1800, 130, 120, 140),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Negative derived carbs",
  "2,000 kcal, 150 g protein, fat 150-170 g. Three meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(2000, 150, 150, 170),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["Derived carbs = (2000 - 600 - 160*9)/4 = -10 g; the input contract does not reject this (spec 2.1 has no validity rule)."])

S("Ceiling below the tolerance window",
  "Target 2,000 kcal but hard cap at 1,700. 130 g protein, 50-70 g fat, three meals.",
  cats=["infeasible", "calorie-ceiling", "nutrition-conflict"], intended="infeasible",
  profile=P(2000, 130, 50, 70, ceiling=1700),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["Window becomes [1800, 1700]: empty. A good implementation should reject pre-search."])

S("Vegan 180 g protein at 2,000 kcal",
  "Vegan cut, 2,000 kcal, 180 g protein, 45-65 g fat, four meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(2000, 180, 45, 65),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=pool("vegan"), pool_note="recipes tagged vegan")

S("3,500 kcal with only snack-time slots",
  "3,500 kcal, 180 g protein, 90-120 g fat, but every meal has to be under five minutes and I only eat three times.",
  cats=["infeasible", "cook-time"], intended="infeasible",
  profile=P(3500, 180, 90, 120),
  days=[day(std3(b=(1, 1, 1)))], pool_ids=CORE, pool_note=FULL)

S("300 g protein",
  "3,000 kcal with 300 g protein, 60-80 g fat, four meals.",
  cats=["infeasible", "nutrition-conflict"], intended="infeasible",
  profile=P(3000, 300, 60, 80),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=CORE, pool_note=FULL)

S("Fiber 60 g every day for a week",
  "Gut health protocol: 60 g fiber daily for 7 days, 2,200 kcal, 110 g protein, 55-80 g fat, three meals.",
  cats=["infeasible", "micronutrients", "multi-day"], intended="infeasible",
  profile=P(2200, 110, 55, 80, micros={"fiber_g": 60}),
  days=rep(day(std3(b=(2, 3, 4))), 7), pool_ids=CORE, pool_note=FULL)

S("Vitamin C 400 mg from food, 1,600 kcal",
  "1,600 kcal, 110 g protein, 40-60 g fat, three meals, and I want 400 mg vitamin C from food.",
  cats=["infeasible", "micronutrients"], intended="infeasible",
  profile=P(1600, 110, 40, 60, micros={"vitamin_c_mg": 400}),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["D=1 with tracked micronutrients: reconciliation Q8 (structural pre-check rejects, but exit skips weekly validation)."])

S("No starches, still 2,800 kcal",
  "I don't eat rice, pasta, bread, potatoes or oats. 2,800 kcal, 150 g protein, 60-90 g fat, three meals.",
  cats=["infeasible", "preferences", "nutrition-conflict"], intended="infeasible",
  profile=P(2800, 150, 60, 90, excluded=["jasmine rice in unsalted water",
                                         "pasta", "sourdough bread", "potatoes flesh", "rolled oats", "cream of rice dry",
                                         "quinoa", "tortillas corn"]),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Allergy list wipes the pool",
  "Allergic to dairy proteins and soy and I can't do whey or nuts. 2,000 kcal, 120 g protein, 50-80 g fat, but only these five recipes.",
  cats=["infeasible", "recipe-inventory", "preferences"], intended="infeasible",
  profile=P(2000, 120, 50, 80, excluded=["milk", "whey protein powder", "greek yogurt plain nonfat", "cottage cheese 1% fat",
                                         "peanut butter", "almonds", "soy sauce", "tofu not silken firm", "edamame beans"]),
  days=[day(std3())],
  pool_ids=["bk_yogurt_berry_bowl", "bk_protein_oats", "sn_protein_shake", "dn_tofu_stir_fry", "sn_edamame_cup"],
  pool_note="five-recipe user list, every one contains an excluded ingredient")

S("Seven days, three recipes",
  "New user, I only have 3 recipes saved. Plan a week of three meals: 1,800 kcal, 115 g protein, 45-60 g fat.",
  cats=["infeasible", "recipe-inventory", "multi-day"], intended="infeasible",
  profile=P(1800, 115, 45, 60),
  days=rep(day(std3(b=(2, 3, 4))), 7),
  pool_ids=["bk_protein_oats", "ln_turkey_sandwich", "dn_beef_rice_bowl"], pool_note="3 saved recipes",
  spec_notes=["The three recipes hit every day-1 window; HC-8 then forbids all of them on day 2 -> FM-1."])

S("Eight meals, 1,400 kcal",
  "My GI doctor wants 8 tiny meals, 1,400 kcal, 90 g protein, 35-50 g fat.",
  cats=["borderline", "meal-timing", "recipe-inventory"], intended="borderline",
  profile=P(1400, 90, 35, 50),
  days=[day([M(f"{h:02d}:00", 1, "snack") for h in (7, 9, 11, 13, 15, 17, 19, 21)])],
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Exactly one set of eight distinct <=5-minute recipes fits; any quick recipe removed from the library breaks it."])

S("Bulk on vegan snacks only",
  "Vegan, 3,000 kcal, 120 g protein, 80-110 g fat, and all four meals must be 5-minute stuff.",
  cats=["infeasible", "cook-time", "preferences"], intended="infeasible",
  profile=P(3000, 120, 80, 110),
  days=[day(std4(b=(1, 1, 1, 1)))], pool_ids=pool("vegan"), pool_note="recipes tagged vegan")

# ======================================================================
# D. Nutrition conflicts
# ======================================================================
S("Low-carb but high fiber",
  "Low carb (2,000 kcal, 160 g protein, 90-110 g fat) and I also want 35 g fiber. Three meals, two days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="infeasible",
  profile=P(2000, 160, 90, 110, micros={"fiber_g": 35}),
  days=rep(day(std3(b=(3, 3, 4))), 2), pool_ids=CORE, pool_note=FULL)

S("Dairy-free with 1,200 mg calcium",
  "Dairy-free, but my doctor wants 1,200 mg calcium. 2,000 kcal, 120 g protein, 55-80 g fat, three meals, three days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2000, 120, 55, 80, micros={"calcium_mg": 1200}, demographic="adult_female"),
  days=rep(day(std3(b=(3, 3, 4))), 3), pool_ids=pool("dairy-free"), pool_note="recipes tagged dairy-free",
  spec_notes=["Looks conflicting, but calcium-set tofu recipes carry ~1,300-1,700 mg calcium each."])

S("Vegetarian iron at 18 mg, 1,700 kcal",
  "Pregnant and vegetarian, iron 27 mg a day, and I can't stand cream of rice. 1,700 kcal, 90 g protein, 45-65 g fat, three meals, three days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="infeasible",
  profile=P(1700, 90, 45, 65, micros={"iron_mg": 27}, demographic="adult_female", excluded=["cream of rice dry"]),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian")

S("Same iron goal with tau 0.8",
  "Same as before (vegetarian, iron 27 mg, 1,700 kcal, 90 g protein, 45-65 g fat) but 80% of the iron target is acceptable.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="feasible",
  profile=P(1700, 90, 45, 65, micros={"iron_mg": 27}, tau=0.8, demographic="adult_female", excluded=["cream of rice dry"]),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian",
  spec_notes=["Pair with the previous scenario: only tau differs. Expect micronutrient_soft_deficit warning (spec 6.6)."])

S("High protein, low fat, low calorie",
  "1,600 kcal, 170 g protein, 25-35 g fat. Four meals.",
  cats=["borderline", "nutrition-conflict"], intended="borderline",
  profile=P(1600, 170, 25, 35),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=CORE, pool_note=FULL)

S("Fat floor too high for a cut",
  "Hormone health: fat at least 90 g, but 1,800 kcal and 150 g protein. Three meals.",
  cats=["borderline", "nutrition-conflict"], intended="borderline",
  profile=P(1800, 150, 90, 110),
  days=[day(std3(b=(3, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Potassium 4,700 mg on 1,800 kcal",
  "Aiming for the 4,700 mg potassium guideline on 1,800 kcal, 120 g protein, 45-70 g fat. Three meals, two days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="feasible",
  profile=P(1800, 120, 45, 70, micros={"potassium_mg": 4700}),
  days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL)

S("Calcium and iron together, 4 days",
  "Track calcium 1,000 mg and iron 18 mg. 2,000 kcal, 110 g protein, 55-80 g fat, four meals, four days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2000, 110, 55, 80, micros={"calcium_mg": 1000, "iron_mg": 18}, demographic="adult_female"),
  days=rep(day(std4()), 4), pool_ids=CORE, pool_note=FULL)

S("Pre-workout carbs vs low-carb day",
  "Low-carb day (1,900 kcal, 150 g protein, 80-100 g fat) but I'm lifting at 6pm and want a proper pre-workout snack.",
  cats=["nutrition-conflict", "meal-timing", "tags"], intended="feasible",
  profile=P(1900, 150, 80, 100),
  days=[day([M("08:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("17:00", 1, "snack", req=["pre-workout"]),
             M("20:00", 4, "dinner")], [W(3, "PM", "high")])],
  pool_ids=CORE, pool_note=FULL)

S("Ceiling slightly under +10%",
  "Target 2,200, ceiling 2,300. 150 g protein, 55-80 g fat, three meals.",
  cats=["nutrition-conflict", "calorie-ceiling"], intended="feasible",
  profile=P(2200, 150, 55, 80, ceiling=2300),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL)

S("Protein floor and fat cap on vegetarian bulk",
  "Vegetarian bulk: 2,900 kcal, 160 g protein, 60-80 g fat, four meals.",
  cats=["nutrition-conflict"], intended="feasible",
  profile=P(2900, 160, 60, 80),
  days=[day(std4(b=(2, 3, 1, 4)))], pool_ids=pool("vegetarian"), pool_note="recipes tagged vegetarian")

S("Magnesium strict vs UL note",
  "Magnesium 420 mg (strict), 2,400 kcal, 130 g protein, 60-90 g fat, three meals, two days.",
  cats=["nutrition-conflict", "micronutrients", "multi-day"], intended="feasible",
  profile=P(2400, 130, 60, 90, micros={"magnesium_mg": 420}),
  days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL,
  spec_notes=["Reference magnesium UL (350 mg, supplement-only) is below this RDI; if ULs were wired into plan_meals this becomes infeasible by construction (reconciliation B6/E10). Oracle does not apply ULs."])

# ======================================================================
# E. Insufficient recipe inventory
# ======================================================================
STARTER6 = ["bk_protein_oats", "bk_yogurt_berry_bowl", "ln_turkey_sandwich", "ln_tuna_poke", "dn_beef_rice_bowl", "dn_tilapia_rice"]

S("Starter pack, one day",
  "Just signed up and saved 6 recipes. 1,900 kcal, 120 g protein, 40-60 g fat, three meals tomorrow.",
  cats=["recipe-inventory", "feasible"], intended="borderline",
  profile=P(1900, 120, 40, 60), days=[day(std3(b=(2, 3, 3)))],
  pool_ids=STARTER6, pool_note="6 saved recipes")

S("Starter pack, two days",
  "Same six recipes, can you do two days? 1,900 kcal, 120 g protein, 40-60 g fat.",
  cats=["recipe-inventory", "multi-day-conflict"], intended="infeasible",
  profile=P(1900, 120, 40, 60), days=rep(day(std3(b=(2, 3, 3))), 2),
  pool_ids=STARTER6, pool_note="6 saved recipes",
  spec_notes=["Only one 3-recipe set fits the day; HC-8 forbids repeating it on day 2 -> FM-1."])

S("Starter pack, full week",
  "OK now the whole week with those six recipes. 1,900 kcal, 120 g protein, 40-60 g fat.",
  cats=["recipe-inventory", "multi-day-conflict"], intended="infeasible",
  profile=P(1900, 120, 40, 60), days=rep(day(std3(b=(2, 3, 3))), 7),
  pool_ids=STARTER6, pool_note="6 saved recipes",
  spec_notes=["With 6 recipes and 3 non-workout slots, HC-8 forces two disjoint triples alternating across 7 days."])

S("Four recipes, four meals, two days",
  "I have four recipes and eat four times a day. 1,850 kcal, 115 g protein, 40-55 g fat, Monday and Tuesday.",
  cats=["recipe-inventory", "multi-day-conflict"], intended="infeasible",
  profile=P(1850, 115, 40, 55), days=rep(day(std4()), 2),
  pool_ids=["bk_overnight_oats", "ln_turkey_sandwich", "sn_yogurt_honey", "dn_beef_rice_bowl"], pool_note="4 saved recipes")

S("Only slow recipes for busy slots",
  "My saved recipes are all weekend cooking projects but I need a weekday plan: breakfast 5 min, lunch 15 min, dinner 30 min. 2,200 kcal, 140 g protein, 55-85 g fat.",
  cats=["recipe-inventory", "cook-time", "infeasible"], intended="infeasible",
  profile=P(2200, 140, 55, 85), days=[day(std3(b=(1, 2, 3)))],
  pool_ids=["dn_beef_chili", "dn_thigh_sheet_pan", "dn_salmon_potatoes", "dn_thigh_quinoa_prep", "hc_pasta_salmon_bake",
            "dn_chickpea_curry", "dn_big_pasta_night"], pool_note="7 recipes, all >30 minutes")

S("Only snack recipes saved",
  "I mostly saved snacks. 2,000 kcal, 110 g protein, 55-80 g fat, three meals and two snacks.",
  cats=["recipe-inventory"], intended="feasible",
  profile=P(2000, 110, 55, 80), days=[day(five())],
  pool_ids=pool("snack"), pool_note="recipes tagged snack")

S("Vegan pool, week of dinners",
  "Vegan, dinners only (I eat at a work canteen otherwise). 700 kcal, 30 g protein, 15-30 g fat per day, 7 days.",
  cats=["recipe-inventory", "multi-day-conflict"], intended="infeasible",
  profile=P(700, 30, 15, 30), days=rep(day([M("19:00", 3, "dinner")]), 7),
  pool_ids=pool("vegan"), pool_note="recipes tagged vegan",
  spec_notes=["Single-slot days: HC-8 needs two alternating dinners that each fit the day windows."])

S("Duplicate-only pool",
  "I generated recipes with the AI and got three beef bowls. 1,700 kcal, 130 g protein, 55-80 g fat, three meals.",
  cats=["recipe-inventory", "data-quality"], intended="infeasible",
  profile=P(1700, 130, 55, 80), days=[day(std3(b=(3, 3, 4)))],
  pool_ids=["dn_beef_rice_bowl", "dup_beef_rice_bowl_v2", "dup_beef_rice_bowl_v3"],
  pool_note="three content-identical recipes under distinct IDs",
  spec_notes=["HC-2 compares IDs, so eating the same bowl three times passes; the day still misses the kcal window (3 x 688 = 2,064 > 1,870)."])

S("Duplicate-content pool that fits",
  "Same three AI beef bowls, but I only eat three meals of ~700. 2,050 kcal, 128 g protein, 60-75 g fat.",
  cats=["recipe-inventory", "data-quality"], intended="borderline",
  profile=P(2050, 128, 60, 75), days=[day(std3(b=(3, 3, 4)))],
  pool_ids=["dn_beef_rice_bowl", "dup_beef_rice_bowl_v2", "dup_beef_rice_bowl_v3"],
  pool_note="three content-identical recipes under distinct IDs",
  spec_notes=["Spec-valid plan serves an identical meal three times (identity by ID; OR review 2.3). Quality metric: distinct content meals = 1."],
  safety={"quality_expectation": "a variety-aware planner should flag or reject identical-content meals in one day"})

S("Breakfast recipes missing",
  "I want a real breakfast every morning but I haven't saved any breakfast recipes yet. 2,100 kcal, 140 g protein, 55-80 g fat.",
  cats=["recipe-inventory", "tag-conflict"], intended="infeasible",
  profile=P(2100, 140, 55, 80), days=[day(std3(req=(["breakfast"], None, None)))],
  pool_ids=pool("dinner"), pool_note="dinner recipes only")

S("Excluded ingredients shrink pool",
  "No beef, no pork, no dairy, nothing with soy. 2,000 kcal, 120 g protein, 50-75 g fat, three meals, two days.",
  cats=["recipe-inventory", "preferences", "multi-day", "borderline"], intended="borderline",
  profile=P(2000, 120, 50, 75, excluded=["hamburger or beef 90%", "hamburger or beef 95%", "roast beef lunchmeat", "salami genoa",
                                         "milk", "butter", "whey protein powder", "greek yogurt plain nonfat", "low fat greek yogurt",
                                         "cottage cheese 1% fat", "sharp cheddar cheese", "feta cheese reduced fat",
                                         "cheddar cheese natural 50% reduced fat", "parmesan cheese hard", "parmesan grated",
                                         "soy sauce", "tofu not silken firm", "edamame beans"]),
  days=rep(day(std3(b=(3, 3, 4))), 2), pool_ids=CORE, pool_note=FULL)

# ======================================================================
# F. Pin conflicts
# ======================================================================
S("Pinned dinner out, relaxed slot",
  "Dinner at my mom's is salmon and potatoes; I'm not cooking, so dinner has no time limit. 2,100 kcal, 140 g protein, 50-80 g fat.",
  cats=["pins", "feasible"], intended="feasible",
  profile=P(2100, 140, 50, 80), days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_salmon_potatoes")],
  spec_notes=["Counterpart to the busyness-3 version: same pin, slot relaxed to busyness 4."])

S("Pinned mass gainer on a cut",
  "Keep my homemade mass gainer shake at breakfast, but I'm on 1,800 kcal, 140 g protein, 45-65 g fat.",
  cats=["pins", "nutrition-conflict"], intended="feasible",
  profile=P(1800, 140, 45, 65), days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "hc_mass_gainer")],
  spec_notes=["Looks like a pin conflict (1,142 kcal pinned of 1,800) but two lean meals close the gap."])

S("Same recipe pinned twice in a day",
  "Protein oats for breakfast AND as my evening snack please. 2,300 kcal, 140 g protein, 55-85 g fat.",
  cats=["pin-conflict"], intended="infeasible",
  profile=P(2300, 140, 55, 85), days=[day(std4())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_protein_oats"), (0, 2, "bk_protein_oats")])

S("Same breakfast every weekday",
  "I eat the yogurt berry bowl every single morning. Pin it Monday through Wednesday. 2,000 kcal, 130 g protein, 50-75 g fat.",
  cats=["pin-conflict", "multi-day-conflict"], intended="infeasible",
  profile=P(2000, 130, 50, 75), days=rep(day(std3()), 3), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_yogurt_berry_bowl"), (1, 0, "bk_yogurt_berry_bowl"), (2, 0, "bk_yogurt_berry_bowl")],
  spec_notes=["HC-8 forbids the same non-workout recipe on consecutive days -> FM-3 pre-validation. A very common real habit the spec cannot express."])

S("Same breakfast every other day",
  "Fine, yogurt bowl Monday and Wednesday only. 2,000 kcal, 130 g protein, 50-75 g fat.",
  cats=["pins", "multi-day"], intended="feasible",
  profile=P(2000, 130, 50, 75), days=rep(day(std3()), 3), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_yogurt_berry_bowl"), (2, 0, "bk_yogurt_berry_bowl")])

S("Pinned recipe contains allergen",
  "Pin the peanut butter banana toast for breakfast. Oh, and peanut butter is on my exclusion list now.",
  cats=["pin-conflict", "preferences"], intended="infeasible",
  profile=P(2100, 120, 55, 80, excluded=["peanut butter"]), days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_pb_banana_toast")])

S("Pinned sheet-pan dinner on a busy night",
  "Pin the chicken thigh sheet pan for Tuesday dinner. Tuesday I only have 15 minutes for dinner. 2,200 kcal, 150 g protein, 55-80 g fat.",
  cats=["pin-conflict", "cook-time"], intended="infeasible",
  profile=P(2200, 150, 55, 80), days=[day(std3(b=(2, 3, 2)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_thigh_sheet_pan")])

S("Pinned meal alone breaks the ceiling",
  "Very low-calorie phase: 1,000 kcal target, never above 1,100, 90 g protein, 20-35 g fat. But it's my birthday, pin Big Pasta Night for dinner.",
  cats=["pin-conflict", "calorie-ceiling"], intended="infeasible",
  profile=P(1000, 90, 20, 35, ceiling=1100), days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_big_pasta_night")])

S("Pin to a slot that no longer exists",
  "I pinned a snack at slot 4 last week but this week I dropped to three meals. 2,000 kcal, 130 g protein, 50-80 g fat.",
  cats=["pin-conflict"], intended="infeasible",
  profile=P(2000, 130, 50, 80), days=[day(std3())], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 3, "sn_trail_mix")],
  spec_notes=["Stale pin: slot_index 3 on a 3-slot day. Spec does not name this case; oracle treats it as FM-3."])

S("Pinned recipe not in selected pool",
  "Only plan from my 'weeknight' list, and keep the salmon pasta bake pinned for dinner. 2,200 kcal, 140 g protein, 55-85 g fat.",
  cats=["pin-conflict", "recipe-inventory"], intended="infeasible",
  profile=P(2200, 140, 55, 85), days=[day(std3(b=(2, 3, 4)))],
  pool_ids=quick(30), pool_note="recipes <=30 min ('weeknight list'); pinned recipe (45 min) is outside it",
  pins=[(0, 2, "hc_pasta_salmon_bake")])

S("Fully pinned day that misses targets",
  "I already know what I'm eating: protein oats, turkey sandwich, beef rice bowl. Just check it. 2,400 kcal, 160 g protein, 55-80 g fat.",
  cats=["pin-conflict", "nutrition-conflict"], intended="infeasible",
  profile=P(2400, 160, 55, 80), days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_protein_oats"), (0, 1, "ln_turkey_sandwich"), (0, 2, "dn_beef_rice_bowl")])

S("Fully pinned day that fits",
  "Same three meals, but my real targets are 1,800 kcal, 115 g protein, 45-60 g fat.",
  cats=["pins", "feasible"], intended="borderline",
  profile=P(1800, 115, 45, 60), days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 0, "bk_protein_oats"), (0, 1, "ln_turkey_sandwich"), (0, 2, "dn_beef_rice_bowl")])

S("Pin lacks the slot's required tag",
  "Lunch must be portable, but on Friday pin the tilapia rice (I'm working from home). 2,100 kcal, 140 g protein, 50-80 g fat.",
  cats=["pins", "tags"], intended="feasible",
  profile=P(2100, 140, 50, 80), days=[day(std3(req=(None, ["portable"], None)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 1, "dn_tilapia_rice")],
  spec_notes=["Precedence pin > required tags (spec 3.5): pinned slot skips HC-9."])

S("Two pins leave little room",
  "Pin chili for lunch and the burger bowl for dinner. 1,900 kcal, 150 g protein, 45-70 g fat, three meals.",
  cats=["pin-conflict", "nutrition-conflict", "borderline"], intended="borderline",
  profile=P(1900, 150, 45, 70), days=[day(std3(b=(2, 4, 4)))], pool_ids=CORE, pool_note=FULL,
  pins=[(0, 1, "dn_beef_chili"), (0, 2, "dn_burger_bowl")])

S("Pins on non-consecutive days of a week",
  "Pin bolognese dinner on Monday, Wednesday, Friday (family pasta nights). 2,300 kcal, 140 g protein, 60-85 g fat, 5 days.",
  cats=["pins", "multi-day"], intended="feasible",
  profile=P(2300, 140, 60, 85), days=rep(day(std3(b=(2, 3, 4))), 5), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_bolognese"), (2, 2, "dn_bolognese"), (4, 2, "dn_bolognese")])

# ======================================================================
# G. Tag conflicts
# ======================================================================
S("Required high-protein breakfast",
  "Breakfast MUST be high-protein. 2,200 kcal, 150 g protein, 55-80 g fat, three meals.",
  cats=["tag-conflict"], intended="infeasible",
  profile=P(2200, 150, 55, 80), days=[day(std3(req=(["high-protein"], None, None)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["high-protein is a nutrition_claim (DM-6): hard_filter_allowed=false, so no recipe can satisfy it as a required tag -> FM-TAG-EMPTY despite many recipes carrying the tag."])

S("Required vegan breakfast in a mixed household",
  "My partner is vegan and we share breakfast, so breakfast has to be vegan; the rest can be anything. 2,200 kcal, 140 g protein, 55-85 g fat.",
  cats=["tags", "feasible"], intended="feasible",
  profile=P(2200, 140, 55, 85), days=[day(std3(req=(["vegan"], None, None)))], pool_ids=CORE, pool_note=FULL)

S("Vegan meal-prep breakfast",
  "Breakfast needs to be vegan AND something I can meal-prep. 2,000 kcal, 120 g protein, 50-80 g fat.",
  cats=["tag-conflict"], intended="infeasible",
  profile=P(2000, 120, 50, 80), days=[day(std3(req=(["breakfast", "vegan", "meal-prep"], None, None)))],
  pool_ids=CORE, pool_note=FULL)

S("Portable vegan breakfast (proposed tag only)",
  "Vegan breakfast I can eat on the train, so portable. 2,000 kcal, 120 g protein, 50-80 g fat.",
  cats=["tag-conflict"], intended="infeasible",
  profile=P(2000, 120, 50, 80), days=[day(std3(req=(["breakfast", "vegan", "portable"], None, None)))],
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Only bk_tofu_scramble carries 'portable', and only as an LLM-proposed tag -> not hard-eligible -> FM-TAG-EMPTY."])

S("Kid's gluten-free dinner, no cheddar",
  "Dinner feeds my kid: it has to be kid-friendly and gluten-free, and they hate cheddar. 2,100 kcal, 140 g protein, 55-85 g fat for me.",
  cats=["tag-conflict", "preferences"], intended="infeasible",
  profile=P(2100, 140, 55, 85, excluded=["sharp cheddar cheese"]),
  days=[day(std3(req=(None, None, ["kid-friendly", "gluten-free"])))], pool_ids=CORE, pool_note=FULL)

S("Unknown tag slug",
  "Make dinner keto. 1,900 kcal, 140 g protein, 70-90 g fat.",
  cats=["tag-conflict", "input-validation"], intended="infeasible",
  profile=P(1900, 140, 70, 90), days=[day(std3(req=(None, None, ["keto"])))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["'keto' is not in the tag registry; MealSlot validation rejects unknown slugs -> INVALID_REQUEST (HTTP 400), not a planner failure."])

S("Tag alias batch-cook",
  "Lunch should be a batch-cook recipe. 2,200 kcal, 140 g protein, 55-85 g fat.",
  cats=["tags", "feasible"], intended="feasible",
  profile=P(2200, 140, 55, 85), days=[day(std3(req=(None, ["batch-cook"], None)))], pool_ids=CORE, pool_note=FULL,
  spec_notes=["'batch-cook' is a registered alias of 'meal-prep' and must resolve before HC-9."])

S("Every slot tagged breakfast",
  "I'm a breakfast-for-every-meal person. All three meals must be breakfast recipes. 2,100 kcal, 110 g protein, 55-80 g fat.",
  cats=["tags"], intended="feasible",
  profile=P(2100, 110, 55, 80),
  days=[day(std3(b=(2, 2, 3), req=(["breakfast"], ["breakfast"], ["breakfast"])))], pool_ids=CORE, pool_note=FULL)

S("Vegetarian dinner every day for a week",
  "Meat at lunch is fine, but dinners must be vegetarian all week. 2,200 kcal, 130 g protein, 55-85 g fat.",
  cats=["tags", "multi-day"], intended="feasible",
  profile=P(2200, 130, 55, 85),
  days=rep(day(std3(b=(2, 3, 4), req=(None, None, ["vegetarian", "dinner"]))), 7), pool_ids=CORE, pool_note=FULL)

S("Quick vegetarian dinners all week",
  "Vegetarian dinners every night this week, and weeknight dinners are 15 minutes max. 2,200 kcal, 130 g protein, 55-85 g fat.",
  cats=["tag-conflict", "multi-day-conflict", "cook-time"], intended="infeasible",
  profile=P(2200, 130, 55, 85),
  days=rep(day(std3(b=(2, 3, 2), req=(None, None, ["vegetarian", "dinner"]))), 7), pool_ids=CORE, pool_note=FULL)

S("Required lunch+dinner dual-tag slot",
  "One big midday meal that works as lunch or dinner (tagged both), plus breakfast. 1,500 kcal, 110 g protein, 35-55 g fat.",
  cats=["tags", "borderline"], intended="borderline",
  profile=P(1500, 110, 35, 55), days=[day([M("08:00", 2, "breakfast"), M("14:00", 4, "lunch", req=["lunch", "dinner"])])],
  pool_ids=CORE, pool_note=FULL)

S("Dairy-free required, pool mostly dairy",
  "Lunch must be dairy-free, I only saved these recipes. 2,000 kcal, 130 g protein, 50-80 g fat.",
  cats=["tag-conflict", "recipe-inventory"], intended="infeasible",
  profile=P(2000, 130, 50, 80), days=[day(std3(req=(None, ["dairy-free"], None)))],
  pool_ids=["bk_yogurt_berry_bowl", "bk_protein_oats", "ln_turkey_sandwich", "ln_cottage_box", "dn_burger_bowl", "dn_bolognese", "sn_protein_shake"],
  pool_note="7 saved recipes, none tagged dairy-free")

S("Preferred tag that no recipe has",
  "Would be nice if lunch were kid-friendly, not required. 2,100 kcal, 140 g protein, 55-80 g fat.",
  cats=["tags", "feasible"], intended="feasible",
  profile=P(2100, 140, 55, 80), days=[day(std3(pref=(None, ["kid-friendly"], None)))],
  pool_ids=pool(drop=[i for i in CORE if "kid-friendly" in _BY_ID[i]["tags"]]), pool_note="library minus kid-friendly recipes",
  spec_notes=["Preferred tags never reject (spec 2.1.1); expect success with no kid-friendly lunch."])

S("Required post-workout meal",
  "The meal right after my 5pm lift must be a post-workout recipe. 2,600 kcal, 180 g protein, 60-90 g fat, four meals, two days.",
  cats=["tags", "meal-timing", "multi-day"], intended="feasible",
  profile=P(2600, 180, 60, 90),
  days=rep(day([M("07:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("18:30", 1, "snack", req=["post-workout"]),
                M("20:30", 4, "dinner")], [W(2, "PM", "high")]), 2),
  pool_ids=CORE, pool_note=FULL)

# ======================================================================
# H. Meal-prep conflicts
# ======================================================================
S("Sunday chili for weekday lunches (busy)",
  "I cook chili Sunday and eat it for lunch Monday-Wednesday. Lunch break is 15 minutes. 2,100 kcal, 150 g protein, 50-80 g fat.",
  cats=["meal-prep-conflict", "cook-time", "multi-day"], intended="infeasible",
  profile=P(2100, 150, 50, 80), days=rep(day(std3(b=(2, 2, 3))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chili", "dn_beef_chili", 3, [(0, 1), (1, 1), (2, 1)])],
  spec_notes=["Q9: the lock's recipe (60 min) is checked against the reheating slot's busyness cap (15 min) -> FM-3 (HC-3). Also violates HC-8. This is the feature's core use case."])

S("Sunday chili, lunch slot relaxed",
  "Same chili plan, I set lunch to 'flexible' so the time limit doesn't block it.",
  cats=["meal-prep-conflict", "multi-day-conflict"], intended="infeasible",
  profile=P(2100, 150, 50, 80), days=rep(day(std3(b=(2, 4, 3))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chili", "dn_beef_chili", 3, [(0, 1), (1, 1), (2, 1)])],
  spec_notes=["HC-3 now passes; HC-8 (same non-workout recipe on consecutive days) still rejects -> FM-3."])

S("Prepped chickpea salad two days in a row",
  "Chickpea salad prepped for Monday and Tuesday lunch. 2,100 kcal, 130 g protein, 55-80 g fat.",
  cats=["meal-prep-conflict", "multi-day-conflict"], intended="infeasible",
  profile=P(2100, 130, 55, 80), days=rep(day(std3(b=(2, 2, 3))), 2), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chickpea", "ln_chickpea_salad", 2, [(0, 1), (1, 1)])])

S("Prepped meal in post-workout slots",
  "I train at lunchtime and eat my prepped thigh-quinoa bowl right after, Monday and Tuesday. 2,300 kcal, 160 g protein, 55-85 g fat.",
  cats=["meal-prep", "meal-timing", "multi-day"], intended="feasible",
  profile=P(2300, 160, 55, 85),
  days=rep(day([M("07:00", 2, "breakfast"), M("13:00", 4, "lunch"), M("19:00", 3, "dinner")], [W(1, "PM", "high")]), 2),
  pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_thigh_quinoa", "dn_thigh_quinoa_prep", 2, [(0, 1), (1, 1)])],
  spec_notes=["Lunch is post-workout, so HC-8 exempts the repeated batch. Busyness 4 lunch avoids HC-3."])

S("Two batches claim the same slot",
  "I prepped both curry and chili and assigned both to Monday dinner by mistake. 2,200 kcal, 140 g protein, 55-85 g fat.",
  cats=["meal-prep-conflict"], intended="infeasible",
  profile=P(2200, 140, 55, 85), days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_curry", "dn_chickpea_curry", 2, [(0, 2)]), B("batch_chili", "dn_beef_chili", 2, [(0, 2)])])

S("Batch assigned more slots than servings",
  "Made 2 servings of curry, assigned it to three dinners.",
  cats=["meal-prep-conflict", "input-validation"], intended="infeasible",
  profile=P(2200, 140, 55, 85), days=rep(day(std3(b=(2, 3, 4))), 5), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_curry", "dn_chickpea_curry", 2, [(0, 2), (2, 2), (4, 2)])],
  spec_notes=["Rejected by MealPrepBatchRepository._validate_create before any planning."])

S("Single-serving batch",
  "I 'meal prepped' one serving of bolognese for Wednesday.",
  cats=["meal-prep-conflict", "input-validation"], intended="infeasible",
  profile=P(2300, 140, 60, 85), days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_bolo", "dn_bolognese", 1, [(2, 2)])],
  spec_notes=["total_servings must be >= 2 (repository validation)."])

S("Batch recipe now contains an excluded ingredient",
  "Chili is prepped for Monday and Wednesday dinner, but I just added reduced-fat cheddar to my exclusions.",
  cats=["meal-prep-conflict", "preferences"], intended="infeasible",
  profile=P(2100, 150, 50, 80, excluded=["cheddar cheese natural 50% reduced fat"]),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chili", "dn_beef_chili", 2, [(0, 2), (2, 2)])])

S("Batch lock overrides a pin",
  "I pinned tilapia for Monday dinner, then later assigned my prepped curry to the same slot.",
  cats=["meal-prep", "pins"], intended="feasible",
  profile=P(2200, 120, 55, 85), days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_tilapia_rice")],
  batches=[B("batch_curry", "dn_chickpea_curry", 2, [(0, 2)])],
  spec_notes=["Batch lock > explicit pin (spec 3.5); expect curry in (0,2) and the pin reported as overridden."])

S("High-calorie batch on a cut",
  "I prepped salmon pasta bake for Monday and Wednesday dinner, but I'm cutting at 1,250 kcal, 110 g protein, 30-42 g fat.",
  cats=["meal-prep-conflict", "nutrition-conflict", "borderline"], intended="borderline",
  profile=P(1250, 110, 30, 42), days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_bake", "hc_pasta_salmon_bake", 2, [(0, 2), (2, 2)])])

S("Mon/Wed/Fri batch",
  "Big pot of curry for Monday, Wednesday and Friday dinners. 2,200 kcal, 120 g protein, 55-85 g fat, 5 days.",
  cats=["meal-prep", "multi-day"], intended="feasible",
  profile=P(2200, 120, 55, 85), days=rep(day(std3(b=(2, 3, 4))), 5), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_curry", "dn_chickpea_curry", 3, [(0, 2), (2, 2), (4, 2)])])

S("Alternating two batches",
  "Two prepped dinners alternating: chili Mon/Wed, curry Tue/Thu. 2,100 kcal, 130 g protein, 50-80 g fat, 4 days.",
  cats=["meal-prep", "multi-day", "borderline"], intended="borderline",
  profile=P(2100, 130, 50, 80), days=rep(day(std3(b=(2, 3, 4))), 4), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_chili", "dn_beef_chili", 2, [(0, 2), (2, 2)]), B("batch_curry", "dn_chickpea_curry", 2, [(1, 2), (3, 2)])])

S("Double-portion batch servings",
  "Prepped 4 servings of the thigh-quinoa bowl; I eat a double portion at dinner Monday and Wednesday. 2,600 kcal, 180 g protein, 60-90 g fat.",
  cats=["meal-prep-conflict", "nutrition-conflict", "borderline"], intended="borderline",
  profile=P(2600, 180, 60, 90), days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[{**B("batch_thigh", "dn_thigh_quinoa_prep", 4, [(0, 2), (2, 2)]),
            "assignments": [{"day_index": 0, "slot_index": 2, "servings": 2.0}, {"day_index": 2, "slot_index": 2, "servings": 2.0}]}],
  spec_notes=["Assignment servings=2.0 is accepted by the repository but not used in nutrition accounting (OR review 2.2). Oracle scores ONE serving; a servings-aware planner would see +620 kcal in each locked slot and likely fail."])

S("Batch assigned beyond the horizon",
  "Curry batch assigned to day 5, but I'm only planning 3 days.",
  cats=["meal-prep-conflict"], intended="infeasible",
  profile=P(2200, 120, 55, 85), days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  batches=[B("batch_curry", "dn_chickpea_curry", 2, [(0, 2), (4, 2)])],
  spec_notes=["Spec does not define locks outside the horizon; oracle treats as FM-3 (slot out of range). Implementations may instead ignore the lock - record which."])

# ======================================================================
# I. Multi-day conflicts
# ======================================================================
WEEKDAY = day(std3(b=(1, 2, 3)))
WEEKEND = day(std3(b=(4, 4, 4), t=("09:30", "13:30", "19:00")))

S("Busy weekdays, relaxed weekend",
  "Weekdays I'm slammed (5/15/30 min), weekends I cook. 2,200 kcal, 140 g protein, 55-85 g fat, a full week starting Monday.",
  cats=["multi-day", "cook-time", "feasible"], intended="feasible",
  profile=P(2200, 140, 55, 85), days=rep(WEEKDAY, 5) + rep(WEEKEND, 2), pool_ids=CORE, pool_note=FULL)

S("Six recipes, alternating week",
  "I rotate six recipes. 1,630 kcal, 122 g protein, 35-45 g fat, three meals, 5 days.",
  cats=["multi-day-conflict", "recipe-inventory"], intended="borderline",
  profile=P(1630, 122, 35, 45), days=rep(day(std3(b=(2, 3, 3))), 5), pool_ids=STARTER6, pool_note="6 saved recipes",
  spec_notes=["Positive twin of the starter-pack week: targets chosen so two disjoint triples both fit, letting HC-8 alternate them."])

S("Five recipes, three meals, five days",
  "Five recipes on rotation, three meals a day, Monday-Friday. 2,000 kcal, 130 g protein, 50-80 g fat.",
  cats=["multi-day-conflict", "recipe-inventory"], intended="infeasible",
  profile=P(2000, 130, 50, 80), days=rep(day(std3(b=(2, 3, 4))), 5),
  pool_ids=["bk_protein_oats", "ln_tuna_poke", "dn_beef_rice_bowl", "dn_thigh_sheet_pan", "bk_yogurt_berry_bowl"],
  pool_note="5 saved recipes")

S("Fiber 38 g strict, full week",
  "Full week, 38 g fiber strict, 2,300 kcal, 130 g protein, 55-85 g fat, three meals.",
  cats=["multi-day", "micronutrients"], intended="feasible",
  profile=P(2300, 130, 55, 85, micros={"fiber_g": 38}),
  days=rep(day(std3(b=(2, 3, 4))), 7), pool_ids=CORE, pool_note=FULL)

S("Dairy-free calcium 1,300 mg, 5 days",
  "Teen-level calcium target 1,300 mg, dairy-free, 5 days, 2,100 kcal, 120 g protein, 55-80 g fat.",
  cats=["multi-day-conflict", "micronutrients", "nutrition-conflict"], intended="infeasible",
  profile=P(2100, 120, 55, 80, micros={"calcium_mg": 1300}),
  days=rep(day(std3(b=(2, 3, 4))), 5), pool_ids=pool("dairy-free", drop=["bk_tofu_scramble", "dn_tofu_stir_fry", "ln_tofu_quinoa_salad"]),
  pool_note="dairy-free recipes, excluding the three tofu dishes (user dislikes tofu)")

S("Training vs rest days, one target",
  "I want more food on training days (Mon/Wed/Fri) and less on rest days, but the app only takes one target, so I put 2,300. 140 g protein, 55-85 g fat. Training days have a post-workout snack.",
  cats=["multi-day", "meal-timing"], intended="feasible",
  profile=P(2300, 140, 55, 85),
  days=[day([M("07:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("17:30", 1, "snack"), M("19:30", 4, "dinner")], [W(2, "PM", "high")]),
        day(std3(b=(2, 3, 4))),
        day([M("07:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("17:30", 1, "snack"), M("19:30", 4, "dinner")], [W(2, "PM", "high")]),
        day(std3(b=(2, 3, 4))),
        day([M("07:00", 2, "breakfast"), M("12:30", 3, "lunch"), M("17:30", 1, "snack"), M("19:30", 4, "dinner")], [W(2, "PM", "high")])],
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Per-day calorie targets are not expressible (single daily target); benchmark records the user's workaround."])

S("Pinned dinner on consecutive days",
  "Leftover bolognese: pin it Thursday and Friday dinner. 2,300 kcal, 140 g protein, 60-85 g fat.",
  cats=["multi-day-conflict", "pin-conflict"], intended="infeasible",
  profile=P(2300, 140, 60, 85), days=rep(day(std3(b=(2, 3, 4))), 2), pool_ids=CORE, pool_note=FULL,
  pins=[(0, 2, "dn_bolognese"), (1, 2, "dn_bolognese")])

S("5:2 fasting week",
  "5:2 diet: normal 2,000 kcal days, but Tuesday and Thursday I only eat one ~600 kcal meal. 120 g protein, 50-75 g fat.",
  cats=["multi-day-conflict", "nutrition-conflict"], intended="infeasible",
  profile=P(2000, 120, 50, 75),
  days=[day(std3(b=(2, 3, 4))), day([M("18:00", 3, "dinner")]), day(std3(b=(2, 3, 4))), day([M("18:00", 3, "dinner")]),
        day(std3(b=(2, 3, 4))), day(std3(b=(2, 3, 4))), day(std3(b=(2, 3, 4)))],
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Daily targets are global, so the one-meal fast days must hit 1,800-2,200 kcal with one recipe -> FM-2. The spec cannot express per-day targets."])

S("Short day then long day, iron floor",
  "Travel day Monday (two meals), normal Tuesday with four meals. Iron 18 mg, 2,000 kcal, 110 g protein, 50-80 g fat.",
  cats=["multi-day", "micronutrients", "borderline"], intended="borderline",
  profile=P(2000, 110, 50, 80, micros={"iron_mg": 18}, demographic="adult_female"),
  days=[day([M("10:00", 1, "breakfast"), M("19:00", 2, "dinner")]), day(std4())],
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Reconciliation E3: FC-4 uses the CURRENT day's slot count for max-achievable; a day with fewer slots than later days can be wrongly pruned."])

S("Weekday lunches all portable for a week",
  "Five workdays, lunch has to be portable and no-cook. 2,300 kcal, 140 g protein, 60-90 g fat.",
  cats=["multi-day", "tags"], intended="feasible",
  profile=P(2300, 140, 60, 90), days=rep(day(std3(b=(2, 1, 4), req=(None, ["portable", "no-cook"], None))), 5),
  pool_ids=CORE, pool_note=FULL,
  spec_notes=["Contrast with the 2-day portable-lunch scenario that fails: lower targets here admit several distinct portable lunches, so HC-8 can rotate them."])

S("Meal-prep dinners every night",
  "Every dinner this week must be a meal-prep recipe (I cook Sunday). 2,200 kcal, 130 g protein, 55-85 g fat.",
  cats=["multi-day", "tags", "meal-prep"], intended="feasible",
  profile=P(2200, 130, 55, 85), days=rep(day(std3(b=(2, 3, 4), req=(None, None, ["meal-prep"]))), 7),
  pool_ids=CORE, pool_note=FULL)

S("Seven-day magnesium strict, tau 1.0",
  "Magnesium 420 mg strict over a whole week, 2,000 kcal, 120 g protein, 55-80 g fat, three meals.",
  cats=["multi-day", "micronutrients"], intended="feasible",
  profile=P(2000, 120, 55, 80, micros={"magnesium_mg": 420}),
  days=rep(day(std3(b=(2, 3, 4))), 7), pool_ids=CORE, pool_note=FULL)

# ======================================================================
# J. Exclusion semantics and data hazards (real cached numbers)
# ======================================================================
S("Peanut allergy typed as 'peanuts'",
  "Severe peanut allergy. 2,200 kcal, 130 g protein, 55-85 g fat, three meals and a snack.",
  cats=["preferences", "safety", "data-quality"], intended="feasible",
  profile=P(2200, 130, 55, 85, excluded=["peanuts"], intent_excluded=["peanuts", "peanut butter"]),
  days=[day(std4())], pool_ids=CORE, pool_note=FULL,
  spec_notes=["HC-1 is exact normalized-name matching; 'peanuts' does not match 'peanut butter' (reconciliation Q10)."],
  safety={"must_not_contain_cache_keys": ["peanut_butter"], "severity": "allergen"})

S("Egg allergy typed as 'egg'",
  "Allergic to egg. 2,000 kcal, 110 g protein, 55-80 g fat, three meals.",
  cats=["preferences", "safety", "data-quality"], intended="feasible",
  profile=P(2000, 110, 55, 80, excluded=["egg"], intent_excluded=["egg", "egg yolk", "eggs"]),
  days=[day(std3())], pool_ids=CORE + ["dh_veggie_egg_scramble"], pool_note="full library + one data-hazard egg recipe",
  safety={"must_not_contain_cache_keys": ["egg_yolk", "eggs"], "severity": "allergen"})

S("Dairy allergy typed as 'dairy'",
  "Dairy allergy. 2,000 kcal, 120 g protein, 50-80 g fat, three meals.",
  cats=["preferences", "safety", "data-quality"], intended="feasible",
  profile=P(2000, 120, 50, 80, excluded=["dairy"],
            intent_excluded=["milk", "butter", "whey protein powder", "greek yogurt plain nonfat", "low fat greek yogurt",
                             "cottage cheese 1% fat", "sharp cheddar cheese", "feta cheese reduced fat",
                             "cheddar cheese natural 50% reduced fat", "parmesan cheese hard", "parmesan grated",
                             "chocolate dark 70-85% cacao solids", "kellogg's rice krispies treats original"]),
  days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE, pool_note=FULL,
  safety={"must_not_contain_ingredient_class": "dairy", "severity": "allergen"})

S("Gluten-free tag on a recipe with egg bread",
  "Celiac, so every meal must be gluten-free. 2,000 kcal, 120 g protein, 55-85 g fat.",
  cats=["tags", "safety", "data-quality"], intended="feasible",
  profile=P(2000, 120, 55, 85),
  days=[day(std3(b=(3, 3, 4), req=(["gluten-free"], ["gluten-free"], ["gluten-free"])))],
  pool_ids=CORE + ["dh_veggie_egg_scramble"], pool_note="full library + data-hazard 'Veggie Egg Scramble' (tagged gluten-free, cache resolves eggs to egg BREAD)",
  safety={"must_not_contain_recipe_ids": ["dh_veggie_egg_scramble"], "severity": "allergen"})

S("Oat parfait that is really oat oil",
  "Pin my oat yogurt parfait for breakfast (it's light, ~300 kcal). 1,800 kcal, 130 g protein, 40-60 g fat.",
  cats=["pin-conflict", "data-quality"], intended="infeasible",
  profile=P(1800, 130, 40, 60), days=[day(std3())], pool_ids=CORE + ["dh_oat_yogurt_parfait"],
  pool_note="full library + data-hazard parfait", pins=[(0, 0, "dh_oat_yogurt_parfait")],
  spec_notes=["Cached 'oats' is oat OIL: the parfait computes to 548 kcal / 41 g fat instead of ~330 kcal / 7 g. The pinned breakfast eats the fat budget and the day fails (FM-3 downstream); the real cause is a mis-resolved ingredient."])

S("Chicken breast bowl that is really deli roll",
  "Chicken breast rice bowl for lunch and dinner-style meals, cutting at 1,900 kcal, 170 g protein, 40-60 g fat.",
  cats=["pins", "data-quality", "pin-conflict"], intended="infeasible",
  profile=P(1900, 170, 40, 60), days=[day(std3())], pool_ids=CORE + ["dh_chicken_breast_rice"],
  pool_note="full library + data-hazard chicken bowl", pins=[(0, 1, "dh_chicken_breast_rice")],
  spec_notes=["With real chicken breast (~56 g protein) this day is likely feasible; with the cached deli-roll entry (33 g) the protein window fails. Data error surfaces as a pin/nutrition failure."])

S("Vitamin D tracked on mis-mapped data",
  "Track vitamin D at 600 IU, 2,100 kcal, 130 g protein, 55-80 g fat, three meals, three days.",
  cats=["micronutrients", "data-quality"], intended="feasible",
  profile=P(2100, 130, 55, 80, micros={"vitamin_d_iu": 600}),
  days=rep(day(std3(b=(2, 3, 4))), 3), pool_ids=CORE, pool_note=FULL,
  spec_notes=["Cached vitamin D values are implausible (e.g. tilapia bowl 9,926 IU, overnight oats 3,360 IU): the floor is trivially met. A correct data layer would make this much harder."])

S("Sweet potato hash with zero-calorie potatoes",
  "Pin the sweet potato beef hash for dinner. 1,700 kcal, 130 g protein, 40-60 g fat.",
  cats=["pins", "data-quality", "borderline"], intended="borderline",
  profile=P(1700, 130, 40, 60), days=[day(std3(b=(2, 3, 4)))], pool_ids=CORE + ["dh_sweet_potato_hash"],
  pool_note="full library + data-hazard hash", pins=[(0, 2, "dh_sweet_potato_hash")],
  spec_notes=["Cached sweet potato has 0 kcal but 17 g carbs/100 g, so the hash is ~170 kcal under-counted; kcal and carb windows disagree about it."])

# ======================================================================
# Saved-profile preferences (liked foods, preferred tags). These come from the
# user's stored profile rather than the request text, and never change
# feasibility (liked_foods is tie-break only; preferred tags are soft).
# ======================================================================
_ENRICH = {
    "Maintenance with afternoon snack": (["greek yogurt", "blueberries"], {2: ["no-cook"]}),
    "Moderate cut, 5 days, 3 meals": (["tuna", "rice"], {1: ["portable"]}),
    "Busy parent, quick meals": (["pasta", "cheddar"], {3: ["kid-friendly"]}),
    "Dairy-free three meals": (["tofu", "salmon"], {}),
    "High-protein cut with shake": (["whey", "turkey"], {0: ["high-protein"], 3: ["high-protein"]}),
    "Shift worker, late schedule": (["beef", "rice"], {2: ["reheats-well"]}),
    "Older adult, smaller appetite": (["cottage cheese", "papaya"], {0: ["low-fat"]}),
    "Five meals bodybuilding": (["beef", "potatoes", "whey"], {1: ["post-workout"]}),
    "Four-day vegetarian with snacks": (["chickpeas", "feta"], {1: ["high-fiber"]}),
    "Week plan, 3 meals, large pool": (["salmon", "chicken thigh"], {2: ["reheats-well"]}),
    "Fiber goal, 3 days": (["black beans", "chia seeds"], {0: ["high-fiber"], 1: ["high-fiber"]}),
    "Vegan high protein": (["tofu", "edamame"], {3: ["high-protein"]}),
    "Big bulk, four meals": (["pasta", "beef"], {}),
    "Everything under five minutes": (["cottage cheese", "turkey"], {1: ["portable"]}),
    "Pescatarian four days": (["tuna", "tilapia"], {}),
    "Vegetarian full week": (["pasta", "yogurt"], {2: ["kid-friendly"]}),
    "Two-a-day training": (["banana", "whey"], {0: ["pre-workout"], 3: ["post-workout"]}),
    "Six small meals": (["almonds", "blueberries"], {1: ["portable"], 3: ["portable"]}),
    "Quick lunches, relaxed dinners, 5 days": (["turkey", "salmon"], {1: ["portable"]}),
    "Low-fat heart diet": (["tilapia", "cottage cheese"], {0: ["low-fat"], 2: ["low-fat"]}),
    "Only snack recipes saved": (["almonds", "dark chocolate"], {}),
    "Required vegan breakfast in a mixed household": (["peanut butter", "banana"], {}),
    "Vegetarian dinner every day for a week": (["chickpeas", "spinach"], {2: ["reheats-well"]}),
    "Busy weekdays, relaxed weekend": (["salmon", "potatoes"], {1: ["portable"]}),
    "Mon/Wed/Fri batch": (["chickpeas", "rice"], {}),
    "Training vs rest days, one target": (["beef", "rice"], {}),
    "Meal-prep dinners every night": (["chicken thigh", "quinoa"], {2: ["reheats-well"]}),
}

for _sc in SCENARIOS:
    if _sc["title"] in _ENRICH:
        _liked, _pref = _ENRICH[_sc["title"]]
        _sc["profile"]["liked_foods"] = sorted(set(_sc["profile"]["liked_foods"]) | set(_liked))
        for _d in _sc["schedule_days"]:
            for _s_idx, _slugs in _pref.items():
                if _s_idx < len(_d["meals"]):
                    _d["meals"][_s_idx]["preferred_tag_slugs"] = list(_slugs)
        if not _sc["preferences_note"]:
            _sc["preferences_note"] = ("liked_foods / preferred_tag_slugs come from the saved profile; "
                                       "soft signals only, must not change feasibility")
assert len(SCENARIOS) == 150, len(SCENARIOS)
assert not [t for t in _ENRICH if t not in {s["title"] for s in SCENARIOS}]
