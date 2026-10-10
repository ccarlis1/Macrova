"""PostToolUse gate for planner determinism (CLAUDE.md law 3, trap 6).

Law 3: same profile + recipe pool + seed must produce the same plan. This hook
reports two classes of risk in ``src/planning/``:

* **input** -- unseeded randomness, wall clock, UUIDs, filesystem ordering.
  ``random.Random(seed)`` stays legal: CLAUDE.md asks for the seed to be
  threaded through, not for randomness to be banned.
* **order** -- unsorted iteration over dicts and sets.

Both classes are measured against ``determinism_baseline.json``, so only *new*
sites are reported. The baseline exists because the planner already contains
legitimate instances of both: 22 order-independent ``.items()`` accumulations,
and 15 ``time.perf_counter()`` calls that only populate ``stats.day_runtimes``.
A hook that fired on untouched code would be switched off within a day, and the
end-to-end proof lives in ``verify_stop.py`` anyway -- it reruns the whole suite
under a second ``PYTHONHASHSEED``.

Regenerate the baseline after a deliberate cleanup -- never to silence a real
finding::

    python3 .claude/hooks/check_determinism.py --write-baseline
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Iterator

import _common as common

WATCHED = "src/planning/"
BASELINE_FILE = Path(__file__).resolve().parent / "determinism_baseline.json"

#: ``obj.<attr>()`` calls whose result depends on something other than input.
BANNED_ATTRS: dict[str, str] = {
    "time": "wall-clock time",
    "monotonic": "wall-clock time",
    "perf_counter": "wall-clock time",
    "now": "wall-clock time",
    "today": "wall-clock time",
    "utcnow": "wall-clock time",
    "uuid1": "a time-based UUID",
    "uuid4": "a random UUID",
    "listdir": "filesystem ordering",
    "scandir": "filesystem ordering",
    "iterdir": "filesystem ordering",
    "glob": "filesystem ordering",
    "rglob": "filesystem ordering",
}

UNORDERED_METHODS = {"items", "keys", "values"}

INPUT, ORDER = "input", "order"


class _Scan(ast.NodeVisitor):
    """Collect determinism findings as ``(lineno, scope, category, label)``."""

    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.scope: list[str] = []
        self.findings: list[tuple[int, str, str, str]] = []

    # -- scope tracking, so a baseline entry survives line-number churn -------

    def _visit_scoped(self, node: ast.AST) -> None:
        self.scope.append(getattr(node, "name", "?"))
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = _visit_scoped
    visit_AsyncFunctionDef = _visit_scoped
    visit_ClassDef = _visit_scoped

    def _record(self, lineno: int, category: str, label: str) -> None:
        self.findings.append((lineno, ".".join(self.scope) or "<module>", category, label))

    # -- input-dependence findings -------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            root = func.value
            if isinstance(root, ast.Name) and root.id == "random":
                if func.attr != "Random":  # a seeded generator is the escape hatch
                    self._record(node.lineno, INPUT, f"random.{func.attr}() -- unseeded randomness")
            elif func.attr in BANNED_ATTRS:
                self._record(node.lineno, INPUT, f".{func.attr}() -- {BANNED_ATTRS[func.attr]}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "random":
            names = ", ".join(alias.name for alias in node.names)
            self._record(node.lineno, INPUT, f"from random import {names} -- unseeded randomness")
        self.generic_visit(node)

    # -- iteration-order findings --------------------------------------------

    def _record_iter(self, iter_node: ast.AST, lineno: int) -> None:
        label = _unordered_label(iter_node)
        if label:
            self._record(lineno, ORDER, label)

    def visit_For(self, node: ast.For) -> None:
        self._record_iter(node.iter, node.lineno)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._record_iter(node.iter, node.lineno)
        self.generic_visit(node)

    def _visit_comprehension(self, node: ast.AST) -> None:
        for generator in getattr(node, "generators", []):
            self._record_iter(generator.iter, getattr(node, "lineno", 0))
        self.generic_visit(node)

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - total on trees we just parsed
        return "<unparseable>"


def _unordered_label(node: ast.AST) -> str | None:
    """Return a stable description when *node* iterates an unordered collection."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in UNORDERED_METHODS:
            return _unparse(node)
        if isinstance(func, ast.Name) and func.id == "set":
            return _unparse(node)
    if isinstance(node, ast.Set):
        return _unparse(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.Sub)):
        if _unordered_label(node.left) or _unordered_label(node.right):
            return _unparse(node)
    return None


