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
