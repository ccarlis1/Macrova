# DM-7 — Canonical recipe tag seed data

**Status:** implemented  ·  **Complexity:** S  ·  **Depends on:** DM-1

## Summary

Commit canonical tag seed data at `data/recipes/recipe_tags.json` (Option C) or provide an equivalent deterministic seed path that `tag_repository.py` loads by default.

## Context

Backend readiness audit found runtime tags are effectively empty unless users create them manually. Frontend tag selector, recipe tagging, and planner tag filtering need deterministic baseline tags available in-repo.

Unblocks: BE-11, BE-13, BE-15.

## Acceptance criteria

- Canonical system tag registry exists in-repo and is loaded by existing tag repository code.
- Seed data includes required tag types: `context`, `time`, `nutrition`, `constraint`.
- Seed data includes required system slugs: `meal-prep`, `time-0`, `time-1`, `time-2`, `time-3`, `time-4`.
- Every seeded tag includes stable `slug`, `display`, `type`, `source`, `aliases`.
- Starting with an empty user-created tag store still yields deterministic system tags via seed load.

## Implementation notes

- Keep this as Option C: extend existing `recipe_tags.json` flow; do not add a second registry path.
- Keep seed scope minimal and frontend-critical.
- Preserve compatibility with BE-1 merge/alias behavior.
- Required-type coverage (`context`, `time`, `nutrition`, `constraint`) is satisfied by a minimal canonical seed set; avoid broad taxonomy growth in this DM.
- Existing hardcoded fallback seeds in `tag_repository.py` may still include additional legacy nutrition slugs (for example `high-omega-3`, `high-calcium`) to preserve runtime compatibility.

## Out of scope

- Full taxonomy expansion.
- Recipe corpus retagging/migration coverage work.
- Frontend tag management behavior.

