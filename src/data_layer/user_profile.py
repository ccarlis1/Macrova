"""User profile loader for loading user preferences from YAML."""
import yaml
from pathlib import Path
from typing import Dict, List

from src.data_layer.models import UserProfile


class UserProfileLoader:
    """Loader for user profile configuration from YAML."""

    def __init__(self, yaml_path: str):
        """Initialize user profile loader from YAML file.

        Args:
            yaml_path: Path to YAML file containing user profile
        """
        self.yaml_path = Path(yaml_path)

    def load(self) -> UserProfile:
        """Load user profile from YAML file.

        Returns:
            UserProfile object

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            KeyError: If required fields are missing
        """
        with open(self.yaml_path, "r") as f:
            data = yaml.safe_load(f)

        nutrition_goals = data["nutrition_goals"]
        schedule = data["schedule"]
        preferences = data["preferences"]

        # Extract nutrition goals
        daily_calories = int(nutrition_goals["daily_calories"])
        daily_protein_g = float(nutrition_goals["daily_protein_g"])
        fat_range = nutrition_goals["daily_fat_g"]
        daily_fat_g = (float(fat_range["min"]), float(fat_range["max"]))

        # Calculate carbs from remaining calories
        # Use median fat (average of min and max) for calculation
        median_fat_g = (daily_fat_g[0] + daily_fat_g[1]) / 2
        # Carbs = (calories - protein*4 - fat*9) / 4
        daily_carbs_g = (daily_calories - daily_protein_g * 4 - median_fat_g * 9) / 4

        # Convert schedule times to integers
        schedule_dict = {str(k): int(v) for k, v in schedule.items()}

        # Extract preferences
        liked_foods = [str(food) for food in preferences.get("liked_foods", [])]
        disliked_foods = [str(food) for food in preferences.get("disliked_foods", [])]
        allergies = [str(allergen) for allergen in preferences.get("allergies", [])]

        return UserProfile(
            daily_calories=daily_calories,
            daily_protein_g=daily_protein_g,
            daily_fat_g=daily_fat_g,
            daily_carbs_g=daily_carbs_g,
            schedule=schedule_dict,
            liked_foods=liked_foods,
            disliked_foods=disliked_foods,
            allergies=allergies,
        )

