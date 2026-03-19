from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.data_layer.exceptions import IngredientNotFoundError
from src.data_layer.models import Ingredient, IngredientInput, Recipe
from src.ingestion.ingredient_validator import IngredientValidator
from src.nutrition.calculator import NutritionCalculator
from src.providers.api_provider import IngredientResolutionError
from src.providers.ingredient_provider import IngredientDataProvider
from src.llm.schemas import RecipeDraft, ValidationFailure, parse_llm_json
from src.llm.types import ValidatedRecipeForPersistence
from src.llm.usda_contract import assert_usda_capable_provider


class RecipeValidationError(Exception):
    """Deterministic error raised when recipe validation cannot proceed."""


def _estimate_cooking_time_minutes(draft: RecipeDraft) -> int:
    # Deterministic placeholder mapping since RecipeDraft schema does not include
    # explicit cooking time. We clamp to keep recipes within reasonable bounds.
    minutes = 5 * len(draft.instructions)
    if minutes < 0:
        return 0
    if minutes > 120:
        return 120
    return int(minutes)


def _validation_failure(
    *,
    error_code: str,
    message: str,
    field_errors: List[str] | None = None,
) -> ValidationFailure:
    return ValidationFailure(
        error_code=error_code,
        message=message,
        field_errors=field_errors or [],
    )


def _ingredient_input_from_draft(draft_ing: Any) -> IngredientInput:
    # IngredientValidator expects a fully structured input: name, quantity, unit.
    return IngredientInput(
        name=str(draft_ing.name),
        quantity=float(draft_ing.quantity),
        unit=str(draft_ing.unit),
    )


