# Task Router

Routing table for classifying tasks before implementation. The **task-router** subagent (`.claude/agents/task-router.md`) uses this table; do not duplicate it elsewhere.

Read [AGENTS.md](../../AGENTS.md) first. For specialist details, see [subagent-guide.md](subagent-guide.md).

---

## backend-api

- **Specialists:** backend-contract-auditor, test-coverage-agent, docs-maintainer
- **Docs:** `src/api/server.py`, `openapi/openapi.json`, `tests/api/`
- **Source:** `src/api/`, `openapi/`
- **Validation:** `python3 scripts/run_export_openapi.py --check`, `python3 scripts/run_pytest.py` (API/contract tests)
- **Docs likely:** `USAGE.md`, OpenAPI snapshot, `docs/architecture/` if boundaries change

## planner-core

- **Specialists:** planner-invariant-reviewer, test-coverage-agent, docs-maintainer
- **Docs:** `docs/planner/mealplan-specification.md`, `docs/planner/planner-rules.md`, `docs/planner/parity-debugging.md`, `docs/tagging/tag-semantics-contract.md`
- **Source:** `src/planning/`, `src/llm/tag_filtering_service.py`, `tests/planning/`
- **Validation:** `python3 scripts/run_pytest.py` (planning tests)
- **Docs likely:** `docs/planner/*`, failure-mode references in `error_mapping.py`

## frontend-wiring

- **Specialists:** flutter-wiring-agent, backend-contract-auditor, test-coverage-agent
- **Docs:** `docs/usage/flutter-setup.md`, `frontend/lib/`
- **Source:** `frontend/lib/providers/`, `frontend/lib/services/`, `frontend/lib/models/`
- **Validation:** `cd frontend && flutter analyze && flutter test`
- **Docs likely:** `docs/usage/flutter-setup.md` if workflow changes

## flutter-ui-redesign

- **Specialists:** flutter-wiring-agent (preserve behavior), test-coverage-agent
- **Docs:** `frontend/lib/screens/`, `frontend/lib/widgets/`
- **Source:** `frontend/lib/`
- **Validation:** `cd frontend && flutter analyze && flutter test`
- **Docs likely:** Usually none unless navigation or feature status changes

## llm-pipeline

- **Specialists:** backend-contract-auditor, planner-invariant-reviewer (if planner feedback), test-coverage-agent, docs-maintainer
- **Docs:** `docs/llm/roadmap.md`, `src/llm/pipeline.py`
- **Source:** `src/llm/`, related API routes in `src/api/server.py`
- **Validation:** `python3 scripts/run_pytest.py` (LLM-related tests)
- **Docs likely:** `docs/llm/roadmap.md`

## tagging-system

- **Specialists:** planner-invariant-reviewer, backend-contract-auditor, docs-maintainer
- **Docs:** `docs/tagging/tag-semantics-contract.md`, `src/llm/tag_repository.py`
- **Source:** `src/llm/tag_*.py`, `data/recipes/recipe_tags.json`
- **Validation:** `python3 scripts/run_pytest.py`
- **Docs likely:** `docs/tagging/tag-semantics-contract.md`

## nutrition-data

- **Specialists:** test-coverage-agent, docs-maintainer
- **Docs:** `docs/product/nutrition-knowledge.md`, `src/nutrition/`, `src/ingestion/`
- **Source:** `src/nutrition/`, `src/ingestion/`, `src/providers/`, `src/data_layer/`
- **Validation:** `python3 scripts/run_pytest.py`
- **Docs likely:** `docs/product/nutrition-knowledge.md` if product rules change

## testing

- **Specialists:** test-coverage-agent
- **Docs:** `docs/testing/`, `pytest.ini`, `scripts/run_pytest.py`
- **Source:** `tests/`, `scripts/run_pytest.py`
- **Validation:** `python3 scripts/run_pytest.py`
- **Docs likely:** `AGENTS.md`, `docs/testing/` if commands change

## documentation

- **Specialists:** docs-maintainer
- **Docs:** `docs/README.md`, nearest canonical doc for the topic
- **Source:** `docs/`, `AGENTS.md`, `.cursor/rules/`
- **Validation:** Grep for stale commands/terms; link checks
- **Docs likely:** The doc being updated plus nav in `docs/README.md`

## agent-rules

- **Specialists:** docs-maintainer, task-router
- **Docs:** `AGENTS.md`, `docs/agents/`, `.cursor/rules/`, `.claude/agents/`
- **Source:** Same as docs
- **Validation:** Conflict greps (see `docs/agents/benchmarks/`), evaluation-log entry
- **Docs likely:** `AGENTS.md`, `docs/agents/README.md`, evaluation-log

## environment-tooling

- **Specialists:** test-coverage-agent, docs-maintainer
- **Docs:** `AGENTS.md`, `QUICK_START.md`, `Makefile`
- **Source:** `scripts/`, `requirements.txt`, `.python-version`, `Makefile`
- **Validation:** `python3 scripts/run_pytest.py`, script smoke checks
- **Docs likely:** `AGENTS.md`, `QUICK_START.md`, `Makefile` comments

---

## When to route

Use the task-router when the task spans multiple domains, touches unfamiliar code, or needs specialist review before implementation. Simple, single-file fixes in a known area usually do not need explicit routing.
