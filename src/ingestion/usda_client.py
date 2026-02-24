"""USDA FoodData Central API client for ingredient lookup.

Step 2.1: Ingredient API Connection – Lookup Foundation.

This module provides deterministic ingredient lookup using the USDA FDC API.
It returns raw API data without normalization or scaling.

API Reference: https://fdc.nal.usda.gov/api-guide.html

DESIGN DECISIONS:
- Deterministic selection: SR Legacy > Foundation > Survey > Branded
- No fuzzy matching or AI logic
- Raw nutrients returned as-is (normalization is Step 2.4)
- Structured error handling (no silent failures)
"""

import os
import requests
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class DataType(Enum):
    """USDA food data types, ordered by preference for selection.
    
    Priority order for deterministic selection:
    1. SR Legacy - Standard Reference (most reliable for raw ingredients)
    2. Foundation - High-quality analytical data
    3. Survey (FNDDS) - Food survey data
    4. Branded - Commercial products (least preferred)
    """
    SR_LEGACY = "SR Legacy"
    FOUNDATION = "Foundation"
    SURVEY = "Survey (FNDDS)"
    BRANDED = "Branded"
    
    @classmethod
    def from_string(cls, data_type_str: str) -> Optional["DataType"]:
        """Convert API string to DataType enum.
        
        Args:
            data_type_str: Data type string from USDA API
            
        Returns:
            DataType enum or None if unknown
        """
        for dt in cls:
            if dt.value == data_type_str:
                return dt
        return None
    
    @classmethod
    def priority(cls, data_type: "DataType") -> int:
        """Get priority rank for data type (lower = better).
        
        Args:
            data_type: DataType enum value
            
        Returns:
            Priority rank (0 = best)
        """
        priority_order = [cls.SR_LEGACY, cls.FOUNDATION, cls.SURVEY, cls.BRANDED]
        try:
            return priority_order.index(data_type)
        except ValueError:
            return 999  # Unknown types ranked last


class USDALookupError(Exception):
    """Exception for USDA API errors.
    
    Used internally; callers receive structured USDALookupResult instead.
    """
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"{error_code}: {message}")


@dataclass
class USDALookupResult:
    """Result of USDA ingredient lookup.
    
    Contains either successful lookup data or structured error information.
    Raw nutrients and measures are returned as-is from the API.
    
    Attributes:
        success: Whether lookup succeeded
        fdc_id: USDA FoodData Central ID (None if failed)
        description: Food description from USDA (None if failed)
        data_type: Type of food data (SR Legacy, Foundation, etc.)
        raw_nutrients: Unmodified nutrient data from API
        raw_measures: Portion/measure data from API (if available)
        source_metadata: Additional metadata about the lookup
        error_code: Error code if lookup failed
        error_message: Human-readable error message if failed
    """
    success: bool
    fdc_id: Optional[int]
    description: Optional[str]
    data_type: Optional[DataType]
    raw_nutrients: List[Dict[str, Any]]
    raw_measures: List[Dict[str, Any]]
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    @classmethod
    def failure(cls, error_code: str, error_message: str, query: str = "") -> "USDALookupResult":
        """Create a failed lookup result.
        
        Args:
            error_code: Machine-readable error code
            error_message: Human-readable error message
            query: Original search query (for debugging)
            
        Returns:
            USDALookupResult with success=False
        """
        return cls(
            success=False,
            fdc_id=None,
            description=None,
            data_type=None,
            raw_nutrients=[],
            raw_measures=[],
            source_metadata={"query": query} if query else {},
            error_code=error_code,
            error_message=error_message
        )


@dataclass
class FoodDetailsResult:
    """Result of USDA food details retrieval (Step 2.3).
    
    Contains the raw USDA nutrition payload exactly as received from the API.
    No filtering, mapping, or normalization is applied at this stage.
    
    The raw_payload will be consumed by Step 2.4 (Nutrient Mapping) for
    conversion to internal data structures.
    
    Attributes:
        success: Whether retrieval succeeded
        fdc_id: USDA FoodData Central ID that was queried
        raw_payload: Complete raw JSON response from USDA API (unchanged)
        error_code: Error code if retrieval failed
        error_message: Human-readable error message if failed
    """
    success: bool
    fdc_id: int
    raw_payload: Dict[str, Any]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    @classmethod
    def failure(cls, fdc_id: int, error_code: str, error_message: str) -> "FoodDetailsResult":
        """Create a failed retrieval result.
        
        Args:
            fdc_id: The FDC ID that was queried
            error_code: Machine-readable error code
            error_message: Human-readable error message
            
        Returns:
            FoodDetailsResult with success=False
        """
        return cls(
            success=False,
            fdc_id=fdc_id,
            raw_payload={},
            error_code=error_code,
            error_message=error_message
        )


