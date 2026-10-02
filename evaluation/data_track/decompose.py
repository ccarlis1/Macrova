#!/usr/bin/env python3
"""E1 — decompose nutrition error into coverage / resolution / mapping / units.

Reads ``panel.json`` (with filled ``per_100g``) and ``results/e0.json``,
compares against the on-disk ingredient cache and calculator unit conversion,
and writes ``results/e1.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.data_layer.models import Ingredient  # noqa: E402
from src.ingestion.nutrient_mapper import NutrientMapper  # noqa: E402
from src.nutrition.calculator import NutritionCalculator  # noqa: E402

from evaluation.data_track.common import (  # noqa: E402
    DATA_TRACK,
    DEFAULT_CACHE_DIR,
    MACRO_FIELDS,
    MICRO_FIELDS,
    RAW_DIR,
    RESULTS_DIR,
    cache_key_for_name,
    load_cache_entry,
    load_library_recipes,
    mapped_nutrition_to_per_100g,
    nutrition_close,
)


NUTRIENT_KEYS = list(MACRO_FIELDS) + list(MICRO_FIELDS)


def _load_raw(fdc_id: int) -> Optional[Dict[str, Any]]:
    path = RAW_DIR / f"{fdc_id}.json"
    if not path.exists():
        return None
    blob = json.loads(path.read_text(encoding="utf-8"))
    return blob.get("raw_payload") or blob


def _abs_dict(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    return {k: abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in NUTRIENT_KEYS}


def _scale(per_100g: Dict[str, float], grams: float) -> Dict[str, float]:
    factor = grams / 100.0
    return {k: float(per_100g.get(k, 0.0)) * factor for k in NUTRIENT_KEYS}


def _zero() -> Dict[str, float]:
    return {k: 0.0 for k in NUTRIENT_KEYS}


def _add(dst: Dict[str, float], src: Dict[str, float]) -> None:
    for k in NUTRIENT_KEYS:
        dst[k] = dst.get(k, 0.0) + float(src.get(k, 0.0))


def calculator_grams(name: str, quantity: float, unit: str) -> float:
    """Grams implied by NutritionCalculator._convert_quantity_to_grams."""
    calc = NutritionCalculator(provider=None)  # type: ignore[arg-type]
    ing = Ingredient(name=name, quantity=quantity, unit=unit)
    return float(calc._convert_quantity_to_grams(ing))


def panel_grams(entry: Dict[str, Any], quantity: float, unit: str) -> Optional[float]:
    gpu = entry.get("grams_per_unit") or {}
    if unit in gpu:
        return float(quantity) * float(gpu[unit])
    if unit == "g":
        return float(quantity)
    if unit == "oz":
        return float(quantity) * 28.35
    return None


def analyze_ingredient(
    entry: Dict[str, Any],
    mapper: NutrientMapper,
    e0_coverage_missing: set[str],
) -> Dict[str, Any]:
    name = entry["name"]
    key = entry["cache_key"]
    cached = load_cache_entry(name, DEFAULT_CACHE_DIR)
    correct_fdc = entry.get("correct_fdc_id")
    cached_fdc = entry.get("cached_fdc_id") or (cached.get("fdc_id") if cached else None)

    channels: Dict[str, Any] = {
        "coverage": {"present": name not in e0_coverage_missing, "error_per_100g": _zero()},
        "resolution": {"wrong_food": False, "error_per_100g": _zero()},
        "mapping": {"consistent": True, "error_per_100g": _zero(), "diffs": []},
        "units": {"usages": [], "total_error": _zero()},
    }

    truth = entry.get("per_100g") or _zero()
    gt_unavailable = bool(entry.get("ground_truth_unavailable"))

    # Coverage: ingredient absent from default local source (local-clean).
    if name in e0_coverage_missing:
        channels["coverage"]["present"] = False
        # Full truth is "missing" error for local path (contributes 0).
        channels["coverage"]["error_per_100g"] = {k: abs(float(truth.get(k, 0.0))) for k in NUTRIENT_KEYS}

    # Resolution: cached fdc != correct fdc
    if (
        not gt_unavailable
        and cached_fdc
        and correct_fdc
        and int(cached_fdc) != int(correct_fdc)
    ):
        channels["resolution"]["wrong_food"] = True
        raw_cached = _load_raw(int(cached_fdc))
        raw_correct = _load_raw(int(correct_fdc))
        if raw_cached and raw_correct:
            mapped_cached = mapped_nutrition_to_per_100g(mapper.map_nutrients(raw_cached))
            mapped_correct = mapped_nutrition_to_per_100g(mapper.map_nutrients(raw_correct))
            channels["resolution"]["error_per_100g"] = _abs_dict(mapped_cached, mapped_correct)
            channels["resolution"]["cached_description"] = (
                cached.get("description") if cached else None
            )
            channels["resolution"]["correct_description"] = entry.get("description")

    # Mapping: cached nutrition vs remap(raw[cached_fdc])
    if cached and cached_fdc:
        raw_cached = _load_raw(int(cached_fdc))
        if raw_cached:
            remapped = mapped_nutrition_to_per_100g(mapper.map_nutrients(raw_cached))
            cached_nut = {
                "calories": float(cached["nutrition"]["calories"]),
                "protein_g": float(cached["nutrition"]["protein_g"]),
                "fat_g": float(cached["nutrition"]["fat_g"]),
                "carbs_g": float(cached["nutrition"]["carbs_g"]),
            }
            micros = cached["nutrition"].get("micronutrients") or {}
            for mf in MICRO_FIELDS:
                cached_nut[mf] = float(micros.get(mf, 0.0))
            ok, diffs = nutrition_close(cached_nut, remapped)
            channels["mapping"]["consistent"] = ok
            channels["mapping"]["diffs"] = diffs
            channels["mapping"]["error_per_100g"] = _abs_dict(cached_nut, remapped)

    return {
        "name": name,
        "cache_key": key,
        "cached_fdc_id": cached_fdc,
        "correct_fdc_id": correct_fdc,
        "quarantined": entry.get("quarantined"),
        "ground_truth_unavailable": gt_unavailable,
        "channels": channels,
        "truth_kcal": float(truth.get("calories", 0.0)),
    }


def rollup_recipes(
    panel_by_name: Dict[str, Dict[str, Any]],
    ingredient_analysis: Dict[str, Dict[str, Any]],
    mapper: NutrientMapper,
) -> List[Dict[str, Any]]:
    """Per-recipe absolute kcal error attributed by dominant channel."""
    results = []
    for library in ("benchmark", "data_recipes"):
        try:
            recipes, raw_by_id = load_library_recipes(library)
        except FileNotFoundError:
            continue
        for recipe in recipes:
            channel_kcal = {
                "coverage": 0.0,
                "resolution": 0.0,
                "mapping": 0.0,
                "units": 0.0,
            }
            channel_abs = {c: _zero() for c in channel_kcal}
            stored = (raw_by_id.get(recipe.id) or {}).get("nutrition")
            # Compute "truth" recipe totals and channel-corrupted totals.
            truth_total = _zero()
            as_cached_total = _zero()  # resolution+mapping via cache per_100g * calc grams
            coverage_zero_total = _zero()  # what local path does when missing
            unit_fixed_total = _zero()  # correct per_100g * panel grams
            calc_grams_total = _zero()  # correct per_100g * calculator grams

            for ing in recipe.ingredients:
                if ing.is_to_taste:
                    continue
                entry = panel_by_name.get(ing.name)
                analysis = ingredient_analysis.get(ing.name)
                if entry is None or analysis is None:
                    continue
                truth = entry.get("per_100g") or _zero()
                calc_g = calculator_grams(ing.name, ing.quantity, ing.unit)
                panel_g = panel_grams(entry, ing.quantity, ing.unit)
                if panel_g is None:
                    panel_g = calc_g  # no separate panel unit → no units error

                truth_scaled = _scale(truth, panel_g)
                _add(truth_total, truth_scaled)
                _add(calc_grams_total, _scale(truth, calc_g))
                _add(unit_fixed_total, truth_scaled)

                # Coverage: local missing → 0 contribution
                cov_present = analysis["channels"]["coverage"]["present"]
                if not cov_present:
                    # skipped → 0; error = truth
                    _add(channel_abs["coverage"], truth_scaled)
                    channel_kcal["coverage"] += abs(truth_scaled["calories"])
                else:
                    _add(coverage_zero_total, truth_scaled)

                # Resolution+mapping via cache values * calc grams (what api-cache does)
                cached = load_cache_entry(ing.name, DEFAULT_CACHE_DIR)
                if cached:
                    cached_nut = {
                        "calories": float(cached["nutrition"]["calories"]),
                        "protein_g": float(cached["nutrition"]["protein_g"]),
                        "fat_g": float(cached["nutrition"]["fat_g"]),
                        "carbs_g": float(cached["nutrition"]["carbs_g"]),
                    }
                    micros = cached["nutrition"].get("micronutrients") or {}
                    for mf in MICRO_FIELDS:
                        cached_nut[mf] = float(micros.get(mf, 0.0))
                    cached_scaled = _scale(cached_nut, calc_g)
                    _add(as_cached_total, cached_scaled)

                    # Resolution share: remap(cached_fdc) vs remap(correct) at calc grams
                    res_err = analysis["channels"]["resolution"]["error_per_100g"]
                    res_scaled = _scale(res_err, calc_g)
                    _add(channel_abs["resolution"], res_scaled)
                    channel_kcal["resolution"] += res_scaled["calories"]

                    # Mapping share: cached vs remap(cached) at calc grams
                    map_err = analysis["channels"]["mapping"]["error_per_100g"]
                    map_scaled = _scale(map_err, calc_g)
                    _add(channel_abs["mapping"], map_scaled)
                    channel_kcal["mapping"] += map_scaled["calories"]
                else:
                    # No cache → treat as coverage for api-clean
                    pass

                # Units: |truth@panel_g - truth@calc_g|
                unit_delta = _abs_dict(_scale(truth, panel_g), _scale(truth, calc_g))
                _add(channel_abs["units"], unit_delta)
                channel_kcal["units"] += unit_delta["calories"]
                if unit_delta["calories"] > 0.5:
                    analysis["channels"]["units"]["usages"].append(
                        {
                            "recipe_id": recipe.id,
                            "quantity": ing.quantity,
                            "unit": ing.unit,
                            "calc_grams": calc_g,
                            "panel_grams": panel_g,
                            "kcal_error": unit_delta["calories"],
                        }
                    )

            total_channel_kcal = sum(channel_kcal.values()) or 1.0
            shares = {c: channel_kcal[c] / total_channel_kcal for c in channel_kcal}
            dominant = max(channel_kcal, key=channel_kcal.get)
            # Api-cache path cannot "miss" coverage; attribute 20% misses without it.
            non_coverage = {
                c: channel_kcal[c] for c in ("resolution", "mapping", "units")
            }
            dominant_non_coverage = max(non_coverage, key=non_coverage.get)

            # Compare api-cache computed (from E0 conceptually) vs truth
            truth_kcal = truth_total["calories"]
            cached_kcal = as_cached_total["calories"]
            kcal_off = abs(cached_kcal - truth_kcal)
            pct_off = (kcal_off / truth_kcal) if truth_kcal > 1e-6 else None

            results.append(
                {
                    "library": library,
                    "recipe_id": recipe.id,
                    "recipe_name": recipe.name,
                    "truth_kcal": truth_kcal,
                    "api_cache_kcal": cached_kcal,
                    "kcal_abs_error_vs_truth": kcal_off,
                    "kcal_pct_error_vs_truth": pct_off,
                    "over_20pct": bool(pct_off is not None and pct_off > 0.20),
                    "channel_kcal_error": channel_kcal,
                    "channel_shares_of_kcal_error": shares,
                    "dominant_channel": dominant,
                    "dominant_channel_excluding_coverage": dominant_non_coverage,
                    "has_stored_nutrition": stored is not None,
                    "channel_abs_nutrients": channel_abs,
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DATA_TRACK / "panel.json")
    parser.add_argument("--e0", type=Path, default=RESULTS_DIR / "e0.json")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "e1.json")
    args = parser.parse_args()

    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    e0 = json.loads(args.e0.read_text(encoding="utf-8"))

    # Coverage missing names = skipped under local-clean for either library.
    missing: set[str] = set()
    for cell in e0.get("cells", []):
        summary = cell.get("summary") or {}
        if summary.get("config") != "local-clean":
            continue
        for recipe in cell.get("recipes", []):
            for ing in recipe.get("ingredients", []):
                if ing.get("status") == "skipped":
                    missing.add(ing["name"])

    mapper = NutrientMapper()
    panel_by_name = {e["name"]: e for e in panel["ingredients"]}
    ingredient_rows = []
    ingredient_analysis = {}
    for entry in panel["ingredients"]:
        row = analyze_ingredient(entry, mapper, missing)
        ingredient_rows.append(row)
        ingredient_analysis[entry["name"]] = row

    recipe_rows = rollup_recipes(panel_by_name, ingredient_analysis, mapper)

    # Primary metric: share of total abs kcal error across recipes by channel
    total_by_channel = defaultdict(float)
    micro_by_channel: Dict[str, Dict[str, float]] = {
        c: defaultdict(float) for c in ("coverage", "resolution", "mapping", "units")
    }
    for r in recipe_rows:
        for c, v in r["channel_kcal_error"].items():
            total_by_channel[c] += v
        for c, nut in r["channel_abs_nutrients"].items():
            for mf in MICRO_FIELDS:
                micro_by_channel[c][mf] += nut.get(mf, 0.0)

    grand = sum(total_by_channel.values()) or 1.0
    kcal_shares = {c: total_by_channel[c] / grand for c in total_by_channel}

    over20 = [r for r in recipe_rows if r["over_20pct"]]
    over20_by_channel = defaultdict(int)
    for r in over20:
        over20_by_channel[r["dominant_channel_excluding_coverage"]] += 1

    # Shares excluding coverage (api-cache / resolution+mapping+units view)
    non_cov_total = sum(
        total_by_channel[c] for c in ("resolution", "mapping", "units")
    ) or 1.0
    kcal_shares_excluding_coverage = {
        c: total_by_channel[c] / non_cov_total
        for c in ("resolution", "mapping", "units")
    }

    n_wrong_resolution = sum(
        1 for r in ingredient_rows if r["channels"]["resolution"]["wrong_food"]
    )
    n_mapping_inconsistent = sum(
        1 for r in ingredient_rows if not r["channels"]["mapping"]["consistent"]
    )
    n_coverage_missing = sum(
        1 for r in ingredient_rows if not r["channels"]["coverage"]["present"]
    )

    # Highlight salmon / egg yolk mapping
    special = {}
    for name in ("salmon canned", "egg yolk"):
        if name in ingredient_analysis:
            special[name] = {
                "mapping_consistent": ingredient_analysis[name]["channels"]["mapping"][
                    "consistent"
                ],
                "mapping_diffs": ingredient_analysis[name]["channels"]["mapping"]["diffs"],
            }

    payload = {
        "experiment": "E1",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "panel_review_status": panel.get("review_status"),
        "summary": {
            "n_ingredients": len(ingredient_rows),
            "n_coverage_missing_local_clean": n_coverage_missing,
            "n_wrong_resolution": n_wrong_resolution,
            "n_mapping_inconsistent": n_mapping_inconsistent,
            "total_abs_kcal_error_by_channel": dict(total_by_channel),
            "share_of_abs_kcal_error_by_channel": kcal_shares,
            "share_of_abs_kcal_error_excluding_coverage": kcal_shares_excluding_coverage,
            "micro_abs_error_by_channel": {
                c: dict(micro_by_channel[c]) for c in micro_by_channel
            },
            "recipes_over_20pct_kcal": len(over20),
            "recipes_over_20pct_by_dominant_channel": dict(over20_by_channel),
            "salmon_egg_yolk_mapping": special,
        },
        "ingredients": ingredient_rows,
        "recipes": recipe_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2)[:2000])
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
