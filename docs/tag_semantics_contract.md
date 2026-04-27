# Tag Semantics Contract

## Purpose & Scope

This document is the authoritative semantics contract for tag interpretation across backend, planner, LLM ingestion, and frontend display/filtering flows. It defines canonical semantic classes, lifecycle eligibility, normalization and alias behavior, and component boundaries to prevent interpretation drift. This is a documentation contract only and introduces no runtime behavior, no new APIs, and no storage or planner implementation changes.

## Canonical Semantic Class Table (Single Source of Truth)


| semantic_class  | description                                                                                                                   | hard_filter_allowed (bool) | soft_score_allowed (bool) | display_only (bool) | allowed_producers ({user, system, llm}) |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------- | ------------------- | --------------------------------------- |
| capability      | Describes practical suitability for a user or scenario (for example quick prep, freezer-friendly, portable).                  | true                       | true                      | false               | {user, system, llm}                     |
| meal_role       | Describes a recipe's intended meal context (for example breakfast, lunch, dinner, snack).                                     | true                       | true                      | false               | {user, system, llm}                     |
| exclusion       | Marks explicit avoid/ban semantics (for example no-shellfish, no-peanuts, vegetarian-only exclusion logic).                   | true                       | false                     | false               | {user, system, llm}                     |
| nutrition_claim | Encodes nutritional framing claims (for example high-protein, low-sodium, fiber-rich).                                        | false                      | true                      | false               | {user, system, llm}                     |
| identity_hint   | Encodes descriptive identity/cuisine/style hints used for discovery or explanation (for example mediterranean, comfort-food). | false                      | true                      | true                | {user, system, llm}                     |
| effort_system   | Encodes preparation effort/time-system hints (for example one-pot, batch-cook, under-30-min).                                 | true                       | true                      | false               | {user, system, llm}                     |


Interpretation notes:

- `hard_filter_allowed=true` means planner-eligible as a hard constraint only when lifecycle eligibility permits.
- `display_only=true` means never used for planner hard constraints.

## Lifecycle & Eligibility

Machine-readable states:

- `proposed`
- `approved`
- `rejected`

Allowed transitions:

- `proposed -> approved`
- `proposed -> rejected`

Eligibility rule block:

- Hard-constraint eligibility = `approved`, OR non-LLM user/system tags per contract policy.
- `proposed` tags are soft/display only.
- `rejected` tags are never used for planner decisions.
- Planner MUST ONLY use approved tags OR user/system tags for decision-making, and must not treat proposed/rejected tags as hard constraints.

Transition matrix (state x allowed operation):


| state    | can_soft_score | can_display | can_hard_filter                           | can_transition_to_approved | can_transition_to_rejected |
| -------- | -------------- | ----------- | ----------------------------------------- | -------------------------- | -------------------------- |
| proposed | true           | true        | false                                     | true                       | true                       |
| approved | true           | true        | true (subject to semantic class booleans) | false                      | false                      |
| rejected | false          | false       | false                                     | false                      | false                      |


## Alias & Normalization Rules

Normative interpretation is aligned to existing `tag_repository.py` behavior.

Normalization rules:

- Slug normalization uses lowercase canonical slugs with normalized separators and trimmed whitespace.
- Whitespace/case normalization is applied before lookup and alias resolution.
- Canonical resolution order is: exact canonical slug match -> normalized slug match -> alias map match -> display-name canonical lookup (when configured by repository data).

Alias and merge rules:

- Alias mapping resolves to one canonical slug.
- Canonical slug always wins over alias in downstream comparisons.
- Alias collisions are resolved deterministically by repository precedence: canonical record priority, then seed load order from `recipe_tags.json`, then stable merge ordering in `merge()` semantics.
- Merging uses existing `merge()` semantics in repository/tag ingestion flow; this contract does not introduce new merge logic.

Examples:

- Whitespace/case normalization: `"  High Protein  "` -> `high-protein`
- Alias to canonical slug: `quick-meal` -> `quick-prep`
- Display-name to canonical resolution: `"High Protein"` -> `high-protein`

## LLM Quarantine / Curation Rule

Quarantine scope:

- All LLM-produced tags are quarantined before planner hard-constraint eligibility.

Normative rules:

- ALL LLM tags enter as `proposed`.
- LLM output must first pass strict schema validation (including JSON parse/shape validation in the existing `parse_llm_json` ingestion path), then semantic eligibility gating.
- LLM `proposed` tags can transition only through curation to `approved` or `rejected`.
- LLM `proposed` tags cannot be treated as hard constraints while in `proposed`.
- Review/curation must occur before hard filtering is allowed.

## Cross-Component Reference Map

Backend (BE):

- `tag_repository.py` is the runtime source for storage, slug normalization, alias resolution, and merge behavior.
- `recipe_tags.json` is the canonical seed/registry shape for preloaded tags and alias metadata, and `tags_by_id` is the canonical per-recipe planner/filtering tag source.
- `tag_filtering_service.py` consumes resolved tags for filtering behavior and must interpret eligibility/class booleans using this contract.
- `Recipe.tags` in `recipes.json` is legacy compatibility projection only and must not be used for hard-filter/planner decision logic.

AI / LLM ingestion:

- LLM generation + validation flow (including `parse_llm_json`) must apply strict schema validation first, then quarantine/eligibility policy from this contract.
- LLM tags remain `proposed` until curation marks `approved` or `rejected`.

Frontend (FE):

- UI should use this table to determine which semantic classes can appear as filter controls, soft preference affordances, or informational chips.
- Display semantics must remain consistent with planner eligibility semantics to avoid UI/backend drift.

Planner:

- Planner constraint usage must follow lifecycle and class booleans in this contract.
- Hard constraints may only use tags that are lifecycle-eligible and semantically hard-filterable per this table.

What this doc governs / what it does not:

- Governs semantic interpretation, lifecycle eligibility language, normalization/alias interpretation, and cross-component consistency.
- Does not implement runtime validation, APIs, persistence changes, schema refactors, new services, or planner algorithm changes.

## Non-Goals

- No API endpoints.
- No schema refactors.
- No planner implementation.
- No persistence changes.
- No new runtime enum/class/service/helper.
- No change to `tag_repository` behavior.

Risks and mitigations:

- Overengineering into a new system (forbidden): mitigated by documentation-only scope and explicit no-runtime-change boundaries.
- Duplicating logic already in `tag_repository`: mitigated by normatively referencing existing normalization/alias/merge behavior.
- Vague semantics causing planner misuse: mitigated by one canonical semantic-class table and explicit lifecycle eligibility matrix.
- LLM tags bypassing validation: mitigated by strict ordering definition: schema validation first, then quarantine (`proposed`), then curation for hard-constraint eligibility.

