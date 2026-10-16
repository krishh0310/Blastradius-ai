"""Graph operation contracts against the fixture and optional live FalkorDB."""

import os
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.database import DatabaseManager
from src.graph_queries import GraphQueries, QueryLimits, edge_key
from src.investigator import investigate
from src.seed import load_topology


@pytest.fixture
def queries():
    return GraphQueries(load_topology())


def test_exact_search_and_fuzzy_lookup(queries):
    assert queries.exact_lookup("vault").matched.id == "vault"
    assert queries.exact_lookup("tOkEn vAuLt").matched.id == "vault"
    assert queries.exact_lookup("Orders Database").matched.id == "orders-db"
    assert [n.id for n in queries.search("TOKEN")] == ["vault"]
    missing = investigate(queries, "Token Vualt")
    assert missing.matched_component is None
    assert missing.suggestions[0].id == "vault"
    assert missing.evidence_nodes == []
    assert investigate(queries, "totally nonexistent xyz").matched_component is None


def test_one_hop_and_long_cascade(queries):
    assert {i.component.id for i in queries.direct_dependents("vault")} == {
        "auth",
        "payment",
        "subscription",
    }
    assert {i.component.id for i in queries.direct_dependencies("vault")} == {"vault-db"}
    impact = {i.component.id: i for i in queries.blast_radius("vault")}
    assert impact["web"].hops >= 3
    assert impact["web"].path.node_ids[0] == "vault"
    assert impact["web"].path.node_ids[-1] == "web"
    assert {i.component.id for i in queries.blast_radius("vault", 1)} == {
        "auth",
        "payment",
        "subscription",
    }
    assert "vault-db" not in impact
    assert "vault-db" in {i.component.id for i in queries.dependencies("vault")}


def test_cycles_terminate_and_deduplicate(queries):
    assert queries.cycles()[0].node_ids == ["analytics", "notification"]
    impacts = queries.blast_radius("analytics", 8)
    assert len({i.component.id for i in impacts}) == len(impacts)
    assert all(len(i.path.node_ids) == len(set(i.path.node_ids)) for i in impacts)
    assert "analytics" not in {i.component.id for i in impacts}


def test_optional_paths_and_required_alternative(queries):
    email = queries.direct_dependents("email-api")
    assert email[0].component.id == "notification"
    assert email[0].required is False
    assert queries.critical_paths("email-api", "notification") == []
    # A two-hop required route must survive a one-hop optional shortcut.
    topology = load_topology()
    edge = next(
        e for e in topology.relationships if e.source == "analytics" and e.target == "notification"
    )
    topology.relationships.extend(
        [
            edge.model_copy(
                update={
                    "source": "notification",
                    "target": "vault",
                    "type": "CALLS",
                    "required": False,
                }
            ),
            edge.model_copy(
                update={
                    "source": "notification",
                    "target": "auth",
                    "type": "CALLS",
                    "required": True,
                }
            ),
        ]
    )
    graph = GraphQueries(topology)
    result = graph.blast_radius("vault")
    notification = next(i for i in result if i.component.id == "notification")
    assert notification.required and notification.hops == 2
    assert graph.shortest_path("vault", "notification", downstream=True).hops == 1


def test_customer_region_and_replica_evidence(queries):
    result = investigate(queries, "Orders Db")
    assert "orbit" in {i.component.id for i in result.impacted_customers}
    orbit = next(i for i in result.impacted_customers if i.component.id == "orbit")
    assert orbit.hops >= 3
    assert {i.component.id for i in result.impacted_regions} == {"mumbai", "singapore", "frankfurt"}
    assert [n.id for n in queries.deployment("vault").regions] == ["mumbai"]
    assert [n.id for n in queries.deployment("orders-db").replica_targets] == ["warehouse-db"]
    assert queries.health("orders-db").status == "degraded"
    assert queries.health("missing") is None


