# DATA-2 — Correct the inflated vitamin D values and re-probe the default lists

**Status:** done  ·  **Complexity:** M  ·  **Depends on:** BE-20 (re-probe), DATA-1 (provenance conventions)

## Summary

Owner approval (2026-11-15): "correct the inflated vitamin D values in the ingredient table and re-probe
the default lists". The close-out demo (README → Close-out results, step 2b) found `vitamin_d_iu` in
`data/reference/ingredient_nutrition.json` about 40 times too high. Fix the cause, correct each entry from
its own FDC record, add a data check that fails on the old values, then re-derive the D-A default lists.

## Root cause

The bug was in live code, `src/ingestion/nutrient_mapper.py`, which both the USDA API provider path and
the reference-table build use:

- `USDA_NUTRIENT_MAP` had the two FDC vitamin D ids swapped. In FDC, id **1110** (nutrient number 324,
  "Vitamin D (D2 + D3), International Units") is in **IU** and id **1114** (number 328, "Vitamin D (D2 + D3)")
  is in **µg**. The map labelled 1110 as µg with `conversion: 40.0` and 1114 as IU.
- `_process_nutrient` **summed** every id mapped to the same field ("Take the first non-zero value or sum them").

So every food carrying both entries got `IU × 40 + µg`. Eggs (FDC 171287: 82 IU, 2.0 µg) → 3,282.
All 18 non-zero entries reconstruct exactly as `IU × 40 + µg` from their FDC records.

How it reached the table: `evaluation/data_track/fill_panel_nutrition.py` filled
`evaluation/data_track/panel.json` → `per_100g` by running the live `NutrientMapper` over raw FDC payloads;
the panel was then promoted to `data/reference/ingredient_nutrition.json` (`source_panel`). The same mapper
fills the USDA ingredient cache (`src/ingestion/ingredient_cache.py`) in API mode.

Fix (commit "Map USDA vitamin D by unit"): 1110 is used as is; 1114 × 40 is a fallback used only when a food
has no IU entry; no field may be fed by two primary ids. `MAPPER_VERSION` 1 → 2. Regression test:
`tests/test_nutrient_mapper.py::test_vitamin_d_both_units_uses_iu_not_x40_not_sum` (FDC-shaped egg payload
with both entries, both orders → 82).

### Other copies of the inflated values (not changed here)

| Where | State |
|---|---|
| `evaluation/data_track/panel.json` | Same inflated values (it is the source panel). Left as the historical draft; re-running `fill_panel_nutrition.py` with the fixed mapper corrects it. |
| `frontend/assets/dev/cached_ingredients.json` | Inflated copy (for example egg yolk 8725.4, tilapia 4963.1, sharp cheddar 1641). Out of scope (no frontend change beyond fixtures). |
| `data/ingredients/custom_ingredients.json.example` | Cheddar 200.1 (FDC value 5 IU). Legacy path, out of scope. |
| `evaluation/benchmark/recipes.json` | Stored per-serving nutrition carries inflated vitamin D (64 recipes with a value, max 9,926 IU). The benchmark plans with this stored nutrition by default (`run_benchmark.py`, `NUTRITION=stored`), so the table correction cannot move the 153/153 baseline. Not changed (benchmark data; changing it is a scenario/oracle question for the owner). |
| `.cache/ingredients/` (gitignored, local only) | Entries written by mapper version 1 keep the inflated value; the cache does not re-map on a version change. Delete the local cache, or re-fetch, to pick up the fix. |

### Other nutrients checked for a similar unit error

Every mapped id was checked against the `nutrient.name` / `unitName` in the 18 fetched FDC payloads. No other
unit double-conversion: vitamin A uses 1106 (RAE, µg; the IU entry 1104 is not mapped), vitamin E 1109
(alpha-tocopherol, mg), folate 1177 (µg), niacin 1167 (mg), all other minerals and vitamins match their
units. Not fixed, listed for the owner:

- **`omega_3_g` maps id 1272, which is `PUFA 22:6 n-3 (DHA)` only**, not total omega-3 (the comment says
  "total polyunsaturated omega-3"). ALA (1404), EPA (1278) and DPA (1280) are not counted, so plant foods
  show 0 omega-3. This likely contributes to omega-3 being unmeetable in every D-A probe. A semantic mapping
  choice (which sum is "omega-3"), not a unit error.
- `omega_6_g` maps 1269 (`PUFA 18:2`, all 18:2 isomers including trans/CLA), a proxy for linoleic acid
  (1316 is `18:2 n-6 c,c`). Small difference.
- `folate_ug` maps 1177 (Folate, total), while the RDIs are in DFE (1190). Equal for unfortified foods;
  understates fortified foods.
- `vitamin_e_mg` (1109) excludes added vitamin E (1242); niacin is preformed niacin, not niacin equivalents.

## Data correction

