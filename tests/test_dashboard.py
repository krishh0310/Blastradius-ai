"""Dashboard scenario, presentation, caching, and safe action regression tests."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from src.config import Settings
from src.dashboard_service import SCENARIOS, prepare_graph, run_investigation
from src.graph_queries import EvidencePath, edge_key
from src.seed import load_topology
from src.topology import Topology
from src.visualization import graph_figure

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(scope="module")
def prepared():
    return prepare_graph(load_topology().model_dump_json(), 6)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenarios_use_graph_services_and_keep_evidence(prepared, name):
    scenario = SCENARIOS[name]
    with patch("src.reports.generate") as provider:
        bundle = run_investigation(
            prepared, scenario.component_id, scenario.text, scenario.status, Settings()
        )
    provider.assert_not_called()
    result = bundle.investigation
    assert result.matched_component.id == scenario.component_id
    assert result.evidence_nodes and result.evidence_edges
    assert bundle.analysis
    if bundle.regional:
        assert bundle.report is None
        assert "Worst-case" in bundle.analysis_scope
        vault = next(r for r in bundle.regional_deployments if r["id"] == "vault")
        assert vault["single_region"]
        gateway = next(r for r in bundle.regional_deployments if r["id"] == "gateway")
        assert not gateway["single_region"]
    else:
        assert bundle.report.provider == "deterministic"
    node_ids = {n.id for n in result.evidence_nodes}
    edges = {edge_key(e) for e in result.evidence_edges}
    for impact in result.direct_impact + result.cascading_impact + result.impacted_customers:
        assert impact.path.node_ids[0] == scenario.component_id
        assert set(impact.path.node_ids) <= node_ids
        assert all(edge_key(e) in edges for e in impact.path.edges)


def test_plot_empty_single_filtered_and_bounded_graph():
    figure, note = graph_figure([], [])
    assert figure.layout.annotations[-1].text == "No nodes match these filters."
    topology = load_topology()
    figure, _ = graph_figure([topology.nodes[0]], [])
    assert len(figure.data) >= 8
    figure, note = graph_figure(topology.nodes, topology.relationships, node_types=[])
    assert "Showing 0 nodes" in note
    large_nodes = [
        topology.nodes[0].model_copy(update={"id": f"service-{i}", "name": f"Service {i}"})
        for i in range(250)
    ]
    figure, note = graph_figure(large_nodes, [])
    assert "Showing 180 nodes" in note and "Display cap reached" in note
    assert figure.layout.showlegend is not False


def test_plot_preserves_optional_style_and_arrow_direction():
    topology = load_topology()
    figure, _ = graph_figure(topology.nodes, topology.relationships)
    assert any(trace.line.dash == "dash" for trace in figure.data if trace.mode == "lines")
    assert len(figure.layout.annotations) == len(topology.relationships)
    path = EvidencePath(
        node_ids=["payment", "vault"],
        edges=[
            next(e for e in topology.relationships if e.source == "payment" and e.target == "vault")
        ],
        hops=1,
        required=True,
        criticality=5,
    )
    figure, note = graph_figure(
        topology.nodes, topology.relationships, path_filter=path, critical_paths=[path]
    )
    assert "Showing 2 nodes and 1 edges" in note
    assert any(
        trace.line.color == "#ff647c" and trace.line.width == 3
        for trace in figure.data
        if trace.mode == "lines"
    )


@pytest.fixture
def app():
    import src.dashboard_ui as ui

    ui.prepared_snapshot.clear()
    snapshot = (load_topology().model_dump_json(), "2026-10-16T00:00:00Z")
    with patch.object(ui, "read_snapshot", return_value=snapshot):
        yield AppTest.from_file(APP_PATH, default_timeout=30).run()


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_every_demo_renders_every_tab_without_errors(app, name):
    app.selectbox(key="scenario").select(name).run()
    app.button(key="investigate").click().run()
    assert not app.exception
    assert not app.error
    assert len(app.tabs) == 9
    assert len(app.metric) == 8
    assert (
        app.session_state["result_bundle"].investigation.matched_component.id
        == SCENARIOS[name].component_id
    )
    for tab in app.tabs:
        assert len(tab.children) > 0


def test_filters_reset_and_no_repeated_provider_call(app):
    with patch("src.dashboard_ui.run_investigation", wraps=run_investigation) as call:
        app.button(key="investigate").click().run()
        assert call.call_count == 1
        app.multiselect(key="viz_types").set_value([]).run()
        assert not app.exception and not app.error
        assert call.call_count == 1
        app.button(key="reset").click().run()
    assert not app.exception
    assert len(app.metric) == 0
    assert app.button(key="seed_button").disabled


def test_empty_graph_tabs_and_seeding_confirmation():
    import src.dashboard_ui as ui

    with patch.object(
        ui,
        "read_snapshot",
        return_value=(Topology(nodes=[], relationships=[]).model_dump_json(), "now"),
    ):
        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        assert not app.exception and len(app.tabs) == 9
        assert app.button(key="seed_button").disabled
        with patch.object(ui, "seed") as write:
            app.checkbox(key="seed_confirm").check().run()
            assert not app.button(key="seed_button").disabled
            write.assert_not_called()


def test_connection_error_is_safe():
    with patch(
        "src.dashboard_ui.read_snapshot", side_effect=RuntimeError("SECRET_INTERNAL_DETAIL")
    ):
        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert app.error
    assert all("SECRET_INTERNAL_DETAIL" not in error.value for error in app.error)


def test_seed_cannot_repeat_on_cosmetic_reruns(app):
    import src.dashboard_ui as ui

    with (
        patch.object(ui, "DatabaseManager") as connection,
        patch.object(ui, "seed", return_value={"nodes": 54, "relationships": 141}) as write,
    ):
        app.checkbox(key="seed_confirm").check().run()
        app.button(key="seed_button").click().run()
        assert write.call_count == 1
        assert app.button(key="seed_button").disabled
        app.run()
        assert write.call_count == 1
        connection.assert_called_once()


def test_context_entity_renders_empty_categories(app):
    app.selectbox(key="component").select("payments").run()
    app.button(key="investigate").click().run()
    assert not app.exception and not app.error
    assert len(app.tabs) == 9
    assert app.metric[0].value == "Unknown"
    assert app.session_state["result_bundle"].analysis is None


def test_incident_notes_redact_known_credentials(prepared):
    bundle = run_investigation(
        prepared,
        "vault",
        "notes with a fake-key-value",
        "failed",
        Settings(gemini_api_key="fake-key-value"),
    )
    assert "fake-key-value" not in bundle.model_dump_json()
    assert "[redacted]" in bundle.investigation.incident_input


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires the seeded local FalkorDB graph"
)
def test_live_dashboard_all_scenarios():
    import src.dashboard_ui as ui

    ui.read_snapshot.clear()
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception and not app.error
    for name in SCENARIOS:
        app.selectbox(key="scenario").select(name).run()
        app.button(key="investigate").click().run()
        assert not app.exception and not app.error, name
        assert len(app.metric) == 8 and len(app.tabs) == 9
