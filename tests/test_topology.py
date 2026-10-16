"""Fixture validation and real FalkorDB idempotency checks."""

import os
from collections import Counter
from uuid import uuid4

import networkx as nx
import pytest
from pydantic import ValidationError

from src.config import Settings
from src.database import DatabaseManager
from src.seed import load_topology, seed, snapshot
from src.topology import DEPENDENCIES, Topology, integrity


def test_fixture_counts_and_demonstration_paths():
    topology = load_topology()
    counts = Counter(n.label for n in topology.nodes)
    assert counts == {
        "Service": 18,
        "Database": 5,
        "Queue": 3,
        "Region": 3,
        "Customer": 6,
        "Team": 6,
        "API": 3,
        "BusinessFlow": 4,
        "Runbook": 5,
        "Incident": 1,
    }
    report = integrity(topology)
    assert report["errors"] == []
    assert report["dependency_cycles"] == [["analytics", "notification"]]
    assert "vault" in report["dependency_articulation_points"]
    graph = nx.DiGraph(
        (e.source, e.target) for e in topology.relationships if e.type in DEPENDENCIES
    )
    assert nx.is_path(graph, ["web", "gateway", "checkout", "payment", "fraud", "auth", "vault"])
    assert all(
        nx.has_path(graph, service, "orders-db")
        for service in ["checkout", "shipping", "notification", "analytics"]
    )
    assert any(not e.required for e in topology.relationships if e.type in DEPENDENCIES)
    assert {
        e.target for e in topology.relationships if e.source == "vault" and e.type == "DEPLOYED_IN"
    } == {"mumbai"}


def test_duplicate_ids_missing_endpoints_and_owners_are_rejected():
    topology = load_topology()
    broken = topology.model_copy(deep=True)
    broken.nodes.append(broken.nodes[0])
    broken.relationships[0].target = "missing"
    broken.relationships = [e for e in broken.relationships if e.type != "OWNED_BY"]
    errors = integrity(broken)["errors"]
    assert any("Duplicate ID" in e for e in errors)
    assert any("Missing endpoint" in e for e in errors)
    assert any("Missing owner" in e for e in errors)


def test_missing_criticality_and_unsafe_labels_are_rejected():
    data = load_topology().model_dump()
    del data["nodes"][0]["criticality"]
    data["nodes"][1]["label"] = "Service) DELETE n"
    with pytest.raises(ValidationError) as error:
        Topology.model_validate(data)
    assert len(error.value.errors()) == 2


def test_isolated_node_is_reported():
    topology = load_topology()
    topology.relationships = [
        e for e in topology.relationships if "lotus" not in (e.source, e.target)
    ]
    assert "Isolated node: lotus" in integrity(topology)["errors"]


def test_invalid_topology_does_not_write():
    topology = load_topology()
    topology.nodes.append(topology.nodes[0])
    with pytest.raises(ValueError, match="Duplicate ID"):
        seed(None, topology)


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1",
    reason="Set FALKORDB_INTEGRATION=1 with local FalkorDB running",
)
def test_live_seed_is_idempotent_and_reset_is_scoped():
    settings = Settings.from_env().model_copy(
        update={"falkordb_graph": "phase2_test_" + uuid4().hex}
    )
    with DatabaseManager(settings) as db:
        try:
            topology = load_topology()
            first = seed(db, topology)
            second = seed(db, topology)
            assert first == second
            assert (second["nodes"], second["relationships"]) == (54, 141)
            db.execute_query("CREATE (:Unrelated {id: 'keep'})")
            assert seed(db, topology, reset=True, confirm_reset=settings.falkordb_graph) == first
            assert db.execute_query("MATCH (n:Unrelated) RETURN n.id") == [["keep"]]
            assert integrity(snapshot(db))["errors"] == []
        finally:
            db.connect().delete()
