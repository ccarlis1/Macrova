# DM-1 — Unify tag registry with `tag_repository`

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** —

## Summary

Evolve **`src/llm/tag_repository.py`** and **`recipe_tags.json`** into the canonical typed-tag registry (slugs, types, aliases, merge). Optional thin types module may wrap persistence, but **there must not be a second tag database** alongside the existing repository.

## Context

Architecture already has `RecipeTagsJson`, `recipe_tag_filtering`, and `tag_repository.py`. DM-1 extends that stack so planner + LLM share one read path (resolves critical/major duplicate-abstraction issues from `.cursor/report.json`).

Unblocks: DM-2, BE-1, BE-3, AI-3, FE-5.

## Acceptance criteria

- [ ] Typed slug model: `TagType = Literal["context", "time", "nutrition", "constraint"]`, `TagSource = Literal["user", "llm", "system"]`, canonical `slug`, `display`, `created_at`.
- [ ] Slug normalization: lowercased, whitespace → `-`, non-`[a-z0-9-]` stripped.
- [ ] `resolve(slug_or_display) -> TagMeta`; `merge(src_slug, dst_slug)` transactional across recipes.
- [ ] Aliases stored in the same persistence story as `recipe_tags.json` (extend schema; avoid a forked `data/tags/*.json` unless it is clearly the single backing file adopted by `tag_repository`).
- [ ] Curated starter nutrition slug set present in registry (at minimum `high-omega-3`, `high-fiber`, `high-calcium`) to support deficit-recovery scoring without uncontrolled tag sprawl.
- [ ] `apply_tag_filtering` / planner reads **only** this registry + per-recipe slug lists post-migration.
- [ ] Unit tests: normalization, alias resolution, merge, unknown slug behavior.

## Implementation notes

- Prefer extending existing load/save paths in `tag_repository.py` over new parallel modules.
- Do **not** attach full tag objects to `Recipe` in this task — DM-2.
- Keep nutrition-slug curation explicit in one place (registry seed data), so LLM and planner use the same canonical set.

## Out of scope

- HTTP routes (BE-1).
- UI (FE-5).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/tag_repository.py` — primary target; extend load/save paths here; do not fork
- `src/llm/schemas.py` — `RecipeTagsJson` schema lives here; extend in-place
- `src/llm/tag_filtering_service.py` + `src/llm/tag_filter.py` — read consumers that must remain compatible
- `src/api/server.py` — references `DEFAULT_TAG_PATH = data/recipes/recipe_tags.json`; persistence path must stay aligned

**Entities to reuse (from `architecture.json`):**
- `RecipeTagsJson` — existing schema in `src/llm/schemas.py`; the typed tag fields extend this model, they do not replace it
- Feature `tag_based_recipe_pool_filtering` — implemented across `tag_filtering_service.py` / `tag_filter.py`; these read paths must continue to work after the registry is extended

**Do NOT create:**
- A second tag persistence file alongside `recipe_tags.json` (e.g., no `data/tags/registry.json` as a separate store)
- A parallel module that duplicates load/save logic from `tag_repository.py`
- Any HTTP routes (that is BE-1)

**Known gap:** `data/recipes/recipe_tags.json` is referenced in `server.py` but absent from the repo snapshot. Treat its schema as defined by `RecipeTagsJson` in `schemas.py` and ensure the extended schema round-trips cleanly.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/tag_repository.py` in full.** Identify: load function, save function, existing data shape, any existing normalization logic, and how `apply_tag_filtering` calls into it.
2. **Read `src/llm/schemas.py`.** Confirm the exact current shape of `RecipeTagsJson`. Note all field names and types.
3. **Read `src/llm/tag_filtering_service.py` and `src/llm/tag_filter.py`.** Identify every attribute on the tag objects these files read so you do not break them when extending the schema.
4. **Confirm the backing file path** used in `tag_repository.py` load/save (compare against `DEFAULT_TAG_PATH` in `server.py`).
5. **List the exact methods to add/modify** on `tag_repository.py` (`resolve`, `merge`, normalization), and confirm no equivalent already exists under a different name.
6. Only after steps 1–5, state your integration approach and the files you will modify (should be `tag_repository.py`, `schemas.py`, and one migration/seed function — nothing else for DM-1).

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following before marking done:

- [ ] `src/llm/tag_repository.py` is the **only** file with tag load/save logic; no parallel module was created
- [ ] `RecipeTagsJson` in `schemas.py` is extended (not replaced) and existing fields remain intact
- [ ] `tag_filtering_service.py` and `tag_filter.py` require **zero** changes to remain functional
- [ ] `resolve(slug_or_display)` and `merge(src_slug, dst_slug)` exist and are importable from `tag_repository.py`
- [ ] Slug normalization: `"High Fiber"` → `"high-fiber"`, `"high fiber!"` → `"high-fiber"` (run the unit tests)
- [ ] Curated nutrition slugs (`high-omega-3`, `high-fiber`, `high-calcium`) present in seed data, verifiable without an HTTP call
- [ ] All unit tests (normalization, alias resolution, merge, unknown slug) pass
- [ ] No new files were introduced beyond what is specified in the acceptance criteria
