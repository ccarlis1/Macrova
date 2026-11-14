# BE-20 — Demo micronutrient default (D-A), user override, MCP busyness 2/3/4 (D-B)

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DATA-1

## Summary

Apply the owner's D-A decision to every place a new user's micronutrient floors come from:
- the MCP `demographic` path;
- `config/user_profile.yaml.example`;
- the Flutter new-user default.

Let users override that default where they can't today (MCP). Change the MCP shorthand busyness default to 2/3/4. Then prove the first run succeeds on the bundled data.

## Context

Follow-up 15. Owner decisions, 2026-11-14 (README → Decisions):
- **D-A: option 4.** For new users and the demo only, the default is a shorter list at τ = 1.0: drop the nutrients the bundled pools can't meet, and warn in plain language which ones were left out. **Users must be able to change these values.**
- **D-B: 2/3/4.** The MCP shorthand default busyness is 2/3/4 for 3 meals, so the last meal has no cooking-time limit. For other meal counts: first meal 2, last meal 4, any others 3; a single meal stays 2. The owner gave no rule for those counts, so confirm it in the PR.
- **W7: option a.** `config/user_profile.yaml.example` is the shipped default profile. `config/user_profile.yaml` is the owner's personal profile: untrack it (it stays on disk) and never edit it.

Where the defaults live today (2026-11-14):
- **MCP busyness:** `src/mcp_server/tools.py::_schedule_days` (~line 279) builds `[2] + [3] * (n - 1)`. The `schedule` field description in `src/mcp_server/server.py` (~line 91) says "busyness 2/3/3".
- **MCP micronutrients:** `src/mcp_server/tools.py` ~line 493 sets `micronutrient_goals = daily_rdis(demographic)` (all 25) and `micronutrient_weekly_min_fraction = 1.0` when `targets.demographic` is set.
- **YAML:** `config/user_profile.yaml` and `config/user_profile.yaml.example` list all 25 goals at **τ = 0.8** (not 1.0 as follow-up 15 assumed), and the loader warns below 0.85. The committed profile still fails over HTTP with FM-4 at 1 day (BE-16 probe).
- **Flutter:** `MicronutrientGoals` defaults are all 0 and `toPlanMicronutrientGoals` omits zeros, so a new Flutter user sends **no** micronutrient goals and gets no floors at all. The Profile screen already lets the user edit every goal and τ (`profile_screen.dart`, `_microField`, `_micronutrientTauCtrl`).
- **Override:** YAML and Flutter users can already change goals. The MCP `Targets` model (`src/mcp_server/models.py` ~line 48) has only `demographic`, so an MCP user can't change the default.

Probe evidence (committed pool, 3 days): only `omega_3_g` fails alone at τ = 1.0; the other 24 pass together; all 25 need τ ≈ 0.5.

## Acceptance criteria

The nutrient list comes from the re-run probe (expected: all except `omega_3_g`). The structure is fixed:

