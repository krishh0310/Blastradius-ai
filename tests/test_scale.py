"""Synthetic tenants preserve the judge fixture and remain inside graph bounds."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.graph_queries import GraphQueries
from src.seed import load_topology
from src.topology import integrity


def test_scale_topology_is_deterministic_connected_and_cross_tenant():
    from src.scale import build_scale_topology

    original = load_topology().model_dump_json()
    topology = build_scale_topology()
    assert len(topology.nodes) == 1083
    assert len(topology.relationships) == 2842
    assert not integrity(topology)["errors"]
    assert topology == build_scale_topology()
    assert load_topology().model_dump_json() == original
    graph = GraphQueries(topology)
    impacts = graph.blast_radius("shared-secrets")
    ids = {impact.component.id for impact in impacts}
    assert {"tenant01-vault", "tenant20-vault", "tenant02-payment"} <= ids
    assert all(impact.path.hops > 0 for impact in impacts)


def test_benchmark_validates_before_opening_database():
    from scripts.scale_benchmark import run

    with patch(
        "scripts.scale_benchmark.DatabaseManager", side_effect=AssertionError("Must not connect")
    ):
        for kwargs in ({"tenants": 31}, {"iterations": 2}, {"warmup": 6}):
            with pytest.raises(ValueError):
                run(**kwargs)


@pytest.mark.skipif(os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires local FalkorDB")
def test_live_scale_seed_parity_and_disposable_cleanup():
    from scripts.scale_benchmark import run
    from src.config import Settings
    from src.database import DatabaseManager

    with DatabaseManager(Settings.from_env()) as db:
        db.connect()
        existing = set(db._client.list_graphs())
    result = run(tenants=2, iterations=3, warmup=0)
    assert result["nodes"] == 111 and result["relationships"] == 286
    assert result["cleanup_completed"]
    assert all(item["same_affected_ids"] for item in result["queries"].values())
    with DatabaseManager(Settings.from_env()) as db:
        db.connect()
        assert set(db._client.list_graphs()) == existing


@pytest.mark.parametrize("tenants", [0, 31, True, "20", 1.5])
def test_invalid_scale_size_rejected(tenants):
    from src.scale import build_scale_topology

    with pytest.raises(ValueError):
        build_scale_topology(tenants)


def test_scale_maximum_within_existing_snapshot_limits():
    from src.scale import build_scale_topology

    topology = build_scale_topology(30)
    assert len(topology.nodes) == 1623
    assert len(topology.relationships) < 10000
    assert not integrity(topology)["errors"]


@pytest.mark.parametrize(
    "deletions, completed, attempts",
    [
        ([OSError("private SDK detail"), None], True, 2),
        ([OSError("private SDK detail")] * 3, False, 3),
    ],
)
def test_cleanup_retries_without_masking_original_failure(deletions, completed, attempts):
    from scripts.scale_benchmark import BenchmarkError, run

    database = MagicMock()
    database.__enter__.return_value = database
    database.connect.return_value.delete.side_effect = deletions
    with (
        patch("scripts.scale_benchmark.DatabaseManager", return_value=database),
        patch("scripts.scale_benchmark.seed", side_effect=ValueError("private original failure")),
        pytest.raises(BenchmarkError) as error,
    ):
        run(tenants=1, iterations=3, warmup=0)
    report = error.value.report
    assert report["error"] == "benchmark_failed"
    assert report["cleanup_completed"] is completed
    assert report["cleanup_attempts"] == attempts
    assert report["graph"].startswith("scale_test_")
    assert "private" not in str(error.value)
    assert bool(report["warnings"]) is (not completed)


@pytest.mark.parametrize("fails, exit_code", [(False, 0), (True, 1)])
def test_cleanup_cli_reports_owned_graph_without_traceback(fails, exit_code, capsys):
    import json

    from scripts.scale_benchmark import main
    from src.scale import build_scale_topology

    graph = GraphQueries(build_scale_topology(1))
    database = MagicMock()
    database.__enter__.return_value = database
    if fails:
        database.connect.return_value.delete.side_effect = OSError("private deletion error")
    with (
        patch(
            "sys.argv", ["scale_benchmark", "--tenants", "1", "--iterations", "3", "--warmup", "0"]
        ),
        patch("scripts.scale_benchmark.DatabaseManager", return_value=database) as connections,
        patch(
            "scripts.scale_benchmark.seed",
            return_value={"nodes": 57, "relationships": 144, "errors": []},
        ),
        patch("scripts.scale_benchmark.GraphQueries.from_database", return_value=graph),
        patch("scripts.scale_benchmark.NativeGraphQueries", return_value=graph),
    ):
        assert main() == exit_code
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["cleanup_completed"] is (not fails)
    assert report["cleanup_attempts"] == (3 if fails else 1)
    assert all(
        call.args[0].falkordb_graph == report["graph"] for call in connections.call_args_list
    )
    assert "private" not in captured.out and not captured.err
    if fails:
        assert report["error"] == "cleanup_failed"
