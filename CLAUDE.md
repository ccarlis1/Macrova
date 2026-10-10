# CLAUDE.md — Macrova (nutrition-agent) Operating Manual

Macrova is a meal planner: a **deterministic, phase-based backtracking planner** (Python/FastAPI,
`src/`) + a **Flutter app** (`frontend/`, package `macrova`) + an **LLM recipe-acquisition
pipeline** (`src/llm/`). The LLM acquires recipes and tags; it never plans and never produces
nutrition numbers. Work happens spec-first: sprint docs with per-task stubs are written before
code, and code is expected to honor them.

---

## 1. The four laws (violating any of these is a failed change)

1. **One canonical path — extend, never fork.** Every concern has exactly one owning module
   (table in §3). If your change wants a new module that overlaps an existing one, you are
   about to fork a pipeline. Extend the existing module instead.
2. **Additive contract evolution.** API request/response fields, persisted JSON shapes, and
   Flutter DTOs only gain optional fields. Never rename, remove, or change the type of an
   existing field (e.g. `day`, `dayTotals` stay as-is).
3. **The planner is deterministic and LLM-independent.** Same profile + recipe pool + seed →
   same plan, with the LLM disabled. No wall-clock, no unseeded randomness, no unsorted
   dict/set iteration in `src/planning/`.
4. **Nutrition numbers come only from computation** (local ingredient DB or USDA), never from
   LLM output. LLM JSON schemas deliberately exclude nutrition fields — keep it that way.

## 2. Environment and commands

Run **everything from the repo root** — default data paths (`data/recipes/recipes.json`,
`config/user_profile.yaml`) are relative, and `pytest.ini` sets `pythonpath = .`.

```bash
source .venv/bin/activate                 # local venv (CI uses Python 3.11)
pip install -r requirements.txt           # repair step if imports/collection fail
python -m pytest tests/ -q                # full backend suite: ~950 tests, <10 s — always run ALL of it
python scripts/export_openapi.py --check  # CI fails on OpenAPI drift; regen with no --check
python3 plan_meals.py                     # CLI planner (wraps src/cli.py); --output json, --days N
uvicorn src.api.server:app --port 8000    # REST API
cd frontend && flutter analyze && flutter test   # Flutter checks
cd frontend && flutter run -d chrome      # run the app (web)
```

- `.env` at repo root holds `USDA_API_KEY`, `LLM_API_KEY`, `LLM_MODEL`. Both `src/cli.py` and
  `src/api/server.py` parse it manually; uvicorn does not.
- CI (`.github/workflows/ci.yml`) = pytest + OpenAPI drift check, nothing else. `flutter test`
  is not in CI — run it yourself when you touch `frontend/`.

**Data file rules:**

| File | In git? | Rule |
|---|---|---|
| `config/user_profile.yaml` | **Yes, deliberately** (despite a stale `.gitignore` entry) | This is the user's real profile. Edits show up in `git status`; don't casually rewrite it. |
| `data/recipes/recipes.json`, `data/ingredients/custom_ingredients.json` | No — only `.example` committed | Schema changes must update the `.example` file (and a migration if needed), or CI and clean clones break. `tests/conftest.py` auto-copies `.example` → real when missing. |
| `data/recipes/recipe_tags.json` | No, created at runtime | Schema defined by `tag_repository.py` / `RecipeTagsJson` in `src/llm/schemas.py`. |

## 3. Ownership map — where a change goes

