"""Primary demo must need one click and never enable a cloud provider."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest


def test_run_demo_and_mitigation_shortcuts(topology):
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch(
        "src.dashboard_ui.read_snapshot",
        return_value=(topology.model_dump_json(), "fictional snapshot"),
    ):
        app = AppTest.from_file(str(app_path), default_timeout=30).run()
        assert not app.exception
        buttons = {item.label: item for item in app.button}
        assert "Run Token Vault Agent" in buttons
        with patch("src.reports.generate") as provider:
            buttons["Run Token Vault Agent"].click().run()
        provider.assert_not_called()
        assert not app.exception
        assert app.session_state["result_bundle"].analysis.risk.severity == "Critical"
        app.button(key="view_evidence").click().run()
        receipt = next(
            item for item in app.expander if item.label == "Executed Cypher and safe query receipts"
        )
        assert receipt.proto.expanded
        buttons = {item.label: item for item in app.button}
        assert "Simulate Recommended Mitigation" in buttons
        assert app.button(key="open_mitigation").disabled


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires seeded local FalkorDB"
)
def test_live_three_click_flow_uses_native_evidence_without_provider():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    with patch("src.reports.generate") as provider:
        app.button(key="run_demo").click().run()
        bundle = app.session_state["result_bundle"]
        assert bundle.investigation.reasoning_engine == "FalkorDB Cypher"
        assert bundle.investigation.query_diagnostics
        assert bundle.analysis.risk.severity == "Critical"
        assert bundle.report.provider == "deterministic"
        app.button(key="view_evidence").click().run()
        assert next(
            item for item in app.expander if item.label == "Executed Cypher and safe query receipts"
        ).proto.expanded
        assert len(app.session_state["result_agent"].trace) == 7
        assert app.button(key="open_mitigation").disabled
        app.checkbox(key="result_action_confirm").check().run()
        app.button(key="open_mitigation").click().run()
    assert not app.exception
    assert app.session_state["result_agent"].trace[-1].output.simulation.risk_reduction > 0
    provider.assert_not_called()
