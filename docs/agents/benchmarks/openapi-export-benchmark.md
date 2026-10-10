# Benchmark: OpenAPI Export

Repeatable check that API changes trigger OpenAPI export and contract alignment.

## Task

Ask an agent to add or modify an API request/response model in `src/api/`.

## Expected behavior

- Runs `python3 scripts/run_export_openapi.py` (or `--check`)
- Keeps `openapi/openapi.json` in sync
- Runs or recommends API contract tests via `python3 scripts/run_pytest.py`
- Does not invent routes/models without updating source and snapshot

## Files likely involved

- `src/api/server.py`, routers under `src/api/`
- `openapi/openapi.json`
- `tests/api/`, `tests/test_api_v1_and_openapi.py`

## Validation commands

```bash
python3 scripts/run_export_openapi.py --check
python3 scripts/run_pytest.py tests/api/
```

## Pass conditions

- OpenAPI snapshot updated or check passes
- Contract tests pass or explicitly reported

## Failure conditions

- API model changed but OpenAPI stale
- Bare `python3 scripts/export_openapi.py` on system Python recommended as primary
- Frontend/backend DTO mismatch not flagged
