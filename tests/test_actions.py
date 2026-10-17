"""Fictional actions require real graph relationships and explicit confirmation."""

import asyncio

import pytest

from src.config import Settings
from src.tooling import ToolService


def test_vault_has_containment_but_no_invented_replica(graph):
    from src.actions import action_options, recommend_action

    options = {item.action: item for item in action_options(graph, "vault")}
    assert not options["activate_declared_replica"].eligible
    assert options["isolate_unhealthy_dependency"].eligible
    assert options["execute_fictional_runbook"].eligible
    chosen = recommend_action(list(options.values()))
    assert chosen.action == "isolate_unhealthy_dependency"
    assert all(path.edges for path in chosen.paths)
    assert all(path.node_ids[0] == "vault" for path in chosen.paths)


def test_optional_feature_and_replica_are_graph_gated(graph):
    from src.actions import action_options, recommend_action

    optional = recommend_action(action_options(graph, "email-api"))
    assert optional.action == "disable_optional_feature"
    assert all(not edge.required for path in optional.paths for edge in path.edges)
    replicas = {item.action: item for item in action_options(graph, "payment")}
    assert replicas["activate_declared_replica"].eligible
    assert any(
        edge.type in {"DEPLOYED_IN", "REPLICATES_TO"}
        for path in replicas["activate_declared_replica"].paths
        for edge in path.edges
    )
    assert not any(item.eligible for item in action_options(graph, "missing"))
    assert not any(item.eligible for item in action_options(graph, "vault", status="healthy"))


@pytest.mark.parametrize("confirmed", [False, "true", 1])
def test_simulation_cannot_bypass_human_confirmation(graph, confirmed):
    result = ToolService(Settings(), queries=graph).call(
        "simulate_fictional_mitigation",
        {"component": "vault", "action": "isolate_unhealthy_dependency", "confirmed": confirmed},
    )
    assert result.error in {"confirmation_required", "invalid_input"}
    assert result.simulation is None


def test_confirmed_simulation_rechecks_gate_and_keeps_graph_unchanged(graph):
    original = (
        [node.model_dump() for node in graph.nodes.values()],
        [edge.model_dump() for edge in graph.edges],
    )
    tools = ToolService(Settings(), queries=graph)
    no_replica = tools.call(
        "simulate_fictional_mitigation",
        {"component": "vault", "action": "activate_declared_replica", "confirmed": True},
    )
    assert no_replica.error == "action_rejected"
    result = tools.call(
        "simulate_fictional_mitigation",
        {"component": "vault", "action": "isolate_unhealthy_dependency", "confirmed": True},
    )
    assert result.error is None
    assert result.simulation.risk_reduction == 49
    assert result.simulation.after.risk.score == 42.62
    assert result.paths and result.evidence_ids
    assert original == (
        [node.model_dump() for node in graph.nodes.values()],
        [edge.model_dump() for edge in graph.edges],
    )


def test_agent_recommendation_never_executes_it_automatically(graph):
    from src.agent import AgentRequest, run_agent

    service = ToolService(Settings(), queries=graph)
    result = asyncio.run(run_agent(AgentRequest(component="vault"), service.execute))
    assert result.recommendation.action == "isolate_unhealthy_dependency"
    assert all(step.tool != "simulate_fictional_mitigation" for step in result.trace)
    assert len(result.trace) == 7


def test_confirmed_mcp_action_is_eighth_call_and_cannot_repeat(graph):
    from src.agent import AgentRequest, run_agent, simulate_recommended
    from src.mcp_server import create_server

    service = ToolService(Settings(), queries=graph)
    request = AgentRequest(component="vault")
    result = asyncio.run(run_agent(request, service.execute))
    refused = asyncio.run(
        simulate_recommended(result, request, confirmed=False, server=create_server(service))
    )
    assert len(refused.trace) == 7
    confirmed = asyncio.run(
        simulate_recommended(result, request, confirmed=True, server=create_server(service))
    )
    assert len(confirmed.trace) == 8
    assert confirmed.trace[-1].output.simulation.risk_reduction == 49
    repeated = asyncio.run(
        simulate_recommended(confirmed, request, confirmed=True, server=create_server(service))
    )
    assert len(repeated.trace) == 8
    assert "budget" in repeated.stopping_reason.lower()


def test_replica_action_compares_against_no_automatic_recovery(graph):
    result = ToolService(Settings(), queries=graph).call(
        "simulate_fictional_mitigation",
        {
            "component": "payment",
            "action": "activate_declared_replica",
            "confirmed": True,
        },
    )
    assert result.simulation.risk_reduction > 0


@pytest.mark.parametrize(
    "component,action",
    [
        ("payment", "reroute_traffic"),
        ("vault", "switch_to_read_only_mode"),
        ("email-api", "disable_optional_feature"),
        ("vault", "execute_fictional_runbook"),
    ],
)
def test_other_supported_actions_return_relationship_evidence(graph, component, action):
    result = ToolService(Settings(), queries=graph).call(
        "simulate_fictional_mitigation",
        {
            "component": component,
            "action": action,
            "confirmed": True,
        },
    )
    assert result.error is None and result.simulation
    assert any(path.edges for path in result.paths)
