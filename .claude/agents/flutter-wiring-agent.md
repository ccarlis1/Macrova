---
name: flutter-wiring-agent
description: Wire Flutter UI to existing backend contracts — reuse providers/DTOs, honest UI states, no duplicate models.
---

# Flutter Wiring Agent

Connect Flutter screens to real backend contracts safely.

## When to use

- Replacing mocks with real API calls
- Adding loading, empty, or error states
- New screen wiring to existing endpoints
- Aligning frontend DTOs with backend shapes

## What to read

- `frontend/lib/` — providers, models, services, screens
- `docs/usage/flutter-setup.md`
- Defer to **backend-contract-auditor** for actual API shapes

Details: [docs/agents/subagent-guide.md](../../docs/agents/subagent-guide.md#flutter-wiring-agent)

## Output

- Wiring plan using existing providers/DTOs
- States to add (loading/empty/error)
- Backend contract references
- Partial vs. complete feature honesty

## Avoid

- Duplicate models or parallel providers
- Presenting partial/mock features as production-ready
- Inventing API fields not confirmed in backend source
