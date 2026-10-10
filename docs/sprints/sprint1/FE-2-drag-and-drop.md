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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/widgets/planner/` — `MealCard` and `DayColumn` from FE-1; `Draggable<MealCardPayload>` wraps `MealCard`; slot container `DragTarget<MealCardPayload>` wraps the slot area in `DayColumn`
- `frontend/lib/providers/meal_plan_provider.dart` — plan state; optimistic updates go here; rollback on server error
- `frontend/lib/services/api_service.dart` — the PATCH call for move/swap; look at existing PATCH patterns before writing a new one

**Payload type:** `MealCardPayload` with fields `{slot_id, date, meal_id, source, batch_id?}` — define this in `frontend/lib/widgets/planner/` (not inline in a screen).

**Do NOT:**
- Implement dragging from the Meal Prep Tray (FE-3 owns `TrayCardPayload` and tray-side `Draggable`s)
- Make two separate PATCH calls for a swap — one call handles both sides
- Introduce state outside of `MealPlanProvider`

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/widgets/planner/meal_card.dart` (FE-1 output) in full.** Identify the widget's constructor and how it exposes meal source/id/batch data — `MealCardPayload` is derived from this.
2. **Read `frontend/lib/providers/meal_plan_provider.dart`.** Identify the state mutation API for moving and swapping meals, and how to implement rollback on server error.
3. **Read `frontend/lib/services/api_service.dart`.** Find existing PATCH calls to understand the pattern for the move/swap endpoint.
4. **Confirm the PATCH endpoint exists on the backend** (or note it as a backend dependency not yet landed in Sprint 1).
5. State the `MealCardPayload` field list, the `DragTarget` drop handler logic for empty-slot vs. occupied-slot, and the rollback mechanism before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] Every `MealCard` is a `Draggable<MealCardPayload>`; every slot container is a `DragTarget<MealCardPayload>`
- [ ] Drop on empty slot: one server PATCH call; loading shimmer shown on target during the call
- [ ] Drop on occupied slot: one PATCH call (swap); not two sequential calls
- [ ] If `source == "meal_prep_batch"`: `DetachServingDialog` opens with three options (Move, Detach, Cancel)
- [ ] Narrow-viewport fallback: long-press → floating "Move to…" sheet with slot buttons
- [ ] Optimistic update applied immediately; rolled back on server error; error toast shows `FM-*` code or HTTP status
- [ ] `TrayCardPayload` (FE-3) and `MealCardPayload` (this task) are distinct types — `DragTarget` in slot container handles both, but tray-side `Draggable`s are not implemented here
- [ ] Widget tests pass: happy-path move, detach dialog options, rollback on failed PATCH
