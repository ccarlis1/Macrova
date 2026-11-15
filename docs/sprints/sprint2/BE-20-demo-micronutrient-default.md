# BE-20 — Demo micronutrient default (D-A), user override, MCP busyness 2/3/4 (D-B)

**Status:** blocked (owner decision: supplement-only magnesium/niacin ULs applied to food; see probe record below)  ·  **Complexity:** M  ·  **Depends on:** DATA-1

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

## Probe re-run (2026-11-14) — STOPPED, owner decision needed

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

## Out of scope

- Reviewing DRI values (human-only).
- A new nutrient-picker UI. The existing Profile fields are the override in Flutter.
- Changing the committed owner profile.
