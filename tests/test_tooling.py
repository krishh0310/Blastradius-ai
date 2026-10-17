"""Typed tools share graph services and fail closed at the protocol boundary."""

import asyncio
import time
from unittest.mock import patch

import pytest
from mcp import Client

from src.config import Settings


def test_regional_tools_preserve_deployment_and_business_paths(graph):
    tools = service(graph)
    impact = tools.call("find_customer_impact", {"component": "mumbai"})
    assert impact.customers
    assert all(item.path.node_ids[0] == "mumbai" for item in impact.customers)
    risk = tools.call("calculate_risk", {"component": "mumbai"})
    assert risk.analysis and risk.analysis.risk.score == 91.62
    assert "envelope" in " ".join(risk.warnings).lower()


def service(graph):
    from src.tooling import ToolService

    return ToolService(Settings(), queries=graph)


def test_lookup_and_business_evidence(graph):
    tools = service(graph)
    lookup = tools.call("lookup_component", {"component": "Token Vault"})
    assert lookup.component.id == "vault"
    customers = tools.call("find_customer_impact", {"component": "vault"})
    assert len(customers.customers) == 6
    assert customers.workflows
    assert all(p.hops == len(p.edges) for p in customers.paths)
    assert all(p.node_ids[0] == "vault" for p in customers.paths)
    assert customers.evidence_ids and customers.duration_ms >= 0


@pytest.mark.parametrize(
    "name",
    [
        "trace_upstream_dependencies",
        "trace_downstream_blast_radius",
        "find_business_workflows",
        "find_critical_paths",
        "detect_bottlenecks",
        "get_owner_and_runbook",
        "calculate_risk",
        "inspect_falkordb_evidence",
    ],
)
def test_registered_read_tools_return_typed_evidence(graph, name):
    result = service(graph).call(name, {"component": "vault"})
    assert result.error is None
    assert result.component.id == "vault"
    assert result.paths
    assert result.evidence_ids


@pytest.mark.parametrize(
    "arguments",
    [
        {"component": "vault", "depth": 9},
        {"component": "vault", "depth": True},
        {"component": "vault", "max_paths": 101},
        {"component": "vault' MATCH (n) DETACH DELETE n //"},
        {"component": "vault", "cypher": "RETURN 1"},
        {"component": "vault", "depth": "6"},
    ],
)
def test_invalid_inputs_do_not_enter_graph_code(graph, arguments):
    result = service(graph).call("lookup_component", arguments)
    assert result.error == "invalid_input"
    assert not result.paths


def test_unknown_tools_components_caps_and_secrets(graph):
    tools = service(graph)
    assert tools.call("execute_python", {"component": "vault"}).error == "unknown_tool"
    assert tools.call("lookup_component", {"component": "Token Vualt"}).suggestions
    limited = tools.call("trace_downstream_blast_radius", {"component": "vault", "max_paths": 1})
    assert len(limited.impacts) <= 1 and limited.warnings
    tools.max_result_bytes = 100
    assert tools.call("find_customer_impact", {"component": "vault"}).error == "result_limit"
    tools = service(graph)
    tools.settings = Settings(groq_api_key="private-test-credential")
    graph.nodes["vault"].description = "private-test-credential"
    assert (
        "private-test-credential"
        not in tools.call("lookup_component", {"component": "vault"}).model_dump_json()
    )


def test_tool_timeout_and_busy_work_are_bounded(graph):
    tools = service(graph)
    tools.timeout_seconds = 0.01
    original = tools.call

    def slow(name, args):
        time.sleep(0.05)
        return original(name, args)

    async def check():
        with patch.object(tools, "call", side_effect=slow):
            result = await tools.execute("lookup_component", {"component": "vault"})
            assert result.error == "timeout"
            assert (await tools.execute("lookup_component", {"component": "vault"})).error == "busy"

    asyncio.run(check())


def test_real_mcp_discovery_and_structured_call(graph):
    from src.mcp_server import create_server
    from src.tooling import TOOL_NAMES

    async def check():
        async with Client(create_server(service(graph))) as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == set(TOOL_NAMES)
            assert all(tool.input_schema and tool.output_schema for tool in listing.tools)
            response = await client.call_tool("lookup_component", {"component": "vault"})
            assert response.structured_content["component"]["id"] == "vault"
            bad = await client.call_tool(
                "lookup_component", {"component": "vault", "extra": "private"}
            )
            assert bad.is_error
            assert "private" not in str(bad)

    asyncio.run(check())
