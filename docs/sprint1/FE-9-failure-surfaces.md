# FE-9 — Failure-state surfaces

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-7, FE-1

## Summary

Render planner failures (`FM-*`) as actionable red banners on the affected slot cards with a one-click recovery CTA.

## Context

Dead-end errors are a big UX regression; turn them into recovery prompts per `SPRINT_1.md` §5.3.

## Acceptance criteria

- [ ] `FailureBanner` widget placed inside the affected `DayColumn` (or `MealCard`, depending on the failure's slot targeting):
  - Red background, one-line `fix_hint` (server-provided).
  - Primary CTA dispatches based on code:
    - `FM-TAG-EMPTY` → opens FE-6 LLM suggest sheet pre-populated with the missing tag as a query, OR a "Create a recipe with tag X" quick action.
    - `FM-BATCH-CONFLICT` → scrolls to and highlights both conflicting batches in the tray.
    - `FM-MACRO-INFEASIBLE` → opens a bottom sheet showing the macro deltas and a "Relax targets" link.
  - Dismiss button (only hides locally; re-runs will show again if still failing).
- [ ] When `termination_code != "OK"`, the planner screen shows a top-of-screen banner "This plan has issues" with a count + scroll-to-first-failure action.
- [ ] Widget tests:
  - Each failure code renders its correct CTA.
  - Dismissing is local and does not mutate server state.

## Implementation notes

- `fix_hint` is server-authored (BE-7). Do not rewrite copy client-side — this keeps i18n and testing centralized.
- Visual weight: banners use the `error` color role; must still pass a11y contrast.

## Out of scope

- Actually performing "Relax targets" from the banner (future; for Sprint 1 it deep-links to the profile screen).
- Multi-failure aggregation views beyond the count banner.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/widgets/planner/day_column.dart` (FE-1 output) — `FailureBanner` is placed inside the affected `DayColumn`; read its widget tree before deciding banner placement
- `frontend/lib/screens/meal_plan_view_screen.dart` — `MealPlanViewScreen`; top-of-screen "This plan has issues" banner goes here; do not create a new screen
- `frontend/lib/providers/meal_plan_provider.dart` — `failures: List<Failure>` comes from the plan response (BE-7 output); the provider must expose this list to `FailureBanner` and the top banner
- `frontend/lib/features/agent/agent_pane_screen.dart` — LLM suggest sheet (FE-6) is opened from the `FM-TAG-EMPTY` CTA; confirm the navigation/callback pattern

**`fix_hint` is server-authored (BE-7).** Do not rewrite or localize it client-side in this task. Display as-is.

**Do NOT create:**
- Client-side `fix_hint` strings — display the server value
- Logic that mutates server state when the dismiss button is tapped — local dismiss only

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/providers/meal_plan_provider.dart`.** Confirm whether the `failures` list from the BE-7 response is already exposed, or if the provider must be updated to parse and surface it.
2. **Read `frontend/lib/widgets/planner/day_column.dart` (FE-1 output).** Identify where in the `DayColumn` widget tree a `FailureBanner` is inserted (above/below meal cards, or inlined at the top of the column).
3. **Read `frontend/lib/screens/meal_plan_view_screen.dart`.** Identify where the top-of-screen "This plan has issues" banner is inserted (above the `MealPrepTray` from FE-3 and above the `DayColumn` row).
4. **Confirm the navigation to FE-6 LLM suggest sheet** for the `FM-TAG-EMPTY` CTA — read FE-6's opening mechanism.
5. State the `FailureBanner` widget props (accepts a `Failure` model from BE-7), the dismiss state mechanism (local `ValueNotifier` or provider), and the three CTA dispatch handlers before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `FailureBanner` reads `fix_hint` from the server `Failure` object — no client-side copy is written or maintained
- [ ] `FM-TAG-EMPTY` CTA opens FE-6 `LlmSuggestSheet` pre-populated with the missing tag as a query
- [ ] `FM-BATCH-CONFLICT` CTA scrolls to and highlights conflicting batch cards in FE-3's tray
- [ ] `FM-MACRO-INFEASIBLE` CTA opens a bottom sheet showing macro deltas and a "Relax targets" deep-link to ProfileScreen
- [ ] Dismiss is local only — no server call; re-running the plan shows the banner again if the issue persists
- [ ] When `termination_code != "OK"`, top-of-screen banner shows "This plan has issues" with a failure count + scroll-to-first-failure action
- [ ] Banners use the `error` color role and pass a11y contrast requirements
- [ ] Widget tests pass: each failure code renders its correct CTA; dismiss is local
