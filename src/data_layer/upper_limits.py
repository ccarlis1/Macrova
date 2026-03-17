"""Upper Tolerable Intake (UL) loader and validation for micronutrients.

Loads daily UL values from reference data by demographic.
Validates daily micronutrient intake against ULs.
Reference source: IOM DRI / EFSA guidelines.

Spec: MEALPLAN_SPECIFICATION_v1.md Section 2.3 — UL table loaded from
data/reference/ul_by_demographic.json, merged with user overrides.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.data_layer.models import UpperLimits, MicronutrientProfile

# Spec Section 2.3: default path for UL reference data
DEFAULT_UL_REFERENCE_PATH = "data/reference/ul_by_demographic.json"


@dataclass
class ULViolation:
    """Represents a single Upper Limit violation for a nutrient.
    
    Created when daily intake exceeds the tolerable upper limit.
    """
    nutrient: str    # Field name (e.g., "vitamin_a_ug")
    actual: float    # Actual daily intake
    limit: float     # Upper limit that was exceeded
    excess: float    # Amount over limit (actual - limit)


class UpperLimitsLoader:
    """Loads Upper Tolerable Intake limits from reference JSON file.
    
    ULs are loaded by demographic (e.g., adult_male, adult_female).
    Field names in the JSON must match MicronutrientProfile exactly.
    JSON null values become Python None (no UL for that nutrient).
    Missing fields default to None.
    """

    def __init__(self, json_path: str):
        """Initialize loader with path to UL reference JSON.
        
        Args:
            json_path: Path to ul_by_demographic.json file
        """
        self.json_path = Path(json_path)
        self._data: Optional[Dict[str, Any]] = None

    def _load_data(self) -> Dict[str, Any]:
        """Load and cache JSON data from file.
        
        Returns:
            Parsed JSON data
            
        Raises:
            FileNotFoundError: If JSON file doesn't exist
        """
        if self._data is None:
            if not self.json_path.exists():
                raise FileNotFoundError(f"UL reference file not found: {self.json_path}")
            
            with open(self.json_path, "r") as f:
                self._data = json.load(f)
        
        return self._data

    def load_for_demographic(self, demographic: str) -> UpperLimits:
        """Load ULs for a specific demographic.
        
        Args:
            demographic: Demographic key (e.g., "adult_male", "adult_female")
            
        Returns:
            UpperLimits instance with values for the demographic.
            Missing fields default to None (no UL).
            
        Raises:
            KeyError: If demographic not found in reference data
            FileNotFoundError: If reference file doesn't exist
        """
        data = self._load_data()
        demographics = data.get("demographics", {})
        
        if demographic not in demographics:
            raise KeyError(
                f"Demographic '{demographic}' not found in UL reference. "
                f"Available: {list(demographics.keys())}"
            )
        
        ul_values = demographics[demographic]
        
        # Get valid field names from UpperLimits (must match MicronutrientProfile)
        valid_fields = {f.name for f in UpperLimits.__dataclass_fields__.values()}
        
        # Build kwargs for UpperLimits, converting JSON null to Python None
        kwargs = {}
        for field_name in valid_fields:
            if field_name in ul_values:
                value = ul_values[field_name]
                # JSON null becomes Python None; otherwise convert to float
                kwargs[field_name] = float(value) if value is not None else None
            else:
                # Missing field defaults to None (no UL)
                kwargs[field_name] = None
        
        return UpperLimits(**kwargs)

    def get_available_demographics(self) -> list:
        """Get list of available demographics in reference data.
        
        Returns:
            List of demographic keys
        """
        data = self._load_data()
        return list(data.get("demographics", {}).keys())


def resolve_upper_limits(
    loader: UpperLimitsLoader,
    demographic: str,
    overrides: Optional[Dict[str, Optional[float]]] = None
) -> UpperLimits:
    """Resolve final ULs by merging reference data with user overrides.
    
    Override precedence rules:
    1. Load reference ULs for the specified demographic
    2. Apply user overrides for explicitly listed nutrients only
    3. Null/None override values are IGNORED (reference value used)
    4. Invalid field names in overrides are IGNORED (no error)
    5. Override values replace reference values (can increase or decrease)
    6. Unlisted nutrients continue using reference ULs
    
    Args:
        loader: UpperLimitsLoader instance with reference data
        demographic: User's demographic (e.g., "adult_male")
        overrides: Optional dict of nutrient overrides from user_profile.yaml
                   Keys must match MicronutrientProfile field names.
                   None values are ignored.
    
    Returns:
        UpperLimits instance with resolved values
        
    Raises:
        KeyError: If demographic not found in reference data
        FileNotFoundError: If reference file doesn't exist
    """
    # Step 1: Load reference ULs for demographic
    reference_ul = loader.load_for_demographic(demographic)
    
    # Step 2: If no overrides, return reference as-is
    if not overrides:
        return reference_ul
    
    # Step 3: Get valid field names
    valid_fields = {f.name for f in UpperLimits.__dataclass_fields__.values()}
    
    # Step 4: Build merged kwargs starting from reference values
    kwargs = {}
    for field_name in valid_fields:
        reference_value = getattr(reference_ul, field_name)
        
        # Check if this field has an override
        if field_name in overrides:
            override_value = overrides[field_name]
            
            # Null/None overrides are ignored - use reference
            if override_value is None:
                kwargs[field_name] = reference_value
            else:
                # Valid override - convert to float
                kwargs[field_name] = float(override_value)
        else:
            # No override - use reference value
            kwargs[field_name] = reference_value
    
    # Invalid field names in overrides are silently ignored
    # (they won't match any field_name in the loop above)
    
    return UpperLimits(**kwargs)


def validate_daily_upper_limits(
    daily_micros: MicronutrientProfile,
    upper_limits: UpperLimits
) -> List[ULViolation]:
    """Validate daily micronutrient intake against upper tolerable limits.
    
    For each micronutrient:
    - If UL is None: skip (no limit established)
    - If intake <= UL: pass
    - If intake > UL: violation recorded
    
    Note: Intake exactly at the UL (==) is considered valid (not exceeded).
    
    Args:
        daily_micros: MicronutrientProfile with daily totals
        upper_limits: UpperLimits with resolved limits (reference + overrides)
    
    Returns:
        List of ULViolation objects. Empty list means all limits passed.
    """
    violations = []
    
    # Get all micronutrient field names (same fields in both dataclasses)
    field_names = [f.name for f in MicronutrientProfile.__dataclass_fields__.values()]
    
    for field_name in field_names:
        # Get actual intake and limit
        actual_intake = getattr(daily_micros, field_name)
        ul_value = getattr(upper_limits, field_name)
        
        # Skip if no UL established (None)
        if ul_value is None:
            continue
        
        # Check if intake exceeds limit (strictly greater than)
        if actual_intake > ul_value:
            violations.append(ULViolation(
                nutrient=field_name,
                actual=actual_intake,
                limit=ul_value,
                excess=actual_intake - ul_value
            ))
    
    return violations
