# Benchmark: Frontend Wiring

Repeatable check that Flutter wiring reuses existing patterns.

## Task

Ask an agent to wire a screen to a real backend endpoint (or replace a mock).

## Expected behavior

- Reads backend contracts first (defers to backend-contract-auditor mindset)
- Reuses existing providers and DTOs — no duplicate models
- Adds loading, empty, and error states where appropriate
- Does not present partial/mock features as complete

## Files likely involved

- `frontend/lib/providers/`, `frontend/lib/services/`, `frontend/lib/models/`
- `frontend/lib/screens/`
- `docs/usage/flutter-setup.md`

## Validation commands

```bash
cd frontend && flutter analyze && flutter test
```

## Pass conditions

- No new parallel provider/model for existing concepts
- UI states handled honestly
- `flutter analyze` clean (for changed files at minimum)

## Failure conditions

- Invented API fields not in backend
- Duplicate DTOs or providers
- Mock wired as "done" without backend support
