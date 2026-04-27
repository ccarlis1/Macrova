# BE-8 — Slot constraint evaluator in planner

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** BE-2, BE-3, DM-4, DM-6

## Summary

Add a per-slot constraint evaluator inside planner candidate generation/search so slot-level hard constraints are enforced in the planner core, not only in a global prefilter.

## Context

BE-3 handles pool-level filtering. This task owns slot-level checks for `required_tag_slugs`, pin/lock compatibility, and deterministic precedence.

Unblocks: FE-10, BE-7.

## Acceptance criteria

- [ ] Planner evaluates candidates per slot using canonical `SlotAddress = (day_index, slot_index)`.
- [ ] Slot-level required/preferred slug checks consume canonical per-recipe tags from `recipe_tags.json/tags_by_id` (via planner recipe canonical tag payload), not `Recipe.tags`.
- [ ] Constraint precedence is deterministic: batch lock > pin > required tags > preferred/scoring.
- [ ] Hard required-tag checks only use planner-eligible tags (approved/system/user), excluding quarantined LLM `proposed` tags.
- [ ] If no candidate satisfies slot-level hard constraints, planner emits `FM-TAG-EMPTY` with slot context.
- [ ] Preferred tags remain soft and flow into scoring only (no hard rejection).
- [ ] Tests cover: lock+pin conflicts, required-tag-empty slots, and deterministic outcomes for equal seeds.

## Implementation notes

- Integrate into existing planner path (`plan_meals` and current phase pipeline), no shadow planner.
- Keep BE-3 as coarse pool filter; do not duplicate global filter logic here.

## Out of scope

- Adding new global tag filtering rules (BE-3).
- Changing meal prep batch persistence format (DM-3).