class USDAClient:
    """Client for USDA FoodData Central API.
    
    Provides deterministic ingredient lookup with structured results.
    
    Usage:
        client = USDAClient(api_key="your_key")
        # or
        client = USDAClient.from_env()  # reads USDA_API_KEY env var
        
        result = client.lookup("chicken breast")
        if result.success:
            print(f"Found: {result.description} (FDC ID: {result.fdc_id})")
        else:
            print(f"Error: {result.error_message}")
    """
    
    BASE_URL = "https://api.nal.usda.gov/fdc/v1"
    
    # Priority order for data type selection (lower index = higher priority)
    DATA_TYPE_PRIORITY = [
        DataType.SR_LEGACY,
        DataType.FOUNDATION, 
        DataType.SURVEY,
        DataType.BRANDED
    ]
    
    def __init__(self, api_key: str):
        """Initialize USDA client with API key.
        
        Args:
            api_key: USDA FoodData Central API key
            
        Raises:
            ValueError: If API key is empty
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key is required. Get one at https://fdc.nal.usda.gov/api-key-signup.html")
        self.api_key = api_key.strip()
    
    @classmethod
    def from_env(cls, env_var: str = "USDA_API_KEY") -> "USDAClient":
        """Create client from environment variable.
        
        Args:
            env_var: Name of environment variable containing API key
            
        Returns:
            USDAClient instance
            
        Raises:
            ValueError: If environment variable not set
        """
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(
                f"Environment variable {env_var} not set. "
                "Get an API key at https://fdc.nal.usda.gov/api-key-signup.html"
            )
        return cls(api_key=api_key)
    
    def lookup(self, ingredient_name: str, normalize: bool = True) -> USDALookupResult:
        """Look up an ingredient by name.
        
        Performs a search and selects the best matching food item
        using deterministic rules (no AI/fuzzy logic).
        
        Selection priority:
        1. Data type: SR Legacy > Foundation > Survey > Branded
        2. Within same data type: exact name match > first result
        
        Args:
            ingredient_name: Ingredient name to search for
            normalize: If True, lowercase the query for consistency (default True)
            
        Returns:
            USDALookupResult with food data or structured error
        """
        # Validate and normalize query
        query = ingredient_name.strip() if ingredient_name else ""
        if normalize:
            query = query.lower()
        if not query:
            return USDALookupResult.failure(
                error_code="INVALID_QUERY",
                error_message="Ingredient name cannot be empty",
                query=ingredient_name or ""
            )
        
        # Perform search
        try:
            search_results = self._make_request(query)
        except USDALookupError as e:
            return USDALookupResult.failure(
                error_code=e.error_code,
                error_message=e.message,
                query=query
            )
        
        # Check for empty results
        foods = search_results.get("foods", [])
        if not foods:
            return USDALookupResult.failure(
                error_code="NOT_FOUND",
                error_message=f"No results found for '{query}'",
                query=query
            )
        
        # Select best match using deterministic rules
        best_food = self._select_best_match(foods, query)
        
        # Extract data type
        data_type_str = best_food.get("dataType", "")
        data_type = DataType.from_string(data_type_str)
        
        # Build successful result with raw data
        return USDALookupResult(
            success=True,
            fdc_id=best_food.get("fdcId"),
            description=best_food.get("description"),
            data_type=data_type,
            raw_nutrients=best_food.get("foodNutrients", []),
            raw_measures=best_food.get("foodMeasures", []),
            source_metadata={
                "query": query,
                "total_hits": search_results.get("totalHits", 0),
                "data_type_raw": data_type_str,
            }
        )
    
    def _make_request(self, query: str) -> Dict[str, Any]:
        """Make API request to USDA search endpoint.
        
        Args:
            query: Search query string
            
        Returns:
            Parsed JSON response
            
        Raises:
            USDALookupError: If API request fails
        """
        url = f"{self.BASE_URL}/foods/search"
        params = {
            "api_key": self.api_key,
            "query": query,
            "pageSize": 25,  # Get enough results for good selection
            "dataType": "SR Legacy,Foundation,Survey (FNDDS),Branded"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            # Handle rate limiting
            if response.status_code == 429:
                raise USDALookupError(
                    "RATE_LIMITED",
                    "Too many requests. Please wait before trying again."
                )
            
            # Handle other HTTP errors
            if response.status_code != 200:
                raise USDALookupError(
                    "API_ERROR",
                    f"USDA API returned status {response.status_code}"
                )
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise USDALookupError("TIMEOUT", "USDA API request timed out")
        except requests.exceptions.ConnectionError:
            raise USDALookupError("CONNECTION_ERROR", "Failed to connect to USDA API")
        except requests.exceptions.RequestException as e:
            raise USDALookupError("API_ERROR", f"Request failed: {str(e)}")
    
    def _select_best_match(
        self, foods: List[Dict[str, Any]], query: str
    ) -> Dict[str, Any]:
        """Select best matching food using deterministic rules.
        
        Selection algorithm:
        1. Group foods by data type priority (SR Legacy first)
        2. Within each priority group, prefer exact description match
        3. If no exact match, take first result in highest priority group
        
        Args:
            foods: List of food items from API
            query: Original search query (for exact match comparison)
            
        Returns:
            Best matching food item
        """
        query_lower = query.lower()
        
        # Score each food by (priority, exact_match, position)
        # Lower score = better match
        def score_food(food: Dict[str, Any], index: int) -> tuple:
            data_type_str = food.get("dataType", "")
            data_type = DataType.from_string(data_type_str)
            
            # Priority based on data type (0 = best)
            priority = DataType.priority(data_type) if data_type else 999
            
            # Exact match bonus (0 = exact, 1 = not exact)
            description = food.get("description", "").lower()
            exact_match = 0 if query_lower in description or description in query_lower else 1
            
            # Shorter descriptions are often more canonical
            # e.g., "Chicken breast" vs "Chicken, breast, boneless, skinless, raw"
            desc_length = len(description)
            
            return (priority, exact_match, desc_length, index)
        
        # Sort by score (best first)
        scored_foods = [(score_food(f, i), f) for i, f in enumerate(foods)]
        scored_foods.sort(key=lambda x: x[0])
        
        return scored_foods[0][1]
    
    def lookup_validated(self, validated_ingredient) -> USDALookupResult:
        """Look up a validated ingredient using its canonical name.
        
        This is the recommended method for looking up ingredients that have
        already been validated by IngredientValidator.
        
        Per Step 2.1/2.2:
        - Uses canonical_name (pre-normalized) for API lookup
        - Returns structured result with raw API data
        
        Args:
            validated_ingredient: ValidatedIngredient with canonical_name field
            
        Returns:
            USDALookupResult with food data or structured error
            
        Note:
            For "to taste" ingredients, returns a structured failure since
            they should be excluded from nutrition calculations.
        """
        # "to taste" ingredients should not be looked up
        if validated_ingredient.is_to_taste:
            return USDALookupResult.failure(
                error_code="EXCLUDED",
                error_message="'To taste' ingredients are excluded from nutrition lookup",
                query=validated_ingredient.name
            )
        
        # Use canonical_name for lookup (already normalized)
        canonical_name = validated_ingredient.canonical_name
        if not canonical_name:
            # Fall back to original name if canonical_name not set
            canonical_name = validated_ingredient.name
        
        # Lookup with normalize=False since canonical_name is already normalized
        return self.lookup(canonical_name, normalize=False)
    
    def get_food_details(self, fdc_id: int) -> FoodDetailsResult:
        """Fetch raw nutrition data for a food by FDC ID (Step 2.3).
        
        Calls the USDA Food Details endpoint and returns the complete
        raw payload without any filtering, mapping, or normalization.
        
        The raw payload contains:
        - foodNutrients: Array of nutrient data with IDs, amounts, units
        - foodPortions: Serving size information (if available)
        - Metadata: description, dataType, publicationDate, etc.
        
        This raw data will be consumed by Step 2.4 (Nutrient Mapping)
        for conversion to internal NutritionProfile structures.
        
        Args:
            fdc_id: USDA FoodData Central ID (from lookup result)
            
        Returns:
            FoodDetailsResult with raw_payload or structured error
            
        Note:
            No normalization occurs at this stage to preserve the
            authoritative USDA data for accurate downstream processing.
        """
        # Validate fdc_id
        if fdc_id is None or fdc_id <= 0:
            return FoodDetailsResult.failure(
                fdc_id=fdc_id or 0,
                error_code="INVALID_FDC_ID",
                error_message=f"Invalid FDC ID: {fdc_id}. Must be a positive integer."
            )
        
        # Fetch raw data from API
        try:
            raw_payload = self._get_food_details_request(fdc_id)
        except USDALookupError as e:
            return FoodDetailsResult.failure(
                fdc_id=fdc_id,
                error_code=e.error_code,
                error_message=e.message
            )
        
        # Return raw payload unchanged
        return FoodDetailsResult(
            success=True,
            fdc_id=fdc_id,
            raw_payload=raw_payload,
            error_code=None,
            error_message=None
        )
    
    def _get_food_details_request(self, fdc_id: int) -> Dict[str, Any]:
        """Make API request to USDA Food Details endpoint.
        
        Args:
            fdc_id: USDA FoodData Central ID
            
        Returns:
            Raw JSON response from API
            
        Raises:
            USDALookupError: If API request fails
        """
        url = f"{self.BASE_URL}/food/{fdc_id}"
        params = {
            "api_key": self.api_key,
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            
            # Handle rate limiting
            if response.status_code == 429:
                raise USDALookupError(
                    "RATE_LIMITED",
                    "Too many requests. Please wait before trying again."
                )
            
            # Handle not found
            if response.status_code == 404:
                raise USDALookupError(
                    "NOT_FOUND",
                    f"Food with FDC ID {fdc_id} not found"
                )
            
            # Handle other HTTP errors
            if response.status_code != 200:
                raise USDALookupError(
                    "API_ERROR",
                    f"USDA API returned status {response.status_code}"
                )
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise USDALookupError("TIMEOUT", "USDA API request timed out")
        except requests.exceptions.ConnectionError:
            raise USDALookupError("CONNECTION_ERROR", "Failed to connect to USDA API")
        except requests.exceptions.RequestException as e:
            raise USDALookupError("API_ERROR", f"Request failed: {str(e)}")
