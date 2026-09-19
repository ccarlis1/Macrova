from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.data_layer.exceptions import IngredientNotFoundError
from src.data_layer.models import Ingredient, IngredientInput, Recipe
from src.ingestion.ingredient_normalizer import CONTROLLED_DESCRIPTORS
from src.ingestion.ingredient_validator import IngredientValidator
from src.nutrition.calculator import NutritionCalculator
from src.providers.api_provider import IngredientResolutionError
from src.providers.ingredient_provider import IngredientDataProvider
from src.llm.recovery_types import GapSpec
from src.llm.repository import find_near_duplicate
from src.llm.schemas import RecipeDraft, ValidationFailure
from src.llm.types import ValidatedRecipeForPersistence
from src.llm.usda_contract import assert_usda_capable_provider


VALIDATION_VERSION = "2"  # bumped with the semantic gates (LLM overhaul Stage 4)

# Single-recipe plausibility envelope (per serving as authored).
MAX_PLAUSIBLE_RECIPE_KCAL = 2500.0
MAX_FAT_KCAL_SHARE = 0.85  # above this, and >400 kcal, the recipe is essentially oil


class RecipeValidationError(Exception):
    """Deterministic error raised when recipe validation cannot proceed."""


def _estimate_cooking_time_minutes(draft: RecipeDraft) -> int:
    # Heuristic used ONLY when the draft carries no claim and no slot cap applies.
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
    return IngredientInput(
        name=str(draft_ing.name),
        quantity=float(draft_ing.quantity),
        unit=str(draft_ing.unit),
    )


_WORD = re.compile(r"[a-z0-9%]+")
_STOP = {"and", "or", "of", "with", "in", "the", "a", "an", "style", "fresh"} | set(CONTROLLED_DESCRIPTORS)


def _tokens(text: str) -> List[str]:
    return [t for t in _WORD.findall(str(text).lower()) if t not in _STOP]


def _stem(token: str) -> str:
    t = token
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("es") and len(t) > 4 and t[-3] in "sxzh":
        return t[:-2]
    if t.endswith("s") and len(t) > 3:
        return t[:-1]
    return t


def ingredient_matches_exclusion(ingredient_name: str, excluded: Sequence[str]) -> Optional[str]:
    """Class-aware exclusion match: 'peanuts' excludes 'peanut butter', 'egg' excludes 'eggs'.

    Deterministic token/prefix matching; returns the matching exclusion term or None.
    """
    name_tokens = [_stem(t) for t in _WORD.findall(str(ingredient_name).lower())]
    for term in excluded:
        term_tokens = [_stem(t) for t in _WORD.findall(str(term).lower())]
        if not term_tokens:
            continue
        # every token of the exclusion term must appear (as a token or token prefix) in the name
        if all(any(nt == tt or nt.startswith(tt) for nt in name_tokens) for tt in term_tokens):
            return str(term)
    return None


# USDA descriptions often start with a food *group* word before the specific food
# ("Fish, tilapia, raw"; "Nuts, almond butter"). These prefixes are allowed to precede a match.
_USDA_GROUP_PREFIXES = {
    "fish", "seafood", "shellfish", "mollusks", "crustaceans", "nuts", "seeds", "cereals", "beverages",
    "snacks", "squash", "sauce", "spices", "vegetables", "fruit", "fruits", "game", "cheese", "beans",
    "peppers", "sausage", "lamb", "pork", "veal", "beef", "chicken", "turkey", "soup", "juice", "candies",
    "sweets", "grains", "legumes", "herbs",
}


def _tok_match(a: str, b: str) -> bool:
    return a == b or a.startswith(b) or b.startswith(a)


