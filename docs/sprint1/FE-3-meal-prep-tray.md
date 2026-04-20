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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/meal_plan_view_screen.dart` — `MealPlanViewScreen`; `MealPrepTray` is placed **above** the 7-column `DayColumn` row from FE-1
- `frontend/lib/services/api_service.dart` — `GET /api/v1/meal_prep_batches?active=true` and `DELETE /api/v1/meal_prep_batches/{id}` calls (BE-5 output); add service methods here, not inline in the widget
- `frontend/lib/providers/meal_plan_provider.dart` — or a new dedicated `MealPrepBatchProvider`; tray data is fetched and held in a Riverpod provider

**Backend dependency:** `GET /api/v1/meal_prep_batches?active=true` is confirmed MISSING from the current repo snapshot (architecture unknown). This endpoint is provided by BE-5. Do not stub or mock it in production code — wire the real call.

**Drag payload:** `TrayCardPayload` — a distinct type from FE-2's `MealCardPayload`. Slot `DragTarget`s in FE-2's `DayColumn` must accept both payload types; coordinate the `DragTarget` update with FE-2 if it has already landed.

**Do NOT create:**
- Inline HTTP calls in `MealPrepTray` widget — use service methods from `api_service.dart`
- Batch creation UI (FE-7)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/meal_plan_view_screen.dart` (FE-1 output).** Identify the exact widget tree location where `MealPrepTray` is inserted above the `DayColumn` row.
2. **Read `frontend/lib/services/api_service.dart`.** Note existing HTTP method patterns; add `listActiveBatches()` and `deleteBatch(id)` following the same pattern.
3. **Check whether a `MealPrepBatchProvider` already exists** — if not, decide whether to extend `MealPlanProvider` or create a small dedicated provider.
4. **Read FE-2's `DayColumn`/slot `DragTarget` implementation** (if landed) to confirm how to extend it to accept `TrayCardPayload` drops.
5. State the `TrayCardPayload` fields, the optimistic decrement mechanism for `servings_remaining`, and the rollback strategy before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `MealPrepTray` widget is placed above the `DayColumn` row in `MealPlanViewScreen`
- [ ] Active batches are loaded via `GET /api/v1/meal_prep_batches?active=true` through `api_service.dart` — not inline in the widget
- [ ] Each tray card shows recipe name, `servings_remaining / total_servings`, cook date, and delete icon with confirmation
- [ ] Tray card is a `Draggable<TrayCardPayload>`; dropping on a slot posts a new `BatchAssignment`; plan view refreshes
- [ ] Empty state renders with "Meal prep saves time — **+ New batch**" CTA (CTA routes to "Coming soon" snackbar until FE-7 lands)
- [ ] Collapsible tray: chevron collapses to single-line summary; state persists per user
- [ ] Orphaned batches show a warning icon and "Recipe deleted — dismiss?" option
- [ ] Optimistic `servings_remaining` decrement applied on drop; rolled back on server error
- [ ] Widget tests pass: empty state, populated state, collapse toggle