| Concern | The ONE owning place |
|---|---|
| Planner entry point | `src/planning/planner.py::plan_meals` → `phase7_search.run_meal_plan_search`. No shadow `plan()` helpers. |
| Planner result | `MealPlanResult` (`src/planning/phase10_reporting.py`). Extend its `report`; never add a competing top-level plan type. |
| Hard/soft constraints | `phase2_constraints` (HC-*), `phase3_feasibility` (FC-*), `phase6_candidates`; scoring in `phase4_scoring`. |
| Schedule contract | `src/models/schedule.py` (`DaySchedule`, `MealSlot`, `WorkoutSlot`) — module docstring is the contract. Legacy YAML mapping: `src/models/legacy_schedule_migration.py`. |
| Tags: registry + persistence | `src/llm/tag_repository.py` + `data/recipes/recipe_tags.json`. **No second tag store, ever.** |
| Tags: filtering | `apply_tag_filtering` in `src/llm/tag_filtering_service.py` / `tag_filter.py`. One filter pipeline. |
| Forcing precedence | batch locks > `pinned_assignments` > required tag slugs > scoring (SPRINT_1.md §3.5). |
| Profile ↔ planner conversion | `src/planning/converters.py` (`convert_profile`, `convert_recipes`, `extract_ingredient_names`). |
| Ingredient nutrition | provider abstraction (`src/providers/`); all lookups resolved **before** planning, never during search. |
| API error responses | `src/api/error_mapping.py::map_exception_to_api_error` → `{"error": {"code", "message"}}`. Every new exception type gets a mapping + status code here. |
| LLM structured outputs | `src/llm/schemas.py`; generation/validation flow in `src/llm/pipeline.py` — extend, don't parallel. |
| Flutter server I/O | `frontend/lib/services/api_service.dart` + `frontend/lib/models/`. |

## 4. Documentation authority (docs lie; know which ones)

Trust in this order — when layers disagree, the higher one wins and the discrepancy gets
reported, not silently reconciled:

1. **Code + tests** (ground truth).
2. **`docs/SYSTEM_RULES.md`** and **`docs/MEALPLAN_SPECIFICATION_v2.md`** (normative product
   rules: τ, ULs, sodium advisory, FM-* failure modes).
3. **`docs/SPRINT_1.md` + `docs/sprint1/*.md`** (current intent; stubs carry binding
   IMPLEMENTATION CONTRACT sections).
4. **README / ARCHITECTURE / everything else** (orientation only, known stale).

Known dead references — do not go looking for these, they don't exist:
`docs/MEALPLAN_SPECIFICATION_v1.md`, `docs/planner_architecture.md`, `architecture.json`,
`.cursor/report.json`, `KNOWLEDGE.md`.

## 5. Conventions

**In force (match these):**
- Pydantic v2 models with `ConfigDict(extra="forbid")` and `Field(..., description=...)` for
  anything crossing a contract boundary; plain `@dataclass` for internal planner structures.
- Module docstrings state **contracts and invariants** (see `src/models/schedule.py`), not
  narration.
- Exceptions are module-specific hierarchies with deterministic, SCREAMING_SNAKE error codes
  (`LLMTimeoutError`, `TagConflictError`, …), mapped centrally in `error_mapping.py`.
- Naming grammar: failure modes `FM-*` (FM-1 unfillable slot, FM-2 daily infeasibility, FM-3
  pinned conflict, FM-4 weekly micronutrient, FM-5 attempt limit), hard constraints `HC-*`,
  forward checks `FC-*`, planner phases `phaseN_*.py`, tests `tests/test_<module>.py`.
- Tests: plain pytest functions (occasionally Given/When/Then classes), `tmp_path` for any
  file I/O, mocks for USDA — the suite needs **no network and no real keys**.
