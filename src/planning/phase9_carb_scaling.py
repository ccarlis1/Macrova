"""Phase 9: Primary Carb Downscaling. Spec Section 6.7.

Loads scalable carb reference data, computes variant nutrition, and generates
scaled variants for candidate step 8. No recursive scaling; no scoring/constraint changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.data_layer.models import MicronutrientProfile, NutritionProfile

from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile, micronutrient_profile_to_dict


# Default path relative to project root
DEFAULT_SCALABLE_CARB_SOURCES_PATH = "data/reference/scalable_carb_sources.json"


def load_scalable_carb_sources(path: Optional[str] = None) -> Dict[str, List[str]]:
    """Load rice_variants and potato_variants from JSON. Fail fast on malformed data.

    Returns dict with keys 'rice_variants' and 'potato_variants', each a list of strings.
    """
    p = Path(path or DEFAULT_SCALABLE_CARB_SOURCES_PATH)
    if not p.is_absolute():
        # Assume project root is parent of src/
        p = Path(__file__).resolve().parent.parent.parent / p
    text = p.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("scalable_carb_sources.json must be a JSON object")
    rice = data.get("rice_variants")
    potato = data.get("potato_variants")
    if not isinstance(rice, list) or not all(isinstance(x, str) for x in rice):
        raise ValueError("rice_variants must be a list of strings")
    if not isinstance(potato, list) or not all(isinstance(x, str) for x in potato):
        raise ValueError("potato_variants must be a list of strings")
    return {"rice_variants": list(rice), "potato_variants": list(potato)}


def _scalable_source_set(sources: Dict[str, List[str]]) -> Set[str]:
    out: Set[str] = set()
    for v in sources.get("rice_variants", []):
        out.add(v.strip().lower())
    for v in sources.get("potato_variants", []):
        out.add(v.strip().lower())
    return out


def is_recipe_scalable(recipe: PlanningRecipe, scalable_sources: Dict[str, List[str]]) -> bool:
    """True if recipe has primary_carb_contribution and primary_carb_source in scalable list."""
    if recipe.primary_carb_contribution is None:
        return False
    src = getattr(recipe, "primary_carb_source", None)
    if not src or not isinstance(src, str):
        return False
    allowed = _scalable_source_set(scalable_sources)
    return src.strip().lower() in allowed


def compute_variant_nutrition(
    recipe: PlanningRecipe,
    step_index: int,
    profile: PlanningUserProfile,
) -> NutritionProfile:
    """Variant nutrition for step_index in 1..K. Spec 6.7.4.

    contribution_scaled = contribution_original * (1 - step_index * sigma)
    variant_nutrition = r.nutrition - contribution_original + contribution_scaled

    step_index 0 is not used (base recipe); for step_index 0 callers use recipe.nutrition.
    """
    if step_index <= 0:
        return recipe.nutrition
    contrib = recipe.primary_carb_contribution
    if contrib is None:
        return recipe.nutrition
    K = max(1, profile.max_scaling_steps)
    sigma = max(0.0, min(1.0, profile.scaling_step_fraction))
    if K * sigma >= 1.0:
        sigma = 0.99 / K
    scale = 1.0 - step_index * sigma
    if scale <= 0:
        scale = 1e-9
    # contribution_scaled = contribution_original * scale
    c_cal = contrib.calories * scale
    c_pro = contrib.protein_g * scale
    c_fat = contrib.fat_g * scale
    c_carb = contrib.carbs_g * scale
    # variant = base - original + scaled
    micro_orig = getattr(contrib, "micronutrients", None)
    micro_base = getattr(recipe.nutrition, "micronutrients", None)
    if micro_orig is None and micro_base is None:
        micro_out = None
    else:
        base_d = micronutrient_profile_to_dict(micro_base) if micro_base else {}
        orig_d = micronutrient_profile_to_dict(micro_orig) if micro_orig else {}
        valid = list(MicronutrientProfile.__dataclass_fields__.keys())
        out_d = {}
        for k in valid:
            b = base_d.get(k, 0.0)
            o = orig_d.get(k, 0.0)
            out_d[k] = b - o + o * scale
        micro_out = MicronutrientProfile(**{k: out_d.get(k, 0.0) for k in valid})

    # Macros for variant = base - original + scaled
    v_cal = recipe.nutrition.calories - contrib.calories + c_cal
    v_pro = recipe.nutrition.protein_g - contrib.protein_g + c_pro
    v_fat = recipe.nutrition.fat_g - contrib.fat_g + c_fat
    v_carb = recipe.nutrition.carbs_g - contrib.carbs_g + c_carb

    # Guard against malformed primary_carb_contribution that would drive any nutrient negative.
    if v_cal < 0:
        raise ValueError(
            f"Invalid primary_carb_contribution for recipe {recipe.id}: "
            f"calories would become negative after scaling"
        )
    if v_pro < 0:
        raise ValueError(
            f"Invalid primary_carb_contribution for recipe {recipe.id}: "
            f"protein_g would become negative after scaling"
        )
    if v_fat < 0:
        raise ValueError(
            f"Invalid primary_carb_contribution for recipe {recipe.id}: "
            f"fat_g would become negative after scaling"
        )
    if v_carb < 0:
        raise ValueError(
            f"Invalid primary_carb_contribution for recipe {recipe.id}: "
            f"carbs_g would become negative after scaling"
        )

    if micro_out is not None:
        for fname in MicronutrientProfile.__dataclass_fields__.keys():
            if getattr(micro_out, fname) < 0:
                raise ValueError(
                    f"Invalid primary_carb_contribution for recipe {recipe.id}: "
                    f"{fname} would become negative after scaling"
                )

    return NutritionProfile(
        v_cal,
        v_pro,
        v_fat,
        v_carb,
        micronutrients=micro_out,
    )


def generate_scaled_variants(
    recipe_pool: List[PlanningRecipe],
    calorie_excess_rejections: Set[str],
    day_index: int,
    slot_index: int,
    slot: "MealSlot",
    constraint_state: "ConstraintStateView",
    feasibility_state: "FeasibilityStateView",
    profile: PlanningUserProfile,
    resolved_ul: Optional["UpperLimits"],
    macro_bounds: "MacroBoundsPrecomputation",
    scalable_sources: Dict[str, List[str]],
    activity_context_set: Set[str],
    is_workout: bool,
) -> List[Tuple[str, int, NutritionProfile]]:
    """Generate (recipe_id, variant_index, variant_nutrition) for step 8.

    Preconditions: feature on, sedentary slot, not pinned, recipe in calorie_excess_rejections,
    recipe scalable. Each variant re-checked against HC-1, HC-2, HC-3, HC-5, HC-8, FC-1, FC-2, FC-3.
    """
    from src.planning.phase2_constraints import (
        check_hc1_excluded_ingredients,
        check_hc2_no_same_day_reuse,
        check_hc3_cooking_time_bound,
        check_hc5_max_daily_calories,
        check_hc8_cross_day_non_workout_reuse,
    )
    from src.planning.phase3_feasibility import (
        check_fc1_daily_calories,
        check_fc2_daily_macros,
        check_fc3_incremental_ul,
    )

    if not profile.enable_primary_carb_downscaling:
        return []
    if "sedentary" not in activity_context_set:
        return []
    # Defensive guard: never generate variants for pinned slots, even if caller misuses this API.
    day_1based = day_index + 1
    if (day_1based, slot_index) in profile.pinned_assignments:
        return []
    K = max(1, profile.max_scaling_steps)
    sigma = max(0.0, min(1.0, profile.scaling_step_fraction))
    if K * sigma >= 1.0:
        sigma = 0.99 / K

    result: List[Tuple[str, int, NutritionProfile]] = []
    for recipe in recipe_pool:
        if recipe.id not in calorie_excess_rejections:
            continue
        if not is_recipe_scalable(recipe, scalable_sources):
            continue
        if recipe.primary_carb_contribution is None:
            continue
        for i in range(1, K + 1):
            scale = 1.0 - i * sigma
            if scale <= 0:
                continue
            variant_nutrition = compute_variant_nutrition(recipe, i, profile)
            # Recipe-like with variant nutrition for constraint/feasibility checks
            recipe_view = PlanningRecipe(
                id=recipe.id,
                name=recipe.name,
                ingredients=recipe.ingredients,
                cooking_time_minutes=recipe.cooking_time_minutes,
                nutrition=variant_nutrition,
                primary_carb_contribution=recipe.primary_carb_contribution,
                primary_carb_source=recipe.primary_carb_source,
            )
            if not check_hc1_excluded_ingredients(recipe_view, slot, day_index, constraint_state, profile, resolved_ul):
                continue
            if not check_hc2_no_same_day_reuse(recipe_view, slot, day_index, constraint_state, profile, resolved_ul):
                continue
            if not check_hc3_cooking_time_bound(recipe_view, slot, day_index, constraint_state, profile, resolved_ul):
                continue
            if not check_hc5_max_daily_calories(recipe_view, slot, day_index, constraint_state, profile, resolved_ul):
                continue
            if day_index > 0 and not is_workout:
                if not check_hc8_cross_day_non_workout_reuse(
                    recipe_view, slot, day_index, constraint_state, profile, resolved_ul, is_workout
                ):
                    continue
            if not check_fc1_daily_calories(
                recipe_view, slot, day_index, slot_index, feasibility_state, profile, resolved_ul, macro_bounds
            ):
                continue
            if not check_fc2_daily_macros(
                recipe_view, slot, day_index, slot_index, feasibility_state, profile, resolved_ul, macro_bounds
            ):
                continue
            if not check_fc3_incremental_ul(recipe_view, slot, day_index, feasibility_state, profile, resolved_ul):
                continue
            result.append((recipe.id, i, variant_nutrition))
    return result
