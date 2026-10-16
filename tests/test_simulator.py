"""Deterministic simulation, evidence, failover, and UI playback contracts."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from src.graph_queries import edge_key
from src.seed import load_topology
from src.simulator import SimulationConfig, Simulator
from src.topology import Topology

APP = Path(__file__).resolve().parents[1] / "app.py"


def engine(component="vault", **kwargs):
    return Simulator(load_topology(), SimulationConfig(component_id=component, **kwargs))


def test_deterministic_propagation_without_topology_mutation():
    topology = load_topology()
    original = topology.model_dump()
    simulator = Simulator(topology, SimulationConfig(component_id="vault"))
    first, second = simulator.run(), simulator.run()
    assert first == second
    assert topology.model_dump() == original
    events = {event.entity_id: event for event in first.events}
    assert events["payment"].timestamp_seconds == 3
    assert events["checkout"].timestamp_seconds == 6
    assert events["orbit"].timestamp_seconds >= 9
    assert first.frames[0].statuses["vault"] == "healthy"
    assert first.frames[-1].statuses["vault"] == "down"
    assert first.peak.risk.severity == "Critical"
    assert first.events[0].supporting_edge is None


def test_optional_dependency_degrades_or_blocks():
    degraded = engine("analytics", automatic_failover=False, optional_policy="degrade").run()
    ignored = engine("analytics", automatic_failover=False, optional_policy="ignore").run()
    assert degraded.frames[-1].statuses["notification"] == "degraded"
    assert ignored.frames[-1].statuses["notification"] == "healthy"
    assert ignored.frames[-1].statuses["orbit"] == "down"  # reporting is required
    assert ignored.peak.risk.score < degraded.peak.risk.score


def test_later_required_route_overrides_optional_evidence_without_duplicate_transition():
    topology = load_topology()
    prototype = next(
        e for e in topology.relationships if e.source == "payment" and e.target == "vault"
    )
    topology.relationships.extend(
        [
            prototype.model_copy(
                update={
                    "source": "notification",
                    "target": "vault",
                    "type": "CALLS",
                    "required": False,
                }
            ),
            prototype.model_copy(
                update={
                    "source": "notification",
                    "target": "auth",
                    "type": "CALLS",
                    "required": True,
                }
            ),
        ]
    )
    run = Simulator(
        topology, SimulationConfig(component_id="vault", failure_status="degraded")
    ).run()
    notification = next(
        i for i in run.frames[-1].investigation.cascading_impact if i.component.id == "notification"
    )
    assert notification.required
    assert notification.path.node_ids == ["vault", "auth", "notification"]
    assert len([e for e in run.events if e.entity_id == "notification"]) == 1


def test_healthy_regional_failover_reduces_exposure():
    unprotected = engine("payment", automatic_failover=False).run()
    protected = engine("payment", automatic_failover=True).run()
    assert protected.frames[-1].statuses["payment"] == "healthy"
    assert protected.frames[-1].affected_ids == []
    assert protected.peak.risk.score < unprotected.peak.risk.score
    recovery = next(event for event in protected.events if event.new_status == "healthy")
    assert recovery.supporting_edge.type == "DEPLOYED_IN"
    assert recovery.supporting_edge.target in {"singapore", "frankfurt"}


def test_replication_requires_healthy_recorded_target():
    topology = load_topology()
    # Orders Database is Mumbai-only, with a declared warehouse replica.
    good = Simulator(topology, SimulationConfig(component_id="orders-db")).run()
    assert good.frames[-1].statuses["orders-db"] == "healthy"
    next(n for n in topology.nodes if n.id == "warehouse-db").status = "down"
    bad = Simulator(topology, SimulationConfig(component_id="orders-db")).run()
    assert bad.frames[-1].statuses["orders-db"] == "down"


def test_regional_failover_does_not_hide_shared_dependency_failure():
    run = engine("mumbai").run()
    assert any("failover" in event.cause and event.new_status == "healthy" for event in run.events)
    assert run.frames[-1].statuses["mumbai"] == "down"
    assert run.frames[-1].statuses["vault"] == "down"
    assert run.frames[-1].statuses["payment"] == "down"
    assert run.frames[-1].statuses["orbit"] == "down"
    assert run.frames[-1].statuses["purchase"] == "down"
    assert "Regional exposure envelope" in run.risk_scope


def test_cycles_and_event_limit_are_bounded():
    run = engine("analytics", automatic_failover=False).run()
    assert len(run.events) < 20
    for event in run.events:
        assert len(event.dependency_path.node_ids) == len(set(event.dependency_path.node_ids))
    limited = engine(max_events=2).run()
    assert len(limited.events) == 2
    assert any("Event limit" in warning for warning in limited.warnings)


def test_every_transition_has_correct_history_and_original_graph_evidence():
    topology = load_topology()
    simulator = Simulator(topology, SimulationConfig(component_id="vault"))
    run = simulator.run()
    states = dict(run.frames[0].statuses)
    edges = {edge_key(e) for e in topology.relationships}
    assert [e.timestamp_seconds for e in run.events] == sorted(
        e.timestamp_seconds for e in run.events
    )
    for event in run.events:
        assert states[event.entity_id] == event.previous_status
        states[event.entity_id] = event.new_status
        assert event.dependency_path.node_ids[-1] == event.entity_id
        assert event.dependency_path.hops == len(event.dependency_path.edges)
        if event.supporting_edge:
            assert edge_key(event.supporting_edge) in edges
        assert event.cause and event.confidence and event.recommended_response
    assert states == run.frames[-1].statuses


def test_runbook_mitigation_reduces_risk_and_active_critical_paths():
    simulator = engine()
    run = simulator.run()
    mitigation = simulator.mitigate(run, "Execute fictional runbook")
    assert mitigation.after.risk.score < run.peak.risk.score
    assert mitigation.risk_reduction == 70
    assert mitigation.after.affected_ids == []
    assert mitigation.removed_critical_paths
    assert len(mitigation.events) == len(run.frames[-1].affected_ids)
    assert all(event.confidence == "Fictional mitigation" for event in mitigation.events)
    root = next(e for e in mitigation.events if e.entity_id == "vault")
    assert root.supporting_edge.type == "HAS_RUNBOOK"
    assert simulator.mitigate(run, "Execute fictional runbook") == mitigation
    assert simulator.run() == run


def test_supported_mitigation_policies_do_not_invent_alternatives():
    simulator = engine()
    assert simulator.mitigation_options()["Activate regional replica"]
    with pytest.raises(ValueError, match="alternate"):
        simulator.mitigate(simulator.run(), "Activate regional replica")
    isolated = simulator.mitigate(simulator.run(), "Isolate unhealthy dependency")
    assert isolated.after.statuses["vault"] == "down"
    assert isolated.after.statuses["payment"] == "degraded"
    assert isolated.after.statuses["checkout"] == "healthy"
    assert isolated.after.risk.score < simulator.run().peak.risk.score
    readonly = simulator.mitigate(simulator.run(), "Degraded read-only mode")
    assert readonly.after.statuses["vault"] == "degraded"
    optional = engine("analytics", automatic_failover=False)
    disabled = optional.mitigate(optional.run(), "Disable optional feature")
    assert disabled.after.statuses["notification"] == "healthy"
    assert disabled.after.statuses["orbit"] == "down"


def test_explicit_failover_and_reroute_rehearsals():
    simulator = engine("payment", automatic_failover=False)
    run = simulator.run()
    for action in ("Activate regional replica", "Reroute traffic"):
        after = simulator.mitigate(run, action)
        assert after.after.statuses["payment"] == "healthy"
        assert after.after.risk.score < run.peak.risk.score


@pytest.fixture
def app():
    with patch(
        "src.dashboard_ui.read_snapshot",
        return_value=(load_topology().model_dump_json(), "test snapshot"),
    ):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.radio(key="workspace").set_value("Cascade simulation").run()
        yield app


def test_playback_next_pause_reset_and_mitigation_ui(app):
    app.button(key="sim_build").click().run()
    assert not app.exception and not app.error
    original = app.session_state["sim_run"].model_dump_json()
    assert app.session_state["sim_cursor"] == 0
    app.button(key="sim_next").click().run()
    assert app.session_state["sim_cursor"] == 1
    app.button(key="sim_play").click().run()
    assert app.session_state["sim_playing"]
    app.session_state["sim_deadline"] = 0
    app.run()
    assert app.session_state["sim_cursor"] == 2
    app.button(key="sim_pause").click().run()
    assert not app.session_state["sim_playing"]
    app.select_slider(key="sim_speed").set_value(4.0).run()
    assert app.session_state["sim_speed"] == 4.0
    app.selectbox(key="sim_action").select("Execute fictional runbook").run()
    app.button(key="sim_mitigate").click().run()
    assert not app.exception and not app.error
    assert app.session_state["sim_mitigation"].after.affected_ids == []
    app.button(key="sim_reset").click().run()
    assert app.session_state["sim_cursor"] == 0
    assert app.session_state["sim_run"].model_dump_json() == original
    assert "sim_mitigation" not in app.session_state
    assert not app.exception


def test_regional_ui_and_no_database_write(app):
    with patch("src.database.DatabaseManager.execute_query") as database:
        app.selectbox(key="sim_component").select("mumbai").run()
        app.button(key="sim_build").click().run()
        assert not app.exception and not app.error
        assert "Regional" in app.session_state["sim_run"].risk_scope
        database.assert_not_called()


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires seeded local FalkorDB"
)
def test_live_simulation_reads_but_never_modifies_graph():
    from src.config import Settings
    from src.database import DatabaseManager
    from src.graph_queries import GraphQueries

    with DatabaseManager(Settings.from_env()) as database:
        first = GraphQueries.from_database(database)
        topology = Topology(nodes=list(first.nodes.values()), relationships=first.edges)
        simulator = Simulator(topology, SimulationConfig(component_id="vault"))
        run = simulator.run()
        simulator.mitigate(run, "Execute fictional runbook")
        second = GraphQueries.from_database(database)
    assert topology == Topology(nodes=list(second.nodes.values()), relationships=second.edges)