- [ ] The decided default lives in **one** place (a constant or reference-data entry next to `rdi_by_demographic.json`'s loader). MCP, the YAML example and Flutter's default are derived from it or match it. A test asserts the MCP path and the YAML example agree.
- [ ] Re-run the D-A probe on the **sample recipes** after DATA-1, at τ = 1.0: 7 days, the MCP shorthand schedule at **2/3/4**, each of the 4 demographics. Drop every nutrient that fails, and record the table and the final list in this stub.
- [ ] MCP test: `macrova_plan_meals` with `use_sample_recipes: true`, `demographic: "adult_male"`, 3 meals (default busyness), 7 days → `status: "success"`. Fails before the change (all 25 at τ = 1.0).
- [ ] When the default leaves nutrients out, the plan result (MCP `warnings`; HTTP `warnings` when the default is applied) names them in plain language and says how to add them back (the override). No warning when the user supplied their own goals. Tests for both.
- [ ] **User override (MCP):** add an optional `targets.micronutrient_goals` (map of nutrient key → daily amount) and an optional `targets.micronutrient_weekly_min_fraction` (0 < τ ≤ 1). When given, they replace the default for that nutrient or τ. An empty map means no floors. Unknown keys are rejected with a plain-language error. The change is additive: existing calls behave as before apart from the default list. Tests: an override restores `omega_3_g`, an override lowers τ, an unknown key fails. Each fails before the change because the fields don't exist.
- [ ] **Busyness (D-B):** `_schedule_days` defaults to 2/3/4 for 3 meals, using the rule above for other counts. The `schedule` field description says 2/3/4. Test: shorthand `meals_per_day: 3` with no `busyness` gives `busyness_level`s `[2, 3, 4]`, and an explicit `busyness` still applies to every meal. Fails before the change (`[2, 3, 3]`).
- [ ] **Flutter:** a new user's Profile screen starts with the default goals for the chosen demographic, and every value stays editable. Editing one, saving and planning sends the edited value. That's a DTO and default change, which needs BE-17's demographic plumbing. Widget test: default shown, edit wins. If BE-17 is cut, record here that Flutter keeps all-zero defaults (no floors), and say so in the PR.
- [ ] **Demo profile (W7):**
  - `config/user_profile.yaml.example` gets the D-A default, in canonical `schedule_days` form with 3 meals. Test: it loads, and planning on it succeeds for 1, 3 and 7 days with the committed pool.
  - `git rm --cached config/user_profile.yaml`. The owner's local copy stays; check that `git status` shows it as ignored, not deleted.
  - When `config/user_profile.yaml` is missing, the CLI and the server either fall back to the example or fail with a message saying to copy it. Pick whichever the code already does, and test it. Document the copy step in README's quick start, next to BE-22's data-folder setup step. Whichever task lands second rebases onto the first's wording.
  - Note in the PR: the personal settings stay in git history. Untracking stops future changes from shipping; it doesn't erase past ones.
- [ ] `benchmark-audit`: 153/153, 0 regressions. Benchmark scenarios set their own micronutrient goals; if any read the example YAML, stop and report.
- [ ] OpenAPI check green (no HTTP shape change expected; the MCP fields are additive). Update the MCP tool docs and `tests/mcp_server/` for the new optional fields.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/mcp_server/tools.py` (~lines 270–300 and 400–520), `src/mcp_server/models.py` (`Targets`, `ShorthandSchedule`), `src/mcp_server/server.py` (tool field descriptions), `src/mcp_server/nutrients.py` (or wherever BE-17 moved `daily_rdis`), `data/reference/rdi_by_demographic.json`, `config/user_profile.yaml.example`, `src/data_layer/user_profile.py` (τ warning ~line 289), `frontend/lib/models/user_profile.dart` (`MicronutrientGoals` defaults), `tests/mcp_server/test_server.py`.
- Do NOT: edit `rdi_by_demographic.json` values (human review), change `config/user_profile.yaml` (the owner's real profile), or lower τ globally unless D-A says so.

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: what reads `config/user_profile.yaml` and what happens when it's missing: the CLI default path, the server's profile routes, pin and schedule writes (`src/data_layer/user_profile.py`), `scripts/export_planner_debug_artifacts.py` and tests. Any test that reads the real file must switch to the example or a fixture.
2. Re-run `docs/sprints/sprint2/probes/micro_probe.py`, pointed at the sample pool (`data/recipes/recipes.json.example`), 7 days and 2/3/4. If the default list still fails on the samples, stop and report to the owner before changing anything.
3. `REQUIRES_VERIFICATION`: whether 2/3/4 alone changes which nutrients fail. A busyness-4 slot admits more recipes, so run the probe at 2/3/4, not 2/3/3.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check`
- `benchmark-audit`: 153/153, 0 regressions
- `cd frontend && flutter analyze && flutter test` if Flutter changed

## Out of scope

- Reviewing DRI values (human-only).
- A new nutrient-picker UI. The existing Profile fields are the override in Flutter.
- Changing the committed owner profile.
