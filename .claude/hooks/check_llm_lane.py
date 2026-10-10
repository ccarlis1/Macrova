"""PostToolUse gate keeping the LLM in its lane (CLAUDE.md law 4, trap 7).

Law 4: nutrition numbers come only from computation -- the local ingredient DB
or USDA -- never from LLM output. The enforcement point is the structured-output
schema: if an LLM-facing pydantic model grows a ``calories`` field, the model is
being asked to invent nutrition, and guardrail AI-4 is gone.

``PlannerTargets`` is exempt and must stay exempt: its ``calories``/``protein``
(src/llm/schemas.py) are *user targets* parsed out of natural language, not
nutrition the model asserted about food. A hook that flagged them would be
wrong on day one and switched off by day two.
"""

from __future__ import annotations

import ast

import _common as common

WATCHED = "src/llm/"

#: Substrings that mean "a nutrition number" on a field name.
NUTRITION_TOKENS = (
    "calorie",
    "kcal",
    "protein",
    "carb",
    "sodium",
    "fiber",
    "fibre",
    "sugar",
    "cholesterol",
    "saturated",
    "micronutrient",
    "macronutrient",
    "nutrition",
    "nutrient",
    "vitamin",
    "mineral",
)

#: Field names that merely *contain* a token but carry no nutrition value.
FIELD_ALLOWLIST = {"nutrition_source", "nutrient_source", "tag_type", "nutrition_tag"}

#: Models whose nutrition-shaped fields are legitimately not LLM nutrition output.
CLASS_ALLOWLIST = {
    "PlannerTargets": "user targets parsed from natural language, not LLM-asserted nutrition",
}


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("BaseModel"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("BaseModel"):
            return True
    return False


def _field_names(node: ast.ClassDef) -> list[tuple[str, int]]:
    fields: list[tuple[str, int]] = []
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            fields.append((statement.target.id, statement.lineno))
    return fields


def _offending_fields(rel: str) -> list[str]:
    path = common.project_dir() / rel
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, SyntaxError):
        return []

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_pydantic_model(node):
            continue
        if node.name in CLASS_ALLOWLIST:
            continue
        for field, lineno in _field_names(node):
            lowered = field.lower()
            if lowered in FIELD_ALLOWLIST:
                continue
            hit = next((token for token in NUTRITION_TOKENS if token in lowered), None)
            if hit:
                findings.append(f"  {rel}:{lineno}  {node.name}.{field}  (matched '{hit}')")
    return findings


def main() -> None:
    event = common.read_event()
    touched = [
        rel
        for rel in common.edited_paths(event)
        if rel.startswith(WATCHED) and rel.endswith(".py")
    ]
    if not touched:
        common.ok()

    findings: list[str] = []
    for rel in touched:
        findings.extend(_offending_fields(rel))
    if not findings:
        common.ok()

    exempt = ", ".join(f"{name} ({why})" for name, why in CLASS_ALLOWLIST.items())
    common.block(
        "LLM LANE VIOLATION -- a nutrition field on an LLM-facing schema:\n\n"
        + "\n".join(findings)
        + "\n\nCLAUDE.md law 4: 'Nutrition numbers come only from computation (local ingredient "
        "DB or USDA), never from LLM output. LLM JSON schemas deliberately exclude nutrition "
        "fields -- keep it that way.'\n\n"
        "Compute the value after validation from USDA/local data (guardrail AI-4) instead.\n"
        f"Already exempt: {exempt}. If this field is genuinely the same kind of exception, add "
        "it to CLASS_ALLOWLIST in this hook with the reason -- don't widen the tokens."
    )


if __name__ == "__main__":
    main()
