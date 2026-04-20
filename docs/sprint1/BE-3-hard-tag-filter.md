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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/tag_filtering_service.py` — `apply_tag_filtering` is implemented here; **extend** this function, do not replace it
- `src/llm/tag_filter.py` — underlying filter primitives; extend as needed while keeping existing behavior intact
- `src/llm/tag_repository.py` — `TagRegistry.resolve()` (DM-1 output); unified tag resolution path
- `src/models/schedule.py` — `MealSlot.required_tag_slugs` (DM-4 output); the new filter reads this field
- `src/api/server.py` — `PlanRequest` model; confirm which tag fields it currently exposes vs. what BE-3 needs to add; close the gap flagged in architecture unknowns: "Flutter PlanRequest model does not include backend tag-filter fields"
- `frontend/lib/models/models.dart` — Flutter `PlanRequest` / schedule model; the acceptance criteria explicitly require closing the Flutter vs. server tag-field gap

**Entities to reuse:**
- `apply_tag_filtering` in `src/llm/tag_filtering_service.py` — the single filter pipeline; slot-level required tags are an extension of this, not a second pipeline
- Feature `tag_based_recipe_pool_filtering` — already implemented; BE-3 is an evolution

**Do NOT create:**
- A second filter pipeline alongside `apply_tag_filtering`
- Any LLM calls in this path

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/tag_filtering_service.py` and `src/llm/tag_filter.py` in full.** Understand the current `apply_tag_filtering` interface: inputs, outputs, how recipes are selected, how the fallback-to-full-pool logic works.
2. **Read `src/models/schedule.py`.** Confirm `MealSlot.required_tag_slugs` exists (DM-4 output) and its type.
3. **Read `src/api/server.py`.** Identify the `PlanRequest` fields related to tags and whether `required_tag_slugs` is threaded through to the planner call. Note the gap.
4. **Read `frontend/lib/models/models.dart`.** Confirm which tag fields the Flutter model currently has and what needs to be added to close the gap.
5. **Determine how slot-level required tags are passed to `apply_tag_filtering`** — as a parameter per slot, or as a modified request object — and confirm the chosen approach doesn't break the existing call.
6. State the exact extension to `apply_tag_filtering` (new parameters, changed behavior) before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `apply_tag_filtering` in `src/llm/tag_filtering_service.py` is extended — the existing function is not replaced or forked
- [ ] For each planning slot, only recipes satisfying `required_tag_slugs ⊆ recipe.tag_slugs` are candidates; empty result → `FM-TAG-EMPTY` with full context
- [ ] `FM-TAG-EMPTY` payload includes `{day_index, slot_index, required_tag_slugs}` at minimum
- [ ] Exactly-one-recipe pool still produces a deterministic selection compatible with `pinned_assignments` precedence
- [ ] Flutter `PlanRequest` model in `frontend/lib/models/models.dart` includes the tag fields required by the server — the architecture gap is closed
- [ ] No LLM calls exist anywhere in the filter path
- [ ] Tests pass: multi-slug intersection, empty pool, pin + required-tags precedence
