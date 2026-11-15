# Sprint 2: minimal public demo

**Written:** 2026-11-14 · **Horizon:** 2 weeks (2026-11-16 to 2026-11-27) · **Planned from:** `merge-frontend-redesign` @ `ee22f5e` (PR #63), `main` @ `bd5fad9`

## Goal

A new user, and the MCP server, can plan meals successfully with the bundled data. The Flutter app shows the backend features that already exist: plain-language failures, meal-prep batches, pins and recipe tags.

This sprint closes the follow-ups left after Sprint 1, the MCP server (PR #61) and the redesign (PR #63). It adds no new planner capability.

## Prerequisites (in order)

1. **PR #63 (`merge-frontend-redesign`) merged into `main`.** Every FE task, and the Flutter DTO part of BE-17 and BE-19, is written against the redesigned widgets (`AppShell`, `TodayScreen`, `FailurePanel`, `MealCard`, `MealDetailSheet`, Macrova tokens). None of them may start against `main`'s legacy UI. Status on 2026-11-14: open, `MERGEABLE`.
2. **DOC-1 done.** It re-statuses the Sprint 1 stubs, so no Sprint 1 stub stays `todo` (roadmap Part 3, Stop 1).

## Starting state (verified 2026-11-14)

| Claim | Result | How it was checked |
|---|---|---|
| 1,328 Python tests pass | ✅ 1,328 passed (on `merge-frontend-redesign`, which equals `main` + the redesign) | `python3 scripts/run_pytest.py` |
| Benchmark 153/153 exact | ✅ committed `evaluation/harness/results/compare.json`: 153 × `MATCH`. **Not re-run**, because the harness rewrites committed result files. | read the JSON |
| OpenAPI snapshot current | ✅ | `python3 scripts/run_export_openapi.py --check` → exit 0 |
| MCP server merged | ✅ PR #61 merged; `tests/mcp_server/` present | `gh pr list` |
| PR #63 open, blocks FE | ✅ open, mergeable. `flutter analyze` clean and 102 Flutter tests pass on the branch. | `gh pr view 63`, `flutter analyze`, `flutter test` |

Environment note: `.venv` runs Python 3.10.12, while AGENTS.md says 3.12 and the session hook says CI pins 3.11. The suite passes on 3.10. Treat version-specific failures as environment issues first.

## Notes for executors

- Run each stub with the `sprint-task` skill. That skill's text names `docs/sprint1/` and bare `python -m pytest tests/ -q` / `python scripts/export_openapi.py --check`. Use this folder, and AGENTS.md's canonical commands: `python3 scripts/run_pytest.py` and `python3 scripts/run_export_openapi.py --check`.
- **Roadmap Part 3 conflict, recorded deliberately.** Part 3 says "spec at most the next 5 tasks" and "never write a new sprint doc while any stub from the previous batch is still `todo`". This sprint has 13 stubs, and 16 Sprint 1 stubs were `todo` when it was written. The mitigations:
  - DOC-1 closes Sprint 1 before any Sprint 2 code;
  - only 5 tasks are in Wave 1;
  - Wave 2 stubs expire on 2026-11-28;
  - every acceptance criterion names its test, so a stale stub fails loudly.
- `probes/` holds the read-only scripts behind the evidence in BE-16 and D-A. Run them from the repo root with `.venv/bin/python`.

## Tasks

Waves follow roadmap Part 3, which allows at most 5 tasks in flight. FE-11 moved to Wave 2 to make room for BE-22. Wave 2 stubs were written ahead of execution and **expire on 2026-11-28**: a Wave 2 stub not started by then is parked, not executed as written. Before starting any Wave 2 stub, re-run its `REQUIRES_VERIFICATION` checks.

| ID | Title | Cx | Depends on | Wave | Status |
|---|---|---|---|---|---|
| [DOC-1](./DOC-1-sprint1-closeout.md) | Close out Sprint 1 stubs | S | — | 0 | done |
| [BE-16](./BE-16-profile-request-keeps-workouts.md) | Profile → PlanRequest keeps workout slots (CLI/API parity) | S | — | 1 | done |
| [BE-18](./BE-18-to-taste-policy.md) | `to taste` only for seasonings; drop recipes that hide nutrients | M | — | 1 | done |
| [DATA-1](./DATA-1-sample-recipe-portions.md) | FDC portion weights so all 18 sample recipes are plannable | M | — | 1 | done |
| [BE-21](./BE-21-recipe-detail-nutrition.md) | Recipe detail returns real per-100 g nutrition and unit conversions (bug) | S | — | 1 | done |
| [BE-22](./BE-22-user-data-folder-starter-pack.md) | User data folder, empty starting pool, starter-pack import (W6) | M | — | 1 | done |
| [FE-11](./FE-11-plain-language-failures.md) | Plain-language failure panel per failing slot | M | P0 | 2 | done |
| [BE-17](./BE-17-plan-request-demographic-uls.md) | Optional `demographic` on PlanRequest enforces daily ULs | M | P0 | 2 | blocked: backend done, Flutter half held on the magnesium UL decision |
| [BE-19](./BE-19-recipe-save-plannable.md) | Recipe saves are plannable: unit conversions, unit rejection, sync `errors`, derived time tags | M | P0, BE-18, BE-21, BE-22 | 2 | done |
| [FE-12](./FE-12-recipe-builder-tags.md) | Recipe builder: meal-role/cuisine/cost tags and meal-prep switch | M | P0, BE-19 | 2 | done |
| [FE-13](./FE-13-unit-guard-sync-errors.md) | Unknown units fail in Flutter; sync errors shown | S | BE-19, FE-12 | 2 | done |
| [FE-14](./FE-14-meal-prep-tray.md) | Meal-prep tray, batch meal cards and create-batch sheet | M | FE-12 | 2 | done |
| [FE-15](./FE-15-pins.md) | Pin and unpin a meal; pinned meal cards | S | FE-14 | 2 | done |
| [FE-16](./FE-16-starter-pack-picker.md) | Starter-pack picker; no personal profile in the app bundle | M | P0, BE-22 | 2 | done |
| [BE-20](./BE-20-demo-micronutrient-default.md) | Demo micronutrient default (D-A), user override, MCP busyness 2/3/4 (D-B), demo profile (W7) | M | DATA-1 | 2 | todo: backend done except W7 untrack (owner) and the 1-day example plan; Flutter default open |

`P0` = PR #63 merged. Complexity: S ≈ half a day of agent work and one small PR; M ≈ one day and one PR. No task is L. If one grows past M during Phase 1 analysis, stop and split it.

Sizing check: 15 PRs in 2 weeks. The repo merged 20 PRs in 2026-10 (about 10 per two weeks) and 7 so far in 2026-11, so this is about 50% above recent pace, and well above the roadmap's July assumption of 2–3 a week. The owner chose to keep FE-15 (pins) and FE-16 (starter pack) in this sprint (2026-11-14). If Wave 1 isn't done by 2026-11-21, cut FE-13, then BE-17, in that order, to Sprint 3. If more must go, ask the owner before cutting FE-15 or FE-16.

## Dependency graph

```
P0 (PR #63 merged) ─┬─► FE-11
                    ├─► BE-17
                    ├─► FE-16
                    └─► (Flutter DTO lines in BE-19, FE-12)

BE-18 ─┐
BE-21 ─┼─► BE-19 ─► FE-12 ─┬─► FE-13
BE-22 ─┤                   └─► FE-14 ─► FE-15
       └─► FE-16

DATA-1 ─► BE-20      (D-A, D-B, W7 decided)

DOC-1, BE-16: no dependencies
```

Why each edge exists:
- BE-18 → BE-19: both edit save validation in `recipe_sync.py` (file overlap).
- BE-21 → BE-19: BE-19 builds on BE-21's working gram conversion and `unit_conversions` in the detail response.
- BE-19 → FE-12: sync must accept `cuisine`/`cost_level`. They're `RecipeTagsJson` fields, not slugs, and sync can't set them today.
- FE-12 → FE-13: same file, `recipe_builder_screen.dart`.
- FE-12 → FE-14: FE-14 needs `Recipe.isMealPrepCapable`.
- FE-14 → FE-15: same files, `meal_card.dart` and `meal_detail_sheet.dart`.
- BE-22 → BE-19: both change the recipe store (`server.py` paths, `recipe_sync.py`); the data-folder setting goes in first.
- BE-22 → FE-16: FE-16 calls the starter-pack endpoints.

Critical path: BE-18, BE-21 or BE-22 (whichever merges last) → BE-19 → FE-12 → FE-14 → FE-15, five PRs in sequence. P0 must land before FE-12.

## Order of work

1. **Wave 0.** Owner merges PR #63. Run DOC-1 (doc-only, about 15 minutes).
2. **Wave 1** (5 tasks, in parallel where files don't overlap):
   - BE-16, BE-18, BE-21, BE-22 and DATA-1 don't touch `frontend/`, so they can start before PR #63 merges.
   - D-A, D-B, W6 and W7 are already decided.
3. **Wave 2.**
   - BE-19 starts as soon as BE-18, BE-21 and BE-22 merge, even if the rest of Wave 1 is still running: it's on the critical path.
   - FE-11 and BE-17 any time after P0.
   - FE-16 after BE-22 and P0, preferably after DATA-1.
   - FE-12 after BE-19 (and P0). Then FE-13 and FE-14 in parallel, then FE-15 after FE-14.
   - BE-20 once DATA-1 is done.
4. **Close.** Run the definition-of-done demo script below and record the results in this README.

## Follow-up coverage

Every open follow-up maps to a task, a decision, or an explicit deferral.

| # | Follow-up | Disposition |
|---|---|---|
| 1 | Plain-language failures in Flutter | **FE-11** |
| 2 | Meal-prep batches in Flutter, `source`/`batch_id`, tray always visible | **FE-14** |
| 3 | Pins in Flutter | **FE-15** |
| 4 | Recipe tags: Flutter DTO, builder; app recipes dropped by pool filters | **BE-19** (server stores derived time tags for every synced recipe) + **FE-12** (Flutter sends/reads `tag_slugs_by_type`, builder chips, filter warning). Slot `required_tag_slugs`/`preferred_tag_slugs` editor: **deferred** (see Sprint 3, FE-8). The drop is confirmed: see FE-12 Context. |
| 5 | Tag registry approval UI | **Deferred**: no route can approve a proposed tag (`tag_routes.py` has list/create/rename/alias/merge only), and LLM tagging is not on the demo path. |
| 6 | Demographic picker never sent | **BE-17** (DTO + send; picker restricted to the 4 demographics the reference files have) |
| 7a | Show sync `errors` | **BE-19** (the server never fills `errors` today) + **FE-13** (show them) |
| 7b | Use `is_meal_prep_capable` | **FE-12** (read + switch) and **FE-14** (filter the create-batch recipe list) |
| 7c | Does `/api/v1/profile/schedule` matter? | **Decided: not this sprint.** Flutter sends its schedule on every plan request. The server reads the profile YAML schedule only to validate pin indices, and only when the YAML has `schedule_days`; the committed YAML has only the legacy `schedule`, so validation is skipped. FE-15 adds a test for a pin outside the requested schedule. The schedule editor (FE-8) is deferred. |
| 8 | Enforce daily ULs over HTTP | **BE-17** |
| 9 | CLI vs API disagree on the committed profile | **BE-16**: root cause found (workout slot dropped), see the stub |
| 10 | `to taste` counts as 0 g | **BE-18** |
| 11 | Units: send conversions, fail unknown units, reject at save | **BE-21** (detail returns the record's real `grams_per_unit`, not `{}`) + **BE-19** (server accepts and validates conversions; sync DTO) + **FE-13** (`toGrams`, editor guard) |
| 12 | 6 of 18 sample recipes plannable | **DATA-1** |
| 13 | MCP hosted hardening | **Deferred** (hosted-MCP track, see below) |
| 14 | MCP spec submission cases as a test | **Deferred** (hosted-MCP track). The MCP spec is not in the repo, so the 8 cases are unknown: input I-1. |
| 15 | First run fails on micronutrients | **D-A → BE-20** |
| — | Found while planning: recipe detail returns 0 kcal per 100 g for every ingredient | **BE-21** |
| — | Owner, 2026-11-14: users choose their own recipes; no one else's recipes in a new user's pool | **BE-22** (data folder, empty pool, starter-pack import) + **FE-16** (picker) |
| — | Found while planning: the owner's profile ships inside every Flutter build (`assets/dev/user_profile.yaml`) | **FE-16** |

## Sprint 1 FE stubs: dispositions

All 10 Sprint 1 FE stubs were written before the redesign. DOC-1 applies these statuses in `docs/sprints/sprint1/`.

| Sprint 1 stub | Disposition | Where it went |
|---|---|---|
| FE-1 Planner card rebuild | **Superseded** by the redesign (PR #63: `TodayScreen`, `MealPlanView`, `MealCard`, `MealDetailSheet`). The `source` card variants move to FE-14/FE-15. | FE-14, FE-15 |
| FE-2 Drag and drop | **Deferred** to Sprint 3+. Polish for zero weekly users (roadmap Stop 2), and needs a move/swap endpoint that doesn't exist. | — |
| FE-3 Meal-prep tray | **Carried**, rewritten | FE-14 |
| FE-4 Recipe builder revamp | **Merged, reduced**: Tags section and meal-prep switch → FE-12; unit guard → FE-13. Resolve-status badges and the "LLM assist" button are deferred. | FE-12, FE-13 |
| FE-5 Tag chip picker | **Merged** into FE-12: reuse `MacrovaChip`, no new chip widget. Inline "+ New tag" deferred with follow-up 5. | FE-12 |
| FE-6 LLM suggest flow | **Deferred**: depends on AI-1/AI-2 (not done). FE-11 offers the existing `assisted` planning mode instead. | — |
| FE-7 Meal-prep wizard | **Merged, reduced** to one create-batch sheet | FE-14 |
| FE-8 Slot config in Profile | **Deferred** to Sprint 3: needs the schedule-write decision (7c) and slot tag editors; L. Slot tags stay settable via YAML, CLI and MCP. | — |
| FE-9 Failure surfaces | **Carried**, rewritten against `FailurePanel` and the new explanation fields | FE-11 |
| FE-10 Forcing-mode UX | **Merged, partial**: pin control and precedence copy → FE-15. Tag-forcing mode deferred with FE-8. | FE-15 |

### Other Sprint 1 stubs that aren't done

The stub format says `done`, but Sprint 1 uses `implemented` for finished work. DOC-1 records that both mean finished.

| Stub | Status | Disposition |
|---|---|---|
| BE-15 Backend readiness contract tests | `todo` | DOC-1 checks each of its 5 bullets against `tests/api/` and `tests/test_api_v1_and_openapi.py`. Covered bullets are marked; any gap is listed for Sprint 3. `REQUIRES_VERIFICATION`. |
| AI-1 LLM suggest | `todo` | **Parked**: LLM features are optional and not on the demo path |
| AI-2 Two-stage generation | `todo` | **Parked** |
| AI-3 RecipeTagger v2 | `todo` | **Parked**. Check whether the current `recipe_tagger.py` already covers it before reviving. |
| AI-4 Nutrition guardrail | `todo` | **Parked**. `recipe_validator.py` plausibility gates may already cover it: `REQUIRES_VERIFICATION`. |
| AI-5 Duplicate detection | `todo` | **Parked**. The roadmap (2026-07-06) called AI-5 one of 3 done tasks, but its stub says `todo`: DOC-1 reconciles. |

## Decisions (owner)

D-A, D-B, W6 and W7 were resolved by the owner on 2026-11-14. The rest of D-C (W1–W8) is still open, and none of it blocks Sprint 2.

### D-A: micronutrient default for new users and the demo — **resolved: option 4, user-editable**

The question: keep all 25 RDIs and lower τ, or require a shorter list at τ = 1.0?

Evidence, from an API probe on 2026-11-14 (`probes/micro_probe.py`): committed profile macros, the 32-recipe committed pool, 3 days, no workout slot, deterministic.

| Micronutrient goals | τ | Result |
|---|---|---|
| none | — | success |
| each of the 25 alone | 1.0 | success for 24; **`omega_3_g` alone → FM-4** |
| all except `omega_3_g` (24) | 1.0 | success |
| all 25 | 0.8 / 0.7 | FM-4 |
| all 25 | 0.5 | success |

Not tested yet: the 18 sample recipes (only 6 plannable until DATA-1 lands), 7 days, and the workout slot. BE-20 re-runs the probe after DATA-1.

Options considered:
1. Shorter list at τ = 1.0. Drop the nutrients the bundled pools can't meet (today only omega-3; re-check after DATA-1).
2. All 25 at a lower τ. It takes τ ≈ 0.5 here, which makes the weekly floor close to meaningless for every nutrient.
3. No micronutrient floors by default; daily ULs only.
4. Option 1 plus a plain-language warning naming the nutrients left out.

**Decision: option 4, as the default for new users and the demo only.** Users must be able to change those values: the default is a starting point, not a cap.
- **Flutter:** goals and τ are already editable per nutrient on the Profile screen. BE-20 only changes where the starting values come from.
- **YAML:** already editable (`micronutrient_goals`, `micronutrient_weekly_min_fraction`).
- **MCP:** `targets` takes only `demographic` today, so there's no override. BE-20 adds an optional, additive override.

Applies in BE-20.

**D-A addendum (owner, 2026-11-15).** BE-20's probe re-run found that no goal list planned at all with the daily ULs on: the 350 mg magnesium UL rejected every day, even with no micronutrient floors (see the BE-20 probe record). Decided:
1. **Supplement-only ULs are not enforced against food.** The IOM ULs for magnesium (350 mg) and niacin (35 mg) apply to supplemental/fortified intake only, so `data/reference/ul_by_demographic.json` sets `magnesium_mg` and `b3_niacin_mg` to `null` for all four demographics (as `sodium_mg` already is), with a note in the file. No other reference value changes.
2. **The default list may differ by demographic.** Per-demographic lists, still defined in one place.

### D-B: MCP shorthand schedule default busyness — **resolved: 2/3/4**

Options considered: (1) keep 2/3/3; (2) have the assistant ask; (3) 4/4/4.

**Decision: 2/3/4.** The first meal is ≤ 15 min, the second ≤ 30 min, and the third has no cooking-time limit, which frees at least one slot from cooking-time constraints.
- Today `src/mcp_server/tools.py::_schedule_days` builds `[2] + [3] * (n - 1)`, and the `schedule` field description in `src/mcp_server/server.py` says "busyness 2/3/3".
- **For `meals_per_day` other than 3** the owner gave no rule. BE-20 uses: first meal 2, last meal 4, any others 3, and a single meal stays 2. Confirm this in the BE-20 PR.

Applies in BE-20; the demo script and BE-20's probe use 2/3/4.

### D-C: W1–W8, cloud user simulation (still open)

These come from the owner's draft spec "a cloud agent can use Macrova like a new user" (2026-10-08). The spec isn't committed, so the questions are restated here. W6 and W7 are decided. The other six are **open**; option (a) is recommended for each. The spec's own delivery plan (docs pass; `examples/` with checks; Make targets and data isolation; error surfaces and a guide) is Sprint 3 work.

| W   | Question (recommended option a)                                                                                                                             | Relation to Sprint 2                                                                                                                                                                                                       | Disposition                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| W1  | What counts as "the app" (**a**: CLI + HTTP API now, Flutter web later)                                                                                     | Demo script steps 1–3 already test MCP, HTTP and CLI. Step 4 (Flutter) is human-checked.                                                                                                                                   | Already followed; can decide now                                                                           |
| W2  | One entry point (**a**: Make targets `setup`, `doctor`, `demo`, `serve`, `health`, `stop`, `ingredients`, `journey-check`)                                  | No task                                                                                                                                                                                                                    | Sprint 3                                                                                                   |
| W3  | Where the guide lives (**a**: `docs/usage/first-meal-plan.md` + a `simulate-user` skill)                                                                    | No task                                                                                                                                                                                                                    | Sprint 3                                                                                                   |
| W4  | Example data (**a**: hand-written `examples/` with `expected.json`)                                                                                         | No task. The demo script's inputs (new-user profile, 7-day request) would fit there.                                                                                                                                       | Sprint 3; consider for the demo inputs                                                                     |
| W5  | Check strictness (**a**: outcomes and tolerances, not exact recipe ids)                                                                                     | The demo script already checks outcomes (`status`, matching codes)                                                                                                                                                         | Already followed; can decide now                                                                           |
| W6 | Keep a session from changing committed data | **Decided 2026-11-14:** a `MACROVA_DATA_DIR` setting, with one change from option a: the user folder starts with an **empty** recipe pool instead of a copy of `data/`. The 18 sample recipes become an optional starter pack the user picks from. | Applied in BE-22, FE-16 |
| W7 | Default profile | **Decided 2026-11-14: option a.** `config/user_profile.yaml.example` is the shipped default and gets the D-A defaults (BE-20). `config/user_profile.yaml` holds the owner's personal settings: BE-20 removes it from git with `git rm --cached` (the local copy stays), as `.gitignore` already intends. A fresh clone copies the example. BE-16, the probes and demo step 3 use the example. | Applied in BE-16, BE-20 |
| W8  | Flutter web tier (**a**: spec it after the core passes: semantics flag, `Semantics`/`Key` labels, Linux setup doc, `make web`)                              | FE-11, FE-14 and FE-15 build the screens W8 would label (failure panel, tray, pins)                                                                                                                                        | Sprint 3+; adding `Key`s in those FE tasks now is cheap                                                    |

The spec's fresh-clone findings that are already covered here:
- the first run fails on micronutrients → D-A / BE-20;
- CLI vs API disagree → BE-16;
- `to taste` counts as 0 g → BE-18.

Not covered (Sprint 3):
- The CLI's Markdown output hides `report.failures`.
- OpenAPI doesn't mark `schedule` as required, but a request without one gets a 400 with no details.
- Stale setup docs, no doc on starting the API server, and no stated supported Python range.

**Blocks:** nothing left in Sprint 2 (W6 and W7 are decided). The rest blocks nothing in Sprint 2 and is needed before simulation-based acceptance in Sprint 3.

### Inputs needed (not decisions)

- **I-1: the MCP spec.** PR #61 cites "the MCP spec's list of repo changes", but the spec isn't in the repo, so follow-up 14's 5 positive and 3 negative submission cases can't be written down. Commit it (or just the 8 cases) to `docs/` before the hosted-MCP track starts.
- **I-2: `USDA_API_KEY` for DATA-1 — resolved.** The key is set in the gitignored `.env` on the owner's machine (checked 2026-11-14), so DATA-1 can run its fetch step there. Never commit the key or print it in logs or PRs.

## Human-only work (tracked, not planned as agent tasks)

| Item | Why it's human-only | Blocks |
|---|---|---|
| Review `data/reference/ingredient_nutrition.json` against FDC (`review_status: draft`, 78 entries) | Reviewed data must be checked by a person; flip to `reviewed` only when every entry has a reviewed date | Calling the nutrition "reviewed" in any public demo copy |
| Review draft IOM DRI values in `data/reference/rdi_by_demographic.json` | Same | BE-20's final values, public demo copy |
| Privacy policy, terms and a domain for the hosted MCP | Legal and account decisions | The whole hosted-MCP track (follow-ups 13, 14) |

## Deferred to Sprint 3

| Item | Reason |
|---|---|
| **Hosted-MCP track:** per-client rate limiting, USDA request budget (1,000 req/h per shared IP), submission-case tests (follow-ups 13, 14) | Hosting is blocked on human-only work (privacy policy, terms, domain) and input I-1. Hardening a server with no host is inventory (roadmap Stop 1). The local stdio MCP demo works without it. Start this track when the legal items and I-1 are done. |
| Tag registry approval UI (follow-up 5, rest of FE-5) | Needs a new backend route to change `eligibility` from `proposed` to `approved`, plus UI. LLM tagging isn't on the demo path. |
| Slot config / schedule editor and slot required/preferred tag editors (FE-8, rest of FE-10, follow-ups 4 and 7c) | L. Needs a decision on whether Flutter or the server YAML owns the schedule. Slot tags are usable via YAML, CLI and MCP today. |
| Drag and drop (FE-2) | Polish, and no move/swap endpoint exists |
| LLM suggest flow (FE-6), AI-1 to AI-5 | LLM is optional; FE-11 uses the existing assisted mode as the recipe-gap CTA |
| Duplicate recipes in `data/recipes/recipes.json` (for example several "Oatmeal with Fruits", "Grilled Chicken with Vegetables", "Quinoa Salad") | Found while planning. Affects pool variety and HC-8, not correctness. Needs a dedupe decision. BE-18 drops the to-taste variants anyway. |

## Findings while planning (code vs. the follow-up list)

1. **CLI vs API (follow-up 9).** The cause is neither `liked_foods` nor ULs. `build_plan_request_from_profile` drops the workout slot (BE-16). The existing parity test compares that function with itself.
2. **ULs are enforced only by MCP.** The CLI builds `resolved_ul` for a hard-coded `adult_male` and never passes it. The API never builds one. The YAML `demographic` key is never read. AGENTS.md's "ULs enforced per-day" holds only when `resolved_ul` is passed (BE-17).
3. **Committed τ is 0.8, not 1.0** (follow-up 15). The committed profile still fails (FM-4). MCP hard-codes τ = 1.0. Flutter new users send no micronutrient goals at all.
4. **Sync `errors` is never filled** (follow-up 7a), so there was nothing for Flutter to show (BE-19).
5. **Recipe detail returns zero nutrition** on every ingredient line (`_convert_quantity_to_grams` doesn't exist; the error is swallowed) (BE-21).
6. **Flutter offers `teen_male`, `teen_female` and `child`**, which the RDI/UL reference files don't have (BE-17).
7. **No route approves a proposed tag** (follow-up 5 needs backend work; deferred).
8. **No bundled recipe is meal-prep capable**, so batch creation is impossible with bundled data until a user marks one (FE-12 → FE-14).
9. **Tagged app recipes get fixed `cuisine: unknown`, `cost_level: standard`, `prep_time_bucket: weeknight_meal`**, and untagged ones get no entry (BE-19). Cuisine and cost can't be set through sync at all.
10. **Some sample-recipe gaps are malformed units** (`tbsp, diced`, `cup, whole pieces`), not missing weights (DATA-1).
11. **`data/recipes/recipes.json` has duplicate recipe names** with different ingredients (deferred).
12. The CLI on the committed profile gives different failures by horizon: 1 day FM-1, 3 days FM-MACRO-INFEASIBLE, 7 days FM-5 (attempt limit, 50,000 attempts).
13. **An empty pool doesn't crash, but the message is weak.** HTTP: `FM-1`, "No recipes were available to plan with.", `cause: EMPTY_POOL`, with `recipe_could_help: false` (wrong). CLI: `Success: False`, TC-2, exit 0, no reason. MCP already asks for recipes or `use_sample_recipes` (BE-22).
14. **The benchmark doesn't use `data/recipes/recipes.json`.** It has its own library (`evaluation/benchmark/recipes.json`), so making the user pool start empty can't move the 153/153 baseline. About 20 test files read `recipes.json` as a fixture and keep doing so.
15. **The 18 sample recipes are the first 18 of the committed 32** (same ids and names), with tags already in `recipe_tags.json`. The other 14 include LLM-generated `llm_…` recipes.
16. **Flutter packages the owner's profile and an outdated recipe copy into every build** (`frontend/assets/dev/`, listed in `pubspec.yaml`). Merging them is off by default, but the files ship (FE-16).

## Definition of done

- [ ] Every stub in this folder is `done`, or re-statused `blocked`/`parked` with a one-line reason.
- [ ] `python3 scripts/run_pytest.py` green; `python3 scripts/run_export_openapi.py --check` green.
- [ ] `benchmark-audit`: 153/153, 0 regressions against `main` (`diff_results.py --base main` exits 0) after the last planner- or nutrition-touching task.
- [ ] `cd frontend && flutter analyze && flutter test` green.
- [ ] **Demo script** passes on a fresh clone with no `.env`, and results are recorded here:
  1. MCP stdio: `macrova_plan_meals` with `use_sample_recipes: true`, a demographic, 3 meals with the default shorthand busyness (2/3/4, D-B), 7 days → `status: "success"`, with a warning naming any nutrient left out of the default (needs DATA-1 + BE-20).
  2. HTTP API with `MACROVA_DATA_DIR` set to a fresh folder (BE-22). An empty pool gives the empty-pool message. After importing a chosen subset of the starter pack, the Flutter new-user default profile for 7 days → `plan_status: "success"`, and `git status` stays clean.
  3. CLI and API on `config/user_profile.yaml.example` report the same `termination_code` and failure codes (BE-16).
  4. Flutter: an induced failure (an impossible calorie ceiling) shows explanation, fix and code on the failing slot (FE-11). A batch created in the tray appears as batch meals in the next plan (FE-14). A pinned meal stays put on re-plan (FE-15). A new user starts with an empty library, picks recipes from the starter pack, and plans with only those (FE-16).
- [ ] The Sprint 1 dispositions above are applied (DOC-1).
