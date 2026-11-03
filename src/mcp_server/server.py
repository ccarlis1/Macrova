"""Macrova MCP server: read-only planning tools over stdio (local) or streamable HTTP (hosted).

Run it from anywhere:

    python -m src.mcp_server                     # stdio, for Claude Desktop / Claude Code
    python -m src.mcp_server --transport http    # streamable HTTP on 127.0.0.1:8000/mcp

The tool logic lives in :mod:`src.mcp_server.tools`; this module registers it with
the SDK. ``isError`` is only for bad input: an infeasible plan is a normal result
with ``status: "failed"``.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from typing import Annotated, Iterator, List, Optional

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from src.mcp_server import models as m
from src.mcp_server import tools

INSTRUCTIONS = (
    "Macrova plans meals with a deterministic planner. Every call is stateless: send the "
    "targets, schedule and recipes each time. Days and meals are numbered from 1. Never "
    "change the user's calories, macros, exclusions, pins or schedule on your own to make "
    "a plan succeed; explain the failure and ask what they want to change."
)

PLAN_DESCRIPTION = (
    "Generate a meal plan of 1–7 days from the user's nutrition targets, schedule and recipes. "
    "The planner is deterministic and guarantees daily macro limits and weekly micronutrient "
    "minimums. If no valid plan exists, the result has status \"failed\" with an explanation "
    "and a suggested fix. Tell the user about it and ask them what to change. Never change "
    "targets, exclusions, pins or the schedule on your own to make a plan succeed."
)
ANALYZE_DESCRIPTION = (
    "Check a recipe's ingredients against the nutrition database and return per-serving macros "
    "and micronutrients. Use it before adding a recipe you wrote to a plan. Report any unmatched "
    "ingredients to the user rather than guessing."
)
SAMPLES_DESCRIPTION = (
    "Return Macrova's bundled sample recipes, with per-serving calories and protein, so a new "
    "user can plan right away (or pass use_sample_recipes to macrova_plan_meals)."
)
TAGS_DESCRIPTION = (
    "List the tag slugs recipes and meals can use. Only can_require tags work in a meal's "
    "required_tags; any tag works in preferred_tags and in a recipe's tags."
)


@contextlib.contextmanager
def _tool_errors() -> Iterator[None]:
    """Report bad input as ``isError``. (The SDK's stdio transport keeps stray prints off the wire.)"""
    try:
        yield
    except tools.InputError as exc:
        raise ToolError(str(exc)) from exc


def _read_only(title: str, *, open_world: bool = False) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=open_world,
    )


def build_server() -> MCPServer:
    server = MCPServer("macrova", title="Macrova", instructions=INSTRUCTIONS)
    usda = tools.usda_enabled()

    @server.tool(
        name="macrova_plan_meals",
        description=PLAN_DESCRIPTION,
        annotations=_read_only("Plan meals", open_world=usda),
    )
    def plan_meals(
        days: Annotated[int, Field(ge=1, le=7)],
        targets: m.Targets,
        preferences: Optional[m.Preferences] = None,
        schedule: Annotated[
            Optional[m.Schedule],
            Field(description="Either the shorthand or the full per-day schedule. If omitted: 3 meals per day, busyness 2/3/3."),
        ] = None,
        recipes: Annotated[
            List[m.Recipe], Field(description="The recipe pool. Same shape as macrova_get_sample_recipes output.")
        ] = [],
        use_sample_recipes: Annotated[bool, Field(description="Add the bundled sample recipes to the pool.")] = False,
        pins: Annotated[List[m.Pin], Field(description="Fixed assignments the planner must keep.")] = [],
        meal_prep: Annotated[
            List[m.MealPrep],
            Field(description="Batch-cooked recipes. Servings are placed only where assigned; leftovers are never auto-allocated."),
        ] = [],
    ) -> Annotated[CallToolResult, m.PlanResult]:
        with _tool_errors():
            result, markdown = tools.plan_meals(
                days=days,
                targets=targets,
                preferences=preferences,
                schedule=schedule,
                recipes=recipes,
                use_sample_recipes=use_sample_recipes,
                pins=pins,
                meal_prep=meal_prep,
            )
        return CallToolResult(
            content=[TextContent(type="text", text=markdown)],
            structured_content=result.model_dump(mode="json"),
        )

    @server.tool(
        name="macrova_analyze_recipe",
        description=ANALYZE_DESCRIPTION,
        annotations=_read_only("Analyze a recipe", open_world=usda),
    )
    def analyze_recipe(
        recipe: m.Recipe,
        servings: Annotated[int, Field(ge=1, description="How many servings the ingredient list makes.")] = 1,
    ) -> m.RecipeAnalysis:
        with _tool_errors():
            return tools.analyze_recipe(recipe, servings)

    @server.tool(
        name="macrova_get_sample_recipes",
        description=SAMPLES_DESCRIPTION,
        annotations=_read_only("Get sample recipes"),
    )
    def get_sample_recipes() -> m.SampleRecipes:
        with _tool_errors():
            return tools.get_sample_recipes()

    @server.tool(
        name="macrova_list_tags",
        description=TAGS_DESCRIPTION,
        annotations=_read_only("List tags"),
    )
    def list_tags() -> m.TagList:
        with _tool_errors():
            return tools.list_tags()

    return server


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.mcp_server", description=__doc__.splitlines()[0])
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP only.")
    parser.add_argument("--port", type=int, default=8000, help="HTTP only.")
    args = parser.parse_args(argv)

    # The planner and the data layer read reference files by repo-relative path,
    # and MCP clients start servers from an arbitrary working directory.
    os.chdir(tools.ROOT)
    server = build_server()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        # Stateless: every call carries everything, so no session state to keep.
        server.run("streamable-http", host=args.host, port=args.port, stateless_http=True, json_response=True)


if __name__ == "__main__":
    main()