def resolved_identity_matches(query_name: str, description: str) -> bool:
    """Head-noun identity gate for a resolved USDA description.

    USDA descriptions name the food in the first comma-separated segment, category word
    first ("Oil, oat" -> oil; "Tomatoes, cherry, raw" -> tomatoes). Accept when:
    - the first head token matches a query token (stem/prefix), or
    - the first segment is a known USDA group word (Fish, Nuts, Cereals, Cheese, ...) and a
      token of the first two segments matches a query token ("Fish, tilapia, raw").
    Rejects "oats"->"Oil, oat", "eggs"->"Bread, egg", "bell pepper"->"TACO BELL, Nachos",
    "milk 1% ..."->"Cheese, cottage, ...". Known misses (same head word, different form):
    "cherry tomatoes"->"Cherries, raw", "banana"->"Bananas, dehydrated",
    "acai berry"->"Beverages, Acai berry drink".
    """
    q = [_stem(t) for t in _tokens(query_name)]
    if not q:
        return True  # nothing to check against
    segments = [seg for seg in str(description).split(",")]
    seg0 = _tokens(segments[0]) if segments else []
    if not seg0:
        seg0 = _tokens(description)
    if not seg0:
        return True
    first = _stem(seg0[0])
    if any(_tok_match(qt, first) for qt in q):
        return True
    if seg0[0].lower() in _USDA_GROUP_PREFIXES or first in _USDA_GROUP_PREFIXES:
        rest = [_stem(t) for t in seg0[1:]]
        if len(segments) > 1:
            rest += [_stem(t) for t in _tokens(segments[1])]
        return any(_tok_match(qt, ht) for qt in q for ht in rest)
    return False


