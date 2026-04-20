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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/tag_repository.py` — `TagRegistry` (DM-1); `merge()`, `resolve()`, `create()` must already exist; the service layer wraps this, it does not re-implement it
- `src/api/server.py` — existing FastAPI app instance and route mounting pattern (e.g., `app.include_router(...)`)
- `src/api/recipe_sync.py` — error-mapping pattern to replicate in `tag_routes.py`
- `src/api/error_mapping.py` — existing error codes; add `TAG_NOT_FOUND`, `TAG_CONFLICT`, `TAG_INVALID` here; do not define them inline in `tag_routes.py`
- `src/data_layer/models.py` — `Recipe` (for recipe-count aggregation via `RecipeDB`)
- Existing endpoint `POST /api/v1/recipes/tags/generate` in `server.py` — confirm it does not conflict with the new `/api/v1/tags` namespace

**Entities to reuse:**
- `TagRegistry` from `src/llm/tag_repository.py` — all mutation goes through this; `tag_routes.py` is HTTP glue only
- `RecipeDB` from `src/data_layer/` — for recipe-count aggregation; read current pattern for instantiation

**Do NOT create:**
- A parallel tag registry or tag model separate from DM-1's `tag_repository.py`
- Direct file I/O in `tag_routes.py` — all persistence goes through `TagRegistry`
- Any frontend/Flutter code

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/tag_repository.py` (DM-1 output).** Confirm the exact method signatures for `resolve()`, `merge()`, `create()`, and `list_by_type()`. These are the service layer's vocabulary.
2. **Read `src/api/server.py`.** Find the `include_router` calls to understand where `src/api/tag_routes.py` should be mounted and what prefix is used.
3. **Read `src/api/recipe_sync.py`.** Note the error response pattern (how 409, 404 are returned) and replicate it in `tag_routes.py`.
4. **Read `src/api/error_mapping.py`.** Identify existing error code constants and add the three new ones (`TAG_NOT_FOUND`, `TAG_CONFLICT`, `TAG_INVALID`) without breaking existing entries.
5. **Confirm `RecipeDB` instantiation pattern** used elsewhere in `server.py` — use the same pattern for recipe-count aggregation, not a fresh standalone instantiation.
6. State the full router prefix and each route path before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `src/api/tag_routes.py` exists and is mounted on the existing `/api/v1` prefix in `server.py` — no duplicate prefix
- [ ] All five endpoints work: `GET /api/v1/tags`, `POST /api/v1/tags`, `PATCH /api/v1/tags/{slug}`, `POST /api/v1/tags/{slug}/alias`, `POST /api/v1/tags/{src_slug}/merge_into/{dst_slug}`
- [ ] `POST /api/v1/tags` returns 409 when slug already exists; response body matches `TAG_CONFLICT` from `error_mapping.py`
- [ ] Merge operation is transactional: on failure mid-rewrite, no partial recipe updates
- [ ] Recipe counts in `GET` response come from live `RecipeDB` reads — not hardcoded or cached
- [ ] `src/api/error_mapping.py` has the three new codes; no other file defines them redundantly
- [ ] OpenAPI spec regenerated
- [ ] Integration tests in `tests/api/test_tag_routes.py` pass for: create, duplicate, alias, merge, `GET` filtering