Every entry with a non-zero `vitamin_d_iu` (18 of 78) was checked against its own `fdc_id`. The repo had no
raw FDC payloads (`evaluation/data_track/raw/` and `debug_artifacts/data1/` absent; the local `.cache`
holds mapped, already-inflated values), so each record was fetched from FDC `/v1/food/{fdc_id}` through
`USDAClient.get_food_details` with the key from the gitignored `.env`. Raw payloads:
`debug_artifacts/data2/<fdc_id>.json` (gitignored). New value = FDC nutrient 1110 (IU) per 100 g. Each old
value was first checked to equal `IU × 40 + µg` from the same record (all 18 did, to 0.05); the new value is
therefore consistently ≈ old / 40. Each changed entry's `notes` gets
`"vitamin_d_iu: <old> -> <new> IU/100 g, FDC <fdc_id> nutrient 1110 (number 324, IU) = <IU>; nutrient 1114 = <µg> µg (DATA-2, 2026-11-15; …)"`.

| Ingredient | FDC id | Old IU/100 g | New IU/100 g | FDC µg (1114) |
|---|---|---|---|---|
| cheddar cheese natural 50% reduced fat | 173439 | 200.1 | 5 | 0.1 |
| chicken breast | 171077 | 40 | 1 | 0 |
| chicken thigh skin removed | 173627 | 40 | 1 | 0 |
| egg yolk | 172184 | 8725.4 | 218 | 5.4 |
| eggs | 171287 | 3282 | 82 | 2 |
| feta cheese reduced fat | 173420 | 640.4 | 16 | 0.4 |
| hamburger or beef 90% | 174030 | 120.1 | 3 | 0.1 |
| hamburger or beef 95% | 173110 | 120.1 | 3 | 0.1 |
| milk (Branded) | 1909132 | 1680 | 42 | — (IU only) |
| milk 1% fat lowfat | 170872 | 1921.2 | 48 | 1.2 |
| parmesan cheese hard | 170848 | 760.5 | 19 | 0.5 |
| parmesan grated | 171247 | 840.5 | 21 | 0.5 |
| roast beef lunchmeat | 174570 | 40 | 1 | 0 |
| salmon canned | 175174 | 30459 | 761 | 19 |
| sharp cheddar cheese | 170899 | 1641 | 41 | 1 |
| tilapia | 175176 | 4963.1 | 124 | 3.1 |
| tuna sashimi | 175159 | 2761.7 | 69 | 1.7 |
| turkey breast lunchmeat reduced fat | 172941 | 240.2 | 6 | 0.2 |

**Unverifiable entries:** none. Entries with `vitamin_d_iu = 0` were not re-checked (a zero is not inflated).
No other nutrient, `review_status` (`draft`) or `reviewed` date changed; only the `vitamin_d_iu` and `notes`
lines of these 18 entries differ.

Per starter recipe, vitamin D now peaks at 701.5 IU (Canned Salmon Wrap; was about 28,000). Before, six
starter recipes were above the 4,000 IU daily UL on their own.

Data test: `tests/test_ingredient_vitamin_d_sanity.py`: no entry above 2,000 IU/100 g (justified in the file;
5 entries were above it before), every non-zero entry cites its FDC nutrient 1110, and no starter recipe
exceeds the lowest daily vitamin D UL (6 failed before).

## Re-probe of the default lists

Recorded in the BE-20 stub ("Probe re-run (2026-11-15), after DATA-2 corrected vitamin D"). Every current
default list still plans at 7 days for its demographic, so `DEFAULT_MICRONUTRIENT_LEFT_OUT`,
`config/user_profile.yaml.example` and the Flutter `micronutrient_defaults_*.json` fixtures are unchanged.
Owner option: pregnancy and lactation could keep `vitamin_e_mg` (it now succeeds); the Flutter tests pin
the current pregnancy list. The example profile now plans at 1 day as well (CLI and HTTP, `TC-4`), so
`test_example_profile_one_day_outcome_is_pinned` pins success; MCP's adult_female 2-day failure no longer
names vitamin D (`test_demographic_sets_micronutrient_targets` now checks vitamin E).

## Demo step 2b after the correction

In-process (FastAPI `TestClient`, `MACROVA_DATA_DIR` and `NUTRITION_USER_PROFILE_PATH` on temp paths),
fresh data folder, 7 days, Flutter new-user default request (2000 kcal, 150 g protein, fat 60–74 g, 3 meals
2/3/4 tagged breakfast/lunch/dinner), goals and τ from `GET /api/v1/micronutrient_defaults?demographic=adult_male`:

| Pool | No goals, no demographic | No goals, adult_male | Default goals, no demographic | Default goals, adult_male |
|---|---|---|---|---|
| all 18 | success | success (was partial, FM-MACRO-INFEASIBLE) | partial, FM-5 | partial, TC-3, FM-5 (was failed, FM-4) |
| 8 (`recipe_007, 009, 011, 017, 003, 010, 002, 016`) | partial, FM-MACRO-INFEASIBLE | partial, FM-MACRO-INFEASIBLE | failed, FM-4 | failed, FM-4 |

Binding constraint (all 18, adult_male): the vitamin D floor (600 IU/day, 4,200 IU over 7 days). Default goals
minus `vitamin_d_iu` → success; minus any other single goal → FM-5; `vitamin_d_iu` 600 alone → FM-5, also with
the attempt limit raised in memory to 500,000; `vitamin_d_iu` 300 alone → success. Not tuned: an owner
decision (README → Close-out results). Pinned by `tests/api/test_demo_new_user_default.py`.
