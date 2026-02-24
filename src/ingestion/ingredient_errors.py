"""Structured error types for the ingredient pipeline (Step 2.8).

This module defines explicit, typed errors for all failure modes in the
ingredient lookup and nutrition calculation pipeline.

DESIGN PRINCIPLES:
1. FAIL FAST: Errors are raised immediately, not deferred
2. NO GUESSING: Ambiguous situations raise errors, not heuristic fallbacks
3. EXPLICIT CONTEXT: Every error includes relevant debugging information
4. TYPED ERRORS: Each failure mode has its own error type for precise handling
5. NO PARTIAL DATA: Errors never include partial nutrition data

WHY EXPLICIT FAILURE IS PREFERABLE TO HEURISTIC RECOVERY:
1. Nutritional accuracy is critical (UL validation, health recommendations)
2. Silent wrong data is worse than explicit failure
3. User can correct input when error is clear
4. Debugging is straightforward with explicit errors
5. Testing is deterministic (same input → same error)

HOW THIS SUPPORTS LATER "SMART" PARSING:
1. Smart parsing layer can catch these errors and suggest corrections
2. Base pipeline remains strict and trustworthy
3. User always sees raw error if smart parsing also fails
4. Smart layer can be enabled/disabled without affecting correctness
5. Errors are structured → smart layer can programmatically respond

PIPELINE ERROR FLOW:
    ┌─────────────────────────────────────────────────────┐
    │ User Input                                          │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ Validation        → ValidationFailureError          │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ Normalization     (rarely fails - internal)         │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ API Search        → IngredientNotFoundError         │
    │                   → AmbiguousIngredientError        │
    │                   → APIFailureError                 │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ Nutrition Mapping → MissingNutritionDataError       │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ Scaling           → UnitNotSupportedError           │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │ NutritionProfile (success)                          │
    └─────────────────────────────────────────────────────┘
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class IngredientErrorCode(Enum):
    """Enumeration of all ingredient pipeline error codes.
    
    Each code corresponds to a specific failure mode in the pipeline.
    Codes are string values for easy serialization and logging.
    """
    
    # Lookup errors
    INGREDIENT_NOT_FOUND = "INGREDIENT_NOT_FOUND"
    AMBIGUOUS_INGREDIENT = "AMBIGUOUS_INGREDIENT"
    
    # Unit/quantity errors
    UNIT_NOT_SUPPORTED = "UNIT_NOT_SUPPORTED"
    
    # Nutrition data errors
    MISSING_NUTRITION_DATA = "MISSING_NUTRITION_DATA"
    
    # External API errors
    API_FAILURE = "API_FAILURE"
    
    # Input validation errors
    VALIDATION_FAILURE = "VALIDATION_FAILURE"


class IngredientPipelineError(Exception):
    """Base exception for all ingredient pipeline errors.
    
    All pipeline errors inherit from this class, allowing:
    1. Catching all pipeline errors with a single except clause
    2. Accessing structured error information (code, message, context)
    3. Converting errors to user-friendly or API-friendly formats
    
    Attributes:
        code: IngredientErrorCode identifying the error type
        message: Human-readable error description
        context: Dictionary of relevant error context (ingredient name, etc.)
    """
    
    def __init__(
        self,
        code: IngredientErrorCode,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize pipeline error.
        
        Args:
            code: Error code enum value
            message: Human-readable message
            context: Additional context dictionary (defaults to empty)
        """
        self.code = code
        self.message = message
        self.context = context or {}
        
        # Build exception message
        super().__init__(f"[{code.value}] {message}")
    
    def __str__(self) -> str:
        """Return formatted error string."""
        return f"[{self.code.value}] {self.message}"
    
    def __repr__(self) -> str:
        """Return detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, "
            f"message={self.message!r}, "
            f"context={self.context!r})"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses.
        
        Returns:
            Dictionary with error code, message, and context
        """
        return {
            "error_code": self.code.value,
            "message": self.message,
            "context": self.context
        }


class IngredientNotFoundError(IngredientPipelineError):
    """Raised when an ingredient cannot be found in USDA database.
    
    This error indicates that the search returned zero results.
    User should check spelling or try alternative ingredient names.
    
    Context includes:
        - ingredient_name: The searched ingredient
        - search_query: The actual query sent to API (if different)
    """
    
    def __init__(
        self,
        ingredient_name: str,
        search_query: Optional[str] = None
    ):
        """Initialize not found error.
        
        Args:
            ingredient_name: The ingredient that was not found
            search_query: The actual API query (if normalized differently)
        """
        context = {
            "ingredient_name": ingredient_name,
        }
        if search_query:
            context["search_query"] = search_query
        
        message = f"Ingredient '{ingredient_name}' not found in USDA database"
        if search_query and search_query != ingredient_name:
            message += f" (searched as '{search_query}')"
        
        super().__init__(
            code=IngredientErrorCode.INGREDIENT_NOT_FOUND,
            message=message,
            context=context
        )
        
        # Store for direct access
        self.ingredient_name = ingredient_name
        self.search_query = search_query


