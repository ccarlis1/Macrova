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
