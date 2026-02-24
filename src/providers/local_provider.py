"""Local (JSON-backed) ingredient data provider.

Wraps the existing NutritionDB / IngredientDB so the rest of the system
can program against :class:`IngredientDataProvider` without knowing the
data source.  Behaviour is identical to using NutritionDB directly.
"""

from typing import Dict, Any, Optional, List

from src.providers.ingredient_provider import IngredientDataProvider
from src.data_layer.nutrition_db import NutritionDB


class LocalIngredientProvider(IngredientDataProvider):
    """Provider backed by a local JSON ingredient database.

    All data is loaded into memory when ``NutritionDB`` is constructed,
    so :meth:`resolve_all` is a no-op and :meth:`get_ingredient_info`
    delegates directly to the underlying database.
    """

    def __init__(self, nutrition_db: NutritionDB) -> None:
        self._nutrition_db = nutrition_db

    def get_ingredient_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Delegate to ``NutritionDB.get_ingredient_info``."""
        return self._nutrition_db.get_ingredient_info(name)

    def resolve_all(self, ingredient_names: List[str]) -> None:
        """No-op — local data is already in memory."""
