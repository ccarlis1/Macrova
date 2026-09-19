"""Stage 4: semantic validation gates on LLM recipe drafts."""
from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, Recipe
from src.llm.recipe_validator import (
    ingredient_matches_exclusion,
    resolved_identity_matches,
    validate_recipe_draft,
    validate_recipe_drafts,
)
from src.llm.recovery_types import GapSpec
from src.llm.schemas import RecipeDraft
from src.providers.ingredient_provider import IngredientDataProvider


class Provider(IngredientDataProvider):
    """USDA-capable fake with per-100g nutrition and optional provenance descriptions."""

    usda_capable = True

    def __init__(self, table, descriptions=None):
        self.table = table
        self.descriptions = descriptions or {}

    def get_ingredient_info(self, name):
        key = name.lower()
        if key not in self.table:
            return None
        info = {"name": key, "per_100g": self.table[key]}
        if key in self.descriptions:
            info["provenance"] = {"description": self.descriptions[key], "fdc_id": 1, "method": "deterministic"}
        return info

    def resolve_all(self, names):
        return None


N = lambda kcal=100.0, p=10.0, f=5.0, c=10.0, **micro: {"calories": kcal, "protein_g": p, "fat_g": f, "carbs_g": c, **micro}
TABLE = {"chicken breast": N(165, 31, 3.6, 0), "rice": N(130, 2.7, 0.3, 28), "oats": N(884, 0, 100, 0), "peanut butter": N(598, 22, 51, 22),
         "spinach": N(23, 2.9, 0.4, 3.6, iron_mg=2.7), "olive oil": N(884, 0, 100, 0)}


def draft(name="D", ings=(("chicken breast", 200.0, "g"), ("rice", 150.0, "g")), steps=("Cook.",), cook=None):
    d = {"name": name, "ingredients": [{"name": n, "quantity": q, "unit": u} for n, q, u in ings], "instructions": list(steps)}
    if cook is not None:
        d["cooking_time_minutes"] = cook
    return RecipeDraft.model_validate(d)


def test_exclusion_match_is_class_aware():
    assert ingredient_matches_exclusion("peanut butter", ["peanuts"]) == "peanuts"
    assert ingredient_matches_exclusion("eggs", ["egg"]) == "egg"
    assert ingredient_matches_exclusion("large eggs", ["eggs"]) == "eggs"
    assert ingredient_matches_exclusion("chicken breast", ["peanuts", "egg"]) is None
    assert ingredient_matches_exclusion("eggplant", ["egg"]) == "egg"  # conservative: prefix match, rejects the draft rather than risk it


def test_draft_with_excluded_ingredient_is_rejected():
    ok, res = validate_recipe_draft(draft(ings=(("peanut butter", 30.0, "g"), ("rice", 100.0, "g"))), Provider(TABLE), excluded_ingredients=["peanuts"])
    assert ok is False and res.error_code == "EXCLUDED_INGREDIENT"


def test_unresolvable_ingredient_rejects_instead_of_demoting():
    ok, res = validate_recipe_draft(draft(ings=(("chicken breast", 200.0, "g"), ("unicorn meat", 100.0, "g"))), Provider(TABLE))
    assert ok is False and res.error_code == "INGREDIENT_UNRESOLVED" and "unicorn meat" in res.message


def test_identity_gate_rules():
    assert resolved_identity_matches("oats", "Oil, oat") is False
    assert resolved_identity_matches("eggs", "Bread, egg") is False
    assert resolved_identity_matches("bell pepper", "TACO BELL, Nachos") is False
    assert resolved_identity_matches("milk 1% fat lowfat", "Cheese, cottage, lowfat, 1% milkfat") is False
    assert resolved_identity_matches("acai berry", "Beverages, Acai berry drink, fortified") is True  # known miss: group word + same food name
    assert resolved_identity_matches("chicken breast", "Chicken breast, roll, oven-roasted") is True
    assert resolved_identity_matches("chicken thigh skin removed", "Chicken, broilers or fryers, dark meat, thigh, meat only") is True
    assert resolved_identity_matches("cherry tomatoes", "Tomatoes, cherry, raw") is True
    assert resolved_identity_matches("greek yogurt plain nonfat", "Yogurt, Greek, plain, nonfat") is True
    assert resolved_identity_matches("rolled oats", "Cereals, oats, regular and quick, not fortified, dry") is True  # group word then the food
    assert resolved_identity_matches("olive oil", "Oil, olive, salad or cooking") is True
    assert resolved_identity_matches("tilapia", "Fish, tilapia, raw") is True
    assert resolved_identity_matches("almond butter unsalted", "Nuts, almond butter, plain, without salt added") is True
    assert resolved_identity_matches("whey protein powder", "Beverages, Whey protein powder isolate") is True
    assert resolved_identity_matches("kiwi fruit green", "Kiwifruit (kiwi), green, peeled, raw") is True


