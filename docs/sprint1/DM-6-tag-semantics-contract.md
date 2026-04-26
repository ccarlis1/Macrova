# DM-6 — Tag semantics contract

**Status:** implemented  ·  **Complexity:** S  ·  **Depends on:** DM-1

## Summary

Define explicit semantic tag classes and filterability rules so planner, LLM, and UI all interpret tags the same way.

Canonical contract document: `docs/tag_semantics_contract.md`.

## Context

Typed groups exist, but Sprint 1 still needs a hard contract to prevent drift (for example capability tags being misused as identity or exclusion flags).

Unblocks: BE-3, BE-8, AI-3, FE-5, FE-10.

## Acceptance criteria

- Semantic classes are documented and canonicalized: `capability`, `meal_role`, `exclusion`, `nutrition_claim`, `identity_hint`, `effort_system`.
- Each class has filterability semantics (`hard_filter_allowed`, `soft_score_allowed`, `display_only`) and allowed producers (`user`, `system`, `llm`).
- Alias/normalization rules include examples and conflict rules for merge behavior.
- LLM-ingested tags must pass through a quarantine/curation rule before becoming planner-eligible for hard constraints.
- Tag eligibility lifecycle is explicit and machine-readable (`proposed` -> `approved` or `rejected`) and is defined on canonical tag records.
- Planner hard-constraint checks may only use tags with `eligibility=approved` (or non-LLM system/user tags); `proposed` tags are soft/display only.
- Contract references concrete touchpoints: `tag_repository.py`, `recipe_tags.json`, planner filter/evaluator tasks.

## Implementation notes

- Keep this task documentation-first unless implementation is explicitly requested in a follow-up.
- Prefer one canonical table that can be reused by BE/AI/FE task docs.
- Canonical semantics, lifecycle, normalization, quarantine, and integration references are defined in `docs/tag_semantics_contract.md`.

## Out of scope

- Building new tag API endpoints (BE-1).
- Implementing slot-level enforcement (BE-8).