def validate_recipe_draft(
    draft: RecipeDraft,
    provider: IngredientDataProvider,
    *,
    excluded_ingredients: Optional[Sequence[str]] = None,
    cook_time_cap_minutes: Optional[int] = None,
    gap_spec: Optional[GapSpec] = None,
    existing_recipes: Optional[Sequence[Recipe]] = None,
    source: str = "llm",
) -> Tuple[bool, Recipe | ValidationFailure]:
    """Deterministic validation gate for a single LLM `RecipeDraft`.

    Order:
    1. Unit / quantity / canonical name (IngredientValidator)
    2. Exclusions (class-aware token match) — any ingredient, including "to taste"
    3. Provider resolution: every measurable ingredient must resolve (no demotion)
    4. Identity gate on the resolved description (when provenance is available)
    5. Nutrition recomputation + plausibility envelope
    6. Cook time: author's claim (recorded as provenance) checked against the slot cap
    7. Fitness against the GapSpec, if one was given
    8. Near-duplicate check against existing recipes
    """
    assert_usda_capable_provider(provider)

    ingredient_validator = IngredientValidator()
    validated_ingredients: List[Ingredient] = []
    excluded = [str(x) for x in (excluded_ingredients or []) if str(x).strip()]
    if gap_spec is not None and not excluded:
        excluded = list(gap_spec.excluded_ingredients)
    if cook_time_cap_minutes is None and gap_spec is not None:
        cook_time_cap_minutes = gap_spec.cook_time_cap_minutes

    # 1) Field validation and canonicalization; 2) exclusions.
    for ing_idx, draft_ing in enumerate(draft.ingredients):
        hit = ingredient_matches_exclusion(str(draft_ing.name), excluded)
        if hit is not None:
            return (
                False,
                _validation_failure(
                    error_code="EXCLUDED_INGREDIENT",
                    message=f"Ingredient {draft_ing.name!r} matches excluded ingredient {hit!r}.",
                    field_errors=[f"ingredient_index={ing_idx}", f"excluded={hit}"],
                ),
            )
        ingredient_input = _ingredient_input_from_draft(draft_ing)
        vres = ingredient_validator.validate(ingredient_input)

        if not vres.is_valid or vres.ingredient is None:
            primary = vres.errors[0] if vres.errors else None
            if primary is not None and primary.field == "unit":
                return (False, _validation_failure(error_code="INVALID_UNIT", message=f"Invalid unit for ingredient index {ing_idx}.", field_errors=[f"{primary.field}: {primary.message}"]))
            if primary is not None and primary.field == "quantity":
                return (False, _validation_failure(error_code="INVALID_QUANTITY", message=f"Invalid quantity for ingredient index {ing_idx}.", field_errors=[f"{primary.field}: {primary.message}"]))
            return (False, _validation_failure(error_code="INVALID_INGREDIENT_INPUT", message=f"Ingredient input validation failed at index {ing_idx}.", field_errors=[f"{e.field}: {e.message}" for e in vres.errors]))

        validated = vres.ingredient
        validated_ingredients.append(
            Ingredient(
                name=validated.canonical_name,
                quantity=float(validated.normalized_quantity),
                unit=str(validated.normalized_unit),
                is_to_taste=validated.is_to_taste,
                normalized_unit=str(validated.normalized_unit),
                normalized_quantity=float(validated.normalized_quantity),
            )
        )

    measurable = [i for i in validated_ingredients if not i.is_to_taste]
    if not measurable:
        return (False, _validation_failure(error_code="EMPTY_RECIPE", message="Recipe contains no measurable ingredients."))

    # 3) Resolution: all-or-nothing. No ingredient is silently demoted.
    names = sorted({i.name for i in measurable})
    try:
        provider.resolve_all(names)
    except IngredientResolutionError as e:
        match = re.search(r"Failed to resolve ingredient '([^']+)'", str(e))
        failed = match.group(1) if match else "?"
        return (
            False,
            _validation_failure(
                error_code="INGREDIENT_UNRESOLVED",
                message=f"Ingredient {failed!r} could not be resolved to a USDA record; recipe rejected (no demotion).",
                field_errors=[f"ingredient={failed}"],
            ),
        )

    resolved_ids: Dict[str, Any] = {}
    for ing_idx, ing in enumerate(validated_ingredients):
        if ing.is_to_taste:
            continue
        try:
            info = provider.get_ingredient_info(ing.name)
        except Exception:
            info = None
        if info is None:
            return (
                False,
                _validation_failure(
                    error_code="INGREDIENT_UNRESOLVED",
                    message=f"Ingredient {ing.name!r} has no provider record; recipe rejected (no demotion).",
                    field_errors=[f"ingredient_index={ing_idx}"],
                ),
            )
        # 4) Identity gate when the provider tells us what it resolved to.
        prov = info.get("provenance") if isinstance(info, dict) else None
        if isinstance(prov, dict):
            desc = str(prov.get("description") or "")
            if desc and not resolved_identity_matches(ing.name, desc):
                return (
                    False,
                    _validation_failure(
                        error_code="INGREDIENT_IDENTITY_MISMATCH",
                        message=f"Ingredient {ing.name!r} resolved to {desc!r}, which does not name the same food.",
                        field_errors=[f"ingredient_index={ing_idx}", f"resolved={desc}", f"fdc_id={prov.get('fdc_id')}"],
                    ),
                )
            resolved_ids[ing.name] = prov.get("fdc_id")

    # 5) Nutrition recomputation (authoritative: provider data only) + plausibility.
    calculator = NutritionCalculator(provider)
    total_kcal = total_fat = total_protein = total_carbs = 0.0
    micro_totals: Dict[str, float] = {}
    memo: Dict[Tuple[str, float, str], Any] = {}
    for ing in measurable:
        key = (ing.name, float(ing.quantity), str(ing.unit).lower().strip())
        try:
            if key in memo:
                prof = memo[key]
            else:
                prof = calculator.calculate_ingredient_nutrition(ing)
                memo[key] = prof
        except IngredientNotFoundError:
            return (False, _validation_failure(error_code="NUTRITION_COMPUTATION_FAILED", message=f"Failed to compute nutrition for ingredient: {ing.name}", field_errors=[f"unit={ing.unit}", f"quantity={ing.quantity}"]))
        except Exception as e:
            return (False, _validation_failure(error_code="NUTRITION_COMPUTATION_FAILED", message="Nutrition computation raised an unexpected error.", field_errors=[str(e)]))
        total_kcal += float(prof.calories)
        total_fat += float(prof.fat_g)
        total_protein += float(prof.protein_g)
        total_carbs += float(prof.carbs_g)
        micro = getattr(prof, "micronutrients", None)
        if micro is not None:
            for f in micro.__dataclass_fields__:
                micro_totals[f] = micro_totals.get(f, 0.0) + float(getattr(micro, f, 0.0) or 0.0)

    if total_kcal <= 0.0:
        return (False, _validation_failure(error_code="IMPLAUSIBLE_NUTRITION", message="Recipe computes to zero calories.", field_errors=[f"kcal={total_kcal:.1f}"]))
    if total_kcal > MAX_PLAUSIBLE_RECIPE_KCAL:
        return (False, _validation_failure(error_code="IMPLAUSIBLE_NUTRITION", message=f"Recipe computes to {total_kcal:.0f} kcal per serving, above the plausibility ceiling.", field_errors=[f"kcal={total_kcal:.1f}"]))
    if total_kcal > 400.0 and (total_fat * 9.0) / total_kcal > MAX_FAT_KCAL_SHARE:
        return (False, _validation_failure(error_code="IMPLAUSIBLE_NUTRITION", message="More than 85% of the recipe's calories come from fat; the resolved ingredients are probably wrong (e.g. an oil).", field_errors=[f"kcal={total_kcal:.1f}", f"fat_g={total_fat:.1f}"]))

    # 6) Cook time.
    claimed = draft.cooking_time_minutes
    if claimed is not None:
        cooking_time_minutes = int(claimed)
        cooking_time_source = "llm_claimed"
    elif cook_time_cap_minutes is not None:
        return (False, _validation_failure(error_code="COOK_TIME_UNKNOWN", message="A cook-time cap applies but the draft does not state cooking_time_minutes.", field_errors=[f"cap={cook_time_cap_minutes}"]))
    else:
        cooking_time_minutes = _estimate_cooking_time_minutes(draft)
        cooking_time_source = "heuristic_5min_per_step"
    if cook_time_cap_minutes is not None and cooking_time_minutes > int(cook_time_cap_minutes):
        return (False, _validation_failure(error_code="COOK_TIME_EXCEEDS_CAP", message=f"Claimed cook time {cooking_time_minutes} min exceeds the slot cap {cook_time_cap_minutes} min.", field_errors=[f"cap={cook_time_cap_minutes}", f"claimed={cooking_time_minutes}"]))

    # 7) Fitness against the gap the recipe was requested for.
    if gap_spec is not None:
        if gap_spec.kind == "nutrient_gap" and gap_spec.nutrient_min_per_recipe:
            if not any(micro_totals.get(n, 0.0) >= float(v) for n, v in gap_spec.nutrient_min_per_recipe.items()):
                return (False, _validation_failure(error_code="NOT_USEFUL", message="Recipe does not supply the requested minimum of any deficient nutrient.", field_errors=[f"{n}: has {micro_totals.get(n, 0.0):.2f}, needs {v}" for n, v in gap_spec.nutrient_min_per_recipe.items()]))
        if gap_spec.kind in ("macro_gap", "candidate_gap", "uniqueness_gap") and gap_spec.per_meal_calories:
            t = float(gap_spec.per_meal_calories)
            if not (0.4 * t <= total_kcal <= 1.8 * t):
                return (False, _validation_failure(error_code="NOT_USEFUL", message=f"Recipe is {total_kcal:.0f} kcal; a useful recipe for this gap lands near {t:.0f} kcal per meal.", field_errors=[f"kcal={total_kcal:.1f}", f"per_meal_target={t:.1f}"]))

    recipe = Recipe(
        id="",
        name=str(draft.name).strip(),
        ingredients=validated_ingredients,
        cooking_time_minutes=cooking_time_minutes,
        instructions=list(draft.instructions),
        provenance={
            "source": source,
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "validation_version": VALIDATION_VERSION,
            "cooking_time_source": cooking_time_source,
            "resolved_fdc_ids": resolved_ids,
            "computed_nutrition": {"calories": round(total_kcal, 1), "protein_g": round(total_protein, 1), "fat_g": round(total_fat, 1), "carbs_g": round(total_carbs, 1)},
        },
    )

    # 8) Near-duplicate check.
    if existing_recipes:
        dup = find_near_duplicate(recipe, list(existing_recipes))
        if dup is not None:
            return (False, _validation_failure(error_code="DUPLICATE", message=f"Recipe duplicates existing recipe {dup!r} (same dish under different quantities).", field_errors=[f"duplicate_of={dup}"]))

    return True, recipe


