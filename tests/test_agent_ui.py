"""The MCP demo requires explicit consent and survives cosmetic reruns."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.agent import run_agent_mcp, simulate_recommended
from src.config import Settings
from src.mcp_server import create_server
from src.tooling import ToolService


def test_agent_trace_and_confirmed_simulation(topology, graph):
    server = create_server(ToolService(Settings(), queries=graph))

    def run(request, settings):
        return asyncio.run(run_agent_mcp(request, server=server, settings=settings))

    def simulate(result, request, settings):
        return asyncio.run(
            simulate_recommended(result, request, confirmed=True, settings=settings, server=server)
        )

    with (
        patch("src.dashboard_ui.read_snapshot", return_value=(topology.model_dump_json(), "test")),
        patch("src.agent_ui.run_request", side_effect=run) as runner,
        patch("src.agent_ui.simulate_request", side_effect=simulate),
    ):
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=40).run()
        assert app.button(key="open_mitigation").disabled
        app.checkbox(key="use_planner").check().run()
        app.button(key="run_demo").click().run()
        assert not app.exception
        assert any(item.value == "Agent Tool Trace" for item in app.subheader)
        result = app.session_state["result_agent"]
        assert app.session_state["depth"] == 8
        assert not app.session_state["use_planner"]
        assert not app.session_state["result_agent_request"].use_provider
        assert len(result.trace) == 7 and result.recommendation.eligible
        assert app.button(key="open_mitigation").disabled
        app.checkbox(key="result_action_confirm").check().run()
        app.button(key="open_mitigation").click().run()
        assert not app.exception
        result = app.session_state["result_agent"]
        assert len(result.trace) == 8
        assert result.trace[-1].output.simulation.risk_reduction > 0
        assert app.button(key="open_mitigation").disabled
        app.run()
        assert runner.call_count == 1
        app.button(key="reset").click().run()
        assert "result_agent" not in app.session_state
