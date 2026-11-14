# DATA-1 — FDC portion weights so all 18 sample recipes are plannable

**Status:** done  ·  **Complexity:** M  ·  **Depends on:** — (needs input I-2: `USDA_API_KEY`)

## Summary

12 of the 18 bundled sample recipes (`data/recipes/recipes.json.example`, served by `macrova_get_sample_recipes`) can't be planned, because a household unit has no gram conversion. Add each missing conversion to `data/reference/ingredient_nutrition.json` from FDC `foodPortions`, with the source in `notes`. Where the unit string itself is malformed, fix the sample recipe's unit instead. Never guess a weight.

## Context

Follow-up 12. Sample recipes are the MCP demo's default pool and the obvious first pool for a new user.

`tools.get_sample_recipes()` on 2026-11-14: **6 of 18 `ready_for_planning`**. There are 21 unmatched lines, covering 14 distinct (ingredient, unit) pairs:

| Recipe | Ingredient | Unit |
|---|---|---|
| Bolognese | carrots | `tbsp, diced` |
| Canned Salmon Wrap | salmon canned | `small can` |
| Canned Salmon Wrap | tortillas corn | `large` |
| Shakshuka; Roast Beef Sandwich | sourdough bread | `large slice` |
| Greek Yogurt Protein Bowl; Greek Yogurt Balance; Power Shake | chia seeds | `tbsp, whole pieces` |
| Greek Yogurt Protein Bowl | low fat greek yogurt | `cup` |
| Greek Yogurt Protein Bowl; Pre Workout 1 and 2; Power Shake | whey protein powder 24 grams of protein per scoop | `scoop` |
| Dense Bean Salad | chickpeas drained | `cup, whole pieces` |
| Dense Bean Salad | parmesan cheese hard | `tbsp, grated` |
| Dense Bean Salad | salami genoa | `slice` |
| Greek Yogurt Balance | greek yogurt plain nonfat | `cup` |
| Sweet Potato Bowl | sweet potato | `medium` |
| Power Omelette; Roast Beef Sandwich | roast beef lunchmeat | `medium slice` |
| Roast Beef Sandwich | sauerkraut | `tbsp` |

Two kinds of fix:
- **Missing weight** (for example `cup` for greek yogurt, `medium` for sweet potato): add `grams_per_unit[unit]` from the record's FDC `foodPortions` entry.
- **Compound unit string** (`tbsp, diced`, `cup, whole pieces`, `tbsp, grated`): these look like FDC `measureUnit` + `modifier` pasted together. Prefer adding the key exactly as the recipe spells it, when FDC has that portion (`modifier` matches). Otherwise change the sample recipe's unit to the plain FDC unit. Don't do both.

Precedent: PR #62 (Hass avocado weight) took the weight from FDC and recorded the source.

## Acceptance criteria

- [x] `tools.get_sample_recipes()` reports 18/18 `ready_for_planning`. If an item can't be fixed without guessing (likely candidate: the whey scoop, because SR Legacy has no scoop portion), the stub lists it with the reason, and the count is 17/18 or lower with every gap explained. Test: `tests/mcp_server/test_server.py` gets `test_sample_recipes_ready_for_planning`, asserting the exact expected count and the names of any not-ready recipes. It fails today (6).
- [x] Every added `grams_per_unit` key has a matching `notes` entry on that record, in the form `"<unit>: <grams> g, FDC <fdc_id> foodPortions id <portion id> (<measureUnit> <modifier>)"`. Test: a data test that every non-`g` key in `grams_per_unit` across the file has a `notes` mention. Grandfathered keys that predate this task are listed in the test as known exceptions, so the test fails on any new key without a source.
- [x] No per-100 g nutrient value changes. Test: compare against a snapshot of `per_100g` blocks taken before the change (or check `git diff` in the PR: only `grams_per_unit` and `notes` lines change).
- [x] `review_status` stays `draft`. Human review is tracked separately.
- [x] `/api/v1/plan` with `recipe_ids` set to the 18 sample ids and the Flutter new-user default macros, 3 days: no sample recipe appears in `warnings.nutrition`. Integration test in `tests/integration/`.
- [x] `benchmark-audit`: 153/153, 0 regressions. Changing `grams_per_unit` can change the nutrition of benchmark recipes that use the same unit.

## Implementation notes

### 🔒 Implementation contract
- Files to modify: `data/reference/ingredient_nutrition.json` (only `grams_per_unit` and `notes`), `data/recipes/recipes.json.example` (unit strings only, and only for the compound-unit case), tests.
- Files to inspect: `src/nutrition/calculator.py::to_grams` (how units are looked up; `scoop_size_g` / `large_size_g` explicit fields), `src/mcp_server/tools.py::get_sample_recipes`, `src/ingestion/usda_client.py` (to fetch `/food/{fdcId}` with `foodPortions`).
- Do NOT: guess weights, use weights from non-FDC sources, change nutrient values, change the ingredient a recipe uses, or flip `review_status`.

