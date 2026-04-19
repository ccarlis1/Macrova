# FE-2 — Drag-and-drop between slots

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** FE-1, FE-3

## Summary

Let users drag a `MealCard` from one slot to another (same or different day) to reassign it. Dragging a meal-prep serving triggers a detach/move dialog.

## Context

DnD is the primary rearrange gesture per §5.1. Essential for the "doesn't feel like a spreadsheet" goal.

## Acceptance criteria

- [ ] Every `MealCard` is a `Draggable<MealCardPayload>`; every slot container is a `DragTarget<MealCardPayload>`.
- [ ] Drop on an empty slot: move the meal (server-side call updates the plan). Show a loading shimmer on the target while the call is in flight.
- [ ] Drop on an occupied slot: swap the two meals (one PATCH, not two).
- [ ] If dragged card's `source == "meal_prep_batch"`: on drop, open `DetachServingDialog` with options:
  - **Move this serving** (assignment moves; batch remains).
  - **Detach from batch** (this meal becomes `user_override`; batch's `servings_remaining` increases by 1).
  - **Cancel**.
- [ ] Narrow-viewport fallback: long-press a card → a floating "Move to…" sheet with slot buttons; no drag required.
- [ ] Optimistic UI with rollback on server error; error toast shows the `FM-*` code or HTTP status.
- [ ] Widget tests:
  - Happy-path move between two empty slots.
  - Detach flow dialog renders all three options.
  - Rollback on failed PATCH.

## Implementation notes

- Payload carries `{slot_id, date, meal_id, source, batch_id?}`.
- Avoid dragging out of the Meal Prep Tray in this task (FE-3 owns that side's Draggable). From here, we only move cards that are already placed.
- Accessibility: add semantics labels so screen readers announce "Draggable meal card, Chicken Rice Bowl".

## Out of scope

- Dragging to/from the Meal Prep Tray (FE-3).
- Cross-week dragging.
