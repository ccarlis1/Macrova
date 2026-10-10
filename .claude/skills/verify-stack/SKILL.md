---
name: verify-stack
description: Verify this repo end-to-end and debug planner behavior. Use when tests fail or error at collection, before committing planner or API changes, when the CLI and Flutter app disagree ("parity"), when a plan fails with an FM-* code, or when asked to run/smoke-test the app. Covers environment repair, full test baseline, live CLI/API runs, parity artifacts, and failure-mode interpretation.
---

# Verify the Stack

The planner is deterministic, the test suite runs in seconds, and there is an exporter for
parity artifacts. This means verification is cheap — so it is always done by *running things*,
never by inspection alone.

## Step 0 — Environment triage (do this before believing any failure)

The most common false alarm in this repo is a broken venv, not broken code. If pytest shows
**collection errors** (`ModuleNotFoundError`, starlette/TestClient `RuntimeError`s, import
failures across many files):

```bash
source .venv/bin/activate
python --version                        # CI is 3.11; a mismatched local version is suspect
pip install -r requirements.txt -q      # this alone has fixed 49 collection errors before
python -m pytest tests/ -q              # rerun before touching any source file
```

Also verify: you are in the repo root (relative default paths depend on it), and the
gitignored data files exist (`tests/conftest.py` copies `.example` files automatically, but
the CLI/server outside pytest do not — copy manually if missing):

```bash
cp -n data/recipes/recipes.json.example data/recipes/recipes.json
cp -n data/ingredients/custom_ingredients.json.example data/ingredients/custom_ingredients.json
```

Only if failures survive a clean environment are they real.

## Step 1 — Static baseline (the CI gate, locally)

```bash
python -m pytest tests/ -q                 # full suite, ~950 tests, <10 s — never filter
python scripts/export_openapi.py --check   # drift here fails CI
```

If you changed `src/api/`: regenerate (`python scripts/export_openapi.py`) and commit
`openapi/openapi.json`; then `--check` must pass.

If you changed `frontend/`: `cd frontend && flutter analyze && flutter test` (not in CI —
you are the CI for Flutter).

## Step 2 — Exercise the real flow (tests are necessary, not sufficient)

**CLI planner:**
```bash
python3 plan_meals.py --days 1                  # markdown to stdout
python3 plan_meals.py --days 7 --output json    # structured; inspect termination_code
```

**API:**
```bash
uvicorn src.api.server:app --port 8000 &        # .env is loaded by server.py itself
curl -sS http://127.0.0.1:8000/openapi.json >/dev/null && echo up
```
Then POST a real request — the exporter (Step 3) produces an exact request body, so use it
rather than hand-writing one:
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/plan \
  -H 'Content-Type: application/json' \
  -d @debug_artifacts/cli_plan_request.json | python -m json.tool | head -50
```

**Determinism check (required after any planner change):** run the same plan twice with
identical inputs and diff the JSON outputs. Any diff = you introduced nondeterminism (unsorted
iteration, unseeded randomness, wall clock) — find it before committing.

**Flutter (when frontend behavior is in question):** `cd frontend && flutter run -d chrome`,
drive the affected screen, watch the network tab / server stderr (the server prints tag-filter
JSON to stderr on plan requests).

## Step 3 — Parity debugging (CLI vs Flutter disagree)

Full procedure lives in `docs/DEBUG_PLANNER_PARITY.md`; the short version:

```bash
python3 scripts/export_planner_debug_artifacts.py \
  --profile config/user_profile.yaml \
  --recipes data/recipes/recipes.json \
  --ingredients data/ingredients/custom_ingredients.json \
  --days 1 --out-dir debug_artifacts/
```

Produces `cli_plan_request.json`, `recipe_pool_snapshot.json` (with `recipe_ids_sha256`), and
`planner_run.json`. Then isolate which input differs, in this order — parity bugs are almost
always an input difference, not a planner bug:

1. **Recipe pool**: compare `recipe_ids_sha256` against the server's pool (`GET /api/v1/recipes`
   or the server's `recipes.json`). Different hash → sync issue, stop here.
2. **Request body**: diff `cli_plan_request.json` against the Flutter-sent payload (capture via
   Chrome DevTools → Network → the `plan` POST). Watch especially `ingredient_source`
   (Flutter defaults to `local`; CLI `--ingredient-source api` will not match it) and
   `planning_mode`.
3. **Seed / days**: identical seed and horizon on both sides?
4. Only if all inputs match and outputs still differ: suspect real nondeterminism (Step 2's
   determinism check, applied inside the planner phases).

`debug_artifacts/` is gitignored — never commit it.

## Failure-mode crib sheet (what a result actually means)

| Code | Meaning | First thing to check |
|---|---|---|
| FM-1 | Unfillable slot — no recipe satisfies the slot's hard constraints | Pool size after tag/exclusion filtering for that slot; busyness vs cooking times |
| FM-2 | Daily infeasibility — no combination fits the day's macro bounds | Per-meal calorie/macro math vs daily targets; `max_daily_calories` |
| FM-3 | Pinned conflict — a pin violates constraints or collides | `pinned_assignments` keys `(day_index, slot_index)` valid? Pinned recipe still in pool? |
| FM-4 | Weekly micronutrient floor unmet (τ × daily_RDI × D) | Which nutrient, in `report`; is τ intentionally 1.0? ULs are daily and unaffected by τ |
| FM-5 | Attempt limit exhausted | `stats` attempts; usually over-constrained, not a bug |

Rules that trip people (normative in `docs/SYSTEM_RULES.md`): ULs are enforced **per day,
never averaged**; τ relaxes only the weekly RDI floor, never ULs; the sodium advisory compares
against the un-relaxed goal. A "wrong-looking" FM-4 vs success difference between two runs is
usually `ingredient_source` mismatch (local vs USDA nutrition values), not planner logic.

## HTTP quick reference

- 502 from `/api/v1/ingredients/search` usually means USDA itself rejected that query string
  (test with curl against `api.nal.usda.gov` directly) — not a backend bug.
- All API errors must arrive as `{"error": {"code", "message"}}`. A bare 500 traceback means an
  exception type is missing from `src/api/error_mapping.py` — that is the bug to fix.

## Report format

End with: environment state (repaired or clean), test counts, exactly which flows you exercised
live, and — for parity work — which input layer differed. If something was NOT verified
(e.g. Flutter not run), say so explicitly rather than implying full coverage.
