# FE-3 — Meal Prep Tray panel

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** FE-1, BE-5

## Summary

Persistent, collapsible panel above the week grid listing all active `MealPrepBatch`es. Each tray card is a drag source onto slots.

## Context

Directly resolves R2 (meal prep visibility vs minimalism). The notes flagged this tension; the tray is the explicit design decision.

## Acceptance criteria

- [ ] New widget `MealPrepTray` lives above the 7-column row in the planner screen.
- [ ] Lists active batches from `GET /api/v1/meal_prep_batches?active=true`.
- [ ] Each tray card shows:
  - Recipe name.
  - `servings_remaining / total_servings`.
  - Cook date ("Cook Sun Apr 19").
  - "Delete" icon (confirms before DELETE).
- [ ] Tray is a drag source: dropping a card on a slot POSTs a new `BatchAssignment` (or if a free pattern exists, calls an "assign serving" endpoint). Plan view refreshes.
- [ ] Auto-hide: when `batches.isEmpty`, render an empty-state card with "Meal prep saves time across the week — **+ New batch**" CTA.
- [ ] Collapsible: a chevron button collapses the tray to a single-line summary ("2 active batches · 5 servings left"). State persists per user.
- [ ] "+ New batch" opens the wizard (FE-7 — until FE-7 lands, wire it to a "Coming soon" snackbar).
- [ ] Widget tests: empty state, populated state, collapse toggle.

## Implementation notes

- Drag payload type distinct from FE-2 (`TrayCardPayload`) so slot `DragTarget`s can differentiate between a slot-to-slot move vs a tray-to-slot assignment.
- Optimistic update: decrement `servings_remaining` locally on drop; rollback on server error.
- Orphaned batches surface with a warning icon and a "Recipe deleted — dismiss?" option.

## Out of scope

- Creating batches (FE-7 wizard).
- Editing an existing batch's serving count (Sprint 1: delete and recreate).
