"""Benchmark recipe library built only from locally cached ingredients.

Every ingredient key is a file stem under ``.cache/ingredients/``. Quantities are
grams for ONE serving, so a recipe's computed nutrition is unambiguously one meal
(sidesteps the per-serving vs per-batch ambiguity, reconciliation Q3).

Core recipes use only cache entries whose USDA description matches the intended
food. ``DATA_HAZARD`` recipes deliberately use mis-resolved cache entries so a few
scenarios can measure how the system behaves on the real (wrong) numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / ".cache" / "ingredients"

# Cache entries whose resolved USDA record is not the intended food, or whose
# calories are inconsistent with their macros. Core recipes never use these.
QUARANTINED_INGREDIENTS: Dict[str, str] = {
    "bell_pepper": "resolved to 'TACO BELL, Nachos' (350 kcal/100 g)",
    "eggs": "resolved to 'Bread, egg' (287 kcal, 47.8 g carbs/100 g)",
    "oats": "resolved to 'Oil, oat' (884 kcal, 100 g fat/100 g)",
    "chicken_breast": "resolved to 'Chicken breast, roll, oven-roasted' deli roll (14.6 g protein, 883 mg sodium/100 g)",
    "cherry_tomatoes": "resolved to 'Cherries, raw'",
    "milk_1_fat_lowfat": "resolved to 'Cheese, cottage, lowfat, 1% milkfat'",
    "banana": "resolved to 'Bananas, dehydrated, or banana powder' (346 kcal/100 g)",
    "tortillas_corn": "resolved to flour tortillas (name says corn; gluten-free intent broken)",
    "kiwi_fruit_green": "0 kcal with 13.8 g carbs/100 g (energy field missing)",
    "mushrooms": "0 kcal with 8.2 g carbs/100 g (energy field missing)",
    "spaghetti_squash": "0 kcal with 0 g carbs/100 g (energy field missing)",
    "sweet_potato": "0 kcal with 17.3 g carbs/100 g (energy field missing)",
    "tomato": "0 kcal with 7.1 g carbs/100 g (energy field missing)",
    "acai_berry": "fortified beverage, not the fruit",
}

# Tag vocabulary for the benchmark tag fixture. Semantic class follows the
# DM-6 table in src/llm/tag_repository.py: nutrition claims are NOT hard-eligible.
TAG_VOCAB: Dict[str, Dict[str, str]] = {
    # context -> capability (hard-eligible)
    "breakfast": {"tag_type": "context", "display": "Breakfast"},
    "lunch": {"tag_type": "context", "display": "Lunch"},
    "dinner": {"tag_type": "context", "display": "Dinner"},
    "snack": {"tag_type": "context", "display": "Snack"},
    "portable": {"tag_type": "context", "display": "Portable"},
    "no-cook": {"tag_type": "context", "display": "No Cook"},
    "meal-prep": {"tag_type": "context", "display": "Meal Prep"},
    "reheats-well": {"tag_type": "context", "display": "Reheats Well"},
    "pre-workout": {"tag_type": "context", "display": "Pre-Workout"},
    "post-workout": {"tag_type": "context", "display": "Post-Workout"},
    "kid-friendly": {"tag_type": "context", "display": "Kid Friendly"},
    # constraint -> exclusion (hard-eligible)
    "vegetarian": {"tag_type": "constraint", "display": "Vegetarian"},
    "vegan": {"tag_type": "constraint", "display": "Vegan"},
    "pescatarian": {"tag_type": "constraint", "display": "Pescatarian"},
    "dairy-free": {"tag_type": "constraint", "display": "Dairy Free"},
    "gluten-free": {"tag_type": "constraint", "display": "Gluten Free"},
    "nut-free": {"tag_type": "constraint", "display": "Nut Free"},
    "no-shellfish": {"tag_type": "constraint", "display": "No Shellfish"},
    # nutrition -> nutrition_claim (soft only; NOT hard-eligible)
    "high-protein": {"tag_type": "nutrition", "display": "High Protein"},
    "high-fiber": {"tag_type": "nutrition", "display": "High Fiber"},
    "low-carb": {"tag_type": "nutrition", "display": "Low Carb"},
    "low-fat": {"tag_type": "nutrition", "display": "Low Fat"},
}

HARD_ELIGIBLE_TAG_TYPES = {"context", "constraint", "time"}
TAG_ALIASES = {"batch-cook": "meal-prep"}
KNOWN_SLUGS = set(TAG_VOCAB) | {f"time-{t}" for t in range(5)}


def R(rid, name, minutes, ingredients, tags, proposed=(), notes=""):
    return {
        "id": rid,
        "name": name,
        "cooking_time_minutes": minutes,
        "ingredients": ingredients,
        "tags": list(tags),
        # Tags present in tags_by_id but only LLM-proposed (not hard-eligible).
        "proposed_tags": list(proposed),
        "notes": notes,
    }


# fmt: off
RECIPES: List[dict] = [
    # ---------------- breakfast ----------------
    R("bk_yogurt_berry_bowl", "Greek Yogurt Berry Bowl", 3,
      {"greek_yogurt_plain_nonfat": 250, "blueberries": 100, "honey": 15, "chia_seeds": 15},
      ["breakfast", "snack", "vegetarian", "gluten-free", "nut-free", "no-cook", "high-protein"]),
    R("bk_overnight_oats", "Overnight Oats with Banana", 5,
      {"rolled_oats": 60, "milk": 200, "chia_seeds": 10, "bananas": 100, "honey": 10},
      ["breakfast", "vegetarian", "nut-free", "no-cook", "meal-prep", "high-fiber"]),
    R("bk_protein_oats", "Protein Oatmeal", 8,
      {"rolled_oats": 80, "whey_protein_powder": 30, "blueberries": 80, "almond_butter_unsalted": 16, "milk": 150},
      ["breakfast", "vegetarian", "post-workout", "high-protein"]),
    R("bk_cottage_papaya", "Cottage Cheese with Papaya and Almonds", 2,
      {"cottage_cheese_1_fat": 225, "papaya": 150, "almonds": 15},
      ["breakfast", "snack", "vegetarian", "gluten-free", "no-cook", "high-protein"]),
    R("bk_avocado_toast_feta", "Avocado Feta Toast", 7,
      {"sourdough_bread": 90, "avocados_raw_all_commercial_varieties": 100, "lemon_juice": 5, "feta_cheese_reduced_fat": 30},
      ["breakfast", "vegetarian", "nut-free"]),
    R("bk_cream_of_rice_whey", "Cream of Rice with Whey and Banana", 6,
      {"cream_of_rice_dry": 60, "whey_protein_powder": 30, "bananas": 120, "honey": 10},
      ["breakfast", "vegetarian", "gluten-free", "nut-free", "pre-workout", "low-fat"]),
    R("bk_tofu_scramble", "Tofu Scramble Wrap", 15,
      {"tofu_not_silken_firm": 200, "spinach": 60, "red_peppers": 80, "olive_oil": 10, "salsa_ready-to-serve": 50},
      ["breakfast", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "high-protein"],
      proposed=["portable"]),
    R("bk_pb_banana_toast", "Peanut Butter Banana Toast", 4,
      {"sourdough_bread": 80, "peanut_butter": 32, "bananas": 120, "honey": 10},
      ["breakfast", "vegan", "vegetarian", "dairy-free", "kid-friendly"]),
    R("bk_chia_pudding", "Blackberry Chia Pudding", 5,
      {"chia_seeds": 35, "milk": 250, "blackberries_unsweetened": 100, "honey": 10},
      ["breakfast", "snack", "vegetarian", "gluten-free", "nut-free", "no-cook", "meal-prep", "high-fiber"]),
    R("bk_salmon_toast", "Salmon Cottage Cheese Toast", 5,
      {"sourdough_bread": 90, "salmon_canned": 100, "cottage_cheese_1_fat": 100, "cucumber": 60, "lemon_juice": 5},
      ["breakfast", "lunch", "pescatarian", "nut-free", "high-protein"]),
    R("bk_yolk_spinach_toast", "Egg Yolk Spinach Toast", 10,
      {"egg_yolk": 51, "spinach": 60, "butter": 5, "sourdough_bread": 70},
      ["breakfast", "vegetarian", "nut-free"]),
    R("bk_big_oat_bowl", "Big Oat Bowl (Bulk)", 6,
      {"rolled_oats": 120, "milk": 300, "peanut_butter": 32, "bananas": 120, "honey": 20},
      ["breakfast", "vegetarian", "high-fiber"]),

    # ---------------- lunch ----------------
    R("ln_turkey_sandwich", "Turkey Cheddar Sandwich", 5,
      {"sourdough_bread": 100, "turkey_breast_lunchmeat_reduced_fat": 110, "lettuce": 30, "cheddar_cheese_natural_50_reduced_fat": 30, "cucumber": 40},
      ["lunch", "portable", "no-cook", "nut-free", "high-protein"]),
    R("ln_roast_beef_wrap", "Roast Beef Feta Wrap", 5,
      {"tortillas_corn": 80, "roast_beef_lunchmeat": 120, "lettuce": 30, "feta_cheese_reduced_fat": 30, "red_peppers": 50},
      ["lunch", "portable", "no-cook", "nut-free", "high-protein"],
      notes="tortillas_corn cache entry is actually a flour tortilla; recipe is not gluten-free"),
    R("ln_tuna_poke", "Tuna Poke Bowl", 15,
      {"tuna_sashimi": 150, "jasmine_rice_in_unsalted_water": 220, "edamame_beans": 80, "cucumber": 60, "soy_sauce": 15, "sesame_oil": 5},
      ["lunch", "dinner", "pescatarian", "dairy-free", "nut-free", "no-shellfish", "high-protein"]),
    R("ln_chickpea_salad", "Mediterranean Chickpea Salad", 10,
      {"chickpeas_drained": 200, "cucumber": 100, "red_peppers": 80, "feta_cheese_reduced_fat": 40, "olive_oil": 12, "lemon_juice": 15, "parsley": 10},
      ["lunch", "vegetarian", "gluten-free", "nut-free", "portable", "no-cook", "meal-prep", "high-fiber"]),
    R("ln_black_bean_quinoa", "Black Bean Quinoa Bowl", 25,
      {"quinoa": 70, "black_beans_drained": 150, "salsa_ready-to-serve": 80, "avocados_raw_all_commercial_varieties": 70, "lettuce": 40},
      ["lunch", "dinner", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "meal-prep", "reheats-well", "high-fiber"]),
    R("ln_salmon_salad", "Salmon Avocado Salad", 5,
      {"salmon_canned": 120, "lettuce": 80, "cucumber": 80, "avocados_raw_all_commercial_varieties": 60, "olive_oil": 10, "lemon_juice": 10},
      ["lunch", "pescatarian", "gluten-free", "dairy-free", "nut-free", "no-cook", "low-carb", "high-protein"]),
    R("ln_white_bean_soup", "White Bean Spinach Soup", 30,
      {"beans_white_mature_seeds": 250, "spinach": 80, "carrots": 80, "garlic": 6, "olive_oil": 10, "parmesan_cheese_hard": 15},
      ["lunch", "dinner", "vegetarian", "gluten-free", "nut-free", "meal-prep", "reheats-well", "high-fiber"]),
    R("ln_salami_plate", "Salami and Cheddar Plate", 3,
      {"salami_genoa": 50, "sharp_cheddar_cheese": 40, "sourdough_bread": 60, "cucumber": 80},
      ["lunch", "snack", "portable", "no-cook", "nut-free"]),
    R("ln_cottage_box", "Cottage Cheese Protein Box", 3,
      {"cottage_cheese_1_fat": 200, "carrots": 100, "almonds": 20, "bananas": 100},
      ["lunch", "snack", "vegetarian", "gluten-free", "portable", "no-cook", "high-protein"]),
    R("ln_tuna_pasta_salad", "Tuna Pasta Salad", 20,
      {"pasta": 90, "tuna_sashimi": 120, "cucumber": 80, "olive_oil": 10, "lemon_juice": 10, "parsley": 10},
      ["lunch", "pescatarian", "dairy-free", "nut-free", "no-shellfish", "portable", "meal-prep", "high-protein"]),
    R("ln_tofu_quinoa_salad", "Sesame Tofu Quinoa Salad", 25,
      {"tofu_not_silken_firm": 180, "quinoa": 60, "carrots": 80, "cucumber": 80, "soy_sauce": 10, "sesame_oil": 8},
      ["lunch", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "meal-prep", "portable"],
      proposed=["high-protein"]),

    # ---------------- dinner ----------------
    R("dn_beef_rice_bowl", "Beef and Rice Bowl", 20,
      {"hamburger_or_beef_90": 170, "jasmine_rice_in_unsalted_water": 250, "spinach": 60, "soy_sauce": 10, "sesame_oil": 5},
      ["dinner", "lunch", "dairy-free", "nut-free", "reheats-well", "high-protein"]),
    R("dn_beef_chili", "Lean Beef and Bean Chili", 60,
      {"hamburger_or_beef_95": 200, "black_beans_drained": 150, "salsa_ready-to-serve": 120, "red_peppers": 80, "garlic": 6, "cheddar_cheese_natural_50_reduced_fat": 20},
      ["dinner", "lunch", "gluten-free", "nut-free", "meal-prep", "reheats-well", "high-protein", "high-fiber"]),
    R("dn_thigh_sheet_pan", "Chicken Thigh Sheet Pan with Potatoes", 45,
      {"chicken_thigh_skin_removed": 220, "potatoes_flesh": 300, "carrots": 100, "olive_oil": 12, "garlic": 6},
      ["dinner", "gluten-free", "dairy-free", "nut-free", "meal-prep", "reheats-well", "high-protein"]),
    R("dn_tilapia_rice", "Lemon Butter Tilapia with Rice", 20,
      {"tilapia": 200, "jasmine_rice_in_unsalted_water": 200, "asparagus": 150, "butter": 10, "lemon_juice": 10},
      ["dinner", "pescatarian", "gluten-free", "nut-free", "no-shellfish", "high-protein"]),
    R("dn_bolognese", "Pasta Bolognese", 30,
      {"pasta": 100, "hamburger_or_beef_90": 150, "salsa_ready-to-serve": 100, "parmesan_grated": 15, "olive_oil": 5, "garlic": 5},
      ["dinner", "nut-free", "meal-prep", "reheats-well", "kid-friendly"]),
    R("dn_tofu_stir_fry", "Tofu Vegetable Stir Fry", 20,
      {"tofu_not_silken_firm": 250, "jasmine_rice_in_unsalted_water": 220, "red_peppers": 100, "zucchini": 100, "soy_sauce": 20, "sesame_oil": 10},
      ["dinner", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free"],
      proposed=["high-protein", "meal-prep"]),
    R("dn_salmon_potatoes", "Salmon with Roast Potatoes and Asparagus", 35,
      {"salmon_canned": 150, "potatoes_flesh": 300, "asparagus": 120, "olive_oil": 10, "lemon_juice": 10},
      ["dinner", "pescatarian", "gluten-free", "dairy-free", "nut-free", "no-shellfish", "high-protein"]),
    R("dn_burger_bowl", "Bunless Burger Bowl with Potatoes", 25,
      {"hamburger_or_beef_95": 200, "lettuce": 80, "sharp_cheddar_cheese": 30, "potatoes_flesh": 250, "olive_oil": 10},
      ["dinner", "gluten-free", "nut-free", "kid-friendly", "high-protein"]),
    R("dn_veggie_pasta", "Zucchini Spinach Parmesan Pasta", 20,
      {"pasta": 110, "zucchini": 150, "spinach": 60, "parmesan_cheese_hard": 25, "olive_oil": 15, "garlic": 6},
      ["dinner", "vegetarian", "nut-free", "kid-friendly"]),
    R("dn_thigh_quinoa_prep", "Chicken Thigh Quinoa Prep Bowl", 40,
      {"chicken_thigh_skin_removed": 200, "quinoa": 70, "cauliflower": 150, "olive_oil": 10, "lemon_juice": 10},
      ["dinner", "lunch", "gluten-free", "dairy-free", "nut-free", "meal-prep", "reheats-well", "high-protein"]),
    R("dn_edamame_fried_rice", "Edamame Fried Rice", 20,
      {"edamame_beans": 150, "jasmine_rice_in_unsalted_water": 280, "carrots": 80, "soy_sauce": 20, "sesame_oil": 10, "egg_yolk": 34},
      ["dinner", "vegetarian", "dairy-free", "nut-free"]),
    R("dn_cauli_beef_bowl", "Low-Carb Beef Cauliflower Bowl", 20,
      {"hamburger_or_beef_90": 200, "cauliflower": 250, "spinach": 80, "olive_oil": 10, "parmesan_cheese_hard": 15},
      ["dinner", "gluten-free", "nut-free", "low-carb", "high-protein"]),
    R("dn_big_pasta_night", "Big Pasta Night", 35,
      {"pasta": 160, "hamburger_or_beef_90": 150, "parmesan_grated": 30, "olive_oil": 20},
      ["dinner", "nut-free", "kid-friendly"]),
    R("dn_bean_quesadilla", "Black Bean Cheddar Quesadilla", 15,
      {"tortillas_corn": 120, "black_beans_drained": 200, "sharp_cheddar_cheese": 40, "salsa_ready-to-serve": 80},
      ["dinner", "lunch", "vegetarian", "nut-free", "kid-friendly", "high-fiber"]),
    R("dn_tuna_steak_salad", "Seared Tuna Steak Salad", 15,
      {"tuna_sashimi": 180, "lettuce": 100, "cucumber": 80, "avocados_raw_all_commercial_varieties": 50, "olive_oil": 8, "lemon_juice": 10},
      ["dinner", "lunch", "pescatarian", "gluten-free", "dairy-free", "nut-free", "no-shellfish", "low-carb", "high-protein"]),
    R("dn_chickpea_curry", "Chickpea Spinach Curry with Rice", 35,
      {"chickpeas_drained": 220, "spinach": 100, "salsa_ready-to-serve": 100, "garlic": 6, "olive_oil": 12, "jasmine_rice_in_unsalted_water": 200},
      ["dinner", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "meal-prep", "reheats-well", "high-fiber"]),

    # ---------------- snacks / shakes ----------------
    R("sn_protein_shake", "Banana Whey Shake", 2,
      {"whey_protein_powder": 40, "milk": 300, "bananas": 100},
      ["snack", "post-workout", "vegetarian", "gluten-free", "nut-free", "no-cook", "portable", "high-protein"]),
    R("sn_whey_water", "Whey Isolate with Water", 1,
      {"whey_protein_powder": 35, "water": 400},
      ["snack", "post-workout", "vegetarian", "gluten-free", "nut-free", "no-cook", "portable", "high-protein", "low-fat"]),
    R("sn_banana_pb", "Banana with Peanut Butter", 1,
      {"bananas": 120, "peanut_butter": 32},
      ["snack", "pre-workout", "vegan", "vegetarian", "dairy-free", "gluten-free", "no-cook", "portable"]),
    R("sn_almonds_chocolate", "Almonds and Dark Chocolate", 0,
      {"almonds": 30, "chocolate_dark_70-85_cacao_solids": 20},
      ["snack", "vegetarian", "gluten-free", "no-cook", "portable"]),
    R("sn_yogurt_honey", "Greek Yogurt with Honey", 1,
      {"low_fat_greek_yogurt": 200, "honey": 15},
      ["snack", "breakfast", "vegetarian", "gluten-free", "nut-free", "no-cook", "high-protein"]),
    R("sn_krispie_banana", "Rice Krispies Treat and Banana", 0,
      {"kellogg_s_rice_krispies_treats_original": 44, "bananas": 120},
      ["snack", "pre-workout", "vegetarian", "nut-free", "no-cook", "portable", "low-fat"]),
    R("sn_cottage_blueberry", "Cottage Cheese with Blueberries", 1,
      {"cottage_cheese_1_fat": 150, "blueberries": 80},
      ["snack", "vegetarian", "gluten-free", "nut-free", "no-cook", "high-protein", "low-fat"]),
    R("sn_carrots_almond_butter", "Carrots with Almond Butter", 2,
      {"carrots": 120, "almond_butter_unsalted": 20},
      ["snack", "vegan", "vegetarian", "dairy-free", "gluten-free", "no-cook", "portable"]),
    R("sn_turkey_rollups", "Turkey Cheddar Roll-Ups", 2,
      {"turkey_breast_lunchmeat_reduced_fat": 80, "cheddar_cheese_natural_50_reduced_fat": 30, "lettuce": 20},
      ["snack", "gluten-free", "nut-free", "no-cook", "portable", "low-carb", "high-protein"]),
    R("sn_papaya_yogurt", "Papaya Yogurt Cup", 2,
      {"papaya": 200, "greek_yogurt_plain_nonfat": 150},
      ["snack", "breakfast", "vegetarian", "gluten-free", "nut-free", "no-cook", "low-fat"]),
    R("sn_bedtime_cottage", "Bedtime Cottage Cheese with Almond Butter", 2,
      {"cottage_cheese_1_fat": 250, "almond_butter_unsalted": 16},
      ["snack", "vegetarian", "gluten-free", "no-cook", "high-protein"]),
    R("sn_trail_mix", "Almond Chocolate Trail Mix", 0,
      {"almonds": 40, "chocolate_dark_70-85_cacao_solids": 15, "blueberries": 50},
      ["snack", "vegetarian", "gluten-free", "no-cook", "portable"]),
    R("sn_edamame_cup", "Salted Edamame Cup", 5,
      {"edamame_beans": 200, "soy_sauce": 5},
      ["snack", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "portable", "high-protein"]),
    R("sn_chia_seed_water", "Lemon Chia Water", 2,
      {"chia_seeds": 20, "lemon_juice": 15, "water": 350, "honey": 10},
      ["snack", "vegan", "vegetarian", "dairy-free", "gluten-free", "nut-free", "no-cook", "portable", "high-fiber"]),

    # ---------------- high-calorie (bulking) ----------------
    R("hc_mass_gainer", "Homemade Mass Gainer Shake", 3,
      {"whey_protein_powder": 60, "milk": 400, "rolled_oats": 80, "peanut_butter": 40, "bananas": 120, "honey": 20},
      ["snack", "breakfast", "post-workout", "vegetarian", "no-cook", "portable", "high-protein"]),
    R("hc_double_burger_potatoes", "Double Burger Plate with Potatoes", 30,
      {"hamburger_or_beef_90": 300, "potatoes_flesh": 400, "sharp_cheddar_cheese": 40, "olive_oil": 15},
      ["dinner", "gluten-free", "nut-free", "high-protein"]),
    R("hc_big_beef_rice", "Big Beef Rice Plate", 25,
      {"hamburger_or_beef_90": 250, "jasmine_rice_in_unsalted_water": 400, "butter": 10},
      ["dinner", "lunch", "gluten-free", "nut-free", "high-protein"]),
    R("hc_pasta_salmon_bake", "Salmon Pasta Bake", 45,
      {"pasta": 140, "salmon_canned": 150, "parmesan_grated": 30, "spinach": 80, "olive_oil": 10},
      ["dinner", "pescatarian", "nut-free", "meal-prep", "reheats-well", "high-protein"]),

    # ---------------- near-duplicates (content-identical, distinct IDs) ----------------
    R("dup_beef_rice_bowl_v2", "Beef and Rice Bowl", 20,
      {"hamburger_or_beef_90": 170, "jasmine_rice_in_unsalted_water": 250, "spinach": 60, "soy_sauce": 10, "sesame_oil": 5},
      ["dinner", "lunch", "dairy-free", "nut-free", "reheats-well"],
      notes="content-identical to dn_beef_rice_bowl (LLM duplicate pattern)"),
    R("dup_beef_rice_bowl_v3", "Beef & Rice Bowl", 20,
      {"hamburger_or_beef_90": 170, "jasmine_rice_in_unsalted_water": 250, "spinach": 60, "soy_sauce": 10, "sesame_oil": 5},
      ["dinner", "lunch", "dairy-free", "nut-free"],
      notes="content-identical to dn_beef_rice_bowl (LLM duplicate pattern)"),
]

# Recipes built on quarantined cache entries (used only by data-hazard scenarios).
DATA_HAZARD_RECIPES: List[dict] = [
    R("dh_oat_yogurt_parfait", "Oat Yogurt Parfait", 3,
      {"greek_yogurt_plain_nonfat": 200, "oats": 40, "blueberries": 80, "honey": 10},
      ["breakfast", "vegetarian", "no-cook"],
      notes="'oats' resolves to oat OIL: +354 kcal, +40 g fat vs intent"),
    R("dh_veggie_egg_scramble", "Veggie Egg Scramble", 10,
      {"eggs": 150, "bell_pepper": 80, "spinach": 50, "sharp_cheddar_cheese": 30},
      ["breakfast", "vegetarian", "gluten-free", "high-protein"],
      notes="'eggs' -> egg bread, 'bell_pepper' -> Taco Bell nachos; tagged gluten-free and high-protein but is neither"),
    R("dh_chicken_breast_rice", "Chicken Breast Rice Bowl", 20,
      {"chicken_breast": 180, "jasmine_rice_in_unsalted_water": 200, "asparagus": 100, "olive_oil": 5},
      ["lunch", "dinner", "dairy-free", "gluten-free", "high-protein"],
      notes="'chicken_breast' -> deli roll: 26 g protein instead of ~56 g; 1.6 g sodium"),
    R("dh_sweet_potato_hash", "Sweet Potato Beef Hash", 25,
      {"sweet_potato": 250, "hamburger_or_beef_95": 150, "olive_oil": 10},
      ["dinner", "gluten-free", "dairy-free"],
      notes="'sweet_potato' has 0 kcal but 43 g carbs at this quantity"),
    R("dh_kiwi_smoothie", "Kiwi Banana Smoothie", 3,
      {"kiwi_fruit_green": 150, "bananas": 100, "greek_yogurt_plain_nonfat": 150},
      ["snack", "breakfast", "vegetarian", "gluten-free", "no-cook"],
      notes="'kiwi_fruit_green' has 0 kcal but 20.7 g carbs at this quantity"),
]
# fmt: on

ALL_RECIPES: List[dict] = RECIPES + DATA_HAZARD_RECIPES


def load_cache() -> Dict[str, dict]:
    out = {}
    for f in sorted(CACHE_DIR.glob("*.json")):
        out[f.stem] = json.loads(f.read_text())
    return out


def compute_nutrition(recipe: dict, cache: Dict[str, dict]) -> dict:
    totals: Dict[str, float] = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
    micros: Dict[str, float] = {}
    for key, grams in recipe["ingredients"].items():
        if key not in cache:
            raise KeyError(f"{recipe['id']}: ingredient {key!r} not in local cache")
        n = cache[key]["nutrition"]
        f = grams / 100.0
        for m in totals:
            totals[m] += float(n.get(m) or 0.0) * f
        for m, v in (n.get("micronutrients") or {}).items():
            micros[m] = micros.get(m, 0.0) + float(v or 0.0) * f
    out = {k: round(v, 2) for k, v in totals.items()}
    out["micronutrients"] = {k: round(v, 3) for k, v in sorted(micros.items())}
    return out


def build_library() -> List[dict]:
    cache = load_cache()
    lib = []
    for r in ALL_RECIPES:
        uses_quarantined = sorted(k for k in r["ingredients"] if k in QUARANTINED_INGREDIENTS)
        is_hazard = r in DATA_HAZARD_RECIPES
        if uses_quarantined and not is_hazard and r["id"] not in {"ln_roast_beef_wrap", "dn_bean_quesadilla"}:
            raise ValueError(f"core recipe {r['id']} uses quarantined {uses_quarantined}")
        lib.append(
            {
                "id": r["id"],
                "name": r["name"],
                "cooking_time_minutes": r["cooking_time_minutes"],
                "ingredients": [
                    {"name": cache[k]["canonical_name"], "cache_key": k, "quantity": q, "unit": "g"}
                    for k, q in r["ingredients"].items()
                ],
                "tags": r["tags"],
                "proposed_tags": r["proposed_tags"],
                "data_hazard": is_hazard,
                "uses_quarantined_ingredients": uses_quarantined,
                "notes": r["notes"],
                "nutrition": compute_nutrition(r, cache),
            }
        )
    return lib


def build_tag_fixture(library: List[dict]) -> dict:
    """recipe_tags.json-shaped fixture: registry + tags_by_id with lifecycle metadata."""
    registry = {}
    for slug, meta in TAG_VOCAB.items():
        registry[slug] = {
            "slug": slug,
            "display": meta["display"],
            "tag_type": meta["tag_type"],
            "source": "system",
            "aliases": [],
            "created_at": "1970-01-01T00:00:00Z",
        }
    for t in range(5):
        registry[f"time-{t}"] = {
            "slug": f"time-{t}", "display": f"time-{t}", "tag_type": "time",
            "source": "system", "aliases": [], "created_at": "1970-01-01T00:00:00Z",
        }
    tags_by_id = {}
    for r in library:
        by_type: Dict[str, List[str]] = {}
        meta = {}
        for slug in r["tags"]:
            by_type.setdefault(TAG_VOCAB[slug]["tag_type"], []).append(slug)
        for slug in r["proposed_tags"]:
            by_type.setdefault(TAG_VOCAB[slug]["tag_type"], []).append(slug)
            meta[slug] = {
                "slug": slug, "display": TAG_VOCAB[slug]["display"],
                "tag_type": TAG_VOCAB[slug]["tag_type"], "source": "llm",
                "created_at": "2026-09-18T00:00:00Z", "aliases": [],
                "eligibility": "proposed",
            }
        m = r["cooking_time_minutes"]
        time_tag = "time-0" if m <= 2 else "time-1" if m <= 5 else "time-2" if m <= 15 else "time-3" if m <= 30 else "time-4"
        by_type.setdefault("time", []).append(time_tag)
        bucket = "snack" if m <= 5 else "quick_meal" if m <= 15 else "weeknight_meal" if m <= 30 else "meal_prep"
        flags = [f.replace("-", "_") for f in ("vegetarian", "vegan", "gluten-free", "dairy-free") if f in r["tags"]]
        entry = {
            # Required RecipeTagsJson fields; entries without them are skipped by load_recipe_tags.
            "cuisine": "shared",
            "cost_level": "standard",
            "prep_time_bucket": bucket,
            "dietary_flags": flags,
            "tag_slugs_by_type": {k: sorted(v) for k, v in sorted(by_type.items())},
        }
        if meta:
            entry["tag_metadata"] = meta
        tags_by_id[r["id"]] = entry
    return {"tag_aliases": {"batch-cook": "meal-prep"}, "tag_registry": registry, "tags_by_id": tags_by_id}


def hard_eligible_tags(recipe: dict) -> set:
    """Tags usable for required-tag (HC-9) matching under the DM-6 contract."""
    out = {t for t in recipe["tags"] if TAG_VOCAB[t]["tag_type"] in HARD_ELIGIBLE_TAG_TYPES}
    m = recipe["cooking_time_minutes"]
    out.add("time-0" if m <= 2 else "time-1" if m <= 5 else "time-2" if m <= 15 else "time-3" if m <= 30 else "time-4")
    return out


def all_tags(recipe: dict) -> set:
    return set(recipe["tags"]) | set(recipe["proposed_tags"]) | hard_eligible_tags(recipe)
