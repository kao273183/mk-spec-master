"""MCP entrypoint. Currently a stub — registers one introspection tool so
Glama / Smithery sandboxes get a clean `initialize` + `tools/list` response.

Full tool surface lands in v0.1 (see docs/prd.md §8).
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from . import __version__
from .adapters import REGISTRY
from .config import SOURCE_NAME

app = Server("mk-spec-master")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_spec_source_info",
            description=(
                "Return the active spec source (selected via SPEC_SOURCE env var) "
                "plus all adapters built into this server. Mirrors mk-qa-master's "
                "get_runner_info — call this first in any session so the AI knows "
                "which adapter is active before issuing further calls. "
                "Returns: {active: 'markdown_local', available: ['markdown_local', "
                "'github_issues', ...], version: '0.0.1'}."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get_spec_source_info":
        payload = {
            "active": SOURCE_NAME,
            "available": sorted(REGISTRY),
            "version": __version__,
        }
        return [TextContent(type="text", text=json.dumps(payload, indent=2))]

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {"error": f"unknown tool: {name}", "available": ["get_spec_source_info"]},
            ),
        )
    ]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
