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
