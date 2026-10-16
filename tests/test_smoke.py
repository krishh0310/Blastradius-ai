"""One deterministic end-to-end backend path, with optional live database coverage."""

import os

import pytest

from scripts.check_secrets import scan
from src.analytics import Analytics
from src.config import Settings
from src.database import DatabaseManager
from src.graph_queries import GraphQueries
from src.investigator import investigate
from src.reports import build_evidence, generate_report
from src.seed import snapshot
from src.simulator import SimulationConfig, Simulator
from src.topology import Topology
from src.visualization import graph_figure


def assert_flow(graph):
    result = investigate(graph, "Token Vault")
    analysis = Analytics(graph).analyze(result, "failed")
    report = generate_report(build_evidence(graph, result, analysis), Settings())
    assert report.provider == "deterministic"
    assert report.severity == "Critical"
    assert result.impacted_customers
    assert graph_figure(result.evidence_nodes, result.evidence_edges, result)[0].data
    simulation = Simulator(
        Topology(nodes=list(graph.nodes.values()), relationships=graph.edges),
        SimulationConfig(component_id="vault"),
    )
    before = simulation.run()
    after = simulation.run("Isolate unhealthy dependency")
    assert after.frames[-1].risk.score < before.frames[-1].risk.score


def test_end_to_end_smoke(graph):
    assert_flow(graph)


@pytest.mark.skipif(os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires local FalkorDB")
def test_live_read_only_end_to_end_smoke():
    with DatabaseManager(Settings.from_env()) as db:
        original = snapshot(db).model_dump_json()
        assert_flow(GraphQueries.from_database(db))
        assert snapshot(db).model_dump_json() == original


def test_secret_scan_reports_locations_not_values(tmp_path):
    secret = "gsk_" + "a" * 30
    path = tmp_path / "leak.py"
    path.write_text(f"KEY = '{secret}'")
    assert scan(tmp_path) == ["leak.py:1: potential secret"]
    assert secret not in str(scan(tmp_path))
    path.unlink()
    (tmp_path / ".env").write_text(secret)
    assert scan(tmp_path) == []
