"""Reusable FalkorDB connection and query access."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from src.config import Settings

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Base error for database operations."""


class DatabaseConnectionError(DatabaseError):
    """Raised when FalkorDB cannot be reached or initialized."""


class DatabaseQueryError(DatabaseError):
    """Raised when FalkorDB cannot execute a Cypher query."""


def _create_falkordb_client(**kwargs: Any) -> Any:
    """Import the client only when a real connection is requested."""
    from falkordb import FalkorDB

    return FalkorDB(**kwargs)


class DatabaseManager:
    """Own one FalkorDB client and its selected graph."""

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[..., Any] = _create_falkordb_client,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._client: Any | None = None
        self._graph: Any | None = None

    def connect(self) -> Any:
        """Connect once and select the configured graph."""
        if self._graph is not None:
            return self._graph

        try:
            self._client = self._client_factory(
                host=self.settings.falkordb_host,
                port=self.settings.falkordb_port,
                socket_connect_timeout=3,
                socket_timeout=5,
            )
            self._graph = self._client.select_graph(self.settings.falkordb_graph)
            return self._graph
        except ModuleNotFoundError:
            self.close()
            raise DatabaseConnectionError(
                "FalkorDB client is unavailable. Install project dependencies with "
                "'python -m pip install -r requirements.txt'."
            ) from None
        except Exception as exc:
            self.close()
            logger.warning("event=database_connection_failed error_type=%s", type(exc).__name__)
            raise DatabaseConnectionError(
                "Could not connect to FalkorDB at "
                f"{self.settings.falkordb_host}:{self.settings.falkordb_port}. "
                "Check that Docker is running and the environment settings are correct."
            ) from None

    def test_connection(self) -> bool:
        """Verify the server responds and the configured graph can be selected."""
        self.connect()
        try:
            if not self._client.connection.ping():
                raise DatabaseConnectionError("FalkorDB ping returned false")
            return True
        except Exception as exc:
            self.close()
            logger.warning("event=database_ping_failed error_type=%s", type(exc).__name__)
            raise DatabaseConnectionError(
                "FalkorDB did not respond at "
                f"{self.settings.falkordb_host}:{self.settings.falkordb_port}."
            ) from None

    def execute_query(
        self,
        cypher: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[list[Any]]:
        """Execute a Cypher query against the selected graph and return its rows."""
        if not cypher.strip():
            raise ValueError("Cypher query must not be empty")

        graph = self.connect()
        try:
            result = (
                graph.query(cypher, params=dict(parameters), timeout=3000)
                if parameters is not None
                else graph.query(cypher, timeout=3000)
            )
            return result.result_set
        except Exception as exc:
            logger.warning("event=database_query_failed error_type=%s", type(exc).__name__)
            raise DatabaseQueryError(
                f"Cypher query failed for graph '{self.settings.falkordb_graph}'."
            ) from None

    def close(self) -> None:
        """Close the client safely; repeated calls are harmless."""
        client, self._client, self._graph = self._client, None, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                logger.warning("event=database_close_failed error_type=%s", type(exc).__name__)

    def __enter__(self) -> "DatabaseManager":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
