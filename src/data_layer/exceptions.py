"""Custom exceptions for the nutrition agent."""


class IngredientNotFoundError(Exception):
    """Raised when an ingredient is not found in the nutrition database."""

    def __init__(self, ingredient_name: str):
        """Initialize exception with ingredient name.
        
        Args:
            ingredient_name: Name of the ingredient that was not found
        """
        self.ingredient_name = ingredient_name
        super().__init__(f"Ingredient '{ingredient_name}' not found in nutrition database")

