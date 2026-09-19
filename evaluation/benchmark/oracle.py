"""Independent spec-v3 feasibility oracle for benchmark scenarios.

Deliberately does NOT import ``src/``: it re-implements the spec's hard
constraints so benchmark labels are independent of the planner under test.

Semantics (docs/planner/mealplan-specification-v3.md):
- HC-1 exact normalized-name exclusion (spec) plus an "intent" variant that also
  matches the allergen/dislike class expansion supplied by the scenario.
- HC-2 same-day uniqueness; HC-3 busyness cook-time caps; HC-5 calorie ceiling;
  HC-6 pins; batch locks > pins; HC-8 consecutive-day non-workout repetition;
  HC-9 required tags on hard-eligible tags only (pinned/locked slots exempt).
- Daily windows: kcal/protein/carbs within +-10%, fat within [min, max].
- Horizon micronutrient floor: total >= tau * RDI * D for each tracked nutrient.
- ULs are NOT checked (not wired into plan_meals today; reconciliation B1/3.4).

The oracle is exhaustive (with explicit node caps). It reports how many valid
day-assignments exist, which lets scenarios be labelled borderline when feasible
plans are scarce, and the smallest widened tolerance at which an infeasible
instance becomes feasible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


COOK_CAP = {1: 5, 2: 15, 3: 30, 4: None}
DAY_SOLUTION_CAP = 60000
MULTIDAY_NODE_CAP = 3_000_000


def carbs_target(p: dict) -> float:
    fat_med = (p["daily_fat_g"]["min"] + p["daily_fat_g"]["max"]) / 2.0
    return (p["daily_calories"] - p["daily_protein_g"] * 4 - fat_med * 9) / 4.0


@dataclass
class DayResult:
    solutions: List[Tuple[str, ...]] = field(default_factory=list)
    count: int = 0
    combos: set = field(default_factory=set)
    capped: bool = False
    empty_slot: Optional[Tuple[int, str]] = None  # (slot_index, reason)


class Oracle:
    def __init__(self, library: List[dict], hard_tags, all_tags, aliases=None, known_slugs=None):
        self.aliases = dict(aliases or {})
        self.known = set(known_slugs or [])
        self.lib = {r["id"]: r for r in library}
        self.hard_tags = {r["id"]: hard_tags(r) for r in library}
        self.all_tags = {r["id"]: all_tags(r) for r in library}

    # ---------------------------------------------------------------- helpers
    def _excluded(self, rid: str, excluded: List[str]) -> bool:
        ex = {e.strip().lower() for e in excluded}
        return any(i["name"].strip().lower() in ex for i in self.lib[rid]["ingredients"])

    @staticmethod
    def _workout_slots(day: dict) -> set:
        out = set()
        for w in day.get("workouts", []) or []:
            a = w["after_meal_index"]
            out.add(a - 1)  # pre-workout (0-based)
            out.add(a)      # post-workout
        return out

    def _slot_filter(self, pool, slot, excluded, ceiling_ok=True):
        """Return (eligible_ids, reason_if_empty, pre_tag_count)."""
        cap = COOK_CAP[slot["busyness_level"]]
        base = [r for r in pool if not self._excluded(r, excluded)
                and (cap is None or self.lib[r]["cooking_time_minutes"] <= cap)]
        req = [self.aliases.get(t, t) for t in (slot.get("required_tag_slugs") or [])]
        tagged = [r for r in base if all(t in self.hard_tags[r] for t in req)]
        if not base:
            return tagged, "FM-1", 0
        if req and not tagged:
            return tagged, "FM-TAG-EMPTY", len(base)
        return tagged, None, len(base)

    # ---------------------------------------------------------------- per day
    def enumerate_day(self, pool, day, day_idx, pins, excluded, prof, tol=0.10,
                      want_solutions=True) -> DayResult:
        slots = day["meals"]
        n = len(slots)
        res = DayResult()
        elig: List[List[str]] = []
        for s_idx, slot in enumerate(slots):
            if (day_idx, s_idx) in pins:
                elig.append([pins[(day_idx, s_idx)]])
                continue
            e, reason, _ = self._slot_filter(pool, slot, excluded)
            if reason:
                res.empty_slot = (s_idx, reason)
                return res
            elig.append(e)

        kcal_t = prof["daily_calories"]
        p_t = prof["daily_protein_g"]
        c_t = carbs_target(prof)
        extra = tol - 0.10
        f_lo = prof["daily_fat_g"]["min"] * (1 - extra)
        f_hi = prof["daily_fat_g"]["max"] * (1 + extra)
        lo = (kcal_t * (1 - tol), p_t * (1 - tol), c_t * (1 - tol), f_lo)
        hi = [kcal_t * (1 + tol), p_t * (1 + tol), c_t * (1 + tol), f_hi]
        ceiling = prof.get("max_daily_calories")
        if ceiling is not None:
            hi[0] = min(hi[0], ceiling)
        hi = tuple(hi)

        def vec(rid):
            nu = self.lib[rid]["nutrition"]
            return (nu["calories"], nu["protein_g"], nu["carbs_g"], nu["fat_g"])

        vecs = [[vec(r) for r in e] for e in elig]
        suffix_min = [(0.0,) * 4 for _ in range(n + 1)]
        suffix_max = [(0.0,) * 4 for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            mn = tuple(min(v[k] for v in vecs[i]) for k in range(4))
            mx = tuple(max(v[k] for v in vecs[i]) for k in range(4))
            suffix_min[i] = tuple(a + b for a, b in zip(suffix_min[i + 1], mn))
            suffix_max[i] = tuple(a + b for a, b in zip(suffix_max[i + 1], mx))

        chosen: List[str] = []
        l0, l1, l2, l3 = lo
        h0, h1, h2, h3 = hi

        def rec(i, a0, a1, a2, a3):
            if i == n - 1:
                for rid, v in zip(elig[i], vecs[i]):
                    t0 = a0 + v[0]
                    if t0 < l0 or t0 > h0:
                        continue
                    t1 = a1 + v[1]
                    if t1 < l1 or t1 > h1:
                        continue
                    t2 = a2 + v[2]
                    if t2 < l2 or t2 > h2:
                        continue
                    t3 = a3 + v[3]
                    if t3 < l3 or t3 > h3:
                        continue
                    if rid in chosen:
                        continue
                    res.count += 1
                    res.combos.add(frozenset(chosen + [rid]))
                    if want_solutions:
                        res.solutions.append(tuple(chosen + [rid]))
                    if res.count >= DAY_SOLUTION_CAP:
                        res.capped = True
                        return
                return
            smn = suffix_min[i + 1]
            smx = suffix_max[i + 1]
            for rid, v in zip(elig[i], vecs[i]):
                if rid in chosen:
                    continue
                b0 = a0 + v[0]
                if b0 + smn[0] > h0 or b0 + smx[0] < l0:
                    continue
                b1 = a1 + v[1]
                if b1 + smn[1] > h1 or b1 + smx[1] < l1:
                    continue
                b2 = a2 + v[2]
                if b2 + smn[2] > h2 or b2 + smx[2] < l2:
                    continue
                b3 = a3 + v[3]
                if b3 + smn[3] > h3 or b3 + smx[3] < l3:
                    continue
                chosen.append(rid)
                rec(i + 1, b0, b1, b2, b3)
                chosen.pop()
                if res.capped:
                    return

        rec(0, 0.0, 0.0, 0.0, 0.0)
        return res

    # ---------------------------------------------------------------- scenario
    def evaluate(self, sc: dict, excluded_key="excluded_ingredients") -> dict:
        prof = sc["profile"]
        pool = list(sc["recipe_pool"]["recipe_ids"])
        days = sc["schedule_days"]
        D = len(days)
        excluded = list(prof.get(excluded_key) or [])
        out: dict = {"stage": None, "failure_code": None, "details": {}}

        # ---- 0. request validation: unknown tag slugs are rejected by MealSlot ----
        for d, day in enumerate(days):
            for s_idx, slot in enumerate(day["meals"]):
                for field_name in ("required_tag_slugs", "preferred_tag_slugs"):
                    for t in slot.get(field_name) or []:
                        if self.known and self.aliases.get(t, t) not in self.known:
                            out.update(stage="input_validation", failure_code="INVALID_REQUEST",
                                       details={"day_index": d, "slot_index": s_idx, "field": field_name,
                                                "unknown_slug": t})
                            return out

        # ---- 1. batch-lock normalization (FM-BATCH-CONFLICT) ----
        pins: Dict[Tuple[int, int], str] = {(p["day_index"], p["slot_index"]): p["recipe_id"] for p in sc.get("pins", [])}
        locks: Dict[Tuple[int, int], Tuple[str, str]] = {}
        for b in sorted(sc.get("meal_prep_batches", []), key=lambda b: b["id"]):
            if len(b["assignments"]) > b["total_servings"] or b["total_servings"] < 2 or \
                    sum(a.get("servings", 1) for a in b["assignments"]) > b["total_servings"]:
                out.update(stage="input_validation", failure_code="BATCH_REJECTED",
                           details={"batch_id": b["id"], "reason": "servings/assignments invalid at batch creation"})
                return out
            for a in b["assignments"]:
                addr = (a["day_index"], a["slot_index"])
                if addr in locks and locks[addr][1] != b["recipe_id"]:
                    out.update(stage="pre_search", failure_code="FM-BATCH-CONFLICT",
                               details={"slot_address": list(addr), "batches": [locks[addr][0], b["id"]]})
                    return out
                locks[addr] = (b["id"], b["recipe_id"])
        overridden_pins = [list(k) for k in pins if k in locks and pins[k] != locks[k][1]]
        for addr, (_, rid) in locks.items():
            pins[addr] = rid
        out["details"]["pins_overridden_by_locks"] = overridden_pins

        # ---- 2. pinned pre-validation (FM-3) ----
        for (d, s), rid in sorted(pins.items()):
            if d >= D or s >= len(days[d]["meals"]):
                out.update(stage="pre_search", failure_code="FM-3", details={"pin": [d, s, rid], "violation": "slot-out-of-range"})
                return out
            if rid not in self.lib or rid not in pool:
                out.update(stage="pre_search", failure_code="FM-3", details={"pin": [d, s, rid], "violation": "recipe-not-in-pool"})
                return out
            if self._excluded(rid, excluded):
                out.update(stage="pre_search", failure_code="FM-3", details={"pin": [d, s, rid], "violation": "HC-1"})
                return out
            cap = COOK_CAP[days[d]["meals"][s]["busyness_level"]]
            if cap is not None and self.lib[rid]["cooking_time_minutes"] > cap:
                out.update(stage="pre_search", failure_code="FM-3", details={"pin": [d, s, rid], "violation": "HC-3",
                           "cook_minutes": self.lib[rid]["cooking_time_minutes"], "slot_cap": cap})
                return out
            ceil = prof.get("max_daily_calories")
            if ceil is not None and self.lib[rid]["nutrition"]["calories"] > ceil:
                out.update(stage="pre_search", failure_code="FM-3", details={"pin": [d, s, rid], "violation": "HC-5"})
                return out
        by_day: Dict[int, List[str]] = {}
        for (d, s), rid in pins.items():
            if rid in by_day.setdefault(d, []):
                out.update(stage="pre_search", failure_code="FM-3", details={"day": d, "recipe": rid, "violation": "HC-2"})
                return out
            by_day[d].append(rid)
        wslots = [self._workout_slots(day) for day in days]
        for (d, s), rid in pins.items():
            if s in wslots[d]:
                continue
            for (d2, s2), rid2 in pins.items():
                if d2 == d + 1 and rid2 == rid and s2 not in wslots[d2]:
                    out.update(stage="pre_search", failure_code="FM-3",
                               details={"pins": [[d, s], [d2, s2]], "recipe": rid, "violation": "HC-8"})
                    return out

        # ---- 3. per-day enumeration ----
        day_results: List[DayResult] = []
        sig_cache: Dict[str, DayResult] = {}
        for d, day in enumerate(days):
            day_pins = {k: v for k, v in pins.items() if k[0] == d}
            sig = repr((day["meals"], sorted((k[1], v) for k, v in day_pins.items())))
            if sig not in sig_cache:
                sig_cache[sig] = self.enumerate_day(pool, day, d, pins, excluded, prof)
            r = sig_cache[sig]
            day_results.append(r)
            if r.empty_slot:
                out.update(stage="candidate_generation", failure_code=r.empty_slot[1],
                           details={**out["details"], "day_index": d, "slot_index": r.empty_slot[0]})
                return out
        out["details"]["valid_assignments_per_day"] = [r.count for r in day_results]
        out["details"]["distinct_meal_sets_per_day"] = [len(r.combos) for r in day_results]
        out["details"]["day_enumeration_capped"] = [r.capped for r in day_results]

        zero_days = [d for d, r in enumerate(day_results) if r.count == 0]
        if zero_days:
            # Distinguish pin-caused (FM-3 downstream) from intrinsic (FM-2).
            code = "FM-2"
            if pins:
                d0 = zero_days[0]
                unpinned = self.enumerate_day(pool, days[d0], d0, {}, excluded, prof, want_solutions=False)
                if unpinned.count > 0:
                    code = "FM-3"
            out.update(stage="search", failure_code=code)
            out["details"]["infeasible_days"] = zero_days
            out["details"]["min_tolerance_for_feasibility"] = self._min_tol(pool, days, zero_days[0], pins, excluded, prof)
            return out

        # ---- 4. multi-day search: HC-8 + horizon micronutrient floors ----
        tracked = dict(prof.get("micronutrient_targets") or {})
        tau = float(prof.get("micronutrient_weekly_min_fraction", 1.0))
        found, nodes, inconclusive, best_micro = self._multiday(days, day_results, wslots, tracked, tau)
        out["details"]["multiday_nodes"] = nodes
        if found is not None:
            out.update(stage="complete", failure_code=None)
            out["details"]["witness_plan"] = [list(x) for x in found]
            return out
        if inconclusive:
            out.update(stage="search", failure_code="ORACLE_INCONCLUSIVE")
            return out
        if tracked and best_micro is not None:
            out.update(stage="search", failure_code="FM-4")
            out["details"]["micronutrient_shortfall"] = best_micro
        else:
            out.update(stage="search", failure_code="FM-1" if D > 1 else "FM-2")
            out["details"]["reason"] = "HC-8 consecutive-day repetition leaves no valid day sequence"
        return out

    def _multiday(self, days, day_results, wslots, tracked, tau):
        D = len(days)
        nut = list(tracked)
        floors = [tau * tracked[k] * D for k in nut]

        def micro(sol):
            return tuple(sum(self.lib[r]["nutrition"]["micronutrients"].get(k, 0.0) for r in sol) for k in nut)

        def add(a, b):
            return tuple(x + y for x, y in zip(a, b))

        zero = tuple(0.0 for _ in nut)
        sols = []
        maxes = []
        for r in day_results:
            if nut:
                ms = [micro(s) for s in r.solutions]
                daily = [max(f / D, 1e-9) for f in floors]
                order = sorted(range(len(ms)), key=lambda i: -sum(m / d for m, d in zip(ms[i], daily)))
                sols.append([(r.solutions[i], ms[i]) for i in order])
                maxes.append(tuple(max(m[k] for m in ms) for k in range(len(nut))))
            else:
                sols.append([(s, zero) for s in r.solutions])
        suffix_max = [zero for _ in range(D + 1)]
        if nut:
            for d in range(D - 1, -1, -1):
                suffix_max[d] = add(suffix_max[d + 1], maxes[d])
            short = {k: {"best_achievable": round(suffix_max[0][i], 2), "min_req": round(floors[i], 2)}
                     for i, k in enumerate(nut) if suffix_max[0][i] < floors[i] - 1e-9}
            if short:
                return None, 0, False, short

        nodes = 0
        plan: List[Tuple[str, ...]] = []
        capped_any = any(r.capped for r in day_results)

        def nonworkout(d, sol):
            return {rid for s, rid in enumerate(sol) if s not in wslots[d]}

        def rec(d, acc):
            nonlocal nodes
            if d == D:
                return all(a >= f - 1e-9 for a, f in zip(acc, floors))
            prev_nw = nonworkout(d - 1, plan[-1]) if d > 0 else set()
            for sol, m in sols[d]:
                nodes += 1
                if nodes > MULTIDAY_NODE_CAP:
                    return False
                if prev_nw and (nonworkout(d, sol) & prev_nw):
                    continue
                a = add(acc, m)
                if nut and any(x + y < f - 1e-9 for x, y, f in zip(a, suffix_max[d + 1], floors)):
                    continue
                plan.append(sol)
                if rec(d + 1, a):
                    return True
                plan.pop()
                if nodes > MULTIDAY_NODE_CAP:
                    return False
            return False

        ok = rec(0, zero)
        if ok:
            return list(plan), nodes, False, None
        inconclusive = nodes > MULTIDAY_NODE_CAP or capped_any
        best = None
        if nut:
            best = {k: {"per_day_max_sum_bound": round(suffix_max[0][i], 2), "min_req": round(floors[i], 2)}
                    for i, k in enumerate(nut)}
        return None, nodes, inconclusive, best

    def _min_tol(self, pool, days, d, pins, excluded, prof):
        for tol in (0.12, 0.15, 0.20, 0.30):
            r = self.enumerate_day(pool, days[d], d, pins, excluded, prof, tol=tol, want_solutions=False)
            if r.count > 0:
                return tol
        return None
