"""Primary demo must need one click and never enable a cloud provider."""

from pathlib import Path
from unittest.mock import patch

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
        assert "Run Demo" in buttons
        with patch("src.reports.generate") as provider:
            buttons["Run Demo"].click().run()
        provider.assert_not_called()
        assert not app.exception
        assert app.session_state["result_bundle"].analysis.risk.severity == "Critical"
        buttons = {item.label: item for item in app.button}
        assert "Simulate Mitigation" in buttons
        buttons["Simulate Mitigation"].click().run()
        assert not app.exception
        assert app.session_state["workspace"] == "Cascade simulation"