- API: everything under `/api/v1`; OpenAPI snapshot committed at `openapi/openapi.json`.
- LLM client is provider-agnostic OpenAI-compatible via `requests` — no `openai`/`anthropic`
  SDKs (they're deliberately commented out in requirements.txt).
- Flutter: `provider` package + `ChangeNotifier`, plain `http`, hand-rolled fakes in
  `frontend/test/` — **no Riverpod, no Mockito, no GetIt** (ignore any skill text that assumes
  them).

**Added (follow these too):**
- Always run the **full** pytest suite — it takes seconds; there is no excuse for filtering.
- The codebase is not uniformly black-formatted. Never reformat existing files wholesale;
  match the surrounding style. New files you create may be black-clean.
- Every new public function in `src/` gets type hints and a docstring stating what it
  guarantees (not what it does line-by-line).
- New planner failure conditions get: a string code (`FM-*` style), representation in
  `MealPlanResult.report`, an entry in `error_mapping.py` if surfaced via API, and a test
  asserting the exact code.
- When you check off an acceptance-criteria box in a sprint stub, the test proving it must
  exist in the same commit.

## 6. Named traps — mistakes that WILL happen here without these rules

1. **The Parallel Pipeline.** Symptom: creating `tag_service.py`, `plan_v2.py`,
   `data/tags/registry.json`, a second filter function. Rule: before creating any file, grep
   for the owning module in §3. Sprint stubs have explicit "Do NOT create" lists — they are
   binding. If a task seems to need a new module, stop and justify against §3 first.
2. **The Silent Contract Break.** Symptom: CI fails on "OpenAPI contract (no drift)" or the
   Flutter app breaks after a field rename. Rule: API/DTO changes are additive-optional only;
   after any change to `src/api/` or its request/response models, run
   `python scripts/export_openapi.py` and commit the regenerated `openapi/openapi.json`.
3. **Blaming Code for a Broken Venv.** Symptom: dozens of pytest **collection** errors,
   `ModuleNotFoundError` (e.g. `httpx`), starlette/TestClient RuntimeErrors. That is the local
   env, not the code (it has happened in this repo; the fix was `pip install -r
   requirements.txt`). Rule: if more than ~3 tests error at *collection*, repair the venv and
   rerun before touching a single source file. CI on Python 3.11 is the referee.
4. **The `.example` Split-Brain.** Symptom: schema change works locally (your real data file
   has the field) but CI/clean clones break, or the user's personal data gets committed. Rule:
   any schema change to recipes/ingredients touches the `.example` file; never `git add` the
   gitignored real data files; never delete or truncate them either — they are the user's data.
5. **Trusting Dead Docs.** Symptom: hunting for `MEALPLAN_SPECIFICATION_v1.md` or trying to
   update `architecture.json`. Rule: use the authority order in §4; if a doc contradicts code,
   code wins and you report the contradiction in your summary.
6. **Nondeterminism Creep.** Symptom: parity mismatch between two identical runs, flaky
   planner tests. Rule: in `src/planning/` and anything it calls — sort before iterating over
   dict/set contents, thread the existing seed through, no `time`/`random` without a seed, no
   filesystem ordering assumptions. `sorted()` is cheap; debugging nondeterminism is not.
7. **LLM Lane Violation.** Symptom: LLM JSON schema gains a `calories` field, or LLM-proposed
   tags start driving hard constraints. Rule: nutrition is computed post-validation from
   USDA/local data (guardrail AI-4); LLM-created tag slugs enter as `proposed` and are
   excluded from hard planner constraints until user-approved. `plan_meals` must keep passing
   with LLM disabled (`test_planner_regression_with_llm_disabled.py` guards this).
8. **Workout-as-Meal Confusion.** Symptom: adding a `MealSlot` with `busyness_level=0` for a
   workout, or putting workout fields on meals. Rule: workouts live **only** in
   `DaySchedule.workouts` as `WorkoutSlot` (`after_meal_index`, `type`, `intensity`);
   `busyness_level` is 1–4 and describes cooking-time bands; legacy `0` values are migrated by
   `legacy_schedule_migration.py`, never interpreted as meals.
9. **Weekly-Averaging the Limits.** Symptom: validating micronutrient ULs as a weekly average,
   or applying τ (`micronutrient_weekly_min_fraction`) to ULs. Rule: **ULs are daily and never
   averaged**; τ relaxes only the weekly RDI floor, never UL enforcement, and the sodium
   advisory compares against the un-relaxed goal (`SYSTEM_RULES.md` is normative here — don't
   reason these out from first principles).
10. **The Riverpod Hallucination.** Symptom: Flutter tests written with
    `ProviderContainer`/Mockito/GetIt that don't compile. Rule: copy the structure of an
    existing test in `frontend/test/` (plain `flutter_test`, real objects or hand-rolled
    fakes); the generic parts of the flutter-tester skill override nothing in this repo.
11. **Skipping the Stub Contract.** Symptom: implementing a `docs/sprint1/` task without
    reading its "Files to inspect before writing any code" list, then duplicating existing
    logic. Rule: for sprint tasks, the stub's IMPLEMENTATION CONTRACT / PRE-IMPLEMENTATION
    ANALYSIS / POST-IMPLEMENTATION VALIDATION sections are the process, not suggestions.
    `REQUIRES_VERIFICATION` markers mean: read the actual code signature before wiring
    anything — the spec author explicitly did not check it.
12. **The Wrong-CWD Failure.** Symptom: `FileNotFoundError: data/recipes/recipes.json` from
    tests, CLI, or server. Rule: run everything from the repo root; never "fix" this by
    hardcoding absolute paths.

## 7. Quality bar per deliverable (checkable, not adjectives)

**Any backend change** — done means ALL of:
- [ ] `python -m pytest tests/ -q` passes in full (no deselection, no `-k`).
- [ ] New behavior has at least one test that fails without the change (state which test).
- [ ] No new module duplicates an owner in §3; no file created outside declared scope.
- [ ] New exceptions registered in `error_mapping.py` if they can reach the API.
- [ ] No print-debugging left behind; stderr diagnostics only where the module already does it.

**API surface change** — the above, plus:
- [ ] Change is additive-optional; existing fields untouched.
- [ ] `openapi/openapi.json` regenerated and committed; `--check` passes.
- [ ] Error paths return the `{"error": {"code", "message"}}` envelope with a deterministic code.
- [ ] A `tests/test_api_*.py` test covers success + at least one error mapping.
- [ ] If Flutter consumes it: Dart models/`api_service.dart` updated in the same change, `flutter analyze` + `flutter test` pass.

**Planner behavior change** — backend bar, plus:
- [ ] Two consecutive runs with identical inputs+seed produce identical plans (assert it, don't assume).
- [ ] Failure paths return a `termination_code`/`FM-*` through `MealPlanResult` — never a bare exception from search.
- [ ] Existing phase tests (`tests/test_phase*.py`) untouched or their changes explicitly justified in your summary — a changed planner expectation is a product decision, not a test fix.
- [ ] Precedence (batch locks > pins > required tags > scoring) still has passing tests.

**LLM pipeline change** — backend bar, plus:
- [ ] Structured outputs defined in `src/llm/schemas.py`; no nutrition fields in LLM-facing schemas.
- [ ] Bounded retries; every failure mode maps to a deterministic error code.
- [ ] Full suite passes with no `LLM_API_KEY` set (mocked client only).

**Flutter change:**
- [ ] `flutter analyze` reports nothing new; `flutter test` passes.
- [ ] DTO changes additive and mirrored to the server contract.
- [ ] New provider/coordinator logic has a test in `frontend/test/` following existing patterns.

**Sprint task (docs/sprintN/):**
- [ ] Every acceptance-criteria checkbox either checked with a proving test, or explicitly left
      unchecked with a stated reason.
- [ ] POST-IMPLEMENTATION VALIDATION checklist executed and updated in the stub file.
- [ ] Stub `Status:` line updated (`todo|in-progress|blocked|done`).
- [ ] "Out of scope" section respected — no opportunistic extras.

**Docs change:**
- [ ] Every file path and symbol named in the doc exists in the repo (check them — this repo
      has dead references already; don't add more).

## 8. When uncertain — exact escalation rules

**Resolve yourself, in this order (do not ask about these):**
1. "How does X actually work / what's the real signature?" → read the code. Anything marked
   `REQUIRES_VERIFICATION` in a spec is an instruction to do exactly this.
2. "What should the product do?" → `SYSTEM_RULES.md`, then `MEALPLAN_SPECIFICATION_v2.md`.
3. "Is this in scope?" → the task stub's Summary / Out-of-scope, then `SPRINT_1.md`.
4. Broken venv, missing data files, wrong CWD → fix per §2 and continue.

**Stop and ask the user (these are their decisions, not yours):**
- Any change that would be **non-additive** on an API/DTO/persisted-JSON contract — present
  the additive alternative alongside.
- Code contradicts a normative doc (SYSTEM_RULES / spec v2) — report both sides; never pick
  silently, never "fix" the code to match the doc or vice versa on your own.
- A change alters plan output for scenarios whose tests currently pass (i.e. you'd need to
  edit existing test expectations) — show the before/after diff first.
- Adding a dependency to `requirements.txt` or `pubspec.yaml`.
- Deleting/overwriting anything under `data/` or `config/` that isn't a `.example` file.
- The task stub's acceptance criteria are impossible as written against the real code.
- Two canonical owners in §3 genuinely both claim the change and the stub doesn't say.

**When blocked and the user is unavailable:** implement the smallest additive interpretation,
flag the decision prominently in your final summary with the alternatives you rejected, and
leave the relevant stub checkbox unchecked rather than checking it optimistically.

**Never:** invent product constants (τ semantics, UL values, sodium thresholds, scoring
weights); mark a sprint checkbox done without a proving test; resolve a spec-vs-code conflict
without surfacing it.
