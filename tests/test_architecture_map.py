"""Unit tests for scripts/gen_architecture_map.py on synthetic repos (tmp_path).

These never assert that the committed map is fresh -- that is CI's and the Stop
hook's job (``--check``); asserting it here would break pytest on every source edit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import gen_architecture_map as gam

PLANNER = '''"""Public planning entry point."""

from src.data_layer.models import Recipe


class Planner:
    def run(self):
        return 1


def plan_meals():
    return Planner().run()


LIMIT = 3
'''

MODELS = '''"""Domain models."""
from dataclasses import dataclass
from enum import Enum


@dataclass
class Recipe:
    id: str
    name: str


class Kind(str, Enum):
    A = "a"
    B = "b"
'''

SERVER = '''"""API server."""
from fastapi import FastAPI

from src.planning.planner import plan_meals

app = FastAPI()


@app.post("/api/v1/plan")
@app.post("/api/plan")
def plan_endpoint():
    return plan_meals()
'''

SCREEN = """import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
}

class _HomeScreenState extends State<HomeScreen> {}
"""

API_SERVICE = """import 'package:http/http.dart' as http;

class ApiService {
  static const baseUrl = 'http://localhost';

  static Future<String> plan(String body) async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/plan'), body: body);
    return res.body;
  }

  static Future<void> pin({required int day}) async {
    final uri = Uri.parse('$baseUrl/api/v1/pins/$day');
    await http.put(uri);
  }
}
"""


def _openapi(operations: dict[str, dict[str, str]]) -> str:
    paths: dict[str, dict] = {}
    for path, ops in operations.items():
        paths[path] = {
            method: {"operationId": op_id, "responses": {"200": {"description": "ok"}}}
            for method, op_id in ops.items()
        }
    return json.dumps({"openapi": "3.1.0", "paths": paths})


DEFAULT_OPS = {
    "/api/v1/plan": {"post": "plan_endpoint_api_v1_plan_post"},
    "/api/plan": {"post": "plan_endpoint_api_plan_post"},
}


def make_repo(root: Path, extra: dict[str, str] | None = None, ops=None) -> list[str]:
    files = {
        "src/planning/planner.py": PLANNER,
        "src/data_layer/models.py": MODELS,
        "src/api/server.py": SERVER,
        "plan_meals.py": '"""Entry."""\nfrom src.cli import main\n',
        "src/cli.py": '"""CLI."""\nimport argparse\n\n\ndef main():\n'
        "    p = argparse.ArgumentParser()\n    p.add_argument('--days')\n",
        "tests/test_planner.py": "from src.planning.planner import plan_meals\n",
        "frontend/lib/screens/home_screen.dart": SCREEN,
        "frontend/lib/services/api_service.dart": API_SERVICE,
        "frontend/pubspec.yaml": "name: demo\n",
        "openapi/openapi.json": _openapi(ops if ops is not None else DEFAULT_OPS),
    }
    files.update(extra or {})
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return sorted(files)


def _write_generated(root: Path, files: list[str]) -> None:
    gam.write_outputs(root, gam.render_all(gam.build(root, files)))


# ------------------------------------------------------------------ generation


def test_generation_is_deterministic_and_relative(tmp_path):
    files = make_repo(tmp_path)
    first = gam.render_all(gam.build(tmp_path, files))
    second = gam.render_all(gam.build(tmp_path, list(reversed(files))))
    assert first == second
    assert set(first) == {"index.md", "routes.md", "entities.md"} | {f"{a}.md" for a in gam.AREAS}
    for name, content in first.items():
        assert content.startswith(gam.HEADER + "\n# "), name
        assert str(tmp_path) not in content, name

    _write_generated(tmp_path, files)
    rc, message = gam.run_check(tmp_path, files)
    assert rc == 0, message


def test_generated_facts(tmp_path):
    files = make_repo(tmp_path)
    out = gam.render_all(gam.build(tmp_path, files))
    planning = out["planning.md"]
    assert "**`src/planning/planner.py`** — Public planning entry point." in planning
    assert "classes: Planner; functions: plan_meals" in planning
    assert "imports: src.data_layer.models" in planning
    assert "imported by: src.api.server · tests: 1" in planning
    assert "| POST | `/api/v1/plan` | `src/api/server.py::plan_endpoint` |" in out["routes.md"]
    assert "## Unversioned `/api/...` aliases (1)" in out["routes.md"]
    assert "| `Recipe` | dataclass | `src/data_layer/models.py` | id, name |" in out["entities.md"]
    assert "| `Kind` | Enum | `src/data_layer/models.py` | A, B |" in out["entities.md"]
    frontend = out["frontend.md"]
    assert "HomeScreen [Screen]" in frontend
    assert "_HomeScreenState" not in frontend
    assert "| `services/api_service.dart` | `plan` | POST | `/api/v1/plan` | yes |" in frontend
    assert "| `services/api_service.dart` | `pin` | PUT | `/api/v1/pins/{day}` | NO |" in frontend
    assert "`--days`" in out["interfaces.md"]


def test_check_reports_drift_with_regenerate_command(tmp_path):
    files = make_repo(tmp_path)
    _write_generated(tmp_path, files)
    (tmp_path / "src/planning/planner.py").write_text(PLANNER + "\n\ndef added():\n    pass\n")
    rc, message = gam.run_check(tmp_path, files)
    assert rc == 1
    assert "docs/architecture/map/generated/planning.md" in message
    assert "+  - classes: Planner; functions: added, plan_meals" in message
    assert gam.REGEN_CMD in message


def test_unmapped_src_file_fails_check(tmp_path):
    files = make_repo(tmp_path, {"src/newpkg/thing.py": '"""New."""\n'})
    _write_generated(tmp_path, files)
    rc, message = gam.run_check(tmp_path, files)
    assert rc == 1
    assert "unmapped file: src/newpkg/thing.py" in message
    assert "AREAS" in message


def test_unresolvable_route_handler_fails(tmp_path):
    ops = dict(DEFAULT_OPS)
    ops["/api/v1/ghost"] = {"get": "ghost_endpoint_api_v1_ghost_get"}
    ops["/api/v1/custom"] = {"get": "customOperation"}
    files = make_repo(tmp_path, ops=ops)
    rm = gam.build(tmp_path, files)
    assert any("GET /api/v1/ghost: no top-level function named 'ghost_endpoint'" in e for e in rm.errors)
    assert any("GET /api/v1/custom" in e and "not FastAPI's default" in e for e in rm.errors)
    _write_generated(tmp_path, files)
    rc, message = gam.run_check(tmp_path, files)
    assert rc == 1 and "ghost_endpoint" in message


def test_handler_name_strips_fastapi_suffix():
    assert gam.handler_name("put_pin_api_v1_pins__day___slot__put", "/api/v1/pins/{day}/{slot}", "put") == "put_pin"
    assert gam.handler_name("other", "/api/v1/x", "get") is None


# ------------------------------------------------------------------ link check


def test_hand_doc_link_check(tmp_path):
    files = make_repo(tmp_path)
    doc = tmp_path / gam.HAND_DIR / "planning.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "\n".join(
            [
                "# Planning",
                "Good: `src/planning/planner.py`, `src/planning/planner.py::plan_meals`,",
                "`src/planning/planner.py::Planner.run`, `src/planning/planner.py::LIMIT`,",
                "`src/planning/`, `plan_meals.py`, `frontend/lib/screens/home_screen.dart::HomeScreen`,",
                "`src/planning/planner.py::plan_meals()`.",
                "Bad: `src/planning/gone.py`, `src/planning/planner.py::missing`,",
                "`src/planning/planner.py::Planner.walk`, `src/nowhere/`,",
                "`frontend/lib/screens/home_screen.dart::AwayScreen`.",
                "Ignored: `python3 src/planning/gone.py --x`, `src/planning/phase*.py`, `ok`.",
                "```",
                "`src/planning/fenced.py`",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    # Generated files are not hand docs: a bad ref there is never link-checked.
    gen = tmp_path / gam.GENERATED_DIR
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "x.md").write_text("`src/planning/ignored.py`")

    broken = gam.check_links(tmp_path, files)
    assert broken == [
        "docs/architecture/map/planning.md: src/planning/gone.py",
        "docs/architecture/map/planning.md: src/planning/planner.py::missing",
        "docs/architecture/map/planning.md: src/planning/planner.py::Planner.walk",
        "docs/architecture/map/planning.md: src/nowhere/",
        "docs/architecture/map/planning.md: frontend/lib/screens/home_screen.dart::AwayScreen",
    ]

    (gen / "x.md").unlink()
    _write_generated(tmp_path, files)
    rc, message = gam.run_check(tmp_path, files)
    assert rc == 1
    assert "docs/architecture/map/planning.md: src/planning/gone.py" in message


# ------------------------------------------------------------------ stale intent


def test_attribute_generated_change_uses_paths_and_entry_context():
    old = "\n".join(
        [
            gam.HEADER,
            "# Planning",
            "## `src/planning/`",
            "- **`src/planning/planner.py`** — Doc.",
            "  - functions: plan_meals",
            "  - imports: —",
        ]
    )
    new = old.replace("functions: plan_meals", "functions: plan_meals, replan")
    findings = gam.attribute_generated_change("planning.md", old, new)
    assert findings == {"planning": {"generated planning.md changed for src/planning/planner.py"}}

    routes_old = "| method | path |\n|---|---|\n"
    routes_new = routes_old + "| POST | `/api/v1/x` | `src/api/server.py::x_endpoint` | — |\n"
    findings = gam.attribute_generated_change("routes.md", routes_old, routes_new)
    assert findings == {"api": {"routes changed: POST /api/v1/x"}}

    entities_new = "| `Recipe` | dataclass | `src/data_layer/models.py` | id |\n"
    findings = gam.attribute_generated_change("entities.md", "", entities_new)
    assert findings == {"data": {"generated entities.md changed for src/data_layer/models.py"}}


def test_file_change_findings_and_name_status():
    raw = "\0".join(
        ["A", "src/planning/new.py", "D", "frontend/lib/old.dart", "M", "src/api/server.py",
         "R087", "src/llm/a.py", "src/llm/b.py", "A", "README.md", ""]
    )
    changes = gam.parse_name_status(raw)
    assert changes == [
        ("A", "src/planning/new.py", None),
        ("D", "frontend/lib/old.dart", None),
        ("M", "src/api/server.py", None),
        ("R", "src/llm/a.py", "src/llm/b.py"),
        ("A", "README.md", None),
    ]
    assert gam.file_change_findings(changes) == {
        "planning": {"new file src/planning/new.py"},
        "frontend": {"deleted file frontend/lib/old.dart"},
        "llm": {"renamed src/llm/a.py -> src/llm/b.py"},
    }


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_stale_intent_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    files = make_repo(tmp_path)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
            cwd=tmp_path, check=True, capture_output=True,
        )

    git("init", "-q", "-b", "main")
    _write_generated(tmp_path, files)
    git("add", "-A")
    git("commit", "-q", "-m", "base")

    files = make_repo(tmp_path, {"src/planning/extra.py": '"""Extra."""\n'})
    git("add", "src/planning/extra.py")
    _write_generated(tmp_path, gam.git_ls_files(tmp_path))
    (tmp_path / gam.HAND_DIR / "api.md").write_text("# api\n")  # untracked: counts as reviewed

    assert gam.stale_intent(tmp_path, "main", strict=False) == 0
    out = capsys.readouterr().out
    assert "[stale-intent] planning: " in out
    assert "new file src/planning/extra.py" in out
    assert "review docs/architecture/map/planning.md" in out
    assert "[stale-intent] api" not in out
    assert gam.stale_intent(tmp_path, "main", strict=True) == 1
    capsys.readouterr()

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    gam.stale_intent(tmp_path, "main", strict=False)
    assert "::warning file=docs/architecture/map/planning.md::planning:" in capsys.readouterr().out

    assert gam.stale_intent(tmp_path, "no-such-ref", strict=True) == 0
    assert "cannot find merge-base" in capsys.readouterr().out
