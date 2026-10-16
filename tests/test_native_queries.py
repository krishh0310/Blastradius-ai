"""Native retrieval contracts and opt-in read-only parity against seeded FalkorDB."""

import os
from importlib import import_module
from types import SimpleNamespace

import pytest
from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path

from src.config import Settings
from src.database import DatabaseManager
from src.graph_queries import GraphQueries, QueryLimits
from src.investigator import investigate


def test_native_decoder_preserves_direction_and_evidence(topology):
    cls = import_module("src.native_queries").NativeGraphQueries
    nodes = {n.id: n for n in topology.nodes}
    edge = next(e for e in topology.relationships if e.source == "payment" and e.target == "vault")
    sdk_nodes = [
        Node(
            node_id=i,
            labels=["Component", nodes[name].label],
            properties=nodes[name].model_dump(exclude={"label"}),
        )
        for i, name in enumerate(["vault", "payment"])
    ]
    path = Path(
        sdk_nodes,
        [Edge(1, edge.type, 0, properties=edge.model_dump(exclude={"source", "target", "type"}))],
    )
    native = cls(SimpleNamespace(execute_query=lambda *args: [[path]]))
    impacts = native.blast_radius("vault", 1)
    assert impacts[0].component.id == "payment"
    assert impacts[0].path.node_ids == ["vault", "payment"]
    assert impacts[0].path.edges[0].source == "payment"
    assert impacts[0].path.edges[0].target == "vault"
    assert native.diagnostics[0]["parameters"]["component_id"] == "vault"
    assert "LIMIT $limit" in native.diagnostics[0]["cypher"]


def test_native_limits_and_query_input():
    cls = import_module("src.native_queries").NativeGraphQueries
    calls = []
    db = SimpleNamespace(execute_query=lambda query, params: calls.append((query, params)) or [])
    native = cls(db)
    assert native.blast_radius("vault'}) DELETE n //", 1) == []
    assert "DELETE" not in calls[0][0]
    assert calls[0][1]["component_id"] == "vault'}) DELETE n //"
    with pytest.raises(ValueError):
        native.blast_radius("vault", True)
    with pytest.raises(ValueError):
        native.blast_radius("vault", 9)


def test_path_cap_never_turns_ambiguous_name_into_exact_match(topology):
    cls = import_module("src.native_queries").NativeGraphQueries
    first = topology.nodes[0].model_copy(update={"name": "Same"})
    second = topology.nodes[1].model_copy(update={"name": "Same"})
    rows = [
        Node(
            node_id=i,
            labels=["Component", node.label],
            properties=node.model_dump(exclude={"label"}),
        )
        for i, node in enumerate([first, second])
    ]
    db = SimpleNamespace(
        execute_query=lambda query, params: [] if "n.id =" in query else [[node] for node in rows]
    )
    result = cls(db, QueryLimits(max_paths=1)).exact_lookup("Same")
    assert result.matched is None
    assert len(result.suggestions) == 2


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires seeded local FalkorDB"
)
@pytest.mark.parametrize("depth", [1, 6, 8])
@pytest.mark.parametrize("component", ["vault", "orders-db", "analytics", "email-api", "missing"])
def test_live_native_investigation_parity(component, depth):
    cls = import_module("src.native_queries").NativeGraphQueries
    limits = QueryLimits(depth=depth)
    with DatabaseManager(Settings.from_env()) as db:
        python = investigate(GraphQueries.from_database(db, limits), component)
        native = investigate(cls(db, limits), component)
    for field in [
        "matched_component",
        "suggestions",
        "direct_impact",
        "cascading_impact",
        "dependencies",
        "impacted_customers",
        "impacted_workflows",
        "impacted_regions",
        "owner_teams",
        "runbooks",
        "deployment",
        "shortest_paths",
        "critical_paths",
        "cycles",
    ]:
        left, right = getattr(python, field), getattr(native, field)
        assert left == right, field
    assert native.reasoning_engine == "FalkorDB Cypher"
    assert native.query_diagnostics


@pytest.mark.parametrize("limited", [False, True])
def test_native_parallel_evidence_and_truncation(topology, limited):
    cls = import_module("src.native_queries").NativeGraphQueries
    nodes = {node.id: node for node in topology.nodes}
    sdk_nodes = [
        Node(
            node_id=i,
            labels=["Component", nodes[name].label],
            properties=nodes[name].model_dump(exclude={"label"}),
        )
        for i, name in enumerate(["orders-db", "order"])
    ]
    paths = []
    for number, kind in enumerate(["READS_FROM", "WRITES_TO"]):
        edge = next(
            edge
            for edge in topology.relationships
            if edge.source == "order" and edge.target == "orders-db" and edge.type == kind
        ).model_copy(deep=True)
        if kind == "READS_FROM":
            edge.required, edge.criticality = False, 1
        paths.append(
            Path(
                sdk_nodes,
                [
                    Edge(
                        1,
                        kind,
                        0,
                        edge_id=number,
                        properties=edge.model_dump(exclude={"source", "target", "type"}),
                    )
                ],
            )
        )
    native = cls(
        SimpleNamespace(execute_query=lambda *args: [[path] for path in paths]),
        QueryLimits(max_paths=1 if limited else 500),
    )
    impacts = native.blast_radius("orders-db", 1)
    assert len(impacts) == 1
    if limited:
        assert native.warnings and native.diagnostics[0]["truncated"]
    else:
        assert impacts[0].path.edges[0].type == "WRITES_TO"
        assert impacts[0].required and impacts[0].path.criticality == 5
