"""PreToolUse guard for file-writing tools.

Enforces the parts of AGENTS.md that no test can catch, because they are about
files that must *not* change:

* the user's real profile/ingredient data and the committed recipe and tag
  stores are never rewritten by hand -- changing them is the user's call
  (AGENTS.md invariants "User data paths" and "One tag source").
* one owner per concern -- creating a second
  owner for an existing concern is refused outright for known fork paths, and
  escalated to the user for any other new module under ``src/``.

Editing an existing file is untouched by this hook. Every ``*.example`` file is
always allowed -- that is the sanctioned way to change shipped data shapes.
"""

from __future__ import annotations

import re

import _common as common

#: User-owned or store-owned files. Value is why the file is off-limits.
PROTECTED: dict[str, str] = {
    "config/user_profile.yaml": (
        "the user's real profile -- don't casually rewrite it (AGENTS.md invariant "
        "\"User data paths\")"
    ),
    "config/nutrition_goals.yaml": "user config",
    "config/model_config.yaml": "user config",
    "data/recipes/recipes.json": (
        "the committed recipe pool -- write it through src/data_layer/recipe_db.py / "
        "the sync API, not by hand"
    ),
    "data/recipes/recipe_tags.json": (
        "the runtime tag store owned by src/llm/tag_repository.py -- write it through "
        "the repository, not by hand"
    ),
    "data/ingredients/custom_ingredients.json": "the user's real ingredient data (gitignored)",
    "data/ingredients/usda_ingredients.json": "cached USDA data",
    "data/nutrition/nutrition_db.json": "nutrition data",
    "data/llm/feedback_cache.json": "the LLM feedback cache, written by src/llm/feedback_cache.py",
    ".env": "real API keys",
}

#: Paths that would fork a pipeline that already has exactly one owner.
FORK_PATTERNS: list[tuple[str, str]] = [
    (
        r"^data/tags/",
        "Tag persistence is owned by data/recipes/recipe_tags.json via "
        "src/llm/tag_repository.py. AGENTS.md invariant \"One tag source\": no second tag store.",
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
        "Extend, never fork: a '_v2' module is a parallel pipeline by definition -- "
        "evolve the existing owner additively instead.",
    ),
    (
        r"^src/planning/plan_.*\.py$",
        "The planner entry point is src/planning/planner.py::plan_meals -> "
        "phase7_search.run_meal_plan_search. No shadow plan() helpers.",
    ),
    (
        r"^src/llm/tag_filter_.+\.py$",
        "One filter pipeline only: src/llm/tag_filtering_service.py + tag_filter.py.",
    ),
]

#: Filename keyword -> the owner most likely to already cover the concern.
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
        "Deleting or overwriting anything under data/ or config/ that isn't a .example "
        "file is the user's decision, not yours.",
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
    return "Check docs/architecture/map/ for the module that already owns this concern."


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
                    "One canonical path per concern -- extend, never fork."
                )

        # Only Write creates files; Edit on a missing file fails on its own.
        if tool == "Write" and rel.startswith("src/") and not (root / rel).exists():
            common.ask(
                f"New module: {rel}\n\n"
                f"{_ownership_hint(rel)}\n\n"
                "A parallel pipeline is the repo's most common failure: before creating any "
                "file, grep for the module that already owns the concern. Approve only if "
                "no existing module can be extended to cover this."
            )

    common.ok()


if __name__ == "__main__":
    main()