def validate_recipe_draft(
    draft: RecipeDraft,
    provider: IngredientDataProvider,
) -> Tuple[bool, Recipe | ValidationFailure]:
    """USDA-first validation gate for a single LLM `RecipeDraft`.

    Validation order (deterministic):
    1. Unit + quantity + canonical ingredient name (IngredientValidator)
    2. Provider resolution and ingredient existence check (provider.resolve_all/get)
    3. Nutrition recomputation (NutritionCalculator) and failure detection
    """
    # System invariant: USDA-backed validation is mandatory for recipe validation.
    assert_usda_capable_provider(provider)

    ingredient_validator = IngredientValidator()

    validated_ingredients: List[Ingredient] = []

    def _set_ingredient_to_taste(ing: Ingredient) -> None:
        ing.is_to_taste = True
        ing.unit = "to taste"
        ing.quantity = 0.0
        ing.normalized_unit = "to taste"
        ing.normalized_quantity = 0.0

    def _current_measurable() -> List[Ingredient]:
        return [i for i in validated_ingredients if not i.is_to_taste]

    def _current_measurable_names() -> List[str]:
        # Provider resolution is keyed by canonical name; keep deterministic order.
        return sorted({i.name for i in validated_ingredients if not i.is_to_taste})

    # 1) Validate ingredient fields and canonicalize names.
    for ing_idx, draft_ing in enumerate(draft.ingredients):
        ingredient_input = _ingredient_input_from_draft(draft_ing)
        vres = ingredient_validator.validate(ingredient_input)

        if not vres.is_valid or vres.ingredient is None:
            # Deterministically select a primary failing field for error code mapping.
            primary = vres.errors[0] if vres.errors else None
            if primary is not None and primary.field == "unit":
                return (
                    False,
                    _validation_failure(
                        error_code="INVALID_UNIT",
                        message=f"Invalid unit for ingredient index {ing_idx}.",
                        field_errors=[f"{primary.field}: {primary.message}"],
                    ),
                )
            if primary is not None and primary.field == "quantity":
                return (
                    False,
                    _validation_failure(
                        error_code="INVALID_QUANTITY",
                        message=f"Invalid quantity for ingredient index {ing_idx}.",
                        field_errors=[f"{primary.field}: {primary.message}"],
                    ),
                )
            return (
                False,
                _validation_failure(
                    error_code="INVALID_INGREDIENT_INPUT",
                    message=f"Ingredient input validation failed at index {ing_idx}.",
                    field_errors=[f"{e.field}: {e.message}" for e in vres.errors],
                ),
            )

        validated = vres.ingredient

        # IngredientValidator normalizes unit/quantity into base units that the
        # NutritionCalculator understands more reliably.
        ing = Ingredient(
            name=validated.canonical_name,
            quantity=float(validated.normalized_quantity),
            unit=str(validated.normalized_unit),
            is_to_taste=validated.is_to_taste,
            normalized_unit=str(validated.normalized_unit),
            normalized_quantity=float(validated.normalized_quantity),
        )
        validated_ingredients.append(ing)

    # Recipe-level guard.
    if not _current_measurable():
        return (
            False,
            _validation_failure(
                error_code="EMPTY_RECIPE",
                message="Recipe contains no measurable ingredients.",
            ),
        )

    # 2) Provider resolution and existence check (authoritative).
    # For API providers, resolve_all is required before get_ingredient_info().
    # Roll back to "to taste" on failures so planning can proceed.
    while True:
        measurable = _current_measurable()
        if not measurable:
            return (
                False,
                _validation_failure(
                    error_code="EMPTY_RECIPE",
                    message="Recipe contains no measurable ingredients.",
                ),
            )

        try:
            provider.resolve_all(_current_measurable_names())
            break
        except IngredientResolutionError as e:
            # Expected format:
            #   "Failed to resolve ingredient '<canonical_name>': <details>"
            match = re.search(r"Failed to resolve ingredient '([^']+)'", str(e))
            if match is None:
                raise

            failed_canonical_name = match.group(1).lower().strip()
            converted_any = False
            for ing in validated_ingredients:
                if not ing.is_to_taste and ing.name == failed_canonical_name:
                    _set_ingredient_to_taste(ing)
                    converted_any = True

            # If we can't map the failure back to the recipe, fail fast instead
            # of risking an infinite retry loop.
            if not converted_any:
                raise

    # Existence check loop: if the provider returns None (or raises) we
    # convert that ingredient to "to taste" rather than failing the draft.
    for ing_idx, ing in enumerate(validated_ingredients):
        if ing.is_to_taste:
            continue
        try:
            info = provider.get_ingredient_info(ing.name)
        except Exception:
            info = None
        if info is None:
            _set_ingredient_to_taste(ing)
            if not _current_measurable():
                return (
                    False,
                    _validation_failure(
                        error_code="EMPTY_RECIPE",
                        message="Recipe contains no measurable ingredients.",
                        field_errors=[f"ingredient_index={ing_idx}"],
                    ),
                )

    # 3) Nutrition recomputation: ignore any LLM-provided nutrition fields.
    # Since our RecipeDraft schema has no nutrition fields, the key guard is
    # that nutrition computation succeeds for every measurable ingredient.
    calculator = NutritionCalculator(provider)
    nutrition_computation_cache: Dict[Tuple[str, float, str], bool] = {}
    measurable = _current_measurable()
    for ing in measurable:
        cache_key = (ing.name, float(ing.quantity), str(ing.unit).lower().strip())
        if cache_key in nutrition_computation_cache:
            continue
        try:
            calculator.calculate_ingredient_nutrition(ing)
            nutrition_computation_cache[cache_key] = True
        except IngredientNotFoundError:
            return (
                False,
                _validation_failure(
                    error_code="NUTRITION_COMPUTATION_FAILED",
                    message=f"Failed to compute nutrition for ingredient: {ing.name}",
                    field_errors=[f"unit={ing.unit}", f"quantity={ing.quantity}"],
                ),
            )
        except Exception as e:
            return (
                False,
                _validation_failure(
                    error_code="NUTRITION_COMPUTATION_FAILED",
                    message="Nutrition computation raised an unexpected error.",
                    field_errors=[str(e)],
                ),
            )

    # Construct a Recipe object for safe persistence.
    cooking_time_minutes = _estimate_cooking_time_minutes(draft)
    recipe = Recipe(
        id="",
        name=str(draft.name).strip(),
        ingredients=validated_ingredients,
        cooking_time_minutes=cooking_time_minutes,
        instructions=list(draft.instructions),
    )
    return True, recipe


def validate_recipe_drafts(
    drafts: List[RecipeDraft],
    provider: IngredientDataProvider,
) -> Tuple[List[ValidatedRecipeForPersistence], List[ValidationFailure]]:
    """Validate many drafts, returning accepted recipes and failures."""

    accepted_wrapped: List[ValidatedRecipeForPersistence] = []
    failures: List[ValidationFailure] = []

    for draft_idx, draft in enumerate(drafts):
        ok, res = validate_recipe_draft(draft, provider)
        if ok:
            assert isinstance(res, Recipe)
            accepted_wrapped.append(ValidatedRecipeForPersistence(recipe=res))
        else:
            assert isinstance(res, ValidationFailure)
            failures.append(res)

    return accepted_wrapped, failures