def test_shortest_path_direction_and_parallel_edges(queries):
    path = queries.shortest_path("web", "vault")
    assert path.hops == 4
    assert path.node_ids == ["web", "gateway", "checkout", "payment", "vault"]
    assert queries.shortest_path("vault", "web") is None
    assert queries.shortest_path("vault", "web", downstream=True).hops == 4
    paths = queries.paths("order", "orders-db")
    assert {p.edges[0].type for p in paths if p.hops == 1} == {"READS_FROM", "WRITES_TO"}
    keys = [tuple(edge_key(e) for e in p.edges) for p in paths]
    assert len(keys) == len(set(keys))


def test_every_claim_has_complete_directed_evidence(queries):
    result = investigate(queries, "Token Vault")
    node_ids = {n.id for n in result.evidence_nodes}
    edges = {edge_key(e) for e in result.evidence_edges}
    for field in [
        "direct_impact",
        "cascading_impact",
        "dependencies",
        "impacted_customers",
        "impacted_workflows",
        "impacted_regions",
        "owner_teams",
        "runbooks",
    ]:
        for item in getattr(result, field):
            assert item.hops == len(item.path.edges)
            assert len(item.path.node_ids) == item.hops + 1
            assert item.required == all(e.required for e in item.path.edges)
            assert item.path.node_ids[-1] == item.component.id
            assert set(item.path.node_ids) <= node_ids
            for a, b, edge in zip(item.path.node_ids, item.path.node_ids[1:], item.path.edges):
                assert {a, b} == {edge.source, edge.target}
                assert edge_key(edge) in edges
    assert len(node_ids) == len(result.evidence_nodes)
    assert len(edges) == len(result.evidence_edges)
    assert result.query_execution_ms >= 0
    assert result.owner_teams and result.runbooks and result.critical_paths


def test_limits_and_missing_nodes(queries):
    with pytest.raises(ValidationError):
        QueryLimits(depth=9)
    with pytest.raises(ValueError):
        queries.dependencies("vault", 0)
    assert queries.paths("missing", "vault") == []
    with pytest.raises(ValueError, match="snapshot limits"):
        GraphQueries(load_topology(), QueryLimits(max_nodes=1))
    limited = GraphQueries(load_topology(), QueryLimits(max_paths=1))
    assert len(limited.paths("web", "vault")) == 1
    assert limited.warnings


def test_database_queries_are_bounded_and_parameterized():
    db = Mock()
    db.execute_query.side_effect = [[], []]
    graph = GraphQueries.from_database(db)
    assert graph.nodes == {}
    for call in db.execute_query.call_args_list:
        assert "LIMIT $limit" in call.args[0]
        assert isinstance(call.args[1]["limit"], int)
    db.execute_query.side_effect = [[(["Service"], {})] * 3]
    with pytest.raises(ValueError, match="snapshot limits"):
        GraphQueries.from_database(db, QueryLimits(max_nodes=1))


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1",
    reason="Set FALKORDB_INTEGRATION=1 with Phase 2 seeded",
)
def test_live_investigations_and_evidence():
    with DatabaseManager(Settings.from_env()) as db:
        queries = GraphQueries.from_database(db)
        for component in ["Token Vault", "Orders Db"]:
            result = investigate(queries, component)
            assert result.matched_component
            assert result.direct_impact and result.impacted_customers
            assert result.evidence_nodes and result.evidence_edges
        assert queries.shortest_path("web", "vault").hops == 4
        test_exact_search_and_fuzzy_lookup(queries)
        test_one_hop_and_long_cascade(queries)
        test_cycles_terminate_and_deduplicate(queries)
        test_customer_region_and_replica_evidence(queries)
        test_shortest_path_direction_and_parallel_edges(queries)
        test_every_claim_has_complete_directed_evidence(queries)
        notification = queries.direct_dependents("email-api")[0]
        assert notification.component.id == "notification" and not notification.required
        assert queries.critical_paths("email-api", "notification") == []
        assert queries.impact_paths("vault", "web")
