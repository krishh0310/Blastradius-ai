"""Official SDK stdio MCP server with explicit schemas and sanitized errors."""

import asyncio
import logging

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from src.config import Settings
from src.tooling import TOOL_NAMES, SimulationInput, ToolInput, ToolResult, ToolService


def create_server(service: ToolService | None = None) -> Server:
    service = service or ToolService(Settings.from_env())

    async def list_tools(context, params):
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=name,
                    description="Fictional graph evidence only; bounded inputs, no infrastructure writes. "
                    + name.replace("_", " "),
                    inputSchema=(
                        SimulationInput if name == "simulate_fictional_mitigation" else ToolInput
                    ).model_json_schema(),
                    outputSchema=ToolResult.model_json_schema(),
                    annotations=types.ToolAnnotations(
                        readOnlyHint=True, destructiveHint=False, openWorldHint=False
                    ),
                )
                for name in TOOL_NAMES
            ]
        )

    async def call_tool(context, params):
        result = await service.execute(params.name, params.arguments or {})
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.model_dump_json())],
            structuredContent=result.model_dump(mode="json"),
            isError=bool(result.error),
        )

    return Server("BlastRadius AI", version="1.0", on_list_tools=list_tools, on_call_tool=call_tool)


async def serve() -> None:
    server = create_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(serve())


if __name__ == "__main__":
    main()
