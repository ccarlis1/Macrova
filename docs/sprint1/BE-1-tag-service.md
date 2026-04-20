# BE-1 — TagService (CRUD + normalize)

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

HTTP-facing `TagService` that wraps `TagRegistry`: create, list, rename, merge, and resolve tags. Exposed on FastAPI for Flutter and internal LLM callers.

## Context

DM-1 owns the in-memory/on-disk registry. BE-1 is the one interface for all mutation: the UI, the LLM tagger, and the recipe import path all go through it. Centralizing mutation here is how we prevent tag sprawl (R5).

Unblocks: AI-3, FE-5, FE-8.

## Acceptance criteria

- [ ] `src/api/tag_routes.py` with:
  - `GET /api/v1/tags?type=context|time|nutrition|constraint` → list of tags with recipe counts.
  - `POST /api/v1/tags` → create user-sourced tag. Body: `{slug?, display, type}`. 409 if slug exists.
  - `PATCH /api/v1/tags/{slug}` → rename display only.
  - `POST /api/v1/tags/{slug}/alias` → add alias. Body: `{alias_slug}`. 409 on conflict.
  - `POST /api/v1/tags/{src_slug}/merge_into/{dst_slug}` → merge: rewrite all recipes using `src_slug` to `dst_slug`, register alias, remove `src_slug`.
- [ ] Service layer `src/llm/tag_repository.py` extended (or new `src/services/tag_service.py`) so LLM code calls the same logic, not the HTTP layer.
- [ ] Merge operation is transactional: on failure, no partial recipe updates.
- [ ] Recipe-count aggregation reads from `RecipeDB` — do not cache stale counts.
- [ ] Nutrition-tag create path supports curated micronutrient starter slugs (for example `high-omega-3`, `high-fiber`, `high-calcium`) and keeps nutrition slugs normalized through the same registry controls as other tag types.
- [ ] OpenAPI (`openapi/`) regenerated.
- [ ] Integration tests (`tests/api/test_tag_routes.py`) cover create, duplicate, alias, merge, and `GET` filtering.

## Implementation notes

- Use FastAPI `APIRouter`; mount under the existing `/api/v1` prefix alongside `recipes`.
- For merge, reuse `TagRegistry.merge(src, dst)` from DM-1 and iterate `RecipeDB` with a `save_all` bulk write. Take a file lock while rewriting to avoid corrupting `recipes.json`.
- Rejection taxonomy aligns with `src/api/error_mapping.py`: `TAG_NOT_FOUND`, `TAG_CONFLICT`, `TAG_INVALID`.
- Emit stderr log lines for every mutation so `DEBUG_PLANNER_PARITY.md`-style diffs stay possible.

## Out of scope

- Deletion of system tags (not allowed; return 403 if attempted).
- Bulk import from CSV (future).
- Any UI (FE-5).
