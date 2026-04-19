# DM-1 — Tag model + registry

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** —

## Summary

Introduce a typed `Tag` model and a JSON-backed `TagRegistry` with canonical slugs, aliases, and type validation. This is the foundation for F1, F3, AI-3, FE-5.

## Context

Tagging currently exists only as free-form strings (commented TODO on `Recipe`). Planner, LLM tagger, and UI all need a single source of truth for:
- What tags exist
- Their type (`context | time | nutrition | constraint`)
- How aliases resolve to canonical slugs
- Who created each tag (`user | llm | system`)

Unblocks: DM-2, BE-1, AI-3, FE-5.

## Acceptance criteria

- [ ] `src/data_layer/tags.py` defines:
  - `TagType = Literal["context", "time", "nutrition", "constraint"]`
  - `TagSource = Literal["user", "llm", "system"]`
  - `@dataclass Tag { slug: str, display: str, type: TagType, source: TagSource, created_at: datetime }`
  - `class TagRegistry` with `add`, `get(slug)`, `resolve(slug_or_display)`, `list(type=None)`, `merge(src_slug, dst_slug)`.
- [ ] Slug normalization: lowercased, whitespace → `-`, non-`[a-z0-9-]` stripped.
- [ ] Alias store at `data/tags/aliases.json`; registry at `data/tags/registry.json`.
- [ ] `resolve()` returns the canonical `Tag` for any known slug or alias; raises `UnknownTagError` otherwise.
- [ ] Seed registry with the tags named in `SPRINT_1.md` §2.2 (`meal-prep`, `instant-snack`, `pre-workout`, `portable`, `no-kitchen`, `time-0..time-4`, `high-protein`, `high-carb`, `low-fat`, `no-dairy`, `no-kitchen`, `nut-free`).
- [ ] Unit tests (`tests/data_layer/test_tags.py`) cover slug normalization, alias resolution, merge, and type validation.

## Implementation notes

- Keep the registry in-memory with on-disk persistence; reload on process start.
- Use `slug` as the canonical identifier everywhere; `display` is UI-only.
- Do **not** attach tags to `Recipe` here — that's DM-2.
- Consider a tiny `TagRegistrySingleton` accessor to avoid passing it through every layer, but make it injectable for tests.

## Out of scope

- Exposing HTTP endpoints (see BE-1).
- UI for managing tags (see FE-5, Settings → Tags).
- Any planner or LLM wiring.
