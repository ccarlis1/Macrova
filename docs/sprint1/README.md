# Sprint 1 — Task Index

Per-task stubs for the Sprint 1 plan. See the parent spec at [`../SPRINT_1.md`](../SPRINT_1.md).

## Stub format

Each task file contains:
- **Status** — `todo | in-progress | blocked | done`
- **Complexity** — `S / M / L`
- **Depends on** — blocking task IDs
- **Summary** — 1–2 lines
- **Context** — why this task, what it unblocks
- **Acceptance criteria** — checklist
- **Implementation notes** — files to touch, hints
- **Out of scope** — explicit non-goals

## Critical path (Week 1)

```
DM-1 ─► DM-2 ─► DM-5 ─┐
          │            ├─► BE-3 (pool) ─► BE-8 (slot) ─► BE-4 ─► BE-6 ─► BE-7
          ├─► DM-6 ────┘                                              │
          └─► BE-1 ────────────────────────────────────────────────────┘
DM-3 ──────► BE-2 ─────► BE-5 ───────────────────────────────────────┐
DM-4 ──────► BE-9 ─────► FE-8 ────────────────────────────────────┐  │
                                                                   │  │
                                                           FE-10 ─►│  │
                                                           FE-5  ─►│  │
                                                           FE-1  ─►│  │
                                                           FE-3  ─►│  │
                                                           FE-2  ─►│  │
                                                           FE-9  ─►┘  │

AI-1 ─► AI-2 ─► FE-6 ─────────────────────────────────────────────────┘

                                                       ───────────► Ship Week 1
```

Week 2 buffer focus: AI-3..AI-5, FE-4, FE-7, and polish/stabilization.

## Tasks

### Data Model
- [DM-1 — Unify tag registry with `tag_repository`](./DM-1-tag-model-registry.md)
- [DM-2 — Extend Recipe with tags](./DM-2-recipe-tags-extension.md)
- [DM-3 — MealPrepBatch entity + store](./DM-3-meal-prep-batch-entity.md)
- [DM-4 — Extend canonical `MealSlot` + `DaySchedule`](./DM-4-userprofile-slots.md)
- [DM-5 — Busyness → time-* tag migration](./DM-5-busyness-time-migration.md)
- [DM-6 — Tag semantics contract](./DM-6-tag-semantics-contract.md)

### Backend
- [BE-1 — TagService (CRUD + normalize)](./BE-1-tag-service.md)
- [BE-2 — Meal-prep batch locks in planner path](./BE-2-planner-batch-prefill.md)
- [BE-3 — Extend `recipe_tag_filtering` for required slot slugs](./BE-3-hard-tag-filter.md)
- [BE-4 — Soft scoring: preferred tags + variety](./BE-4-soft-scoring-tags.md)
- [BE-5 — Meal-prep endpoints](./BE-5-meal-prep-endpoints.md)
- [BE-6 — Planner request wiring](./BE-6-plan-request-wiring.md)
- [BE-7 — Failure-code surfacing](./BE-7-failure-codes.md)
- [BE-8 — Slot constraint evaluator in planner](./BE-8-slot-constraint-evaluator.md)
- [BE-9 — Profile schedule write contract](./BE-9-profile-schedule-write-contract.md)

### AI / LLM
- [AI-1 — LLM.suggest_recipes(query, k)](./AI-1-llm-suggest.md)
- [AI-2 — Two-stage generation wiring](./AI-2-two-stage-generation.md)
- [AI-3 — RecipeTagger v2 (typed tags)](./AI-3-recipe-tagger-v2.md)
- [AI-4 — Nutrition hallucination guardrail](./AI-4-nutrition-guardrail.md)
- [AI-5 — Duplicate detection](./AI-5-duplicate-detection.md)

### Frontend (Flutter)
- [FE-1 — Planner screen card-based rebuild](./FE-1-planner-card-rebuild.md)
- [FE-2 — Drag-and-drop between slots](./FE-2-drag-and-drop.md)
- [FE-3 — Meal Prep Tray panel](./FE-3-meal-prep-tray.md)
- [FE-4 — Recipe Builder revamp](./FE-4-recipe-builder-revamp.md)
- [FE-5 — Tag chip picker](./FE-5-tag-chip-picker.md)
- [FE-6 — LLM suggest → approve flow](./FE-6-llm-suggest-flow.md)
- [FE-7 — Meal-prep creation wizard](./FE-7-meal-prep-wizard.md)
- [FE-8 — Slot config in Profile](./FE-8-slot-config.md)
- [FE-9 — Failure-state surfaces](./FE-9-failure-surfaces.md)
- [FE-10 — Forcing mode UX clarity](./FE-10-forcing-mode-ux-clarity.md)
