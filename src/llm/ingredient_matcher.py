from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from src.llm.client import LLMClient
from src.llm.schemas import (
    IngredientMatchResult,
    ValidationFailure,
    parse_llm_json,
)
from src.providers.ingredient_provider import IngredientDataProvider


INGREDIENT_MATCH_CONFIDENCE_THRESHOLD = 0.7


class IngredientMatchingError(Exception):
    """Deterministic error raised when ingredient matching fails."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}


def _clean_query(q: str) -> str:
    return str(q).strip()


def match_ingredient_queries(
    client: LLMClient, queries: List[str]
) -> List[IngredientMatchResult]:
    """Match raw ingredient strings to normalized ingredient names.

    Determinism:
    - ordering is preserved exactly as returned by the LLM
    - each parsed match is returned as a validated `IngredientMatchResult`
    """

    if not isinstance(queries, list) or len(queries) < 1:
        raise IngredientMatchingError(
            error_code="INVALID_QUERIES",
            message="queries must be a non-empty list.",
            details={"queries_type": str(type(queries))},
        )

    cleaned_queries: List[str] = []
    for idx, q in enumerate(queries):
        if not isinstance(q, str):
            raise IngredientMatchingError(
                error_code="INVALID_QUERIES",
                message="Each query must be a string.",
                details={"bad_index": idx, "bad_type": str(type(q))},
            )
        cleaned = _clean_query(q)
        if not cleaned:
            raise IngredientMatchingError(
                error_code="INVALID_QUERIES",
                message="Each query must be a non-empty string.",
                details={"bad_index": idx},
            )
        cleaned_queries.append(cleaned)

    system_prompt = (
        "You are a strict ingredient matcher. "
        "Return ONLY valid JSON. "
        "The top-level response MUST be a JSON object with exactly one key: "
        "`matches`. "
        "`matches` MUST be an array of objects whose length equals the number "
        "of input queries. "
        "The i-th element in `matches` MUST correspond to the i-th input query. "
        "Each match object MUST follow the IngredientMatchResult schema: "
        "{ query, normalized_name, confidence }. "
        "confidence must be a number between 0 and 1 inclusive. "
        "Do not include commentary."
    )

    # Stable representation for deterministic prompting.
    user_prompt = (
        "Input ingredient queries in order:\n"
        f"{json.dumps(cleaned_queries, ensure_ascii=True)}\n"
        "For each query, return its best normalized ingredient name and a confidence "
        "score between 0 and 1."
    )

    raw = client.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="IngredientMatchResult[]",
        temperature=0.0,
    )

    if not isinstance(raw, dict):
        raise IngredientMatchingError(
            error_code="LLM_RAW_NOT_DICT",
            message="LLM response was not a JSON object.",
        )

    allowed_keys = {"matches"}
    raw_keys = set(raw.keys())
    if raw_keys != allowed_keys:
        raise IngredientMatchingError(
            error_code="LLM_ENVELOPE_INVALID_KEYS",
            message="LLM response envelope keys were not exactly ['matches'].",
            details={"raw_keys": sorted(raw_keys)},
        )

    matches_raw: Any = raw.get("matches")
    if not isinstance(matches_raw, list):
        raise IngredientMatchingError(
            error_code="LLM_MATCHES_NOT_LIST",
            message="LLM response field `matches` was not a list.",
        )
    if len(matches_raw) != len(cleaned_queries):
        raise IngredientMatchingError(
            error_code="LLM_WRONG_MATCH_COUNT",
            message="LLM returned the wrong number of matches.",
            details={"expected": len(cleaned_queries), "received": len(matches_raw)},
        )

    parsed: List[IngredientMatchResult] = []
    for i, match_raw in enumerate(matches_raw):
        parsed_or_failure = parse_llm_json(IngredientMatchResult, match_raw)
        if isinstance(parsed_or_failure, ValidationFailure):
            raise IngredientMatchingError(
                error_code="LLM_MATCH_SCHEMA_VALIDATION_FAILED",
                message="A generated match failed strict schema validation.",
                details={
                    "match_index": i,
                    "validation_failure": parsed_or_failure.model_dump(),
                },
            )

        # Never trust the LLM's echo of the original query string.
        # We enforce ordering + map i-th match to i-th input query.
        parsed.append(
            parsed_or_failure.model_copy(update={"query": cleaned_queries[i]})
        )

    return parsed


def _extract_provider_resolution(
    *,
    provider: IngredientDataProvider,
    normalized_name: str,
) -> Optional[Dict[str, Any]]:
    """Resolve a candidate normalized name to a provider dict (or None).

    Some providers require resolve_all() before get_ingredient_info().
    This helper calls resolve_all([name]) deterministically per candidate.
    """

    try:
        provider.resolve_all([normalized_name])
    except Exception:
        return None

    try:
        return provider.get_ingredient_info(normalized_name)
    except Exception:
        return None


def validate_matches(
    matches: List[IngredientMatchResult],
    provider: IngredientDataProvider,
) -> Tuple[List[IngredientMatchResult], List[ValidationFailure]]:
    """Validate LLM matches using provider-backed existence checks.

    Returns:
    - accepted: validated matches (provider-resolved)
    - rejected: structured failures (including original_query in field_errors)
    """

    accepted: List[IngredientMatchResult] = []
    rejected: List[ValidationFailure] = []

    # Batch provider resolution to avoid one-by-one resolve_all() calls.
    names_to_resolve: Set[str] = set()
    normalized_by_match: List[Tuple[IngredientMatchResult, str]] = []
    for match in matches:
        original_query = str(match.query)
        normalized_name = str(match.normalized_name).strip()
        normalized_by_match.append((match, normalized_name))

        if not normalized_name:
            continue
        if match.confidence < INGREDIENT_MATCH_CONFIDENCE_THRESHOLD:
            continue
        # Candidate for provider resolution.
        names_to_resolve.add(normalized_name)

    resolved_info_by_name: Dict[str, Optional[Dict[str, Any]]] = {}
    if names_to_resolve:
        try:
            provider.resolve_all(sorted(names_to_resolve))
        except Exception:
            # Deterministic fallback: treat all as unresolved if provider prefetch fails.
            resolved_info_by_name = {n: None for n in names_to_resolve}
        else:
            for n in names_to_resolve:
                try:
                    resolved_info_by_name[n] = provider.get_ingredient_info(n)
                except Exception:
                    resolved_info_by_name[n] = None

    for match, normalized_name in normalized_by_match:
        original_query = str(match.query)

        if not normalized_name:
            rejected.append(
                ValidationFailure(
                    error_code="INVALID_MATCH_STRUCTURE",
                    message="normalized_name must be a non-empty string.",
                    field_errors=[f"original_query={original_query}"],
                )
            )
            continue

        if match.confidence < INGREDIENT_MATCH_CONFIDENCE_THRESHOLD:
            rejected.append(
                ValidationFailure(
                    error_code="LOW_CONFIDENCE_MATCH",
                    message=(
                        f"Low confidence match: confidence={match.confidence}. "
                        f"Threshold={INGREDIENT_MATCH_CONFIDENCE_THRESHOLD}."
                    ),
                    field_errors=[f"original_query={original_query}"],
                )
            )
            continue

        info = resolved_info_by_name.get(normalized_name)
        if info is None:
            rejected.append(
                ValidationFailure(
                    error_code="INGREDIENT_NOT_FOUND",
                    message=(
                        "Ingredient not found in provider for normalized_name="
                        f"{normalized_name!r}."
                    ),
                    field_errors=[f"original_query={original_query}"],
                )
            )
            continue

        canonical_name = None
        if isinstance(info, dict):
            name_val = info.get("name")
            if isinstance(name_val, str) and name_val.strip():
                canonical_name = name_val.strip()

        accepted.append(
            match.model_copy(
                update={
                    "canonical_name": canonical_name or normalized_name,
                    "validation_status": "ACCEPTED",
                }
            )
        )

    return accepted, rejected

