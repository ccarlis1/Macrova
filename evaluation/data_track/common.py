"""Shared loaders and calculator helpers for the §4.4 data-track harness.

Mirrors the provider/calculator wiring in ``src/api/server.py`` (plan endpoint
lines that choose local vs API ingredient source and call
``NutritionCalculator``), without mutating ``src/``.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.data_layer.exceptions import IngredientNotFoundError
from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile, Recipe
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.nutrition.calculator import NutritionCalculator
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError
from src.providers.ingredient_provider import IngredientDataProvider
from src.providers.local_provider import LocalIngredientProvider

ROOT = Path(__file__).resolve().parents[2]
DATA_TRACK = Path(__file__).resolve().parent
RESULTS_DIR = DATA_TRACK / "results"
RAW_DIR = DATA_TRACK / "raw"

BENCH_RECIPES_PATH = ROOT / "evaluation" / "benchmark" / "recipes.json"
DATA_RECIPES_PATH = ROOT / "data" / "recipes" / "recipes.json"
DATA_RECIPES_EXAMPLE_PATH = ROOT / "data" / "recipes" / "recipes.json.example"
LOCAL_INGREDIENTS_PATH = ROOT / "data" / "ingredients" / "custom_ingredients.json"
LOCAL_INGREDIENTS_EXAMPLE_PATH = (
    ROOT / "data" / "ingredients" / "custom_ingredients.json.example"
)
DEFAULT_CACHE_DIR = ROOT / ".cache" / "ingredients"

MICRO_FIELDS = [f.name for f in fields(MicronutrientProfile)]
MACRO_FIELDS = ("calories", "protein_g", "fat_g", "carbs_g")


@dataclass
class IngredientTrace:
    name: str
    quantity: float
    unit: str
    status: str  # resolved | skipped | to_taste
    grams_used: Optional[float] = None
    unit_key: Optional[str] = None
    fdc_id: Optional[int] = None
    description: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    skip_reason: Optional[str] = None


@dataclass
class RecipeComputation:
    recipe_id: str
    recipe_name: str
    library: str
    config: str
    computed: Dict[str, float]
    stored: Optional[Dict[str, float]]
    deltas: Optional[Dict[str, float]]
    ingredients: List[IngredientTrace] = field(default_factory=list)
    n_resolved: int = 0
    n_skipped: int = 0
    n_to_taste: int = 0
    has_skip: bool = False
    resolve_error: Optional[str] = None


class RecordingCalculator(NutritionCalculator):
    """NutritionCalculator that records per-ingredient resolve/skip outcomes."""

    def __init__(self, provider: IngredientDataProvider):
        super().__init__(provider)
        self.last_traces: List[IngredientTrace] = []

    def calculate_recipe_nutrition(self, recipe: Recipe) -> NutritionProfile:
        self.last_traces = []
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_micros: Dict[str, float] = {f: 0.0 for f in self.MICRONUTRIENT_FIELDS}

        for ingredient in recipe.ingredients:
            if ingredient.is_to_taste:
                self.last_traces.append(
                    IngredientTrace(
                        name=ingredient.name,
                        quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        status="to_taste",
                    )
                )
                continue

            try:
                info = self.provider.get_ingredient_info(ingredient.name)
                if info is None:
                    raise IngredientNotFoundError(ingredient.name)
                unit_key = self._find_nutrition_unit_key(ingredient, info)
                if unit_key is None:
                    raise IngredientNotFoundError(
                        f"{ingredient.name} (no matching nutrition unit found)"
                    )
                grams_used: Optional[float] = None
                if unit_key == "per_100g":
                    grams_used = self._convert_quantity_to_grams(ingredient)

                nutrition = self.calculate_ingredient_nutrition(ingredient)
                total_calories += nutrition.calories
                total_protein += nutrition.protein_g
                total_fat += nutrition.fat_g
                total_carbs += nutrition.carbs_g
                if nutrition.micronutrients is not None:
                    self._add_micronutrients(total_micros, nutrition.micronutrients)

                provenance = info.get("provenance") or {}
                self.last_traces.append(
                    IngredientTrace(
                        name=ingredient.name,
                        quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        status="resolved",
                        grams_used=grams_used,
                        unit_key=unit_key,
                        fdc_id=provenance.get("fdc_id") or info.get("fdc_id"),
                        description=provenance.get("description")
                        or info.get("description"),
                        calories=nutrition.calories,
                        protein_g=nutrition.protein_g,
                        fat_g=nutrition.fat_g,
                        carbs_g=nutrition.carbs_g,
                    )
                )
            except IngredientNotFoundError as exc:
                self.last_traces.append(
                    IngredientTrace(
                        name=ingredient.name,
                        quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        status="skipped",
                        skip_reason=str(exc),
                    )
                )
            except RuntimeError as exc:
                # API provider: name not in resolve_all cache
                self.last_traces.append(
                    IngredientTrace(
                        name=ingredient.name,
                        quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        status="skipped",
                        skip_reason=str(exc),
                    )
                )

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            micronutrients=MicronutrientProfile(**total_micros),
        )


def profile_to_dict(profile: NutritionProfile) -> Dict[str, float]:
    out: Dict[str, float] = {
        "calories": float(profile.calories),
        "protein_g": float(profile.protein_g),
        "fat_g": float(profile.fat_g),
        "carbs_g": float(profile.carbs_g),
    }
    micros = profile.micronutrients
    if micros is not None:
        for name in MICRO_FIELDS:
            out[name] = float(getattr(micros, name, 0.0))
    else:
        for name in MICRO_FIELDS:
            out[name] = 0.0
    return out


def stored_nutrition_to_dict(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    if not raw:
        return None
    out: Dict[str, float] = {
        "calories": float(raw.get("calories", 0.0)),
        "protein_g": float(raw.get("protein_g", 0.0)),
        "fat_g": float(raw.get("fat_g", 0.0)),
        "carbs_g": float(raw.get("carbs_g", 0.0)),
    }
    micros = raw.get("micronutrients") or {}
    for name in MICRO_FIELDS:
        out[name] = float(micros.get(name, 0.0))
    return out


def delta_dicts(
    computed: Dict[str, float], stored: Optional[Dict[str, float]]
) -> Optional[Dict[str, float]]:
    if stored is None:
        return None
    return {k: computed.get(k, 0.0) - stored.get(k, 0.0) for k in computed}


def load_library_recipes(library: str) -> Tuple[List[Recipe], Dict[str, Dict[str, Any]]]:
    """Load Recipe objects plus raw JSON rows (for stored nutrition).

    ``library`` is one of: ``benchmark``, ``data_recipes``.
    """
    if library == "benchmark":
        path = BENCH_RECIPES_PATH
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        rows = payload["recipes"]
        # RecipeDB expects tags path; benchmark recipes may not be in tag repo.
        # Parse ingredients manually to avoid tag warnings / missing tags.
        recipes = [_recipe_from_row(row) for row in rows]
        by_id = {str(r["id"]): r for r in rows}
        return recipes, by_id

    if library == "data_recipes":
        path = DATA_RECIPES_PATH
        if not path.exists():
            raise FileNotFoundError(f"Missing {path} (untracked local recipes)")
        db = RecipeDB(str(path))
        recipes = db.get_all_recipes()
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        by_id = {str(r["id"]): r for r in payload.get("recipes", [])}
        return recipes, by_id

    raise ValueError(f"Unknown library: {library}")


def _recipe_from_row(row: Dict[str, Any]) -> Recipe:
    ingredients: List[Ingredient] = []
    for ing in row.get("ingredients", []):
        unit = ing.get("unit", "")
        is_to_taste = unit == "to taste" or "to taste" in str(unit).lower()
        quantity = 0.0 if is_to_taste else float(ing.get("quantity", 0.0))
        ingredients.append(
            Ingredient(
                name=ing["name"],
                quantity=quantity,
                unit=unit,
                is_to_taste=is_to_taste,
                normalized_unit=unit,
                normalized_quantity=quantity,
            )
        )
    return Recipe(
        id=str(row["id"]),
        name=row["name"],
        ingredients=ingredients,
        cooking_time_minutes=int(row.get("cooking_time_minutes", 0)),
        instructions=list(row.get("instructions", [])),
        default_servings=int(row.get("default_servings", 1)),
        tags=[],
        provenance=row.get("provenance") if isinstance(row.get("provenance"), dict) else None,
    )


def build_provider(
    config: str, *, cache_dir: Optional[Path] = None
) -> Tuple[IngredientDataProvider, Dict[str, Any]]:
    """Build a provider matching a source configuration name.

    Configs:
      - local-machine: data/ingredients/custom_ingredients.json
      - local-clean:   custom_ingredients.json.example
      - api-cache:     CachedIngredientLookup over existing .cache/ingredients,
                       usda_client=None (cache-only, no network)
      - api-clean:     empty temp cache dir, usda_client=None (all lookups miss)
    """
    meta: Dict[str, Any] = {"config": config}

    if config == "local-machine":
        path = LOCAL_INGREDIENTS_PATH
        meta["ingredients_path"] = str(path)
        meta["exists"] = path.exists()
        provider: IngredientDataProvider = LocalIngredientProvider(NutritionDB(str(path)))
        return provider, meta

    if config == "local-clean":
        path = LOCAL_INGREDIENTS_EXAMPLE_PATH
        meta["ingredients_path"] = str(path)
        meta["exists"] = path.exists()
        provider = LocalIngredientProvider(NutritionDB(str(path)))
        return provider, meta

    if config == "api-cache":
        cdir = cache_dir or DEFAULT_CACHE_DIR
        meta["cache_dir"] = str(cdir)
        meta["cache_file_count"] = len(list(cdir.glob("*.json"))) if cdir.exists() else 0
        lookup = CachedIngredientLookup(cache_dir=str(cdir), usda_client=None)
        provider = APIIngredientProvider(lookup)
        return provider, meta

    if config == "api-clean":
        cdir = cache_dir  # caller supplies empty temp dir
        if cdir is None:
            raise ValueError("api-clean requires cache_dir= temporary empty directory")
        meta["cache_dir"] = str(cdir)
        meta["cache_file_count"] = 0
        lookup = CachedIngredientLookup(cache_dir=str(cdir), usda_client=None)
        provider = APIIngredientProvider(lookup)
        return provider, meta

    raise ValueError(f"Unknown config: {config}")


def ingredient_names(recipes: Sequence[Recipe]) -> List[str]:
    names = sorted(
        {
            ing.name
            for recipe in recipes
            for ing in recipe.ingredients
            if not ing.is_to_taste
        }
    )
    return names


def try_resolve_all(
    provider: IngredientDataProvider, names: Sequence[str]
) -> Optional[str]:
    """Call resolve_all; return error string on IngredientResolutionError, else None."""
    try:
        provider.resolve_all(list(names))
        return None
    except IngredientResolutionError as exc:
        return str(exc)


def compute_library(
    library: str,
    config: str,
    *,
    cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    recipes, raw_by_id = load_library_recipes(library)
    provider, meta = build_provider(config, cache_dir=cache_dir)
    names = ingredient_names(recipes)
    resolve_error = try_resolve_all(provider, names)
    calculator = RecordingCalculator(provider)

    recipe_results: List[Dict[str, Any]] = []
    kcal_abs: List[float] = []
    protein_abs: List[float] = []
    recipes_with_skip = 0

    for recipe in recipes:
        stored = stored_nutrition_to_dict(raw_by_id.get(recipe.id, {}).get("nutrition"))
        # On api-clean / failed resolve_all, still attempt per-recipe soft compute
        # by resolving just this recipe's names when possible.
        per_recipe_error: Optional[str] = resolve_error
        if resolve_error and isinstance(provider, APIIngredientProvider):
            # Soft path: try to resolve only this recipe so we can still see skips.
            provider._resolved.clear()  # type: ignore[attr-defined]
            per_recipe_error = try_resolve_all(
                provider, [i.name for i in recipe.ingredients if not i.is_to_taste]
            )

        computed_profile = calculator.calculate_recipe_nutrition(recipe)
        computed = profile_to_dict(computed_profile)
        deltas = delta_dicts(computed, stored)
        traces = calculator.last_traces
        n_resolved = sum(1 for t in traces if t.status == "resolved")
        n_skipped = sum(1 for t in traces if t.status == "skipped")
        n_to_taste = sum(1 for t in traces if t.status == "to_taste")
        has_skip = n_skipped > 0
        if has_skip:
            recipes_with_skip += 1
        if deltas is not None:
            kcal_abs.append(abs(deltas["calories"]))
            protein_abs.append(abs(deltas["protein_g"]))

        recipe_results.append(
            asdict(
                RecipeComputation(
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    library=library,
                    config=config,
                    computed=computed,
                    stored=stored,
                    deltas=deltas,
                    ingredients=traces,
                    n_resolved=n_resolved,
                    n_skipped=n_skipped,
                    n_to_taste=n_to_taste,
                    has_skip=has_skip,
                    resolve_error=per_recipe_error,
                )
            )
        )

    def _pct(vals: List[float], q: float) -> Optional[float]:
        if not vals:
            return None
        ordered = sorted(vals)
        if len(ordered) == 1:
            return ordered[0]
        # nearest-rank
        idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return ordered[idx]

    summary = {
        "library": library,
        "config": config,
        "provider_meta": meta,
        "n_recipes": len(recipes),
        "n_ingredient_names": len(names),
        "library_resolve_error": resolve_error,
        "recipes_with_any_skip": recipes_with_skip,
        "recipes_with_stored_nutrition": sum(
            1 for r in recipe_results if r["stored"] is not None
        ),
        "kcal_abs_delta": {
            "median": statistics.median(kcal_abs) if kcal_abs else None,
            "p90": _pct(kcal_abs, 0.90),
            "max": max(kcal_abs) if kcal_abs else None,
        },
        "protein_abs_delta": {
            "median": statistics.median(protein_abs) if protein_abs else None,
            "p90": _pct(protein_abs, 0.90),
            "max": max(protein_abs) if protein_abs else None,
        },
        "mean_abs_kcal_delta": (
            statistics.mean(kcal_abs) if kcal_abs else None
        ),
    }
    return {"summary": summary, "recipes": recipe_results}


def collect_unique_ingredient_names() -> List[str]:
    names: set[str] = set()
    for library in ("benchmark", "data_recipes"):
        try:
            recipes, _ = load_library_recipes(library)
        except FileNotFoundError:
            continue
        for recipe in recipes:
            for ing in recipe.ingredients:
                if not ing.is_to_taste:
                    names.add(ing.name)
    return sorted(names)


def cache_key_for_name(name: str) -> str:
    import re

    safe = re.sub(r"[^\w\-]", "_", name.lower())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "unnamed"


def load_cache_entry(name_or_key: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Optional[Dict[str, Any]]:
    key = cache_key_for_name(name_or_key)
    path = cache_dir / f"{key}.json"
    if not path.exists():
        # try raw key
        path2 = cache_dir / f"{name_or_key}.json"
        if path2.exists():
            path = path2
        else:
            return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def mapped_nutrition_to_per_100g(mapped) -> Dict[str, float]:
    out = {
        "calories": float(mapped.calories),
        "protein_g": float(mapped.protein_g),
        "fat_g": float(mapped.fat_g),
        "carbs_g": float(mapped.carbs_g),
    }
    for name in MICRO_FIELDS:
        out[name] = float(getattr(mapped.micronutrients, name, 0.0))
    return out


def nutrition_close(
    a: Dict[str, float], b: Dict[str, float], *, rel: float = 0.01, abs_tol: float = 0.01
) -> Tuple[bool, List[Dict[str, Any]]]:
    diffs: List[Dict[str, Any]] = []
    keys = sorted(set(a) | set(b))
    ok = True
    for k in keys:
        av = float(a.get(k, 0.0))
        bv = float(b.get(k, 0.0))
        if abs(av - bv) <= abs_tol:
            continue
        denom = max(abs(av), abs(bv), 1e-9)
        if abs(av - bv) / denom <= rel:
            continue
        ok = False
        diffs.append({"field": k, "cached": av, "remapped": bv, "abs_delta": av - bv})
    return ok, diffs
