"""Deterministic algorithm, candidate ranking, and score contracts."""

import pytest

from src.analytics import Analytics, severity
from src.graph_queries import GraphQueries
from src.investigator import investigate
from src.seed import load_topology


@pytest.fixture
def analytics():
    return Analytics(GraphQueries(load_topology()))


def test_articulation_and_centrality_order(analytics):
    vault = analytics.metrics("vault")
    web = analytics.metrics("web")
    assert vault.articulation_point and vault.single_point_of_failure
    assert vault.in_degree == 3 and vault.out_degree == 1
    assert vault.degree_centrality > web.degree_centrality
    assert vault.pagerank > web.pagerank
    assert analytics.metrics("payment").betweenness > web.betweenness
    assert sum(analytics.page.values()) == pytest.approx(1)


def test_root_cause_ranking_uses_unhealthy_graph_evidence(analytics):
    candidates = analytics.root_causes("checkout")
    assert candidates[0].component.id == "orders-db"
    assert candidates[0].confidence == "Strong candidate"
    assert candidates[0].historical_incident_ids == ["orders-latency"]
    assert candidates[0].supporting_path.node_ids == ["checkout", "orders-db"]
    assert all(c.confidence != "Confirmed" for c in candidates)
    assert all(c.score == round(sum(f.points for f in c.factors), 2) for c in candidates)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "Low"),
        (24, "Low"),
        (25, "Medium"),
        (49, "Medium"),
        (50, "High"),
        (74, "High"),
        (75, "Critical"),
        (100, "Critical"),
    ],
)
def test_severity_boundaries(value, expected):
    assert severity(value) == expected


def test_risk_reproducibility_and_token_vault_failure(analytics):
    result = investigate(analytics.queries, "Token Vault")
    one = analytics.analyze(result, "failed")
    two = analytics.analyze(result, "failed")
    assert one.model_dump() == two.model_dump()
    assert one.risk.severity == "Critical"
    assert one.risk.score == round(
        sum(f.points for f in one.risk.factors) - one.risk.resilience.reduction, 2
    )
    assert analytics.highest_risk()[0].component.id == "vault"


def test_optional_failure_scores_lower(analytics):
    optional = analytics.risk(investigate(analytics.queries, "email-api"), "failed")
    required = analytics.risk(investigate(analytics.queries, "vault"), "failed")
    assert optional.score < required.score
    assert analytics.metrics("email-api").required_dependents == 0
    assert analytics.metrics("email-api").optional_only_dependents > 0
    topology = load_topology()
    next(
        e for e in topology.relationships if e.source == "notification" and e.target == "email-api"
    ).required = True
    required_graph = Analytics(GraphQueries(topology))
    same_component_required = required_graph.risk(
        investigate(required_graph.queries, "email-api"), "failed"
    )
    assert same_component_required.score > optional.score


def test_regional_replica_reduces_score():
    topology = load_topology()
    original = Analytics(GraphQueries(topology))
    before = original.risk(investigate(original.queries, "vault"), "failed")
    edge = next(
        e for e in topology.relationships if e.source == "vault" and e.type == "DEPLOYED_IN"
    )
    topology.relationships.append(edge.model_copy(update={"target": "singapore"}))
    resilient = Analytics(GraphQueries(topology))
    after = resilient.risk(investigate(resilient.queries, "vault"), "failed")
    assert after.score == pytest.approx(before.score - 7.5)
    assert after.resilience.alternate_count == 1
    assert resilient.metrics("vault").single_point_of_failure is False


def test_cycle_scc_and_critical_paths(analytics):
    assert ["analytics", "notification"] in analytics.strongly_connected_components
    result = analytics.analyze(investigate(analytics.queries, "orders-db"), "degraded")
    assert result.cycles[0].node_ids == ["analytics", "notification"]
    assert all(p.required and p.criticality >= 4 for p in result.critical_paths)
    assert any(i.hops >= 3 for i in investigate(analytics.queries, "orders-db").cascading_impact)
    assert analytics.shortest_path("web", "vault").hops == 4
    assert analytics.shortest_path("vault", "web") is None
    assert result.critical_path_rankings
    assert [p.score for p in result.critical_path_rankings] == sorted(
        [p.score for p in result.critical_path_rankings], reverse=True
    )
