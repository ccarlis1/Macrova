"""Ingredient name normalization for USDA API lookup.

Step 2.1: Ingredient Name Normalization.

This module prepares parsed ingredient names for reliable API lookup by:
- Converting to lowercase
- Trimming and normalizing whitespace
- Removing controlled descriptors (size, preparation, quality modifiers)

The goal is to produce a deterministic canonical name suitable for API search.

DESIGN DECISIONS:
- Descriptors are removed as whole words only (not substrings)
- Multi-word descriptors (e.g., "extra large") are handled before single-word
- Comma-separated formats are supported
- Original name is preserved for reference
"""

import re
from dataclasses import dataclass, field
from typing import List, Set


# Controlled descriptors to remove from ingredient names.
# These are modifiers that don't affect the core ingredient identity for API lookup.
# Organized by category for maintainability.

SIZE_DESCRIPTORS = {
    "small", "medium", "large", "extra large", "jumbo",
    "mini", "tiny", "xl", "xs",
}

PREPARATION_DESCRIPTORS = {
    "raw", "cooked", "uncooked",
    "fresh", "frozen", "canned", "dried",
    "roasted", "grilled", "baked", "fried", "steamed", "boiled",
    "smoked", "cured",
}

CUT_DESCRIPTORS = {
    "boneless", "skinless", "bone-in", "skin-on",
    "diced", "sliced", "chopped", "minced", "shredded", "cubed",
    "whole", "halved", "quartered",
    "fillet", "filet", "steak", "ground",
}

QUALITY_DESCRIPTORS = {
    "organic", "conventional",
    "grass-fed", "pasture-raised", "free-range", "cage-free",
    "wild-caught", "farm-raised",
    "lean", "extra lean",
}

# Combined set of all controlled descriptors
CONTROLLED_DESCRIPTORS: Set[str] = (
    SIZE_DESCRIPTORS |
    PREPARATION_DESCRIPTORS |
    CUT_DESCRIPTORS |
    QUALITY_DESCRIPTORS
)


@dataclass
class NormalizationResult:
    """Result of ingredient name normalization.
    
    Attributes:
        original_name: The original input name (unmodified)
        canonical_name: Normalized name for API lookup
        removed_descriptors: List of descriptors that were removed
    """
    original_name: str
    canonical_name: str
    removed_descriptors: List[str] = field(default_factory=list)


class IngredientNormalizer:
    """Normalizes ingredient names for reliable USDA API lookup.
    
    Normalization steps:
    1. Preserve original name
    2. Convert to lowercase
    3. Normalize whitespace and punctuation
    4. Remove controlled descriptors
    5. Return canonical name suitable for API search
    
    Usage:
        normalizer = IngredientNormalizer()
        result = normalizer.normalize("Large Boneless Chicken Breast")
        print(result.canonical_name)  # "chicken breast"
        print(result.removed_descriptors)  # ["large", "boneless"]
    """
    
    def __init__(self, additional_descriptors: Set[str] = None):
        """Initialize normalizer with optional additional descriptors.
        
        Args:
            additional_descriptors: Extra descriptors to remove (optional)
        """
        self.descriptors = CONTROLLED_DESCRIPTORS.copy()
        if additional_descriptors:
            self.descriptors.update(additional_descriptors)
        
        # Sort descriptors by length (longest first) to handle multi-word first
        # e.g., "extra large" before "large", "extra lean" before "lean"
        self._sorted_descriptors = sorted(
            self.descriptors,
            key=lambda x: (-len(x), x)  # Longest first, then alphabetical
        )
    
    def normalize(self, ingredient_name: str) -> NormalizationResult:
        """Normalize an ingredient name for API lookup.
        
        Args:
            ingredient_name: Raw ingredient name from recipe
            
        Returns:
            NormalizationResult with canonical name and removed descriptors
        """
        original = ingredient_name
        removed = []
        
        # Handle empty input
        if not ingredient_name or not ingredient_name.strip():
            return NormalizationResult(
                original_name=original,
                canonical_name="",
                removed_descriptors=[]
            )
        
        # Step 1: Lowercase
        name = ingredient_name.lower()
        
        # Step 2: Normalize punctuation - replace commas with spaces
        name = name.replace(",", " ")
        
        # Step 3: Normalize whitespace - collapse multiple spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Step 4: Remove controlled descriptors
        # Process multi-word descriptors first (they're sorted by length)
        for descriptor in self._sorted_descriptors:
            # Match descriptor as whole word(s), not as substring
            # Use word boundaries to avoid matching "raw" in "strawberry"
            pattern = r'\b' + re.escape(descriptor) + r'\b'
            if re.search(pattern, name):
                name = re.sub(pattern, '', name)
                removed.append(descriptor)
        
        # Step 5: Final cleanup - collapse any resulting multiple spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        return NormalizationResult(
            original_name=original,
            canonical_name=name,
            removed_descriptors=removed
        )
    
    def get_canonical_name(self, ingredient_name: str) -> str:
        """Get just the canonical name (convenience method).
        
        Args:
            ingredient_name: Raw ingredient name
            
        Returns:
            Canonical name string
        """
        return self.normalize(ingredient_name).canonical_name