### 🧠 Pre-implementation analysis
1. For each record, fetch FDC `/v1/food/{fdc_id}` and list its `foodPortions` (`measureUnit.name`, `modifier`, `gramWeight`, `id`). Save the raw responses under `debug_artifacts/` (gitignored) for the PR description.
2. `REQUIRES_VERIFICATION`: how `to_grams` matches unit strings: case, whitespace, plural, and whether `"tbsp, diced"` could match a `"tbsp"` key. If a normalization rule already exists, a compound string may be fixable in the calculator instead. Stop and report rather than changing the calculator in this task.
3. Whey: `"24 grams of protein per scoop"` is a protein amount, not a powder weight. If the record is SR Legacy/Foundation and has no scoop portion, leave it unplannable and list it. Swapping in a branded FDC record is a different ingredient and out of scope.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`
- `benchmark-audit`: 153/153, 0 regressions
- Re-run `tools.get_sample_recipes()` and paste the ready count into this stub.

## Out of scope

- Human FDC review of the table (human-only).
- New ingredients or new sample recipes.
- `data/recipes/recipes.json` (the user/committed pool; separate from the samples).

## Close-out (2026-11-14)

**Result: 11 of 18 samples `ready_for_planning`** (was 6). `tools.get_sample_recipes()` re-run after the change: 11/18. The 7 remaining recipes are blocked by units with no close FDC portion, listed below.

FDC `/v1/food/{fdc_id}` was fetched for all 14 records. Raw payloads are in `debug_artifacts/data1/<fdc_id>.json` (gitignored). Every portion's `measureUnit` is `undetermined`; the portion name is in `modifier`.

**Fixed**
- whey protein powder (FDC 173177): `scoop: 28.67` from foodPortions id 92053 (modifier `scoop`, amount 3 = 86.0 g). The feared gap didn't exist: SR Legacy has a scoop portion. Unblocks Pre Workout 1 and Pre Workout 2.
- carrots `tbsp, diced` (Bolognese): FDC has no diced tbsp portion, so the sample's unit becomes plain `tbsp`, per the compound-unit rule. The weight is the record's existing `tbsp: 7`, which predates this task and has no source (grandfathered in the new data test).

**Not fixed (no close FDC portion)**

| Ingredient (FDC) | Recipe unit | What FDC has |
|---|---|---|
| salmon canned (175174) | `small can` | can, total contents 417 g (id 95800); oz |
| sourdough bread (172675) | `large slice` | slice 139 g (id 91076, looks like a whole-loaf slice); oz |
| chia seeds (170554) | `tbsp, whole pieces` | oz only (id 86844) |
| low fat greek yogurt (170903) | `cup` | container (7 oz) 200 g (id 87526) |
| greek yogurt plain nonfat (170894) | `cup` | container 170 g (id 87513) |
| chickpeas drained (173800) | `cup, whole pieces` | can drained 253 g (id 93273) |
| parmesan cheese hard (170848) | `tbsp, grated` | cubic inch 10.3 g (id 87388); oz; package |
| salami genoa (2126122, Branded) | `slice` | no foodPortions; servingSize 56 g ("2 ONZ") |

**Near matches (approved by the user on 2026-11-14 after the exact-match pass)**

Each is an FDC portion that names the same food but not the recipe's size word. The note on each record says it's a near match.
- sweet potato `medium: 130`: portion 83167, `sweetpotato, 5" long`. FDC has no size names. Unblocks Sweet Potato Bowl.
- tortillas corn `large: 24`: portion 95472, `tortilla`, the only tortilla size (enchilada is 19 g). Canned Salmon Wrap is still blocked by the salmon can.
- roast beef lunchmeat `medium slice: 13.8`: portion 94596, `slice rectangle`, the larger of the two slices (oval is 9.3 g). Unblocks Power Omelette.
- sauerkraut `tbsp: 8.88`: derived from portion 84590, cup 142 g / 16. Roast Beef Sandwich is still blocked by the bread.

**Rejected as not near**

The closest FDC portion is a different amount, so mapping would put wrong calories into plans:
- salmon `small can` = 417 g whole can, about 2.5× a small can.
- sourdough `large slice` = 139 g slice, several ordinary slices.
- yogurt `cup` = container 170 g or 200 g; a cup is a different volume.
- chickpeas `cup` = can drained 253 g, about 1.5 cups.
- parmesan `tbsp, grated` = cubic inch 10.3 g, solid not grated.
- chia `tbsp` and salami `slice` have no portion at all (oz only; branded record with no portions).

Fixing the rest needs a different FDC record for the same food (a different ingredient, so out of scope here), or a sample recipe rewritten in grams.

**Tests**
- `tests/mcp_server/test_server.py::test_sample_recipes_ready_for_planning`: exactly 11, with the 7 not-ready names.
- `tests/test_ingredient_unit_sources.py`: every non-`g` key needs an FDC note. The 41 earlier keys are grandfathered, and the test fails if one is removed without leaving the list.
- `tests/integration/test_sample_recipes_plan.py`: a 3-day `/api/v1/plan` over the 18 sample ids with the Flutter new-user macros (2000 kcal, 150 g protein, fat 60–74 g). `warnings.nutrition` names exactly the 7 not-ready recipes and no others.
- The data diff is the whey `grams_per_unit` and `notes` plus one sample unit string. No `per_100g` or `review_status` change.

**Validation:** full suite 1371 passed; OpenAPI `--check` exit 0; benchmark (main → branch) 153/153, 0 regressions, diff exit 0; probes P1 OK valid, P2 FM-3, P3 OK valid.
