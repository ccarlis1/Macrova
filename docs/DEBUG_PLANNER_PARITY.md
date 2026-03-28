# Collecting planner parity debug artifacts (CLI vs Flutter)

## What you run locally (CLI-derived — automated)

From the repo root with your venv activated:

```bash
python3 scripts/export_planner_debug_artifacts.py \
  --profile config/user_profile.yaml \
  --recipes data/recipes/recipes.json \
  --ingredients data/ingredients/custom_ingredients.json \
  --days 1 \
  --out-dir debug_artifacts/
```

This writes:

| File | Contents |
|------|----------|
| `cli_plan_request.json` | Exact **POST `/api/v1/plan`** JSON body equivalent to your YAML profile + `--days` |
| `recipe_pool_snapshot.json` | Sorted recipe ids, names, counts, `recipe_ids_sha256` for quick pool diffs |
| `planner_run.json` | `termination_code`, `failure_mode`, full `report`, `stats`, planning profile summary |

**`planner_run.json` uses the same `--ingredient-source` as the CLI** (`local` vs `api` / USDA). If you only set `ingredient_source` in `cli_plan_request.json` but the dry-run used local nutrition, results would not match `plan_meals.py --ingredient-source api` (e.g. FM-4 vs a successful plan).

**Flutter:** `ingredient_source` comes from `MealPlanProvider.ingredientSource` (default `local`), persisted under planner config. The **Meal Planner Configuration** screen includes **Ingredient nutrition source** (local vs USDA API) so you can match CLI `--ingredient-source api` without editing code. The server must have `USDA_API_KEY` (e.g. in `.env`) when using `api`.

Optional flags:

- `--days 7` — match a multi-day Flutter run
- `--recipe-ids id1,id2` — restrict pool like Flutter `recipe_ids`
- `--planning-mode assisted` — only if you intentionally use assisted modes

Replay the exported request against a running API (optional):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/plan \
  -H 'Content-Type: application/json' \
  -d @debug_artifacts/cli_plan_request.json | jq .
```

---

## What you capture manually (Flutter / API)

These cannot be inferred from YAML alone because the app builds its own `PlanRequest`.

### 1) Raw Flutter → API request body

**Chrome (Flutter web):**

1. Open DevTools → **Network**
2. Trigger **Generate Meal Plan**
3. Find **`plan`** (or `POST .../api/v1/plan`)
4. Open **Payload** or **Request** → copy the JSON  
   Or: right-click the request → **Copy** → **Copy as cURL** (includes body)

Save as e.g. `debug_artifacts/flutter_plan_request.json`.

**Temporary one-liner in Dart** (remove after capture): in `ApiService.plan`, before `http.post`:

```dart
debugPrint('PLAN_PAYLOAD ${jsonEncode(body.toJson())}');
```

Copy from the debug console into a file.

### 2) Backend logs for that request

Start the API with stderr visible, or redirect:

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 2> debug_artifacts/api_stderr.log
```

The server already prints tag-filter JSON to stderr on plan; your stderr file timestamps the run.

### 3) Recipe pool at plan time (Flutter path)

If you use **recipe sync** or a **different server** than your laptop:

- After sync, call `GET /api/v1/recipes` and save the JSON, **or**
- On the server, snapshot `data/recipes/recipes.json` (or re-run the export script pointing `--recipes` at that file).

Compare `recipe_ids_sha256` in `recipe_pool_snapshot.json` between CLI export and Flutter/server snapshot.

---

## Ingredient search shows `502 Bad Gateway` in DevTools

`/api/v1/ingredients/search` calls **FoodData Central** via `USDAClient.search_candidates()`. If the USDA HTTP response is **not 200**, the server raises `USDALookupError` with code `API_ERROR` (or `RATE_LIMITED`, etc.) and returns **502** (except `INVALID_QUERY` → **400**).

So a **502 on `q=peper`** while **`q=peppers` returns 200** usually means **USDA rejected or errored on that specific query string** (typo / edge case), not a Flutter or DDC bug.

The **`ddc_module_loader.js` / “pool size = 1000”** lines are **normal Dart Dev Compiler** startup noise on web, not application errors.

To confirm the USDA side:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  "https://api.nal.usda.gov/fdc/v1/foods/search?api_key=$USDA_API_KEY&query=peper&pageSize=25&pageNumber=1"
```

---

## What to send for a full diff

1. `cli_plan_request.json` + `flutter_plan_request.json`
2. `recipe_pool_snapshot.json` (CLI) + server recipe list or snapshot (Flutter)
3. `planner_run.json` (CLI-side deterministic outcome)
4. API JSON response for the Flutter request (or `curl` replay body + response)
5. `api_stderr.log` (or terminal copy) for both runs if possible