def validate_recipe_drafts(
    drafts: List[RecipeDraft],
    provider: IngredientDataProvider,
    *,
    excluded_ingredients: Optional[Sequence[str]] = None,
    cook_time_cap_minutes: Optional[int] = None,
    gap_spec: Optional[GapSpec] = None,
    existing_recipes: Optional[Sequence[Recipe]] = None,
    source: str = "llm",
) -> Tuple[List[ValidatedRecipeForPersistence], List[ValidationFailure]]:
    """Validate many drafts, returning accepted recipes and failures.

    Accepted drafts within the same batch are also checked against each other for
    near-duplicates so one call cannot persist the same dish twice.
    """

    accepted_wrapped: List[ValidatedRecipeForPersistence] = []
    failures: List[ValidationFailure] = []
    seen: List[Recipe] = list(existing_recipes or [])

    for draft in drafts:
        ok, res = validate_recipe_draft(
            draft,
            provider,
            excluded_ingredients=excluded_ingredients,
            cook_time_cap_minutes=cook_time_cap_minutes,
            gap_spec=gap_spec,
            existing_recipes=seen,
            source=source,
        )
        if ok:
            assert isinstance(res, Recipe)
            accepted_wrapped.append(ValidatedRecipeForPersistence(recipe=res))
            seen.append(res)
        else:
            assert isinstance(res, ValidationFailure)
            failures.append(res)

    return accepted_wrapped, failures
