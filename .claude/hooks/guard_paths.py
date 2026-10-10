"""PreToolUse guard for file-writing tools.

Enforces the parts of CLAUDE.md that no test can catch, because they are about
files that must *not* change:

* §2 data-file rules and §8 "stop and ask" -- the user's real, gitignored
  profile/recipe/ingredient data is never rewritten by an agent (trap 4).
* §3 ownership map and trap 1 (The Parallel Pipeline) -- creating a second
  owner for an existing concern is refused outright for known fork paths, and
  escalated to the user for any other new module under ``src/``.

Editing an existing file is untouched by this hook. Every ``*.example`` file is
always allowed -- that is the sanctioned way to change shipped data shapes.
"""

from __future__ import annotations

import re

import _common as common

#: Gitignored, user-owned files. Value is why the file is off-limits.
PROTECTED: dict[str, str] = {
    "config/user_profile.yaml": (
        "the user's real profile -- CLAUDE.md §2: 'This is the user's real profile. "
        "Edits show up in git status; don't casually rewrite it.'"
    ),
    "config/nutrition_goals.yaml": "gitignored user config",
    "config/model_config.yaml": "gitignored user config",
    "data/recipes/recipes.json": "the user's real recipe pool (gitignored)",
    "data/recipes/recipe_tags.json": (
        "the runtime tag store owned by src/llm/tag_repository.py -- write it through "
        "the repository, not by hand"
    ),
    "data/ingredients/custom_ingredients.json": "the user's real ingredient data (gitignored)",
    "data/ingredients/usda_ingredients.json": "gitignored cached USDA data",
    "data/nutrition/nutrition_db.json": "gitignored nutrition data",
    "data/llm/feedback_cache.json": "the LLM feedback cache, written by src/llm/feedback_cache.py",
    ".env": "real API keys",
}

#: Paths that would fork a pipeline that already has exactly one owner (§3).
FORK_PATTERNS: list[tuple[str, str]] = [
    (
        r"^data/tags/",
        "Tag persistence is owned by data/recipes/recipe_tags.json via "
        "src/llm/tag_repository.py. CLAUDE.md §3: 'No second tag store, ever.'",
    ),
    (
        r"(^|/)tag_service\.py$",
        "Tag registry + persistence is owned by src/llm/tag_repository.py; filtering by "
        "apply_tag_filtering in src/llm/tag_filtering_service.py. Extend those.",
    ),
    (
        r"(^|/)tag_registry\.py$",
        "The tag registry lives in src/llm/tag_repository.py -- extend it.",
    ),
    (
        r"(^|/)[A-Za-z0-9_]+_v2\.py$",
        "CLAUDE.md law 1: extend, never fork. A '_v2' module is the Parallel Pipeline "
        "trap by definition -- evolve the existing owner additively instead.",
    ),
    (
        r"^src/planning/plan_.*\.py$",
        "The planner entry point is src/planning/planner.py::plan_meals -> "
        "phase7_search.run_meal_plan_search. CLAUDE.md §3: 'No shadow plan() helpers.'",
    ),
    (
        r"^src/llm/tag_filter_.+\.py$",
        "One filter pipeline only: src/llm/tag_filtering_service.py + tag_filter.py.",
    ),
]

#: Filename keyword -> the §3 owner most likely to already cover the concern.
OWNERSHIP_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        ("tag",),
        "src/llm/tag_repository.py (registry + persistence) and "
        "src/llm/tag_filtering_service.py / tag_filter.py (filtering)",
    ),
    (
        ("phase", "search", "candidate", "constraint", "feasib", "scor", "order", "backtrack"),
        "src/planning/phaseN_*.py -- planner.py::plan_meals delegates to "
        "phase7_search.run_meal_plan_search; extend the owning phase",
    ),
    (
        ("api", "route", "endpoint", "server"),
        "src/api/server.py, or a focused router like src/api/tag_routes.py included "
        "with prefix='/api/v1'",
    ),
    (
        ("error", "exception"),
        "src/api/error_mapping.py::map_exception_to_api_error (every new exception type "
        "gets a mapping + status code there)",
    ),
    (
        ("schema", "prompt", "pipeline", "generat", "valid"),
        "src/llm/schemas.py (structured outputs) and src/llm/pipeline.py "
        "(generation/validation flow) -- extend, don't parallel",
    ),
    (
        ("schedule", "slot", "workout"),
        "src/models/schedule.py -- its module docstring is the contract; legacy YAML "
        "mapping lives in src/models/legacy_schedule_migration.py",
    ),
    (
        ("ingredient", "nutrition", "usda", "provider", "nutrient"),
        "the provider abstraction in src/providers/ (all lookups resolve before "
        "planning), with parsing/ranking helpers in src/ingestion/",
    ),
    (
        ("convert", "adapter", "profile"),
        "src/planning/converters.py (convert_profile, convert_recipes, "
        "extract_ingredient_names)",
    ),
    (
        ("report", "result", "format", "output"),
        "MealPlanResult in src/planning/phase10_reporting.py (extend its report) and "
        "src/output/formatters.py",
    ),
]


def _protected_reason(rel: str, why: str) -> str:
    example = common.project_dir() / (rel + ".example")
    lines = [
        f"BLOCKED: {rel} is {why}.",
        "",
        "CLAUDE.md §8 lists 'deleting/overwriting anything under data/ or config/ that "
        "isn't a .example file' as the user's decision, not yours.",
    ]
    if example.is_file():
        lines.append(f"If you need to change the shipped shape, edit {rel}.example instead.")
    lines.append("If the user explicitly asked for this file to change, ask them to confirm.")
    return "\n".join(lines)


def _ownership_hint(rel: str) -> str:
    stem = rel.rsplit("/", 1)[-1].lower()
    for keywords, owner in OWNERSHIP_HINTS:
        if any(keyword in stem for keyword in keywords):
            return f"The concern in '{stem}' looks like it is already owned by {owner}."
    return "Check the §3 ownership table in CLAUDE.md for the module that already owns this concern."


def main() -> None:
    event = common.read_event()
    tool = event.get("tool_name", "")
    root = common.project_dir()

    for rel in common.edited_paths(event):
        if rel.endswith(".example"):
            continue

        why = PROTECTED.get(rel)
        if why:
            common.deny(_protected_reason(rel, why))

        for pattern, explanation in FORK_PATTERNS:
            if re.search(pattern, rel):
                common.deny(
                    f"BLOCKED: creating {rel} forks a pipeline that already has one owner.\n\n"
                    f"{explanation}\n\n"
                    "CLAUDE.md law 1: 'One canonical path -- extend, never fork.'"
                )

        # Only Write creates files; Edit on a missing file fails on its own.
        if tool == "Write" and rel.startswith("src/") and not (root / rel).exists():
            common.ask(
                f"New module: {rel}\n\n"
                f"{_ownership_hint(rel)}\n\n"
                "CLAUDE.md trap 1 (The Parallel Pipeline) is the repo's most common failure: "
                "'before creating any file, grep for the owning module in §3'. Approve only if "
                "no existing module can be extended to cover this."
            )

    common.ok()


if __name__ == "__main__":
    main()
