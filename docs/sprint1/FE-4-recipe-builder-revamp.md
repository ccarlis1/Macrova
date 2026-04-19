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
