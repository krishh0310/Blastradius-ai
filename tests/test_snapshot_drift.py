"""Fresh native evidence must never be scored/reported as a different snapshot."""

from unittest.mock import patch

import pytest

from src.config import Settings
from src.dashboard_service import prepare_graph, run_investigation
from src.graph_queries import GraphQueries


@pytest.mark.parametrize("change", ["new_node", "changed_node"])
def test_native_drift_uses_one_explicitly_labeled_snapshot(topology, change):
    prepared = prepare_graph(topology.model_dump_json(), 6)
    if change == "new_node":
        node = topology.nodes[0].model_copy(update={"id": "new-dependent", "name": "New consumer"})
        topology.nodes.append(node)
        for prototype in [
            next(
                e for e in topology.relationships if e.source == "payment" and e.target == "vault"
            ),
            next(e for e in topology.relationships if e.source == "web" and e.type == "OWNED_BY"),
        ]:
            topology.relationships.append(prototype.model_copy(update={"source": node.id}))
    else:
        next(node for node in topology.nodes if node.id == "vault").status = "down"
    fresh = GraphQueries(topology)
    fresh.reasoning_engine = "FalkorDB Cypher"
    with (
        patch("src.database.DatabaseManager"),
        patch("src.native_queries.NativeGraphQueries", return_value=fresh),
    ):
        bundle = run_investigation(prepared, "vault", "", "failed", Settings(), use_native=True)
    assert bundle.investigation.reasoning_engine == "bounded Python fallback"
    assert any(
        "snapshot" in warning and "changed" in warning.lower()
        for warning in bundle.investigation.warnings
    )
    assert "new-dependent" not in {node.id for node in bundle.investigation.evidence_nodes}
    assert bundle.investigation.matched_component.status == "healthy"