def _scan(rel: str) -> _Scan | None:
    path = common.project_dir() / rel
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, SyntaxError):
        return None
    scan = _Scan(rel)
    scan.visit(tree)
    return scan


def _planning_modules() -> Iterator[str]:
    root = common.project_dir()
    for path in sorted((root / WATCHED).rglob("*.py")):
        yield path.relative_to(root).as_posix()


def _load_baseline() -> set[tuple[str, str, str, str]]:
    try:
        raw = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        (item["file"], item["scope"], item["category"], item["label"])
        for item in raw.get("allowed", [])
    }


def _write_baseline() -> int:
    seen: set[tuple[str, str, str, str]] = set()
    for rel in _planning_modules():
        scan = _scan(rel)
        if scan:
            seen.update((rel, scope, category, label) for _, scope, category, label in scan.findings)
    payload = {
        "_comment": (
            "Pre-existing determinism findings in src/planning/, allowlisted so "
            "check_determinism.py reports only NEW sites. 'order' entries are "
            "order-independent dict/set accumulation; 'input' entries are "
            "time.perf_counter() calls that only populate stats.day_runtimes. "
            "Regenerate deliberately, never to silence a real finding."
        ),
        "allowed": [
            {"file": f, "scope": s, "category": c, "label": lab}
            for f, s, c, lab in sorted(seen)
        ],
    }
    BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(seen)


HEADLINE = {
    INPUT: (
        "NONDETERMINISM in the planner -- output would depend on something other than input:",
        "CLAUDE.md law 3: 'Same profile + recipe pool + seed -> same plan. No wall-clock, no "
        "unseeded randomness, no unsorted dict/set iteration in src/planning/.'\n"
        "Thread the existing seed through instead (random.Random(seed) is fine). Timing that "
        "only feeds stats is the one tolerated use -- if that is what this is, say so in your "
        "summary rather than letting it reach a branch.",
    ),
    ORDER: (
        "NEW unsorted iteration in the planner:",
        "CLAUDE.md trap 6: 'sort before iterating over dict/set contents. sorted() is cheap; "
        "debugging nondeterminism is not.'\n"
        "Wrap the iterable in sorted(). If the order provably cannot affect output, state that "
        "in your summary rather than adding it to the baseline.",
    ),
}


def main() -> None:
    if "--write-baseline" in sys.argv:
        print(f"wrote {_write_baseline()} allowlisted sites to {BASELINE_FILE.name}")
        return

    event = common.read_event()
    touched = [rel for rel in common.edited_paths(event) if rel.startswith(WATCHED)]
    if not touched:
        common.ok()

    baseline = _load_baseline()
    fresh: dict[str, list[str]] = {INPUT: [], ORDER: []}

    for rel in touched:
        scan = _scan(rel)
        if not scan:
            continue
        for lineno, scope, category, label in scan.findings:
            if (rel, scope, category, label) not in baseline:
                suffix = f" in {scope}()" if category == ORDER else ""
                prefix = "iterates " if category == ORDER else ""
                fresh[category].append(f"  {rel}:{lineno}  {prefix}{label}{suffix}")

    for category in (INPUT, ORDER):
        if fresh[category]:
            headline, guidance = HEADLINE[category]
            common.block(f"{headline}\n\n" + "\n".join(fresh[category]) + f"\n\n{guidance}")

    common.ok()


if __name__ == "__main__":
    main()
