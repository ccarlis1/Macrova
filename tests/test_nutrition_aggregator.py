"""Tests for nutrition aggregator."""
import pytest

from src.nutrition.aggregator import NutritionAggregator
from src.data_layer.models import (
    Meal,
    Recipe,
    NutritionProfile,
    Ingredient,
    MicronutrientProfile,
    DailyNutritionTracker,
    WeeklyNutritionTracker,
)


class TestNutritionAggregator:
    """Tests for NutritionAggregator."""

    def test_aggregate_meals(self):
        """Test aggregating nutrition from multiple meals."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1",
                name="Meal 1",
                ingredients=[],
                cooking_time_minutes=10,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=500.0,
                protein_g=30.0,
                fat_g=20.0,
                carbs_g=50.0,
            ),
            meal_type="breakfast",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2",
                name="Meal 2",
                ingredients=[],
                cooking_time_minutes=15,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=600.0,
                protein_g=40.0,
                fat_g=25.0,
                carbs_g=60.0,
            ),
            meal_type="lunch",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        assert abs(total.calories - 1100.0) < 0.01
        assert abs(total.protein_g - 70.0) < 0.01
        assert abs(total.fat_g - 45.0) < 0.01
        assert abs(total.carbs_g - 110.0) < 0.01

    def test_aggregate_empty_meals(self):
        """Test aggregating empty meal list returns zero nutrition."""
        total = NutritionAggregator.aggregate_meals([])

        assert total.calories == 0.0
        assert total.protein_g == 0.0
        assert total.fat_g == 0.0
        assert total.carbs_g == 0.0

    def test_aggregate_three_meals(self):
        """Test aggregating three meals."""
        meals = [
            Meal(
                recipe=Recipe(
                    id=f"r{i}",
                    name=f"Meal {i}",
                    ingredients=[],
                    cooking_time_minutes=10,
                    instructions=[],
                ),
                nutrition=NutritionProfile(
                    calories=100.0 * (i + 1),
                    protein_g=10.0 * (i + 1),
                    fat_g=5.0 * (i + 1),
                    carbs_g=15.0 * (i + 1),
                ),
                meal_type="breakfast",
            )
            for i in range(3)
        ]

        total = NutritionAggregator.aggregate_meals(meals)

        assert abs(total.calories - 600.0) < 0.01  # 100 + 200 + 300
        assert abs(total.protein_g - 60.0) < 0.01  # 10 + 20 + 30
        assert abs(total.fat_g - 30.0) < 0.01  # 5 + 10 + 15
        assert abs(total.carbs_g - 90.0) < 0.01  # 15 + 30 + 45


class TestMicronutrientAggregation:
    """Tests for micronutrient aggregation across meals."""

    def test_aggregate_meals_with_micronutrients(self):
        """Test that micronutrients are summed across meals."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1",
                name="Salmon Meal",
                ingredients=[],
                cooking_time_minutes=20,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=400.0,
                protein_g=35.0,
                fat_g=20.0,
                carbs_g=10.0,
                micronutrients=MicronutrientProfile(
                    vitamin_d_iu=500.0,
                    omega_3_g=2.0,
                    selenium_ug=40.0,
                ),
            ),
            meal_type="lunch",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2",
                name="Spinach Salad",
                ingredients=[],
                cooking_time_minutes=10,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=150.0,
                protein_g=8.0,
                fat_g=5.0,
                carbs_g=15.0,
                micronutrients=MicronutrientProfile(
                    vitamin_a_ug=400.0,
                    vitamin_c_mg=30.0,
                    vitamin_k_ug=450.0,
                    iron_mg=3.0,
                ),
            ),
            meal_type="dinner",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        # Verify macros still work
        assert abs(total.calories - 550.0) < 0.01
        assert abs(total.protein_g - 43.0) < 0.01

        # Verify micronutrients are aggregated
        assert total.micronutrients is not None
        assert abs(total.micronutrients.vitamin_d_iu - 500.0) < 0.01
        assert abs(total.micronutrients.omega_3_g - 2.0) < 0.01
        assert abs(total.micronutrients.selenium_ug - 40.0) < 0.01
        assert abs(total.micronutrients.vitamin_a_ug - 400.0) < 0.01
        assert abs(total.micronutrients.vitamin_c_mg - 30.0) < 0.01
        assert abs(total.micronutrients.vitamin_k_ug - 450.0) < 0.01
        assert abs(total.micronutrients.iron_mg - 3.0) < 0.01

    def test_aggregate_meals_mixed_micronutrients(self):
        """Test aggregation when meals have overlapping micronutrients."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1", name="Meal 1", ingredients=[],
                cooking_time_minutes=10, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=300.0, protein_g=20.0, fat_g=10.0, carbs_g=30.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=45.0,
                    iron_mg=4.0,
                    calcium_mg=200.0,
                ),
            ),
            meal_type="breakfast",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2", name="Meal 2", ingredients=[],
                cooking_time_minutes=15, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=400.0, protein_g=25.0, fat_g=15.0, carbs_g=40.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=60.0,  # Overlaps with meal1
                    iron_mg=2.0,  # Overlaps with meal1
                    magnesium_mg=100.0,  # New
                ),
            ),
            meal_type="lunch",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        assert total.micronutrients is not None
        # Vitamin C: 45 + 60 = 105
        assert abs(total.micronutrients.vitamin_c_mg - 105.0) < 0.01
        # Iron: 4 + 2 = 6
        assert abs(total.micronutrients.iron_mg - 6.0) < 0.01
        # Calcium: only in meal1
        assert abs(total.micronutrients.calcium_mg - 200.0) < 0.01
        # Magnesium: only in meal2
        assert abs(total.micronutrients.magnesium_mg - 100.0) < 0.01

    def test_aggregate_meals_without_micronutrients(self):
        """Test aggregation when meals have no micronutrients (backward compat)."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1", name="Meal 1", ingredients=[],
                cooking_time_minutes=10, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=300.0, protein_g=20.0, fat_g=10.0, carbs_g=30.0,
                # No micronutrients
            ),
            meal_type="breakfast",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2", name="Meal 2", ingredients=[],
                cooking_time_minutes=15, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=400.0, protein_g=25.0, fat_g=15.0, carbs_g=40.0,
                # No micronutrients
            ),
            meal_type="lunch",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        # Macros should work
        assert abs(total.calories - 700.0) < 0.01

        # Micronutrients should exist but be zeros
        assert total.micronutrients is not None
        assert total.micronutrients.vitamin_c_mg == 0.0
        assert total.micronutrients.iron_mg == 0.0

    def test_aggregate_meals_partial_micronutrients(self):
        """Test aggregation when only some meals have micronutrients."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1", name="Meal 1", ingredients=[],
                cooking_time_minutes=10, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=300.0, protein_g=20.0, fat_g=10.0, carbs_g=30.0,
                micronutrients=MicronutrientProfile(vitamin_c_mg=50.0),
            ),
            meal_type="breakfast",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2", name="Meal 2", ingredients=[],
                cooking_time_minutes=15, instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=400.0, protein_g=25.0, fat_g=15.0, carbs_g=40.0,
                # No micronutrients (None)
            ),
            meal_type="lunch",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        # Should still get meal1's micronutrients
        assert total.micronutrients is not None
        assert abs(total.micronutrients.vitamin_c_mg - 50.0) < 0.01

    def test_aggregate_empty_meals_has_micronutrients(self):
        """Test empty meal list returns NutritionProfile with zero micronutrients."""
        total = NutritionAggregator.aggregate_meals([])

        assert total.calories == 0.0
        assert total.micronutrients is not None
        assert total.micronutrients.vitamin_c_mg == 0.0
        assert total.micronutrients.iron_mg == 0.0


class TestDailyAggregation:
    """Tests for aggregating meals into daily trackers."""

    def test_aggregate_to_daily_tracker(self):
        """Test creating a DailyNutritionTracker from meals."""
        meals = [
            Meal(
                recipe=Recipe(
                    id="breakfast_1", name="Breakfast", ingredients=[],
                    cooking_time_minutes=10, instructions=[],
                ),
                nutrition=NutritionProfile(
                    calories=500.0, protein_g=30.0, fat_g=15.0, carbs_g=60.0,
                    micronutrients=MicronutrientProfile(
                        vitamin_c_mg=30.0,
                        calcium_mg=200.0,
                    ),
                ),
                meal_type="breakfast",
            ),
            Meal(
                recipe=Recipe(
                    id="lunch_1", name="Lunch", ingredients=[],
                    cooking_time_minutes=20, instructions=[],
                ),
                nutrition=NutritionProfile(
                    calories=700.0, protein_g=45.0, fat_g=25.0, carbs_g=70.0,
                    micronutrients=MicronutrientProfile(
                        vitamin_c_mg=40.0,
                        iron_mg=5.0,
                    ),
                ),
                meal_type="lunch",
            ),
        ]

        tracker = NutritionAggregator.aggregate_to_daily_tracker(
            date="2024-01-15",
            meals=meals,
        )

        assert tracker.date == "2024-01-15"
        assert abs(tracker.calories - 1200.0) < 0.01
        assert abs(tracker.protein_g - 75.0) < 0.01
        assert abs(tracker.fat_g - 40.0) < 0.01
        assert abs(tracker.carbs_g - 130.0) < 0.01

        # Micronutrients
        assert abs(tracker.micronutrients.vitamin_c_mg - 70.0) < 0.01
        assert abs(tracker.micronutrients.calcium_mg - 200.0) < 0.01
        assert abs(tracker.micronutrients.iron_mg - 5.0) < 0.01

        # Meal IDs
        assert len(tracker.meal_ids) == 2
        assert "breakfast_1" in tracker.meal_ids
        assert "lunch_1" in tracker.meal_ids

    def test_aggregate_to_daily_tracker_empty_meals(self):
        """Test creating a DailyNutritionTracker from empty meal list."""
        tracker = NutritionAggregator.aggregate_to_daily_tracker(
            date="2024-01-15",
            meals=[],
        )

        assert tracker.date == "2024-01-15"
        assert tracker.calories == 0.0
        assert tracker.protein_g == 0.0
        assert tracker.micronutrients.vitamin_c_mg == 0.0
        assert len(tracker.meal_ids) == 0


class TestWeeklyAggregation:
    """Tests for aggregating daily trackers into weekly totals."""

    def test_aggregate_to_weekly_tracker(self):
        """Test creating a WeeklyNutritionTracker from daily trackers."""
        daily_trackers = [
            DailyNutritionTracker(
                date="2024-01-15",  # Monday
                calories=2200.0,
                protein_g=140.0,
                fat_g=70.0,
                carbs_g=260.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=90.0,
                    iron_mg=8.0,
                    vitamin_d_iu=400.0,
                ),
                meal_ids=["m1", "m2", "m3"],
            ),
            DailyNutritionTracker(
                date="2024-01-16",  # Tuesday
                calories=2400.0,
                protein_g=160.0,
                fat_g=80.0,
                carbs_g=280.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=100.0,
                    iron_mg=10.0,
                    calcium_mg=800.0,
                ),
                meal_ids=["m4", "m5", "m6"],
            ),
            DailyNutritionTracker(
                date="2024-01-17",  # Wednesday
                calories=2100.0,
                protein_g=130.0,
                fat_g=65.0,
                carbs_g=250.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=80.0,
                    iron_mg=7.0,
                    omega_3_g=2.5,
                ),
                meal_ids=["m7", "m8"],
            ),
        ]

        weekly = NutritionAggregator.aggregate_to_weekly_tracker(
            week_start_date="2024-01-15",
            daily_trackers=daily_trackers,
        )

        assert weekly.week_start_date == "2024-01-15"
        assert weekly.days_completed == 3

        # Macro totals
        assert abs(weekly.total_calories - 6700.0) < 0.01  # 2200+2400+2100
        assert abs(weekly.total_protein_g - 430.0) < 0.01  # 140+160+130
        assert abs(weekly.total_fat_g - 215.0) < 0.01  # 70+80+65
        assert abs(weekly.total_carbs_g - 790.0) < 0.01  # 260+280+250

        # Micronutrient totals
        assert abs(weekly.total_micronutrients.vitamin_c_mg - 270.0) < 0.01  # 90+100+80
        assert abs(weekly.total_micronutrients.iron_mg - 25.0) < 0.01  # 8+10+7
        assert abs(weekly.total_micronutrients.vitamin_d_iu - 400.0) < 0.01  # only day 1
        assert abs(weekly.total_micronutrients.calcium_mg - 800.0) < 0.01  # only day 2
        assert abs(weekly.total_micronutrients.omega_3_g - 2.5) < 0.01  # only day 3

        # Daily trackers preserved
        assert len(weekly.daily_trackers) == 3

    def test_aggregate_to_weekly_tracker_full_week(self):
        """Test weekly tracker with full 7 days."""
        daily_trackers = [
            DailyNutritionTracker(
                date=f"2024-01-{15 + i}",
                calories=2400.0,
                protein_g=150.0,
                fat_g=75.0,
                carbs_g=280.0,
                micronutrients=MicronutrientProfile(
                    vitamin_c_mg=90.0,
                    iron_mg=8.0,
                ),
            )
            for i in range(7)
        ]

        weekly = NutritionAggregator.aggregate_to_weekly_tracker(
            week_start_date="2024-01-15",
            daily_trackers=daily_trackers,
        )

        assert weekly.days_completed == 7
        assert abs(weekly.total_calories - 16800.0) < 0.01  # 2400 * 7
        assert abs(weekly.total_protein_g - 1050.0) < 0.01  # 150 * 7
        assert abs(weekly.total_micronutrients.vitamin_c_mg - 630.0) < 0.01  # 90 * 7
        assert abs(weekly.total_micronutrients.iron_mg - 56.0) < 0.01  # 8 * 7

    def test_aggregate_to_weekly_tracker_empty(self):
        """Test weekly tracker with no daily trackers (start of week)."""
        weekly = NutritionAggregator.aggregate_to_weekly_tracker(
            week_start_date="2024-01-15",
            daily_trackers=[],
        )

        assert weekly.week_start_date == "2024-01-15"
        assert weekly.days_completed == 0
        assert weekly.total_calories == 0.0
        assert weekly.total_protein_g == 0.0
        assert weekly.total_micronutrients.vitamin_c_mg == 0.0
        assert len(weekly.daily_trackers) == 0

    def test_aggregate_to_weekly_tracker_partial_week(self):
        """Test weekly tracker with partial week (e.g., 2 days completed)."""
        daily_trackers = [
            DailyNutritionTracker(
                date="2024-01-15",
                calories=2500.0,
                protein_g=160.0,
                fat_g=80.0,
                carbs_g=290.0,
                micronutrients=MicronutrientProfile(vitamin_e_mg=15.0),
            ),
            DailyNutritionTracker(
                date="2024-01-16",
                calories=2300.0,
                protein_g=145.0,
                fat_g=72.0,
                carbs_g=270.0,
                micronutrients=MicronutrientProfile(vitamin_e_mg=12.0),
            ),
        ]

        weekly = NutritionAggregator.aggregate_to_weekly_tracker(
            week_start_date="2024-01-15",
            daily_trackers=daily_trackers,
        )

        assert weekly.days_completed == 2
        assert abs(weekly.total_calories - 4800.0) < 0.01
        assert abs(weekly.total_micronutrients.vitamin_e_mg - 27.0) < 0.01

    def test_aggregate_to_weekly_tracker_preserves_carryover(self):
        """Test that weekly tracker can preserve carryover needs."""
        # Carryover is set externally (not calculated by aggregator)
        # This test verifies the structure supports it
        weekly = NutritionAggregator.aggregate_to_weekly_tracker(
            week_start_date="2024-01-15",
            daily_trackers=[],
        )

        # Carryover should default to empty dict
        assert weekly.carryover_needs == {}

        # Can be set externally (aggregator doesn't calculate this)
        weekly.carryover_needs = {
            "vitamin_e_mg": 3.0,
            "magnesium_mg": 50.0,
        }
        assert weekly.carryover_needs["vitamin_e_mg"] == 3.0