class AmbiguousIngredientError(IngredientPipelineError):
    """Raised when multiple matching ingredients are found with equal relevance.
    
    This error indicates that the search returned multiple results that
    cannot be automatically disambiguated. User should provide a more
    specific ingredient name.
    
    Context includes:
        - ingredient_name: The searched ingredient
        - matches: List of matching food descriptions
        - match_count: Number of matches
    """
    
    def __init__(
        self,
        ingredient_name: str,
        matches: List[str],
        match_count: Optional[int] = None
    ):
        """Initialize ambiguous ingredient error.
        
        Args:
            ingredient_name: The ambiguous ingredient name
            matches: List of matching food names/descriptions
            match_count: Total number of matches (may differ from len(matches))
        """
        count = match_count or len(matches)
        
        context = {
            "ingredient_name": ingredient_name,
            "matches": matches,
            "match_count": count
        }
        
        message = (
            f"Ambiguous ingredient '{ingredient_name}': "
            f"found {count} possible matches. "
            f"Please specify more precisely."
        )
        
        super().__init__(
            code=IngredientErrorCode.AMBIGUOUS_INGREDIENT,
            message=message,
            context=context
        )
        
        self.ingredient_name = ingredient_name
        self.matches = matches
        self.match_count = count


class UnitNotSupportedError(IngredientPipelineError):
    """Raised when a unit cannot be converted for the given ingredient.
    
    This error indicates that the specified unit is either:
    1. Not in the supported unit list at all
    2. A volume unit for an ingredient without density data
    3. A count unit without a known serving weight
    
    Context includes:
        - unit: The unsupported unit
        - ingredient_name: The ingredient being measured
        - supported_units: List of units that would work
    """
    
    def __init__(
        self,
        unit: str,
        ingredient_name: str,
        supported_units: List[str]
    ):
        """Initialize unsupported unit error.
        
        Args:
            unit: The unit that is not supported
            ingredient_name: The ingredient being measured
            supported_units: List of units that would be valid
        """
        context = {
            "unit": unit,
            "ingredient_name": ingredient_name,
            "supported_units": supported_units
        }
        
        units_str = ", ".join(supported_units) if supported_units else "none"
        message = (
            f"Unit '{unit}' is not supported for '{ingredient_name}'. "
            f"Supported units: {units_str}"
        )
        
        super().__init__(
            code=IngredientErrorCode.UNIT_NOT_SUPPORTED,
            message=message,
            context=context
        )
        
        self.unit = unit
        self.ingredient_name = ingredient_name
        self.supported_units = supported_units


class MissingNutritionDataError(IngredientPipelineError):
    """Raised when critical nutrition data is missing from USDA response.
    
    This error indicates that the USDA database entry lacks required
    nutrition fields (e.g., calories, protein). This can happen with
    experimental or incomplete database entries.
    
    Context includes:
        - ingredient_name: The ingredient with missing data
        - fdc_id: The USDA FoodData Central ID
        - missing_fields: List of fields that are missing
    """
    
    def __init__(
        self,
        ingredient_name: str,
        fdc_id: int,
        missing_fields: List[str]
    ):
        """Initialize missing nutrition data error.
        
        Args:
            ingredient_name: The ingredient name
            fdc_id: USDA FDC ID
            missing_fields: List of missing nutrition field names
        """
        context = {
            "ingredient_name": ingredient_name,
            "fdc_id": fdc_id,
            "missing_fields": missing_fields
        }
        
        fields_str = ", ".join(missing_fields)
        message = (
            f"Incomplete nutrition data for '{ingredient_name}' (FDC ID: {fdc_id}). "
            f"Missing required fields: {fields_str}"
        )
        
        super().__init__(
            code=IngredientErrorCode.MISSING_NUTRITION_DATA,
            message=message,
            context=context
        )
        
        self.ingredient_name = ingredient_name
        self.fdc_id = fdc_id
        self.missing_fields = missing_fields


