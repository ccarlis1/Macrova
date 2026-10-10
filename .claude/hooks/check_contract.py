"""PostToolUse gate for API/DTO contract changes (CLAUDE.md law 2, trap 2).

Two checks, in severity order:

1. **Non-additive break** -- the committed OpenAPI snapshot at ``HEAD`` is
   compared field by field against the schema the edited code would produce.
   Removing or retyping an existing field, dropping a path or schema, or making
   a previously optional field required all break clients in the wild. CI cannot
   catch this: its drift check only compares the snapshot to the code, so a
   change that edits *both* passes CI while breaking Flutter.
2. **Snapshot drift** -- ``scripts/export_openapi.py --check``, the CI gate.

Silent unless the edit touched a file that can move the API surface.
"""

from __future__ import annotations

import json
from typing import Any

import _common as common

WATCHED = ("src/api/", "src/models/", "src/llm/schemas.py", "src/planning/phase10_reporting.py")
SNAPSHOT = "openapi/openapi.json"


def _schema_identity(node: Any) -> str | None:
    """The part of a property schema that clients bind to: its type or ref."""
    if not isinstance(node, dict):
        return None
    if "$ref" in node:
        return f"$ref={node['$ref']}"
    if "type" in node:
        return f"type={node['type']}"
    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator in node:
            parts = [_schema_identity(item) or "?" for item in node[combinator]]
            return f"{combinator}=[{','.join(sorted(parts))}]"
    return None


def _breaking_changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Every way *new* stops honouring the contract *old* already published."""
    problems: list[str] = []

    old_paths = old.get("paths") or {}
    new_paths = new.get("paths") or {}
    for path, operations in sorted(old_paths.items()):
        if path not in new_paths:
            problems.append(f"path {path} was removed")
            continue
        for method in sorted(operations):
            if method not in new_paths[path]:
                problems.append(f"operation {method.upper()} {path} was removed")

    old_schemas = (old.get("components") or {}).get("schemas") or {}
    new_schemas = (new.get("components") or {}).get("schemas") or {}
    for name, schema in sorted(old_schemas.items()):
        if name not in new_schemas:
            problems.append(f"schema {name} was removed")
            continue
        fresh = new_schemas[name]

        old_props = schema.get("properties") or {}
        new_props = fresh.get("properties") or {}
        for field, definition in sorted(old_props.items()):
            if field not in new_props:
                problems.append(f"{name}.{field} was removed or renamed")
                continue
            was, now = _schema_identity(definition), _schema_identity(new_props[field])
            if was and now and was != now:
                problems.append(f"{name}.{field} changed type ({was} -> {now})")

        newly_required = sorted(set(fresh.get("required") or []) - set(schema.get("required") or []))
        for field in newly_required:
            problems.append(
                f"{name}.{field} became required (old clients that omit it now fail)"
            )

    return problems


def main() -> None:
    event = common.read_event()
    touched = [rel for rel in common.edited_paths(event) if rel.startswith(WATCHED)]
    if not touched:
        common.ok()

    fresh_file = common.state_dir() / "openapi.fresh.json"
    rc, out = common.run(
        [common.project_python(), "scripts/export_openapi.py", "--output", str(fresh_file)],
        timeout=60,
    )
    if rc != 0:
        common.block(
            "The OpenAPI schema could not be exported after your edit -- the app no longer "
            f"imports cleanly:\n\n{out.strip()[-1500:]}"
        )

    committed = common.git_show(f"HEAD:{SNAPSHOT}")
    if committed:
        try:
            problems = _breaking_changes(
                json.loads(committed), json.loads(fresh_file.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, OSError):
            problems = []
        if problems:
            listed = "\n".join(f"  - {problem}" for problem in problems[:15])
            common.block(
                "BREAKING API CONTRACT CHANGE -- this is not additive:\n\n"
                f"{listed}\n\n"
                "CLAUDE.md law 2: 'API request/response fields, persisted JSON shapes, and "
                "Flutter DTOs only gain optional fields. Never rename, remove, or change the "
                "type of an existing field.'\n\n"
                "§8 makes this the user's call. Stop, and present the additive alternative "
                "(a new optional field, a new endpoint, or /api/v2) alongside it."
            )

    rc, out = common.run(
        [common.project_python(), "scripts/export_openapi.py", "--check"], timeout=60
    )
    if rc != 0:
        common.block(
            f"OpenAPI snapshot drift -- CI fails on this ('{out.strip().splitlines()[-1][:200]}').\n\n"
            "Run `python scripts/export_openapi.py` and commit openapi/openapi.json "
            "(CLAUDE.md trap 2)."
        )

    common.ok()


if __name__ == "__main__":
    main()
