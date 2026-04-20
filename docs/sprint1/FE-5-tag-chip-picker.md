# FE-5 — Tag chip picker

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-1

## Summary

Reusable `TagChip` + `TagChipPicker` widgets. Chips are color-coded by tag type; picker is grouped by type with search.

## Context

Used in the Recipe Builder (FE-4), Slot Config (FE-8), and the `MealCard` display (FE-1). Centralizing here avoids 3 divergent implementations.

## Acceptance criteria

- [ ] `TagChip({Tag tag, bool selected = false, VoidCallback? onTap, bool dense = false})`:
  - Color palette: context = blue, time = amber, nutrition = green, constraint = red.
  - LLM-sourced tags show a small sparkle icon; unconfirmed until user interacts in Settings.
  - Dense variant for `MealCard`; regular for pickers.
- [ ] `TagChipPicker({List<String> requiredTypes, List<String> selectedSlugs, ValueChanged<List<String>> onChanged})`:
  - Renders one row per tag type, wrapping.
  - Search field filters across all types.
  - "+ New tag" inline creator (calls `POST /api/v1/tags`).
  - Emits slug list on change.
- [ ] A11y: ≥ 4.5:1 contrast for chip text against background; tested in light + dark theme.
- [ ] Widget tests cover: selection toggles, inline creation, filter search, color-per-type assertions.

## Implementation notes

- Fetch the tag registry once per screen via a Riverpod provider; invalidate on POST success.
- Keep the widget presentational; no direct HTTP calls from `TagChip` itself — picker owns side effects.
- Icon set: Material `filter_list` for picker header, `auto_awesome` for LLM-sourced.

## Out of scope

- Alias/merge UI (lives in Settings → Tags, separate follow-up; confirmation flow is a Week 2 polish).
- Drag-reordering of tags within a recipe.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/services/api_service.dart` — add `getTags(type?)` (`GET /api/v1/tags`) and `createTag(slug, display, type)` (`POST /api/v1/tags`) methods here; do not make HTTP calls from inside the widget
- `frontend/lib/widgets/app_shell.dart` — understand the widget tree context where `TagChipPicker` will be embedded (Profile, Recipe Builder, Planner config)
- `frontend/lib/screens/recipe_builder_screen.dart` — primary consumer (FE-4); confirm the prop interface `TagChipPicker` must expose before finalizing it

**Backend dependency:** `GET /api/v1/tags` and `POST /api/v1/tags` come from BE-1. These endpoints must exist before these widgets can be tested end-to-end.

**New widget location:** `frontend/lib/widgets/tags/tag_chip.dart` and `frontend/lib/widgets/tags/tag_chip_picker.dart` (or `frontend/lib/widgets/planner/` — pick one location and use it consistently; document the choice).

**Do NOT create:**
- Direct HTTP calls inside `TagChip` — the picker owns all side effects
- A separate tag color/palette file if it can live as constants in the widget file

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/services/api_service.dart` in full.** Note the HTTP client pattern and how provider methods call it — add `getTags()` and `createTag()` following the same pattern.
2. **Check whether a tag-fetching Riverpod provider exists** — if not, a small `tagRegistryProvider` that calls `getTags()` and invalidates on POST success is needed.
3. **Read `frontend/lib/screens/recipe_builder_screen.dart` (or its FE-4 spec)** to confirm the exact `TagChipPicker` props needed: `requiredTypes`, `selectedSlugs`, `onChanged`.
4. **Decide the widget file location** (`frontend/lib/widgets/tags/` vs. `frontend/lib/widgets/planner/`) — this affects FE-1, FE-4, FE-8 imports; pick one and stay consistent.
5. State the `TagChip` and `TagChipPicker` constructor signatures before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `TagChip` and `TagChipPicker` are in a single, consistent location; FE-1, FE-4, FE-8 all import from the same path
- [ ] Color palette: context = blue, time = amber, nutrition = green, constraint = red — enforced via constants, not magic values
- [ ] LLM-sourced tags show `auto_awesome` sparkle icon; unconfirmed state is visible
- [ ] Dense variant renders smaller (for `MealCard`); regular variant renders normally (for pickers)
- [ ] `TagChipPicker` fetches tag registry once per screen via Riverpod provider; invalidates on `POST` success
- [ ] "+ New tag" inline creator calls `POST /api/v1/tags` via `api_service.dart` — no direct HTTP in the widget
- [ ] A11y: ≥ 4.5:1 contrast for chip text in light and dark theme
- [ ] Widget tests pass: selection toggles, inline creation, filter search, color-per-type assertions
