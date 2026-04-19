# BE-3 — Extend `recipe_tag_filtering` for required slot slugs

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-2, DM-4, DM-5

## Summary

**Extend** `src/llm/tag_filtering_service.py` / `tag_filter.py` / `tag_repository.py` so the **same** `apply_tag_filtering` path enforces **`MealSlot.required_tag_slugs`** as a hard constraint during planning. **Do not** add a second filter pipeline or delete the existing service.

## Context

Snapshot feature `recipe_tag_filtering` is already implemented; BE-3 is an evolution, not a rewrite (per `.cursor/report.json`).

Unblocks: BE-4, BE-7.

## Acceptance criteria

- [ ] For each planning slot, candidate recipes satisfy `required_tag_slugs ⊆ recipe_tag_slugs` after unified tag resolution.
- [ ] Empty candidate set → `FM-TAG-EMPTY` with `{day_index, slot_index, required_tag_slugs, ...}` in extended `report` (BE-7).
- [ ] Exactly one matching recipe → deterministic selection (coexists with **`pinned_assignments`** per §3.5 precedence).
- [ ] Flutter plan request sends tag fields expected by server (close `flutter_plan_request_vs_server_tag_fields` gap).
- [ ] Tests: multi-slug intersection; empty pool; pin + required tags precedence.

## Implementation notes

- Slot fields: `required_tag_slugs` / `preferred_tag_slugs` on `schedule.MealSlot` (DM-4).
- Recipe side: slug set from unified persistence (DM-2 / `RecipeTagsJson` extension).
- **Do not** call LLM in this path.

## Out of scope

- Preferred-tag scoring (BE-4).
- Final JSON envelope shape beyond BE-7.