class APIFailureError(IngredientPipelineError):
    """Raised when USDA API call fails.
    
    This error indicates a failure in the external API call, such as:
    - Network timeout
    - HTTP error (4xx, 5xx)
    - Rate limiting
    - Invalid API key
    
    Context includes:
        - operation: What operation was being performed
        - status_code: HTTP status code (if applicable)
        - response_body: Response body (if applicable)
        - ingredient_name: Ingredient being looked up
        - timeout: Whether this was a timeout
        - rate_limited: Whether rate limited
        - endpoint: API endpoint URL (if applicable)
    """
    
    def __init__(
        self,
        operation: str,
        status_code: Optional[int],
        response_body: Optional[str],
        ingredient_name: Optional[str] = None,
        timeout: bool = False,
        rate_limited: bool = False,
        endpoint: Optional[str] = None
    ):
        """Initialize API failure error.
        
        Args:
            operation: The operation that failed (search, get_food_details, etc.)
            status_code: HTTP status code (None for non-HTTP errors)
            response_body: Response body text
            ingredient_name: Ingredient being looked up
            timeout: Whether this was a timeout
            rate_limited: Whether rate limited (HTTP 429)
            endpoint: API endpoint URL
        """
        context: Dict[str, Any] = {
            "operation": operation,
        }
        
        if status_code is not None:
            context["status_code"] = status_code
        if response_body is not None:
            context["response_body"] = response_body
        if ingredient_name is not None:
            context["ingredient_name"] = ingredient_name
        if timeout:
            context["timeout"] = timeout
        if rate_limited:
            context["rate_limited"] = rate_limited
        if endpoint is not None:
            context["endpoint"] = endpoint
        
        # Build message based on failure type
        if timeout:
            message = f"USDA API timeout during {operation}"
        elif rate_limited:
            message = f"USDA API rate limit exceeded during {operation}"
        elif status_code:
            message = f"USDA API error during {operation}: HTTP {status_code}"
        else:
            message = f"USDA API failure during {operation}"
        
        if ingredient_name:
            message += f" (ingredient: {ingredient_name})"
        
        super().__init__(
            code=IngredientErrorCode.API_FAILURE,
            message=message,
            context=context
        )
        
        self.operation = operation
        self.status_code = status_code
        self.response_body = response_body
        self.ingredient_name = ingredient_name
        self.timeout = timeout
        self.rate_limited = rate_limited
        self.endpoint = endpoint


class ValidationFailureError(IngredientPipelineError):
    """Raised when ingredient input validation fails.
    
    This error indicates that the input data is invalid before any
    API calls are made. Examples:
    - Negative quantity
    - Empty ingredient name
    - Unparseable unit format
    
    Context includes:
        - field: Which field failed validation
        - value: The invalid value
        - reason: Why it failed
        - validation_errors: List of all validation errors (if multiple)
    """
    
    def __init__(
        self,
        field: str,
        value: Any,
        reason: str,
        validation_errors: Optional[List[Dict[str, str]]] = None
    ):
        """Initialize validation failure error.
        
        Args:
            field: The field that failed validation
            value: The invalid value
            reason: Why validation failed
            validation_errors: List of all validation errors (for batch validation)
        """
        context: Dict[str, Any] = {
            "field": field,
            "value": str(value) if value is not None else None,
            "reason": reason
        }
        
        if validation_errors:
            context["validation_errors"] = validation_errors
        
        message = f"Validation failed for '{field}': {reason}"
        if value is not None:
            message += f" (value: {value})"
        
        super().__init__(
            code=IngredientErrorCode.VALIDATION_FAILURE,
            message=message,
            context=context
        )
        
        self.field = field
        self.value = value
        self.reason = reason
        self.validation_errors = validation_errors


# Convenience function for creating errors from validation results
def validation_error_from_result(validation_result) -> ValidationFailureError:
    """Create ValidationFailureError from ValidationResult.
    
    Args:
        validation_result: ValidationResult with is_valid=False
        
    Returns:
        ValidationFailureError with all errors from result
    """
    if validation_result.is_valid:
        raise ValueError("Cannot create error from valid result")
    
    errors = validation_result.errors
    if not errors:
        return ValidationFailureError(
            field="unknown",
            value=None,
            reason="Unknown validation error"
        )
    
    # If single error, use it directly
    if len(errors) == 1:
        err = errors[0]
        return ValidationFailureError(
            field=err.field,
            value=err.value,
            reason=err.message
        )
    
    # Multiple errors
    validation_errors = [
        {"field": e.field, "message": e.message, "value": e.value}
        for e in errors
    ]
    
    return ValidationFailureError(
        field="multiple",
        value=None,
        reason=f"{len(errors)} validation errors",
        validation_errors=validation_errors
    )
