"""Evidence must not depend on which parallel relationship sorts first."""

import pytest

from src.analytics import Analytics
from src.graph_queries import GraphQueries


def test_required_write_wins_optional_read(topology):
    read = next(
        e
        for e in topology.relationships
        if e.source == "order" and e.target == "orders-db" and e.type == "READS_FROM"
    )
    read.required = False
    read.criticality = 1
    graph = GraphQueries(topology)
    evidence = Analytics(graph).shortest_path("order", "orders-db")
    assert evidence.required
    assert evidence.criticality == 5
    assert evidence.edges[0].type == "WRITES_TO"


@pytest.mark.parametrize(
    "criticality,status,expected",
    [
        (5, "healthy", "WRITES_TO"),
        (4, "down", "WRITES_TO"),
        (4, "healthy", "READS_FROM"),
    ],
)
def test_parallel_tie_breakers(topology, criticality, status, expected):
    for edge in topology.relationships:
        if edge.source == "order" and edge.target == "orders-db":
            edge.required = True
            edge.criticality = 4 if edge.type == "READS_FROM" else criticality
            edge.status = "healthy" if edge.type == "READS_FROM" else status
    graph = GraphQueries(topology)
    assert Analytics(graph).shortest_path("order", "orders-db").edges[0].type == expected
