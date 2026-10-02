# §4.4 decision gate (after E0–E1b)

Status: **decided** (2026-10-02).

## Evidence summary

| Finding | Number |
|---|---|
| Local coverage missing (of 78 panel ingredients) | **72** |
| Share of abs kcal error — coverage / resolution / units / mapping | **84% / 15.5% / 0.6% / ~0%** |
| Api-cache view (excl. coverage) — resolution / units / mapping | **96% / 4% / 0% kcal** |
| Wrong resolutions | **13** |
| Recipes >20% kcal off (api-cache vs draft truth) | **20**, all resolution-dominated |
| Cache entries superseded under current mapper | **1 / 83** (`salmon_canned`) → **patch**, not rebuild |
| Zero-kcal-with-carbs cache keys | kiwi, mushrooms, sweet_potato, tomato (+ spaghetti_squash 0/0) |

## Decisions

1. **Q2 acceptability:** **(d) + (a)** — curated committed ingredient table; new USDA resolutions gated by macro plausibility (`4P+4C+9F` within ±15% of kcal).
2. **Missing ingredient:** **Fail recipe out of pool + warning** (same style as C6 unclassified warnings).
3. **Committed recipes:** **Both** — track `data/recipes/recipes.json` (the 32) and keep coverage over `.example` + benchmark library.
4. **Fix order:** confirmed —
   1. committed reviewed table
   2. no silent zeros
   3. plausibility gate on cache write
   4. coverage test
   5. benchmark `--nutrition computed`
