"""Command-line health check for configuration and FalkorDB."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from src.config import LLMProvider, Settings
from src.database import DatabaseConnectionError, DatabaseManager

logger = logging.getLogger(__name__)


class HealthReport(BaseModel):
    """Structured Phase 1 health result."""

    configuration_ok: bool
    falkordb_connected: bool
    graph_name: str
    llm_provider: LLMProvider
    provider_key_configured: bool | None
    database_error: str | None = None


def check_health(
    settings: Settings,
    manager: DatabaseManager | None = None,
) -> HealthReport:
    """Check configuration and FalkorDB without exposing credentials."""
    database = manager or DatabaseManager(settings)
    connected = False
    error: str | None = None
    try:
        connected = database.test_connection()
    except DatabaseConnectionError as exc:
        error = str(exc)
    finally:
        database.close()

    return HealthReport(
        configuration_ok=True,
        falkordb_connected=connected,
        graph_name=settings.falkordb_graph,
        llm_provider=settings.llm_provider,
        provider_key_configured=settings.provider_key_configured,
        database_error=error,
    )


def main() -> int:
    """Print a readable health report and return a shell-friendly status code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        settings = Settings.from_env()
    except Exception as exc:
        print(f"Python configuration: ERROR ({exc})")
        return 1

    report = check_health(settings)
    key_status = (
        "not required"
        if report.provider_key_configured is None
        else "configured"
        if report.provider_key_configured
        else "missing"
    )
    print("Python configuration: OK")
    print(f"FalkorDB connectivity: {'OK' if report.falkordb_connected else 'ERROR'}")
    print(f"Selected graph: {report.graph_name}")
    print(f"LLM provider: {report.llm_provider}")
    print(f"Required provider key: {key_status}")
    if report.database_error:
        print(f"Database error: {report.database_error}")
    return 0 if report.falkordb_connected else 1


if __name__ == "__main__":
    raise SystemExit(main())
