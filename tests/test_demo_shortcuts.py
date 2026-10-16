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
        assert "Run Token Vault Demo" in buttons
        with patch("src.reports.generate") as provider:
            buttons["Run Token Vault Demo"].click().run()
        provider.assert_not_called()
        assert not app.exception
        assert app.session_state["result_bundle"].analysis.risk.severity == "Critical"
        app.button(key="view_evidence").click().run()
        receipt = next(
            item for item in app.expander if item.label == "Executed Cypher and safe query receipts"
        )
        assert receipt.proto.expanded
        buttons = {item.label: item for item in app.button}
        assert "Simulate Mitigation" in buttons
        buttons["Simulate Mitigation"].click().run()
        assert not app.exception
        assert app.session_state["workspace"] == "Cascade simulation"
        run = app.session_state["sim_run"]
        mitigation = app.session_state["sim_mitigation"]
        assert run.config.component_id == "vault"
        assert mitigation.risk_reduction > 0
        assert mitigation.after.risk.score < run.peak.risk.score
        assert mitigation.removed_critical_paths
        assert app.session_state["sim_cursor"] == len(run.frames)
        original = mitigation.model_dump_json()
        app.run()
        assert not app.exception
        assert app.session_state["sim_mitigation"].model_dump_json() == original
        app.button(key="sim_reset").click().run()
        assert app.session_state["sim_cursor"] == 0
        assert "sim_mitigation" not in app.session_state


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
        app.button(key="open_mitigation").click().run()
    assert not app.exception
    assert app.session_state["sim_mitigation"].risk_reduction > 0
    provider.assert_not_called()
