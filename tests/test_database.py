"""Tests for configuration, FalkorDB access, and health reporting."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.database import DatabaseConnectionError, DatabaseManager, DatabaseQueryError
from src.health import check_health


def test_settings_load_supported_environment_values() -> None:
    values = {
        "FALKORDB_HOST": "db.internal",
        "FALKORDB_PORT": "6380",
        "FALKORDB_GRAPH": "incident_graph",
        "LLM_PROVIDER": "groq",
        "GEMINI_API_KEY": "gemini-secret",
        "GEMINI_MODEL": "gemini-test",
        "GROQ_API_KEY": "groq-secret",
        "GROQ_MODEL": "groq-test",
        "OLLAMA_BASE_URL": "http://ollama:11434",
        "OLLAMA_MODEL": "qwen3:8b",
    }

    with patch.dict(os.environ, values, clear=True):
        settings = Settings.from_env(env_file=None)

    assert settings.falkordb_host == "db.internal"
    assert settings.falkordb_port == 6380
    assert settings.falkordb_graph == "incident_graph"
    assert settings.llm_provider == "groq"
    assert settings.groq_api_key == "groq-secret"
    assert settings.provider_key_configured is True
    assert settings.ollama_base_url == "http://ollama:11434"


@pytest.mark.parametrize("provider", ["gemini", "groq", "ollama", "deterministic"])
def test_settings_accept_supported_providers(provider: str) -> None:
    with patch.dict(os.environ, {"LLM_PROVIDER": provider}, clear=True):
        assert Settings.from_env(env_file=None).llm_provider == provider


def test_settings_reject_invalid_port_and_provider() -> None:
    with patch.dict(
        os.environ,
        {"FALKORDB_PORT": "0", "LLM_PROVIDER": "unknown"},
        clear=True,
    ):
        with pytest.raises(ValidationError):
            Settings.from_env(env_file=None)


def test_database_connects_selects_graph_and_executes_query() -> None:
    query_result = SimpleNamespace(result_set=[[1]])
    graph = Mock()
    graph.query.return_value = query_result
    client = Mock()
    client.connection.ping.return_value = True
    client.select_graph.return_value = graph
    factory = Mock(return_value=client)
    manager = DatabaseManager(Settings(), client_factory=factory)

    assert manager.test_connection() is True
    assert manager.execute_query("RETURN $value", {"value": 1}) == [[1]]

    factory.assert_called_once_with(
        host="localhost",
        port=6379,
        socket_connect_timeout=3,
        socket_timeout=5,
    )
    client.select_graph.assert_called_once_with("blast_radius")
    graph.query.assert_called_once_with("RETURN $value", params={"value": 1}, timeout=3000)


def test_database_reports_connection_errors_without_leaking_details() -> None:
    factory = Mock(side_effect=OSError("secret transport detail"))
    manager = DatabaseManager(Settings(), client_factory=factory)

    with pytest.raises(DatabaseConnectionError, match="localhost:6379") as error:
        manager.test_connection()

    assert "secret transport detail" not in str(error.value)


@pytest.mark.parametrize("parameters", [None, {"value": 1}])
def test_readonly_manager_never_uses_write_capable_query(parameters) -> None:
    graph = Mock()
    graph.query.side_effect = AssertionError("Write-capable route must not run")
    graph.ro_query.return_value = SimpleNamespace(result_set=[[1]])
    client = Mock()
    client.select_graph.return_value = graph
    manager = DatabaseManager(Settings(), client_factory=Mock(return_value=client), read_only=True)
    assert manager.execute_query("RETURN $value" if parameters else "RETURN 1", parameters) == [[1]]
    graph.ro_query.side_effect = RuntimeError("private backend response")
    with pytest.raises(DatabaseQueryError) as error:
        manager.execute_query("RETURN 1")
    assert "private backend response" not in str(error.value)


@pytest.mark.skipif(os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires local FalkorDB")
def test_live_readonly_rejects_write_on_disposable_graph():
    from uuid import uuid4

    settings = Settings.from_env().model_copy(
        update={"falkordb_graph": "readonly_test_" + uuid4().hex}
    )
    with DatabaseManager(settings) as writer:
        try:
            writer.execute_query("CREATE (:Probe {id: 'original'})")
            with DatabaseManager(settings, read_only=True) as reader:
                assert reader.execute_query("MATCH (n:Probe) RETURN n.id") == [["original"]]
                with pytest.raises(DatabaseQueryError):
                    reader.execute_query("CREATE (:Probe {id: 'blocked'})")
                assert reader.execute_query("MATCH (n:Probe) RETURN count(n)") == [[1]]
        finally:
            writer.connect().delete()


def test_database_reports_a_missing_client_dependency_clearly() -> None:
    missing_client = ModuleNotFoundError("No module named 'falkordb'", name="falkordb")
    manager = DatabaseManager(
        Settings(),
        client_factory=Mock(side_effect=missing_client),
    )

    with pytest.raises(DatabaseConnectionError, match="Install project dependencies"):
        manager.test_connection()


def test_database_wraps_query_errors_and_rejects_empty_queries() -> None:
    graph = Mock()
    graph.query.side_effect = RuntimeError("query parser detail")
    client = Mock()
    client.select_graph.return_value = graph
    manager = DatabaseManager(Settings(), client_factory=Mock(return_value=client))

    with pytest.raises(ValueError, match="must not be empty"):
        manager.execute_query("  ")
    with pytest.raises(DatabaseQueryError, match="blast_radius") as error:
        manager.execute_query("RETURN 1")

    assert "query parser detail" not in str(error.value)


def test_database_close_is_safe_and_reconnects_later() -> None:
    first_client = Mock()
    first_client.connection.ping.return_value = True
    first_client.select_graph.return_value = Mock()
    second_client = Mock()
    second_client.connection.ping.return_value = True
    second_client.select_graph.return_value = Mock()
    factory = Mock(side_effect=[first_client, second_client])
    manager = DatabaseManager(Settings(), client_factory=factory)

    manager.test_connection()
    manager.close()
    manager.close()
    manager.test_connection()

    first_client.close.assert_called_once_with()
    assert factory.call_count == 2


def test_health_reports_provider_key_and_database_state() -> None:
    settings = Settings(llm_provider="gemini", gemini_api_key=None)
    manager = Mock()
    manager.test_connection.return_value = True

    report = check_health(settings, manager=manager)

    assert report.configuration_ok is True
    assert report.falkordb_connected is True
    assert report.graph_name == "blast_radius"
    assert report.llm_provider == "gemini"
    assert report.provider_key_configured is False
    manager.close.assert_called_once_with()
