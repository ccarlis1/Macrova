# BE-20 — Demo micronutrient default (D-A), user override, MCP busyness 2/3/4 (D-B)

**Status:** done  ·  **Complexity:** M  ·  **Depends on:** DATA-1

## Summary

Apply the owner's D-A decision to every place a new user's micronutrient floors come from:
- the MCP `demographic` path;
- `config/user_profile.yaml.example`;
- the Flutter new-user default.

Let users override that default where they can't today (MCP). Change the MCP shorthand busyness default to 2/3/4. Then prove the first run succeeds on the bundled data.

## Context

Follow-up 15. Owner decisions, 2026-11-14 (README → Decisions):
- **D-A: option 4.** For new users and the demo only, the default is a shorter list at τ = 1.0: drop the nutrients the bundled pools can't meet, and warn in plain language which ones were left out. **Users must be able to change these values.**
- **D-B: 2/3/4.** The MCP shorthand default busyness is 2/3/4 for 3 meals, so the last meal has no cooking-time limit. For other meal counts: one meal 2; two meals 2/4; four or more first 2, last 4, others 3. Confirmed by the owner (2026-11-15).
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

- [x] The decided default lives in **one** place (a constant or reference-data entry next to `rdi_by_demographic.json`'s loader). MCP, the YAML example and Flutter's default are derived from it or match it. A test asserts the MCP path and the YAML example agree.
  - Done: `src/data_layer/upper_limits.py` → `DEFAULT_MICRONUTRIENT_LEFT_OUT` (per demographic), `DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION = 1.0`, `default_micronutrient_goals()` / `default_micronutrient_left_out()`. Test: `tests/test_micronutrient_default.py::test_mcp_path_and_yaml_example_agree_on_the_default`. Flutter: read-only `GET /api/v1/micronutrient_defaults?demographic=<demographic>` (owner decision 2026-11-15) returns `{demographic, micronutrient_goals, left_out, micronutrient_weekly_min_fraction}`, all derived from those helpers; unknown or missing demographic → 400 `INVALID_REQUEST`. It doesn't change planning (`/api/v1/plan` without goals still applies no floors). Tests: `tests/api/test_micronutrient_defaults.py`, `tests/test_api_v1_and_openapi.py::test_openapi_micronutrient_defaults_contract`; contract in `docs/contracts/plan-response.md`. Wiring the Profile screen to it is the frontend track's.
- [x] Re-run the D-A probe on the **sample recipes** after DATA-1, at τ = 1.0: 7 days, the MCP shorthand schedule at **2/3/4**, each of the 4 demographics. Drop every nutrient that fails, and record the table and the final list in this stub.
  - Done: see "Probe re-run (2026-11-15)" below.
- [x] MCP test: `macrova_plan_meals` with `use_sample_recipes: true`, `demographic: "adult_male"`, 3 meals (default busyness), 7 days → `status: "success"`. Fails before the change (all 25 at τ = 1.0).
  - `tests/mcp_server/test_server.py::test_sample_recipes_with_demographic_default_plan_seven_days`.
- [x] When the default leaves nutrients out, the plan result (MCP `warnings`; HTTP `warnings` when the default is applied) names them in plain language and says how to add them back (the override). No warning when the user supplied their own goals. Tests for both.
  - MCP: `test_default_warning_names_left_out_nutrients_and_the_override`, `test_no_left_out_warning_when_the_user_sends_goals`, `test_no_left_out_warning_without_a_demographic`. HTTP never applies the default (a request without `micronutrient_goals` still plans with no floors, as before; the CLI/YAML path sends the example's explicit goals), so there is no HTTP case to warn on.
- [x] **User override (MCP):** add an optional `targets.micronutrient_goals` (map of nutrient key → daily amount) and an optional `targets.micronutrient_weekly_min_fraction` (0 < τ ≤ 1). When given, they replace the default for that nutrient or τ. An empty map means no floors. Unknown keys are rejected with a plain-language error. The change is additive: existing calls behave as before apart from the default list. Tests: an override restores `omega_3_g`, an override lowers τ, an unknown key fails. Each fails before the change because the fields don't exist.
  - `test_override_restores_a_left_out_nutrient`, `test_override_replaces_a_value_and_zero_removes_it`, `test_override_lowers_tau`, `test_bad_micronutrient_override_is_an_error`. A value of 0 removes that nutrient's goal. `requested_targets` now echoes the two new fields (null when omitted), and `weekly_micronutrients` lists the goals in effect rather than all 25 RDIs.
- [x] **Busyness (D-B):** `_schedule_days` defaults to 2/3/4 for 3 meals, using the rule above for other counts. The `schedule` field description says 2/3/4. Test: shorthand `meals_per_day: 3` with no `busyness` gives `busyness_level`s `[2, 3, 4]`, and an explicit `busyness` still applies to every meal. Fails before the change (`[2, 3, 3]`).
  - `tools.default_busyness_levels`; tests `test_shorthand_default_busyness_is_2_3_4`, `test_shorthand_default_busyness_rule_for_other_meal_counts` (1 → [2], 2 → [2, 4], 4 → [2, 3, 3, 4]), `test_explicit_shorthand_busyness_still_applies_to_every_meal`, `test_tool_schema_describes_the_new_fields_and_2_3_4`. The rule for counts other than 3 is confirmed by the owner (2026-11-15).
- [x] **Flutter:** a new user's Profile screen starts with the default goals for the chosen demographic, and every value stays editable. Editing one, saving and planning sends the edited value. That's a DTO and default change, which needs BE-17's demographic plumbing. Widget test: default shown, edit wins. If BE-17 is cut, record here that Flutter keeps all-zero defaults (no floors), and say so in the PR.
  - Done: no client copy of the values. `MicronutrientDefaults` + `ApiService.fetchMicronutrientDefaults` read the endpoint; `ProfileProvider.loadMicronutrientDefaults` (injectable fetch fn) caches per demographic and never changes the saved profile. The Profile screen fills the goal fields and τ only when every goal field is empty/zero or still holds an unedited default: on open with a saved demographic and no goals, and on picking a demographic. Typed or saved goals are never replaced; "Not set" fetches nothing. Loading hint; on failure a notice with Retry and the fields untouched; a line names the left-out nutrients and says to enter a value to add one back. Nothing is sent until Save and plan. Saved goals count as the user's own even if they came from the default. Tests: `frontend/test/screens/profile_screen_micronutrient_default_test.dart` (default shown, edit wins in the built `PlanRequest`, own goals kept, failure + Retry, loading, left-out line, Not set), `test/micronutrient_defaults_api_test.dart`, `test/providers/profile_provider_defaults_test.dart`; rules in `docs/frontend/state-invariants.md`.
- [x] **Demo profile (W7):**
  - [x] `config/user_profile.yaml.example` gets the D-A default, in canonical `schedule_days` form with 3 meals. Test: it loads, and planning on it succeeds for 3 and 7 days with the committed pool (was "1, 3 and 7"; changed by the owner decision below).
    - Done for 3 and 7 days (`tests/test_micronutrient_default.py`, HTTP with `demographic: adult_male` ULs on; the CLI gives the same). **1 day fails** (HTTP `partial`, FM-1 on meal 3; MCP FM-4): at D = 1 every floor must be met in one day. On the committed pool every nutrient passes alone, no single extra drop fixes it, and a greedy pass keeps 21 (drops `vitamin_e_mg` and `calcium_mg` as well); 2 days needs `calcium_mg` dropped. **Owner decision (2026-11-15): a 1-day plan with the full default floors is allowed to fail; the default lists stay as they are.** Why: weekly floors are met on the horizon total, so over several days a low day is offset by a high one; a 1-day plan can't average, so that one day must hit every RDI at once. `test_example_profile_one_day_outcome_is_pinned` pins today's 1-day result (HTTP `partial`, `TC-2`, FM-1 at day 0, slot 2) so a change is noticed. The CLI default stays `--days 1`; the first-run commands in README, QUICK_START and USAGE use `--days 3` and say that a 1-day plan with the full default goals can fail (plan 3+ days, or lower or remove goals).
  - [x] `git rm --cached config/user_profile.yaml`. The owner's local copy stays; check that `git status` shows it as ignored, not deleted.
    - Done by the owner in 94c7c42 ("BE-20: Stop tracking the personal config/user_profile.yaml (W7)"); the repo's path-guard hook reserves the command for the owner. The file stays on disk and `git check-ignore` reports it ignored (`.gitignore:52`). Tests no longer read, create or change that file (session guard in `tests/conftest.py`).
  - [x] When `config/user_profile.yaml` is missing, the CLI and the server either fall back to the example or fail with a message saying to copy it. Pick whichever the code already does, and test it. Document the copy step in README's quick start, next to BE-22's data-folder setup step. Whichever task lands second rebases onto the first's wording.
    - Done: the code already fails with a copy hint (CLI exit 1) and the server treats the file as empty (no pins, empty schedule; the first write creates it). Tests: `tests/test_profile_file_missing.py`. README step 1 and QUICK_START (next to "Use Your Own Data Folder").
  - Note in the PR: the personal settings stay in git history. Untracking stops future changes from shipping; it doesn't erase past ones.
- [x] `benchmark-audit`: 153/153, 0 regressions. Benchmark scenarios set their own micronutrient goals; if any read the example YAML, stop and report.
  - 153 → 153 exact, 0 regressed, `diff_results.py --base main` exit 0, after the UL change and again at the end. No scenario reads the example YAML.
- [x] OpenAPI check green (no HTTP shape change expected; the MCP fields are additive). Update the MCP tool docs and `tests/mcp_server/` for the new optional fields.
  - `--check` exit 0, no HTTP change. MCP docs are the tool's field descriptions (`models.py`, `server.py`).

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

## Probe re-run (2026-11-14) — stopped, superseded by the 2026-11-15 run below

Run: `.venv/bin/python docs/sprints/sprint2/probes/micro_probe_be20.py 7 <demographic>` (a copy of
`micro_probe.py` that goes through the MCP tool path: the 18 sample recipes via `use_sample_recipes`,
7 days, 3 meals at busyness **2/3/4**, macros from `config/user_profile.yaml.example`
(2400 kcal, 150 g protein, fat 50–100 g), τ = 1.0, the demographic's daily ULs enforced as BE-17 wires them).

**Result: no goal list works, not even an empty one.** With the ULs on, every demographic fails before any
micronutrient floor is added:

| Demographic | No goals (ULs only) | All 25 | Each alone | All minus failing |
|---|---|---|---|---|
| adult_male | partial, FM-MACRO-INFEASIBLE | failed, FM-4 | all 25 fail | 0 left → FM-MACRO-INFEASIBLE |
| adult_female | partial, FM-MACRO-INFEASIBLE | failed, FM-4 | all 25 fail | 0 left → FM-MACRO-INFEASIBLE |
| pregnancy | partial, FM-MACRO-INFEASIBLE | failed, FM-4 | all 25 fail | 0 left → FM-MACRO-INFEASIBLE |
| lactation | partial, FM-MACRO-INFEASIBLE | failed, FM-4 | all 25 fail | 0 left → FM-MACRO-INFEASIBLE |

Cause: `ul_by_demographic.json` sets a **magnesium UL of 350 mg/day** for all four demographics, and the
planner applies it to magnesium from food. (In the IOM DRIs that UL covers supplemental magnesium only.)
No 3-meal day at 2400 kcal from these pools stays under 350 mg, so every day fails. For `adult_male`
the magnesium RDI (400 mg) is also above that UL, so a magnesium floor can never be met. The same holds
on the committed 32-recipe pool over HTTP: `config/user_profile.yaml.example` (`demographic: adult_male`),
no micronutrient goals → `plan_status: partial`, FM-MACRO-INFEASIBLE at 1, 3 and 7 days; without the
demographic it succeeds. Without micronutrient goals and without ULs, the sample pool succeeds at 1, 3
and 7 days with both 2/3/3 and 2/3/4. The UL failure is also reported as FM-MACRO-INFEASIBLE ("no
combination … meets your daily calorie and macro targets"), which points the user at the wrong fix.

Diagnostic only (`PROBE_DROP_UL=magnesium_mg`, the magnesium UL removed in memory; the reference file is
unchanged):

| Demographic | No goals | All 25 | Fail alone at τ = 1.0 | All minus those |
|---|---|---|---|---|
| adult_male | success | FM-4 | omega_3_g, omega_6_g | 23 → success |
| adult_female | success | FM-4 | omega_3_g, omega_6_g | 23 → success |
| pregnancy | success | FM-4 | iron_mg, omega_3_g, omega_6_g | 22 → success |
| lactation | success | FM-4 | vitamin_a_ug, vitamin_e_mg, omega_3_g, omega_6_g | 21 → success |

So, if the magnesium UL question is settled, the default would be "all except omega_3_g and omega_6_g"
for the adults, with pregnancy and lactation dropping one and two more. That differs by demographic,
which this stub doesn't anticipate.

**Final list: none chosen.** Implementation stopped here per the pre-implementation rule ("if the default
list still fails on the samples, stop and report to the owner"). Owner decisions needed: (1) how the
supplement-only ULs (magnesium; niacin's 35 mg UL is also supplement-only in the IOM tables) apply to food;
that's a reference-data review or a planner rule, neither of which BE-20 may change; (2) whether the default
list may differ by demographic.

### Owner decision (2026-11-15)

Both questions above are decided (README → D-A addendum): magnesium and niacin ULs are set to `null` in
`ul_by_demographic.json` for all four demographics (supplement-only, not enforced against food), and the
default list may differ by demographic. The probe is re-run below with the real reference data.

## Probe re-run (2026-11-15), after the UL decision

Same probe, real reference data (magnesium and niacin ULs now `null`), no in-memory changes. 18 sample
recipes, 7 days, 2/3/4, τ = 1.0, daily ULs on, macros from the example (2400 kcal, 150 g protein,
fat 50–100 g). The goal list under test goes in through `targets.micronutrient_goals`.

| Demographic | No goals (ULs only) | All 25 | Fail alone at τ = 1.0 | All minus those | Extra drop needed |
|---|---|---|---|---|---|
| adult_male | success | failed, FM-4 | omega_3_g, omega_6_g | 23 → success | none |
| adult_female | success | failed, FM-4 | omega_3_g, omega_6_g | 23 → success | none |
| pregnancy | success | failed, FM-4 | omega_3_g, omega_6_g | 23 → partial, FM-5 | any one of vitamin_e_mg, iron_mg |
| lactation | success | failed, FM-4 | vitamin_e_mg, omega_3_g, omega_6_g | 22 → success | none |

Pregnancy: each nutrient passes alone, but the 23 together hit the search limit (FM-5). Dropping either
`vitamin_e_mg` or `iron_mg` as well succeeds. The default drops `vitamin_e_mg` (first in reference order,
and it keeps iron, which matters in pregnancy, tracked). Swap it for `iron_mg` in
`DEFAULT_MICRONUTRIENT_LEFT_OUT` if the owner prefers.

**Final default (τ = 1.0): each demographic's RDIs minus**
- adult_male: `omega_3_g`, `omega_6_g` (23 goals)
- adult_female: `omega_3_g`, `omega_6_g` (23 goals)
- pregnancy: `vitamin_e_mg`, `omega_3_g`, `omega_6_g` (22 goals)
- lactation: `vitamin_e_mg`, `omega_3_g`, `omega_6_g` (22 goals)

With that default, MCP shorthand (3 meals, default busyness) on the sample recipes succeeds for every
demographic at 3 and 7 days, and fails at 1 day (FM-4). `config/user_profile.yaml.example`
(adult_male default, ULs on) on the committed pool over HTTP and the CLI: 1 day fails (FM-1), 3 and 7 days
succeed. The sample pool gives the same result.

## Probe re-run (2026-11-15), after DATA-2 corrected vitamin D

DATA-2 found `vitamin_d_iu` in the ingredient table about 40x too high (mapper bug) and corrected it
from FDC. Same probe as above (18 sample recipes, 7 days, 2/3/4, τ = 1.0, daily ULs on, macros from the
example: 2400 kcal, 150 g protein, fat 50–100 g), real reference data, run per demographic:
`.venv/bin/python docs/sprints/sprint2/probes/micro_probe_be20.py 7 <demographic>`.

| Demographic | No goals (ULs only) | All 25 | Fail alone at τ = 1.0 | All minus those | Extra drop that succeeds | Current default list |
|---|---|---|---|---|---|---|
| adult_male | success | failed, FM-4 | omega_3_g, omega_6_g | 23 → success | none needed | success |
| adult_female | success | failed, FM-4 | omega_3_g | 24 → partial, FM-5 | `vitamin_d_iu` or `omega_6_g` | success |
| pregnancy | success | failed, FM-4 | omega_3_g | 24 → partial, FM-5 | `omega_6_g` only | success |
| lactation | success | failed, FM-4 | omega_3_g | 24 → partial, FM-5 | `omega_6_g` only (dropping `vitamin_d_iu` crashes, see below) | success |

What changed: `omega_6_g` now passes alone for adult_female, pregnancy and lactation, and `vitamin_e_mg`
no longer fails for lactation (the inflated vitamin D had pushed vitamin-D-rich recipes over the 4,000 IU
UL, which removed them from the pool). Omega-6 is still needed as the extra drop in every demographic, so
"omega_3_g + omega_6_g" plans for all four (checked directly: 23 goals → success for each).

**Default lists: unchanged.** Every current list still plans at 7 days, nothing needs more than 3 left out
and every demographic plans without goals, so `DEFAULT_MICRONUTRIENT_LEFT_OUT` stays as above.
Owner option: pregnancy and lactation could now keep `vitamin_e_mg` (22 → 23 goals, also succeeds). It
was not changed here because the Flutter tests pin "Left out: Vitamin E, Omega-3, Omega-6" for pregnancy
(`frontend/test/screens/profile_screen_micronutrient_default_test.dart`,
`frontend/test/providers/profile_provider_defaults_test.dart`), which DATA-2 may not edit.

Example profile on the committed pool (adult_male, ULs on), CLI and HTTP: **1 day now succeeds**
(`TC-4`; was partial / FM-1), 3 and 7 days succeed. `test_example_profile_one_day_outcome_is_pinned`
pins the new result. MCP shorthand on the sample recipes with each demographic's default (2400 kcal)
now succeeds at 1, 3 and 7 days (was FM-4 at 1 day). The first-run docs (README, QUICK_START, USAGE) keep
their "a 1-day plan with the full default goals can fail" note as a general caution; with the bundled pools
it no longer fails, so the owner may drop or soften it.

Found by the probe: on lactation, goals = RDIs minus `omega_3_g` and `vitamin_d_iu` make
`tools.plan_meals` raise `PlannerStateError: negative weekly micronutrient potassium_mg=-1.24e-09`
(`src/planning/phase7_search.py::_validate_planner_state` via `_unwind_to`): floating-point drift when
backtracking subtracts a tracker total. Planner bug, not data; not fixed here.

## Out of scope

- Reviewing DRI values (human-only).
- A new nutrient-picker UI. The existing Profile fields are the override in Flutter.
- Changing the committed owner profile.
