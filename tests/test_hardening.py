"""Regression tests for security boundaries and graceful failure."""

import logging
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.database import DatabaseConnectionError, DatabaseManager, DatabaseQueryError
from src.graph_queries import GraphQueries, QueryLimits
from src.seed import load_topology, seed
from src.simulator import SimulationConfig, Simulator
from src.topology import Relationship


def test_dotenv_cannot_interpolate_process_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-value")
    monkeypatch.delenv("FALKORDB_GRAPH", raising=False)
    path = tmp_path / ".env"
    path.write_text("FALKORDB_GRAPH=${GEMINI_API_KEY}\n")
    settings = Settings.from_env(path)
    assert settings.falkordb_graph == "${GEMINI_API_KEY}"
    assert "private-test-value" not in settings.model_dump_json()


@pytest.mark.parametrize("value", ["bad\nvalue", "x" * 513])
def test_config_rejects_control_characters_and_oversized_text(value):
    with pytest.raises(ValidationError):
        Settings(falkordb_graph=value)


def test_logs_and_errors_never_include_transport_secrets(caplog):
    client = Mock()
    client.connection.ping.side_effect = OSError("private-transport-secret")
    client.close.side_effect = OSError("private-close-secret")
    manager = DatabaseManager(Settings(), client_factory=Mock(return_value=client))
    with caplog.at_level(logging.DEBUG), pytest.raises(DatabaseConnectionError) as error:
        manager.test_connection()
    assert "private-" not in caplog.text
    assert error.value.__suppress_context__
    assert manager._client is None
    assert "event=database_ping_failed" in caplog.text


def test_false_ping_is_not_reported_healthy():
    client = Mock()
    client.connection.ping.return_value = False
    manager = DatabaseManager(Settings(), client_factory=Mock(return_value=client))
    with pytest.raises(DatabaseConnectionError):
        manager.test_connection()
    client.close.assert_called_once()


def test_query_failure_has_no_raw_traceback(caplog):
    client = Mock()
    client.select_graph.return_value.query.side_effect = RuntimeError("private-query-secret")
    manager = DatabaseManager(Settings(), client_factory=Mock(return_value=client))
    with caplog.at_level(logging.DEBUG), pytest.raises(DatabaseQueryError) as error:
        manager.execute_query("RETURN $value", {"value": "private-parameter"})
    assert "private-" not in caplog.text
    assert error.value.__suppress_context__


def test_programmatic_reset_requires_exact_confirmation(topology):
    db = Mock(settings=Settings())
    with pytest.raises(ValueError, match="confirmation"):
        seed(db, topology, reset=True)
    db.execute_query.assert_not_called()


def test_mutated_model_cannot_inject_cypher(topology):
    topology.nodes[0].label = "Service) DETACH DELETE n //"
    db = Mock()
    with pytest.raises(ValidationError):
        seed(db, topology)
    db.execute_query.assert_not_called()
    with pytest.raises(ValidationError):
        GraphQueries(topology)


def test_nonfinite_latency_is_rejected(topology):
    edge = topology.relationships[0].model_dump()
    edge["latency_ms"] = float("inf")
    with pytest.raises(ValidationError):
        Relationship.model_validate(edge)


def test_topology_file_size_is_bounded(tmp_path):
    path = tmp_path / "large.json"
    with path.open("wb") as stream:
        stream.truncate(5_000_001)
    with pytest.raises(ValueError, match="5 MB"):
        load_topology(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("depth", 9),
        ("max_nodes", 2001),
        ("max_edges", 10001),
        ("max_paths", 501),
        ("max_expansions", 20001),
    ],
)
def test_hard_resource_limits(field, value):
    with pytest.raises(ValidationError):
        QueryLimits(**{field: value})


@pytest.mark.parametrize("operation", ["exact_lookup", "search", "suggestions"])
def test_lookup_inputs_are_bounded(graph, operation):
    with pytest.raises(ValueError, match="512"):
        getattr(graph, operation)("x" * 513)


def test_shortest_path_does_not_enumerate_all_paths(graph, monkeypatch):
    monkeypatch.setattr(graph, "paths", Mock(side_effect=AssertionError("enumerated paths")))
    assert graph.shortest_path("web", "vault").hops == 4
    assert graph.shortest_path("missing", "vault") is None


def test_shortest_path_budget_warns_instead_of_unbounded_work(topology):
    graph = GraphQueries(topology, QueryLimits(max_expansions=1))
    assert graph.shortest_path("vault", "web", downstream=True) is None
    assert any("expansion limit" in warning for warning in graph.warnings)


def test_simulation_schedule_budget_is_bounded_and_explicit(topology):
    simulator = Simulator(topology, SimulationConfig(component_id="vault"))
    simulator.queries.limits.max_expansions = 1
    run = simulator.run()
    assert len(run.events) == 1
    assert any("Simulation expansion limit" in warning for warning in run.warnings)
    assert simulator.run() == run
