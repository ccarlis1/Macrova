# FE-4 — Recipe Builder revamp

**Status:** todo  ·  **Complexity:** L  ·  **Depends on:** DM-2, BE-1, FE-5

## Summary

Rebuild the recipe creation/edit screen with three collapsible sections: Basics, Ingredients, Tags. Required-tag guard blocks save.

## Context

The current builder reinforces spreadsheet feel. This rebuild also lands the "Meal-prep capable" switch and the typed tag UI the whole sprint depends on for data quality.

## Acceptance criteria

- [ ] Sections:
  - **Basics** — name, cooking time (minutes), default servings, "Meal-prep capable" switch (toggling adds/removes the `context:meal-prep` tag; switches `default_servings` minimum to 2 when ON).
  - **Ingredients** — autocomplete from USDA + local DB via existing endpoints. Each row shows a resolve status badge:
    - ✓ resolved
    - ⚠ ambiguous (tap to pick among candidates)
    - ✗ unresolved (tap for "Try USDA API" / "Create custom")
  - **Tags** — four chip rows (context, time, nutrition, constraint). `context` and `time` rows marked required with a red asterisk.
- [ ] Save is disabled until:
  - Name non-empty.
  - ≥ 1 ingredient resolved.
  - `context` has ≥ 1 tag AND `time` has exactly 1 tag.
- [ ] Sticky "LLM assist" button in the top bar opens the suggest→approve side sheet (FE-6).
- [ ] When `cooking_time_minutes` changes, the `time-*` tag updates in place unless the user has manually overridden it (show a small "auto" indicator).
- [ ] Widget tests:
  - Required-tag guard blocks save and shows an inline error.
  - "Meal-prep capable" toggle adds the tag and enforces `default_servings >= 2`.
  - Time-tag auto-update respects manual override.

## Implementation notes

- Reuse `TagChip` + `TagChipPicker` from FE-5.
- Keep the three sections as distinct widgets with their own providers; the save button reads a derived "isValid" flag.
- Server-side validation still runs; client-side is for UX, not trust.

## Out of scope

- LLM assist panel itself (FE-6 owns it).
- Batch creation UI (FE-7).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/recipe_builder_screen.dart` — `RecipeBuilderScreen`; this is rebuilt, not replaced; identify sections to migrate and what must stay (ingredient USDA/local autocomplete, nutrition total display, save action)
- `frontend/lib/providers/recipe_provider.dart` — recipe state; save and validation reads from here; do not introduce a second state source
- `frontend/lib/models/recipe.dart` — `Recipe_frontend`; confirm `default_servings` and `tags` fields exist (DM-2 output on the backend; Flutter model may need updating)
- `frontend/lib/services/api_service.dart` — ingredient autocomplete endpoints (`GET /api/v1/ingredients/search`, `POST /api/v1/ingredients/resolve`) already implemented; reuse these
- `frontend/lib/widgets/planner/tag_chip.dart` (FE-5 output) — **import** `TagChip` and `TagChipPicker` from here; do not reimplement

**Do NOT create:**
- A reimplementation of `TagChip` or `TagChipPicker` — use FE-5's widgets
- A second ingredient autocomplete path
- The LLM assist panel (FE-6)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/recipe_builder_screen.dart` in full.** Map what currently exists: ingredient rows, nutrition display, save logic. Identify what is kept vs. rebuilt in the three-section layout.
2. **Read `frontend/lib/providers/recipe_provider.dart`.** Confirm the recipe save API and validation state hook.
3. **Read `frontend/lib/models/recipe.dart`.** Check whether `default_servings` and `tags` fields are present (they come from DM-2 backend changes — the Flutter model may need updating here).
4. **Confirm FE-5's `TagChip` and `TagChipPicker` are importable** — read their widget signatures before using them.
5. **Confirm the time-bucket auto-update logic source** — the bucket function from DM-5 should drive the `time-*` tag auto-update when `cooking_time_minutes` changes. Confirm where this logic lives on the Flutter side (may need a local port).
6. State the three section widget names, the save-guard `isValid` flag computation, and the auto-update override behavior before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] Recipe Builder has exactly three collapsible sections: Basics, Ingredients, Tags
- [ ] "Meal-prep capable" toggle adds/removes `context:meal-prep` tag and enforces `default_servings >= 2` when ON
- [ ] Ingredient rows show `✓ resolved`, `⚠ ambiguous`, `✗ unresolved` badges; existing USDA/local endpoints are reused — no new HTTP calls added
- [ ] Tags section has four chip rows (context, time, nutrition, constraint) using `TagChip`/`TagChipPicker` from FE-5 — no reimplementation
- [ ] Save is disabled until: name non-empty, ≥ 1 ingredient resolved, `context` ≥ 1 tag, `time` exactly 1 tag
- [ ] `cooking_time_minutes` change auto-updates the `time-*` tag unless user has manually overridden it ("auto" indicator shown)
- [ ] "LLM assist" button in top bar is wired (opens FE-6 side sheet when FE-6 lands; until then, shows stub)
- [ ] Server-side validation still runs on save — client-side is UX-only
- [ ] Widget tests pass: required-tag guard, meal-prep toggle, time-tag auto-update