def test_identity_mismatch_rejects_when_provenance_available():
    prov = Provider(TABLE, descriptions={"oats": "Oil, oat", "rice": "Rice, white, cooked"})
    ok, res = validate_recipe_draft(draft(ings=(("oats", 100.0, "g"), ("rice", 100.0, "g"))), prov)
    assert ok is False and res.error_code == "INGREDIENT_IDENTITY_MISMATCH" and "Oil, oat" in res.message


def test_no_identity_check_without_provenance_but_plausibility_catches_oil_recipe():
    ok, res = validate_recipe_draft(draft(ings=(("oats", 100.0, "g"),)), Provider(TABLE))
    assert ok is False and res.error_code == "IMPLAUSIBLE_NUTRITION"


def test_claimed_cook_time_is_recorded_with_provenance_and_checked_against_cap():
    ok, rec = validate_recipe_draft(draft(cook=25), Provider(TABLE))
    assert ok is True and rec.cooking_time_minutes == 25 and rec.provenance["cooking_time_source"] == "llm_claimed"
    ok2, res = validate_recipe_draft(draft(cook=25), Provider(TABLE), cook_time_cap_minutes=15)
    assert ok2 is False and res.error_code == "COOK_TIME_EXCEEDS_CAP"
    ok3, res3 = validate_recipe_draft(draft(), Provider(TABLE), cook_time_cap_minutes=15)
    assert ok3 is False and res3.error_code == "COOK_TIME_UNKNOWN"


def test_heuristic_cook_time_only_without_cap_and_is_labelled():
    ok, rec = validate_recipe_draft(draft(steps=("a", "b")), Provider(TABLE))
    assert ok and rec.cooking_time_minutes == 10 and rec.provenance["cooking_time_source"] == "heuristic_5min_per_step"


def test_fitness_against_nutrient_gap():
    gap = GapSpec(kind="nutrient_gap", failure_mode="FM-4", days=1, meals_per_day=3, nutrient_min_per_recipe={"iron_mg": 5.0})
    ok, res = validate_recipe_draft(draft(ings=(("rice", 100.0, "g"),)), Provider(TABLE), gap_spec=gap)
    assert ok is False and res.error_code == "NOT_USEFUL"
    ok2, rec = validate_recipe_draft(draft(ings=(("spinach", 200.0, "g"), ("rice", 100.0, "g"))), Provider(TABLE), gap_spec=gap)
    assert ok2 is True


def test_fitness_against_macro_gap_band():
    gap = GapSpec(kind="macro_gap", failure_mode="FM-2", days=1, meals_per_day=3, per_meal_calories=600.0)
    ok, res = validate_recipe_draft(draft(ings=(("rice", 50.0, "g"),)), Provider(TABLE), gap_spec=gap)  # 65 kcal
    assert ok is False and res.error_code == "NOT_USEFUL"


def test_near_duplicate_rejected_against_existing_and_within_batch():
    existing = [Recipe(id="r1", name="Chicken and Rice", ingredients=[Ingredient("chicken breast", 180, "g"), Ingredient("rice", 120, "g")], cooking_time_minutes=20, instructions=[])]
    ok, res = validate_recipe_draft(draft(name="Chicken & rice bowl"), Provider(TABLE), existing_recipes=existing)
    assert ok is False and res.error_code == "DUPLICATE" and "r1" in res.message
    accepted, rejected = validate_recipe_drafts([draft(name="A"), draft(name="A variant", ings=(("chicken breast", 210.0, "g"), ("rice", 140.0, "g")))], Provider(TABLE))
    assert len(accepted) == 1 and [f.error_code for f in rejected] == ["DUPLICATE"]


def test_accepted_recipe_carries_provenance():
    ok, rec = validate_recipe_draft(draft(cook=12), Provider(TABLE, descriptions={"chicken breast": "Chicken, breast, raw", "rice": "Rice, white"}))
    assert ok and rec.provenance["source"] == "llm" and rec.provenance["resolved_fdc_ids"] == {"chicken breast": 1, "rice": 1}
    assert rec.provenance["computed_nutrition"]["calories"] == pytest.approx(165 * 2 + 130 * 1.5, abs=0.2)
