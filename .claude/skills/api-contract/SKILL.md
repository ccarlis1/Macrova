---
name: api-contract
description: Change the API surface safely across the whole stack. Use when adding or modifying anything in src/api/ (endpoints, request/response models, error codes) or any field that Flutter sends or receives. Enforces additive-only evolution, error-envelope registration, OpenAPI snapshot regeneration, and Dart client lockstep.
---

# API Contract Change

The backend contract has three synchronized representations: the FastAPI/pydantic models, the
committed OpenAPI snapshot (`openapi/openapi.json`, drift-checked in CI), and the Dart models
+ `ApiService` in Flutter. A contract change is done only when all three agree. This skill is
the checklist that keeps them in lockstep.

## Rule zero — additive only

- New fields are **optional with a safe default**, on both request and response models.
- Never rename, remove, or retype an existing field. Flutter in the wild parses `day`,
  `dayTotals`, etc. — a rename is a breaking release, not a cleanup.
- Same rule for persisted JSON (`recipes.json`, `recipe_tags.json`, profile YAML): old files
  must still load. If a shape truly must change, that is a migration
  (`legacy_schedule_migration.py` is the pattern) plus a user decision — stop and ask.
- Omitted-field behavior must equal pre-change behavior (regression example already in repo:
  omitted `planning_mode` must default to `deterministic`).

## Backend sequence

1. **Locate the owner.** Routes live in `src/api/server.py` (or a focused router module like
   `src/api/tag_routes.py` included with `prefix="/api/v1"`). Extend the existing router for
   the domain; a new router file is justified only for a genuinely new domain.
2. **Models.** Pydantic v2, `ConfigDict(extra="forbid")` where the existing models do,
   `Field(..., description=...)` on every field — descriptions flow into the OpenAPI schema
   that the user reads and codegens from.
3. **Errors.** Endpoints do not raise raw exceptions to the client. Wrap handler logic so
   failures route through `map_exception_to_api_error` in `src/api/error_mapping.py`, and
   register any new exception type there with a deterministic `SCREAMING_SNAKE` code and the
   right status (400 client input, 404 missing, 409 conflict, 429 rate limit, 502 upstream,
   504 timeout). Response envelope is always `{"error": {"code", "message"}}` — Flutter's
   `ApiException.fromResponse` depends on it.
4. **Tests.** In `tests/test_api_*.py` using the FastAPI TestClient (no network, no real
   keys): happy path, at least one mapped error asserting the exact `code` and status, and —
   for changed endpoints — a test that the **old request shape still works** (fields omitted).
5. **Snapshot.** `python scripts/export_openapi.py` (no `--check`), commit the regenerated
   `openapi/openapi.json`, then confirm `python scripts/export_openapi.py --check` and the full
   `python -m pytest tests/ -q` pass. Forgetting this file is the #1 way to fail CI here.

## Flutter lockstep

Skip only if the field is genuinely server-internal; "Flutter doesn't need it *yet*" still
deserves a note in your summary. The sprint docs track exactly this class of gap
(client not sending fields the server accepts), so half-done lockstep must be visible.

1. **Models** (`frontend/lib/models/`): add the field as nullable/optional; `fromJson` must
   tolerate its absence (old servers) and `toJson` should omit `null` (old backends). Never
   make parsing throw on a missing new field.
2. **ApiService** (`frontend/lib/services/api_service.dart`): wire the field through the
   request builder or response parser. Error handling comes free via `ApiException` if the
   backend followed the envelope rule.
3. **State**: expose through the relevant `ChangeNotifier` provider in
   `frontend/lib/providers/` only if the UI consumes it now.
4. **Tests**: `frontend/test/` — round-trip the new field through `fromJson`/`toJson`
   including the field-absent case (see `recipe_sync_payload_test.dart` for the pattern —
   plain `flutter_test`, hand-rolled fakes, no Mockito/Riverpod/GetIt).
5. `cd frontend && flutter analyze && flutter test` — both clean. Neither runs in CI, so this
   is on you.

## Done means

- [ ] Old clients (field omitted) get pre-change behavior — proven by a test.
- [ ] `openapi/openapi.json` regenerated, committed, `--check` green.
- [ ] Full pytest suite green; new error codes asserted exactly.
- [ ] Dart side parses old + new payloads, or the skipped-lockstep decision is stated in the summary.
- [ ] No existing field renamed, removed, or retyped anywhere in the change.

## Escalate instead of proceeding when

- The requirement seems to demand a breaking change → present the additive alternative
  (new optional field, new endpoint, or `/api/v2`) and let the user choose.
- A response shape conflict exists between what Flutter expects and what the server sends
  today → that is a live bug, report it before layering more contract on top.
