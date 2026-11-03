"""Micronutrient names and daily targets at the MCP boundary.

The planner keys micronutrients like ``vitamin_c_mg``. MCP tools show plain names
with the unit, e.g. ``"Vitamin C (mg)"``. v1 takes no custom goals: the caller
picks a demographic, which selects the daily RDIs (``rdi_by_demographic.json``)
and upper limits (``ul_by_demographic.json``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Literal, Mapping, Optional

from src.data_layer.models import UpperLimits
from src.data_layer.upper_limits import UpperLimitsLoader, resolve_upper_limits

_REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"
RDI_PATH = _REFERENCE_DIR / "rdi_by_demographic.json"
UL_PATH = _REFERENCE_DIR / "ul_by_demographic.json"

Demographic = Literal["adult_male", "adult_female", "pregnancy", "lactation"]

# Planner key -> plain name. The unit comes from the key's suffix.
_PLAIN_NAMES: Dict[str, str] = {
    "vitamin_a_ug": "Vitamin A",
    "vitamin_c_mg": "Vitamin C",
    "vitamin_d_iu": "Vitamin D",
    "vitamin_e_mg": "Vitamin E",
    "vitamin_k_ug": "Vitamin K",
    "b1_thiamine_mg": "Thiamin (B1)",
    "b2_riboflavin_mg": "Riboflavin (B2)",
    "b3_niacin_mg": "Niacin (B3)",
    "b5_pantothenic_acid_mg": "Pantothenic acid (B5)",
    "b6_pyridoxine_mg": "Vitamin B6",
    "b12_cobalamin_ug": "Vitamin B12",
    "folate_ug": "Folate",
    "calcium_mg": "Calcium",
    "copper_mg": "Copper",
    "iron_mg": "Iron",
    "magnesium_mg": "Magnesium",
    "manganese_mg": "Manganese",
    "phosphorus_mg": "Phosphorus",
    "potassium_mg": "Potassium",
    "selenium_ug": "Selenium",
    "sodium_mg": "Sodium",
    "zinc_mg": "Zinc",
    "fiber_g": "Fiber",
    "omega_3_g": "Omega-3 (ALA)",
    "omega_6_g": "Omega-6 (linoleic acid)",
}
_UNITS = {"ug": "µg", "mg": "mg", "g": "g", "iu": "IU"}


def plain_name(key: str) -> str:
    """``vitamin_c_mg`` -> ``"Vitamin C (mg)"``. Unknown keys come back unchanged."""
    name = _PLAIN_NAMES.get(key)
    if name is None:
        return key
    return f"{name} ({_UNITS[key.rsplit('_', 1)[1]]})"


def plain_names(values: Optional[Mapping[str, float]], digits: int = 1) -> Dict[str, float]:
    """Re-key a micronutrient dict by plain name, in the planner's field order. Drops values that round to 0."""
    values = values or {}
    rounded = {key: round(float(values.get(key) or 0.0), digits) for key in _PLAIN_NAMES}
    return {plain_name(key): value for key, value in rounded.items() if value != 0.0}


@lru_cache(maxsize=None)
def _rdi_table() -> Dict[str, Dict[str, float]]:
    with open(RDI_PATH, encoding="utf-8") as f:
        return json.load(f)["demographics"]


def daily_rdis(demographic: Demographic) -> Dict[str, float]:
    """Daily recommended intakes for a demographic, keyed like ``vitamin_c_mg``."""
    return {key: float(value) for key, value in _rdi_table()[demographic].items()}


def upper_limits(demographic: Demographic) -> UpperLimits:
    return resolve_upper_limits(UpperLimitsLoader(str(UL_PATH)), demographic=demographic)
