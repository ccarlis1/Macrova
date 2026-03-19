from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from src.ingestion.usda_client import DataType


# Keywords that strongly indicate the candidate is a compound/product dish
# (not a single canonical ingredient). Kept intentionally conservative.
_COMPOUND_PRODUCT_KEYWORDS: Sequence[str] = (
    # Common sandwich/bakery products
    "sandwich",
    "bagel",
    "burger",
    "wrap",
    "taco",
    "burrito",
    "pizza",
    # Prepared dishes / multi-ingredient meals
    "salad",
    "soup",
    "stew",
    "casserole",
    # Often product-form (not raw ingredient)
    "sauce",
    "dressing",
    "gravy",
    # Desserts / mixed dishes
    "pie",
    "cake",
    "cookie",
    "pudding",
    "dessert",
)


_RAW_LIKE_KEYWORDS: Sequence[str] = (
    "raw",
    "whole",
    "dry",
    "uncooked",
    "plain",
    "unflavored",
)


def _lower(s: Optional[str]) -> str:
    return (s or "").lower()


@dataclass(frozen=True)
class ScoreBreakdown:
    """Explainable breakdown for a single candidate ranking."""

    total_score: float
    data_type_priority: int
    exact_start_match: int
    comma_penalty: float
    description_length_penalty: float
    raw_like_reward: float
    reasons: List[str]


@dataclass(frozen=True)
class RankedCandidate:
    """Wrapper around a USDA food candidate with deterministic metadata."""

    fdc_id: Optional[int]
    description: str
    data_type: Optional[str]
    original_index: int
    score: ScoreBreakdown
    raw_candidate: Dict[str, Any]


@dataclass(frozen=True)
class RankedResult:
    """Final deterministic ranking output."""

    selected: RankedCandidate
    confidence: float
    margin: float
    # Full top-N (post-filter) for testability/debugging
    top_candidates: List[RankedCandidate]
    # Extra explainability at the selection level
    selection_reasons: List[str]


def filter_candidates(query: str, foods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministically filter out likely compound/product candidates.

    Note: this does not attempt semantic understanding; it relies on
    conservative string keyword checks.
    """
    q = _lower(query).strip()
    if not q:
        return foods

    out: List[Dict[str, Any]] = []
    for food in foods:
        desc = _lower(food.get("description"))
        # If the description contains the query but is clearly a dish/product,
        # remove it. This avoids selecting "egg salad" for "egg", etc.
        has_query = q in desc
        is_compound_product = any(kw in desc for kw in _COMPOUND_PRODUCT_KEYWORDS)
        if has_query and is_compound_product:
            continue
        out.append(food)
    return out


def score_candidate(query: str, candidate: Dict[str, Any], *, index: int) -> ScoreBreakdown:
    """Score a candidate with deterministic heuristics (lower = better)."""
    q = _lower(query).strip()
    desc = _lower(candidate.get("description"))

    # 1) Data type priority dominates (SR Legacy preferred).
    data_type_str = candidate.get("dataType")
    dt = DataType.from_string(data_type_str) if data_type_str else None
    data_type_priority = DataType.priority(dt) if dt else 999

    reasons: List[str] = []
    if dt:
        reasons.append(f"data_type_priority={data_type_priority}")
    else:
        reasons.append("data_type_priority=unknown")

    # 2) Prefer descriptions that start with the query token.
    exact_start_match = 0 if desc.startswith(q) else 1
    reasons.append(f"exact_start_match={exact_start_match}")

    # 3) Penalize comma-heavy / verbose descriptions.
    comma_count = desc.count(",")
    comma_penalty = float(comma_count) * 0.75
    if comma_count > 0:
        reasons.append(f"comma_count={comma_count}")

    # 4) Penalize excessive length (very verbose descriptions).
    description_length_penalty = max(0.0, (len(desc) - 20) * 0.03)
    if len(desc) > 20:
        reasons.append(f"description_length_penalty={description_length_penalty:.2f}")

    # 5) Reward raw-like signals for canonical ingredient forms.
    raw_like_reward = 0.0
    for kw in _RAW_LIKE_KEYWORDS:
        if kw in desc:
            raw_like_reward += 1.0
    if raw_like_reward > 0:
        reasons.append(f"raw_like_reward={raw_like_reward:.1f}")

    # Assemble total_score.
    # Keep weights simple and deterministic; data type should dominate.
    total_score = (
        data_type_priority * 1000.0
        + exact_start_match * 10.0
        + comma_penalty
        + description_length_penalty
        - raw_like_reward * 2.5
        + index * 0.0001  # deterministic tie-breaker
    )

    return ScoreBreakdown(
        total_score=total_score,
        data_type_priority=data_type_priority,
        exact_start_match=exact_start_match,
        comma_penalty=comma_penalty,
        description_length_penalty=description_length_penalty,
        raw_like_reward=raw_like_reward,
        reasons=reasons,
    )


def rank_candidates(query: str, foods: List[Dict[str, Any]]) -> RankedResult:
    """Filter + score + select the best candidate deterministically."""
    filtered = filter_candidates(query, foods)
    scored: List[RankedCandidate] = []
    for idx, food in enumerate(filtered):
        fdc_id = food.get("fdcId")
        if not isinstance(fdc_id, int):
            # Keep it optional; downstream uses fdc_id for details.
            fdc_id = None
        raw_description = food.get("description") or ""
        scored.append(
            RankedCandidate(
                fdc_id=fdc_id,
                # Preserve original casing for downstream cache/UI.
                description=raw_description,
                data_type=food.get("dataType"),
                original_index=idx,
                score=score_candidate(query, food, index=idx),
                raw_candidate=food,
            )
        )

    # Defensive: if filtering removed everything, fall back to original list.
    if not scored:
        for idx, food in enumerate(foods):
            fdc_id = food.get("fdcId")
            if not isinstance(fdc_id, int):
                fdc_id = None
            raw_description = food.get("description") or ""
            scored.append(
                RankedCandidate(
                    fdc_id=fdc_id,
                    description=raw_description,
                    data_type=food.get("dataType"),
                    original_index=idx,
                    score=score_candidate(query, food, index=idx),
                    raw_candidate=food,
                )
            )

    scored.sort(key=lambda rc: rc.score.total_score)
    selected = scored[0]
    top_candidates = scored[:8]

    # Confidence/margin based on top-2 score separation.
    if len(scored) >= 2:
        margin = abs(scored[1].score.total_score - selected.score.total_score)
    else:
        margin = float("inf")

    # Normalize margin into a [0, 1] confidence-like value.
    # 0 margin => 0.0 confidence, margin >= 50 => 1.0 confidence.
    if margin == float("inf"):
        confidence = 1.0
    else:
        confidence = max(0.0, min(1.0, margin / 50.0))

    selection_reasons = list(selected.score.reasons)
    selection_reasons.append(f"margin={margin:.2f}")
    selection_reasons.append(f"confidence={confidence:.2f}")

    return RankedResult(
        selected=selected,
        confidence=confidence,
        margin=margin,
        top_candidates=top_candidates,
        selection_reasons=selection_reasons,
    )

