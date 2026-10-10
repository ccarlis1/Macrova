# FE-10 — Forcing mode UX clarity

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** FE-8, BE-8, BE-9

## Summary

Expose explicit per-slot forcing controls so users can choose between `Pinned Recipe` and `Required Tags`, with clear precedence and conflict feedback.

## Context

Without explicit forcing-mode UI, behavior is hidden and users cannot predict outcomes when pins, meal-prep locks, and tags overlap.

Unblocks: Sprint 1 UX discoverability sign-off.

## Acceptance criteria

- [ ] Slot controls show a clear forcing selector with at least `Pinned Recipe` and `Required Tags`.
- [ ] UI copy explains planner precedence: meal-prep lock overrides pin, pin overrides required tags.
- [ ] Conflicts are surfaced inline (for example, pin ignored due to batch lock) with actionable messaging.
- [ ] When a meal-prep lock is the active override, slot UI links users to the batch source (`tray`/`wizard` context) instead of only showing a passive warning.
- [ ] Forcing mode state is persisted/reloaded through FE-8 + BE-9 contract.
- [ ] Widget/integration tests cover mode switching, conflict surfaces, and persisted reload behavior.

## Implementation notes

- Keep controls lightweight and colocated with slot config to avoid fragmented mental models.
- Reuse FE-5 tag picker for required tags when in tag-forcing mode.

## Out of scope

- Implementing planner precedence logic itself (BE-8/BE-2).
- Meal-prep creation flow changes (FE-7).
