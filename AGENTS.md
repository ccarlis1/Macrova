# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Macrova (nutrition-agent) is a Python-based meal planner that generates single- or multi-day meal plans. It has two interfaces: a CLI (`plan_meals.py`) and a REST API (FastAPI on port 8000). A Flutter frontend exists as scaffold only (no source code in `frontend/lib/`). All data is file-based (JSON + YAML) — no databases or Docker required.

### Running the application

Activate the virtual environment before any Python command:

```bash
source /workspace/.venv/bin/activate
```

**CLI (deterministic / local mode):**
```bash
python3 plan_meals.py --ingredient-source local --planning-mode deterministic
```

**FastAPI server:**
```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

Docs at `http://localhost:8000/docs`.

### Key caveats

- The `.env` file contains `LLM_API_KEY` / `LLM_MODEL` which auto-enable "assisted" planning mode. To run the CLI or API without LLM, pass `--planning-mode deterministic` (CLI) or `"planning_mode": "deterministic"` (API body). Without this flag, requests will route through the LLM feedback loop and also require USDA API access.
- `httpx` is needed for FastAPI's `TestClient` but is not listed in `requirements.txt`. It is installed in the venv by the update script.
- `black --check` reports 116 files needing reformatting and `mypy` reports a module shadowing issue (`src/llm/types.py` shadows stdlib `types`). Both are pre-existing in the codebase.

### Testing

```bash
pytest tests/
```

All 839 tests pass with no network or API keys required (mocks are used). See `README.md` and `QUICK_START.md` for full usage docs.

### Linting

```bash
black --check src/ tests/ plan_meals.py
mypy src/ --ignore-missing-imports
```
