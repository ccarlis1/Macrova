"""Phase 5: Heuristic ordering (tie-breaking cascade). Spec Section 7.1.

Orders already-scored candidates when composite scores are equal.
No scoring, no constraints, no feasibility, no state mutation.
Reference: MEALPLAN_SPECIFICATION_v1.md Section 7.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from src.planning.phase0_models import (
    DailyTracker,
    PlanningUserProfile,
    WeeklyTracker,
    micronutrient_profile_to_dict,
)
from src.planning.phase1_state import adjusted_daily_target


# --- State view (read-only) ---


@dataclass(frozen=True)
class OrderingStateView:
    """Read-only state for tie-breaking. Spec Section 3."""

    daily_trackers: Dict[int, DailyTracker]
    weekly_tracker: WeeklyTracker


def get_daily_tracker(state: OrderingStateView, day_index: int) -> Optional[DailyTracker]:
    return state.daily_trackers.get(day_index)


# --- Recipe-like protocol ---


class RecipeLike(Protocol):
    id: str
    ingredients: List[Any]
    nutrition: Any


def _normalize(s: str) -> str:
    return s.strip().lower()


# --- Tie-break rule 1: Micronutrient gap-fill coverage ---


def _nutrients_still_needed(
    state: OrderingStateView,
    profile: PlanningUserProfile,
    day_index: int,
) -> Dict[str, float]:
    """Currently deficient nutrients and their remaining gaps (read-only)."""
    tracked = profile.micronutrient_targets
    if not tracked:
        return {}
    w = state.weekly_tracker
    days_left = w.days_remaining
    if days_left <= 0:
        days_left = 1
    carryover = w.carryover_needs
    tracker = get_daily_tracker(state, day_index)
    consumed = tracker.micronutrients_consumed if tracker else {}
    out: Dict[str, float] = {}
    for n, base_target in tracked.items():
        if base_target <= 0:
            continue
        adj = adjusted_daily_target(base_target, carryover.get(n, 0.0), days_left)
        cur = consumed.get(n, 0.0)
        if cur < adj:
            out[n] = adj - cur
    return out


def gap_fill_count(
    recipe: RecipeLike,
    state: OrderingStateView,
    profile: PlanningUserProfile,
    day_index: int,
) -> int:
    """Rule 1: Count of currently-deficient nutrients that recipe provides non-zero. Spec 7.1."""
    gaps = _nutrients_still_needed(state, profile, day_index)
    if not gaps:
        return 0
    micro = getattr(recipe.nutrition, "micronutrients", None)
    if micro is None:
        return 0
    d = micronutrient_profile_to_dict(micro)
    return sum(1 for n in gaps if d.get(n, 0.0) > 0)


# --- Tie-break rule 2: Total deficit reduction ---


def deficit_reduction(
    recipe: RecipeLike,
    state: OrderingStateView,
    profile: PlanningUserProfile,
    day_index: int,
) -> float:
    """Rule 2: Sum of (contribution as fraction of gap), capped at 1 per nutrient. Spec 7.1."""
    gaps = _nutrients_still_needed(state, profile, day_index)
    if not gaps:
        return 0.0
    micro = getattr(recipe.nutrition, "micronutrients", None)
    if micro is None:
        return 0.0
    d = micronutrient_profile_to_dict(micro)
    total = 0.0
    for n, gap in gaps.items():
        if gap <= 0:
            continue
        amount = d.get(n, 0.0)
        if amount <= 0:
            continue
        total += min(1.0, amount / gap)
    return total


# --- Tie-break rule 3: Liked foods matches ---


def liked_foods_count(recipe: RecipeLike, profile: PlanningUserProfile) -> int:
    """Rule 3: Count of recipe ingredients matching user_profile.liked_foods (case-insensitive). Spec 7.1."""
    liked = profile.liked_foods
    if not liked:
        return 0
    liked_norm = {_normalize(x) for x in liked}
    count = 0
    for ing in recipe.ingredients:
        name = getattr(ing, "name", str(ing))
        if _normalize(name) in liked_norm:
            count += 1
    return count


# --- Sort key for (candidate, score) ---


def ordering_key(
    item: Tuple[RecipeLike, float],
    state: OrderingStateView,
    profile: PlanningUserProfile,
    day_index: int,
) -> Tuple[float, int, float, int, str]:
    """Key for stable sort: primary score descending, then cascade. Spec 7.1.

    Returns (neg_score, neg_gap_fill, neg_deficit_red, neg_liked, id) so that
    ascending sort gives: highest score first, then more gap-fill, then more deficit reduction,
    then more liked, then lexicographically smaller id.
    """
    recipe, score = item
    gap = gap_fill_count(recipe, state, profile, day_index)
    def_red = deficit_reduction(recipe, state, profile, day_index)
    liked = liked_foods_count(recipe, profile)
    return (-float(score), -gap, -def_red, -liked, recipe.id)


# --- Public API: order scored candidates ---


def order_scored_candidates(
    scored_candidates: List[Tuple[RecipeLike, float]],
    state: OrderingStateView,
    profile: PlanningUserProfile,
    day_index: int,
) -> List[Tuple[RecipeLike, float]]:
    """Return a fully ordered list: by composite score descending, then by tie-break cascade. Spec 7.1.

    Does not mutate state. Deterministic. No scoring, constraint, or feasibility logic.
    """
    return sorted(
        scored_candidates,
        key=lambda item: ordering_key(item, state, profile, day_index),
    )
