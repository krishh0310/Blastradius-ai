"""Opt-in real stdio protocol and seeded FalkorDB checks; no provider calls."""

import asyncio
import os

import pytest
from mcp import Client

from src.agent import AgentRequest, mcp_target, run_agent_mcp, simulate_recommended
from src.config import Settings
from src.dashboard_service import SCENARIOS
from src.database import DatabaseManager
from src.graph_queries import GraphQueries
from src.tooling import TOOL_NAMES, ToolResult

pytestmark = pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires seeded local FalkorDB"
)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_live_agent_scenarios(name):
    scenario = SCENARIOS[name]
    request = AgentRequest(
        component=scenario.component_id, incident=scenario.text, status=scenario.status
    )
    result = asyncio.run(run_agent_mcp(request))
    assert result.transport == "MCP"
    assert result.planner == "deterministic fallback"
    assert result.final_confidence == "Graph-supported exposure"
    assert len(result.trace) <= 8
    assert all(not step.output.error for step in result.trace)
    assert all(step.output.reasoning_engine == "FalkorDB Cypher" for step in result.trace)
    assert all(step.output.query_diagnostics for step in result.trace)
    assert result.analysis
    if name == "Token Vault timeout":
        assert result.analysis.risk.severity == "Critical"
        customers = next(step.output for step in result.trace if step.output.customers)
        assert len(customers.customers) == 6
        assert max(item.hops for item in customers.customers) >= 3
    if name == "Mumbai region outage":
        assert any(
            "envelope" in warning.lower()
            for step in result.trace
            for warning in step.output.warnings
        )


def test_live_stdio_registry_and_confirmed_action_preserve_seed():
    settings = Settings.from_env()

    def snapshot():
        with DatabaseManager(settings) as db:
            graph = GraphQueries.from_database(db)
            return (
                [node.model_dump() for node in graph.nodes.values()],
                [edge.model_dump() for edge in graph.edges],
            )

    before = snapshot()

    async def check():
        async with Client(mcp_target(settings)) as client:
            registry = await client.list_tools()
            assert {item.name for item in registry.tools} == set(TOOL_NAMES)
            reply = await client.call_tool("lookup_component", {"component": "Token Vault"})
            assert ToolResult.model_validate(reply.structured_content).component.id == "vault"
            reply = await client.call_tool("lookup_component", {"component": "x'}) DELETE n //"})
            assert ToolResult.model_validate(reply.structured_content).error == "invalid_input"
            reply = await client.call_tool("lookup_component", {"component": "vault", "depth": 9})
            assert ToolResult.model_validate(reply.structured_content).error == "invalid_input"
        request = AgentRequest(component="vault", depth=8)
        result = await run_agent_mcp(request)
        denied = await simulate_recommended(result, request, confirmed=False)
        assert len(denied.trace) == 7
        confirmed = await simulate_recommended(result, request, confirmed=True)
        assert len(confirmed.trace) == 8
        comparison = confirmed.trace[-1].output.simulation
        assert comparison and comparison.risk_reduction == 49
        assert comparison.after.risk.score == 42.62
        return confirmed

    asyncio.run(check())
    assert snapshot() == before
