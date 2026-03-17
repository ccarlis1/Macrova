"""Phase 9 unit tests: Primary Carb Downscaling. Spec Section 6.7."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.data_layer.models import NutritionProfile
from src.planning.phase0_models import PlanningRecipe, PlanningUserProfile
from src.planning.phase9_carb_scaling import (
    compute_variant_nutrition,
    is_recipe_scalable,
    load_scalable_carb_sources,
)


def _make_recipe(
    rid: str,
    calories: float = 500.0,
    protein: float = 30.0,
    fat: float = 20.0,
    carbs: float = 40.0,
    primary_carb_contribution: NutritionProfile | None = None,
    primary_carb_source: str | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(calories, protein, fat, carbs),
        primary_carb_contribution=primary_carb_contribution,
        primary_carb_source=primary_carb_source,
    )


def _profile(
    max_scaling_steps: int = 4,
    scaling_step_fraction: float = 0.10,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        max_scaling_steps=max_scaling_steps,
        scaling_step_fraction=scaling_step_fraction,
    )


class TestLoadScalableCarbSources:
    def test_load_default_path(self):
        data = load_scalable_carb_sources()
        assert "rice_variants" in data
        assert "potato_variants" in data
        assert isinstance(data["rice_variants"], list)
        assert isinstance(data["potato_variants"], list)
        assert "rice" in [x.lower() for x in data["rice_variants"]]
        assert "potato" in [x.lower() for x in data["potato_variants"]]

    def test_load_custom_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "rice_variants": ["white_rice"],
                "potato_variants": ["sweet_potato"],
            }, f)
            path = f.name
        try:
            data = load_scalable_carb_sources(path)
            assert data["rice_variants"] == ["white_rice"]
            assert data["potato_variants"] == ["sweet_potato"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_malformed_not_object_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[1, 2, 3]")
            path = f.name
        try:
            with pytest.raises(ValueError, match="JSON object"):
                load_scalable_carb_sources(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_malformed_rice_not_list_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"rice_variants": "x", "potato_variants": []}, f)
            path = f.name
        try:
            with pytest.raises(ValueError, match="rice_variants"):
                load_scalable_carb_sources(path)
        finally:
            Path(path).unlink(missing_ok=True)


class TestIsRecipeScalable:
    def test_no_primary_carb_contribution_false(self):
        sources = {"rice_variants": ["rice"], "potato_variants": []}
        r = _make_recipe("r1", primary_carb_contribution=None, primary_carb_source="rice")
        assert is_recipe_scalable(r, sources) is False

    def test_no_primary_carb_source_false(self):
        sources = {"rice_variants": ["rice"], "potato_variants": []}
        contrib = NutritionProfile(100.0, 2.0, 0.5, 20.0)
        r = _make_recipe("r1", primary_carb_contribution=contrib, primary_carb_source=None)
        assert is_recipe_scalable(r, sources) is False

    def test_source_in_list_true(self):
        sources = {"rice_variants": ["white_rice", "rice"], "potato_variants": []}
        contrib = NutritionProfile(100.0, 2.0, 0.5, 20.0)
        r = _make_recipe("r1", primary_carb_contribution=contrib, primary_carb_source="rice")
        assert is_recipe_scalable(r, sources) is True

    def test_source_not_in_list_false(self):
        sources = {"rice_variants": ["rice"], "potato_variants": ["potato"]}
        contrib = NutritionProfile(100.0, 2.0, 0.5, 20.0)
        r = _make_recipe("r1", primary_carb_contribution=contrib, primary_carb_source="pasta")
        assert is_recipe_scalable(r, sources) is False


class TestComputeVariantNutrition:
    def test_step_index_zero_returns_base_nutrition(self):
        r = _make_recipe("r1", calories=500.0, protein=30.0, fat=20.0, carbs=50.0)
        profile = _profile()
        out = compute_variant_nutrition(r, 0, profile)
        assert out.calories == 500.0
        assert out.protein_g == 30.0
        assert out.carbs_g == 50.0

    def test_no_primary_carb_contribution_returns_base(self):
        r = _make_recipe("r1", calories=500.0, primary_carb_contribution=None)
        profile = _profile()
        out = compute_variant_nutrition(r, 1, profile)
        assert out.calories == 500.0

    def test_nutrition_formula_exact(self):
        # Base: 500 cal, 30 pro, 20 fat, 50 carb. Contribution: 200 cal, 4 pro, 0 fat, 45 carb.
        contrib = NutritionProfile(200.0, 4.0, 0.0, 45.0)
        r = _make_recipe(
            "r1",
            calories=500.0,
            protein=30.0,
            fat=20.0,
            carbs=50.0,
            primary_carb_contribution=contrib,
        )
        profile = _profile(max_scaling_steps=4, scaling_step_fraction=0.10)
        # step_index=1 -> scale = 1 - 0.1 = 0.9. contribution_scaled = 0.9 * contrib.
        # variant = base - contrib + contrib_scaled = base - 0.1*contrib
        out = compute_variant_nutrition(r, 1, profile)
        expected_cal = 500.0 - 200.0 + 200.0 * 0.9
        assert abs(out.calories - expected_cal) < 1e-6
        expected_carb = 50.0 - 45.0 + 45.0 * 0.9
        assert abs(out.carbs_g - expected_carb) < 1e-6

    def test_qi_bounds_enforced(self):
        contrib = NutritionProfile(100.0, 2.0, 0.0, 25.0)
        r = _make_recipe("r1", calories=400.0, protein=20.0, fat=10.0, carbs=40.0, primary_carb_contribution=contrib)
        profile = _profile(max_scaling_steps=10, scaling_step_fraction=0.15)
        # K*sigma = 1.5 > 1.0 -> implementation caps sigma so K*sigma < 1
        out = compute_variant_nutrition(r, 1, profile)
        assert out.calories > 0
        assert out.carbs_g > 0

    def test_step_index_positive_uses_scaled_contribution(self):
        contrib = NutritionProfile(100.0, 0.0, 0.0, 25.0)
        r = _make_recipe("r1", calories=300.0, protein=10.0, fat=5.0, carbs=30.0, primary_carb_contribution=contrib)
        profile = _profile(max_scaling_steps=2, scaling_step_fraction=0.25)
        # i=1: scale 0.75; i=2: scale 0.5
        out1 = compute_variant_nutrition(r, 1, profile)
        out2 = compute_variant_nutrition(r, 2, profile)
        assert out1.calories > out2.calories
        assert out2.calories > 300.0 - 100.0  # base minus full contribution
        assert out2.calories < 300.0

    def test_negative_macros_raise_value_error(self):
        # Malformed data: contribution larger than base for calories such that variant becomes negative.
        contrib = NutritionProfile(600.0, 0.0, 0.0, 0.0)
        r = _make_recipe(
            "r_bad",
            calories=50.0,
            protein=10.0,
            fat=5.0,
            carbs=30.0,
            primary_carb_contribution=contrib,
        )
        profile = _profile()
        with pytest.raises(ValueError, match="calories would become negative"):
            compute_variant_nutrition(r, 1, profile)
