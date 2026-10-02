"""Allergen class table: expand allergy terms to canonical ingredient names.

HC-1 is a safety guarantee for allergies (reconciliation Q10 / C6). Dislikes stay
exact. Matching itself remains exact-name after this expansion.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

DEFAULT_ALLERGEN_CLASSES_PATH = "data/reference/allergen_classes.json"


def _normalize_name(name: str) -> str:
    return str(name).lower().strip()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@lru_cache(maxsize=4)
def load_allergen_classes(path: Optional[str] = None) -> Dict[str, object]:
    """Load allergen class table. Fail fast on malformed data.

    Returns a dict with:
      - term_to_class: normalized term -> class id
      - class_members: class id -> frozenset of normalized member names
      - classified: frozenset of all classified ingredient names
      - class_ids: tuple of class ids (stable order)
    """
    raw_path = Path(path or DEFAULT_ALLERGEN_CLASSES_PATH)
    if not raw_path.is_absolute():
        raw_path = _project_root() / raw_path
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("allergen_classes.json must be a JSON object")
    classes = data.get("classes")
    if not isinstance(classes, dict) or not classes:
        raise ValueError("allergen_classes.json must contain a non-empty 'classes' object")
    no_major = data.get("no_major_allergen", [])
    if not isinstance(no_major, list) or not all(isinstance(x, str) for x in no_major):
        raise ValueError("no_major_allergen must be a list of strings")

    term_to_class: Dict[str, str] = {}
    class_members: Dict[str, frozenset] = {}
    classified: Set[str] = set()

    for class_id, entry in classes.items():
        if not isinstance(class_id, str) or not isinstance(entry, dict):
            raise ValueError(f"class {class_id!r} must map to an object")
        terms = entry.get("terms", [])
        members = entry.get("members", [])
        if not isinstance(terms, list) or not all(isinstance(x, str) for x in terms):
            raise ValueError(f"class {class_id!r} terms must be a list of strings")
        if not isinstance(members, list) or not all(isinstance(x, str) for x in members):
            raise ValueError(f"class {class_id!r} members must be a list of strings")
        member_norm = frozenset(_normalize_name(m) for m in members if _normalize_name(m))
        class_members[class_id] = member_norm
        classified.update(member_norm)
        for term in terms:
            t = _normalize_name(term)
            if not t:
                continue
            if t in term_to_class and term_to_class[t] != class_id:
                raise ValueError(
                    f"term {t!r} maps to both {term_to_class[t]!r} and {class_id!r}"
                )
            term_to_class[t] = class_id

    for name in no_major:
        n = _normalize_name(name)
        if n:
            classified.add(n)

    return {
        "term_to_class": term_to_class,
        "class_members": class_members,
        "classified": frozenset(classified),
        "class_ids": tuple(sorted(class_members.keys())),
    }


def clear_allergen_cache() -> None:
    """Test helper: drop the cached table."""
    load_allergen_classes.cache_clear()


def is_classified(name: str, *, path: Optional[str] = None) -> bool:
    """True if the ingredient name appears in a class members list or no_major_allergen."""
    table = load_allergen_classes(path)
    return _normalize_name(name) in table["classified"]  # type: ignore[operator]


def expand_allergy_terms(
    terms: Sequence[str],
    *,
    path: Optional[str] = None,
) -> List[str]:
    """Expand allergy terms to class members plus the original terms.

    Deterministic: sorted, deduplicated, normalized. Terms that match no class
    are kept as-is so exact HC-1 matching still applies.
    """
    table = load_allergen_classes(path)
    term_to_class: Dict[str, str] = table["term_to_class"]  # type: ignore[assignment]
    class_members: Dict[str, frozenset] = table["class_members"]  # type: ignore[assignment]
    out: Set[str] = set()
    for raw in terms:
        term = _normalize_name(raw)
        if not term:
            continue
        out.add(term)
        class_id = term_to_class.get(term)
        if class_id is not None:
            out.update(class_members.get(class_id, frozenset()))
    return sorted(out)


def unmatched_exclusion_terms(
    allergies: Sequence[str],
    dislikes: Sequence[str],
    pool_ingredient_names: Iterable[str],
    *,
    path: Optional[str] = None,
) -> List[str]:
    """Return allergy/dislike terms that match no class term and no pool ingredient.

    Order is stable: allergies first (input order), then dislikes (input order),
    deduplicated.
    """
    table = load_allergen_classes(path)
    term_to_class: Dict[str, str] = table["term_to_class"]  # type: ignore[assignment]
    pool = {_normalize_name(n) for n in pool_ingredient_names if _normalize_name(n)}
    seen: Set[str] = set()
    unmatched: List[str] = []
    for raw in list(allergies) + list(dislikes):
        term = _normalize_name(raw)
        if not term or term in seen:
            continue
        seen.add(term)
        if term in term_to_class or term in pool:
            continue
        unmatched.append(term)
    return unmatched


def unclassified_pool_ingredients(
    pool_ingredient_names: Iterable[str],
    *,
    path: Optional[str] = None,
) -> List[str]:
    """Sorted unique pool ingredient names missing from the class table."""
    table = load_allergen_classes(path)
    classified: frozenset = table["classified"]  # type: ignore[assignment]
    missing = {
        _normalize_name(n)
        for n in pool_ingredient_names
        if _normalize_name(n) and _normalize_name(n) not in classified
    }
    return sorted(missing)


def exclusion_warning_messages(
    allergies: Sequence[str],
    dislikes: Sequence[str],
    pool_ingredient_names: Iterable[str],
    *,
    path: Optional[str] = None,
) -> List[str]:
    """Human-readable exclusion warnings for the plan response."""
    pool_list = list(pool_ingredient_names)
    messages: List[str] = []
    unmatched = unmatched_exclusion_terms(
        allergies, dislikes, pool_list, path=path
    )
    for term in unmatched:
        messages.append(
            f"Exclusion term {term!r} matched no allergen class and no ingredient in the recipe pool."
        )
    if any(_normalize_name(a) for a in allergies):
        missing = unclassified_pool_ingredients(pool_list, path=path)
        for name in missing:
            messages.append(
                f"Pool ingredient {name!r} is not classified in the allergen table; "
                "allergy safety coverage is incomplete for this ingredient."
            )
    return messages
