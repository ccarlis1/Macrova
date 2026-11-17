---
name: backend-contract-auditor
description: Verify real API/DTO/OpenAPI contracts before inventing or wiring backend or frontend shapes.
---

# Backend Contract Auditor

Prevent invented backend/API contracts. Read source and tests; report actual shapes.

## When to use

- API route or request/response model changes
- Frontend wiring to backend endpoints
- OpenAPI export or contract-test updates
- Recipe, planner, profile, pin, or meal-prep endpoint work

## What to read

- `src/api/server.py`, `recipe_sync.py`, `tag_routes.py`, `meal_prep_routes.py`
- `src/api/error_mapping.py`
- `openapi/openapi.json`
- `tests/api/`

Read first: [docs/architecture/map/api.md](../../docs/architecture/map/api.md) and [generated/routes.md](../../docs/architecture/map/generated/routes.md).

## Output

- Summary of actual request/response shapes for affected endpoints
- Error envelope codes (`error_mapping.py`) and plan failure codes (the `PlanFailure.code` Literal in `server.py`)
- Gaps vs. assumed contracts
- Recommended contract-test additions

## Avoid

- Inventing DTO fields or routes not present in source/OpenAPI
- Treating prose docs over `server.py` and `openapi/openapi.json`
