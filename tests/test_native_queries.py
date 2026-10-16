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
        "direct_impact",
        "cascading_impact",
        "dependencies",
        "impacted_customers",
        "impacted_workflows",
        "impacted_regions",
        "owner_teams",
        "runbooks",
        "deployment",
    ]:
        left, right = getattr(python, field), getattr(native, field)
        assert left == right, field
    assert native.reasoning_engine == "FalkorDB Cypher"
    assert native.query_diagnostics
