"""Playback and comparison presentation for the pure in-memory simulator."""

import json
from time import monotonic

import streamlit as st

from src.simulator import (
    MitigationResult,
    SimulationConfig,
    SimulationFrame,
    SimulationRun,
    Simulator,
)
from src.topology import OWNED_LABELS, Topology
from src.visualization import graph_figure


@st.cache_data(max_entries=12, show_spinner=False)
def simulation_plan(topology_json: str, config_json: str) -> SimulationRun:
    return Simulator(
        Topology.model_validate_json(topology_json),
        SimulationConfig.model_validate_json(config_json),
    ).run()


@st.cache_data(max_entries=12, show_spinner=False)
def mitigation_plan(
    topology_json: str, config_json: str, run_json: str, action: str
) -> MitigationResult:
    simulator = Simulator(
        Topology.model_validate_json(topology_json),
        SimulationConfig.model_validate_json(config_json),
    )
    return simulator.mitigate(SimulationRun.model_validate_json(run_json), action)


@st.cache_data(max_entries=12, show_spinner=False)
def mitigation_eligibility(topology_json: str, config_json: str) -> dict[str, str | None]:
    return Simulator(
        Topology.model_validate_json(topology_json),
        SimulationConfig.model_validate_json(config_json),
    ).mitigation_options()


def reset_playback() -> None:
    """Reset the cursor and discard mitigation without recomputing the graph."""
    st.session_state["sim_cursor"] = 0
    st.session_state["sim_playing"] = False
    st.session_state.pop("sim_mitigation", None)
    st.session_state.pop("sim_deadline", None)


def draw_graph(
    frame: SimulationFrame, topology: Topology, title: str, key: str, compact: bool = False
) -> None:
    figure, note = graph_figure(
        topology.nodes,
        topology.relationships,
        result=frame.investigation,
        critical_paths=[
            p for p in frame.investigation.shortest_paths if p.required and p.criticality >= 4
        ],
        assumed_status=frame.statuses[frame.investigation.matched_component.id],
        status_overrides=frame.statuses,
    )
    figure.update_layout(
        title=title,
        height=365 if compact else 560,
        showlegend=not compact,
        margin=dict(l=5, r=5, t=45, b=15 if compact else 110),
    )
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key=key,
        config={"displaylogo": False, "scrollZoom": False, "displayModeBar": not compact},
    )
    if not compact:
        st.caption(note)


def playback(topology_json: str) -> None:
    """A timed fragment advances a cursor; it never regenerates simulation events."""
    run: SimulationRun = st.session_state["sim_run"]
    topology = Topology.model_validate_json(topology_json)
    mitigation: MitigationResult | None = st.session_state.get("sim_mitigation")
    frames = run.frames + ([mitigation.after] if mitigation else [])
    events = run.events + (mitigation.events if mitigation else [])
    controls = st.columns(4)
    if controls[0].button("Play", key="sim_play", disabled=st.session_state["sim_playing"]):
        if st.session_state["sim_cursor"] >= len(frames) - 1:
            st.session_state["sim_cursor"] = 0
        st.session_state["sim_playing"] = True
        st.session_state["sim_deadline"] = monotonic() + 1 / st.session_state["sim_speed"]
        st.rerun(scope="app")
    if controls[1].button("Pause", key="sim_pause", disabled=not st.session_state["sim_playing"]):
        st.session_state["sim_playing"] = False
        st.rerun(scope="app")
    if controls[2].button(
        "Next step", key="sim_next", disabled=st.session_state["sim_cursor"] >= len(frames) - 1
    ):
        st.session_state["sim_cursor"] += 1
        st.session_state["sim_playing"] = False
        st.rerun(scope="app")
    if controls[3].button("Reset simulation", key="sim_reset"):
        reset_playback()
        st.rerun(scope="app")
    if st.session_state["sim_playing"] and monotonic() >= st.session_state.get("sim_deadline", 0):
        st.session_state["sim_cursor"] = min(st.session_state["sim_cursor"] + 1, len(frames) - 1)
        st.session_state["sim_deadline"] = monotonic() + 1 / st.session_state["sim_speed"]
        if st.session_state["sim_cursor"] == len(frames) - 1:
            st.session_state["sim_playing"] = False
            st.rerun(scope="app")
    cursor = st.session_state["sim_cursor"]
    frame = frames[cursor]
    stage = (
        "Before failure"
        if cursor == 0
        else "After mitigation"
        if cursor >= len(run.frames)
        else "Cascade"
    )
    st.progress(
        cursor / max(1, len(frames) - 1), text=f"{stage} • T+{frame.timestamp_seconds:02d}s"
    )
    metrics = st.columns(4)
    metrics[0].metric(
        "Current simulated risk",
        f"{frame.risk.score:.2f}",
        frame.risk.severity,
        delta_color="off",
        help="Existing risk formula applied to active simulated exposure.",
    )
    metrics[1].metric("Entities currently affected", len(frame.affected_ids))
    metrics[2].metric("Simulated elapsed time", f"T+{frame.timestamp_seconds:02d}s")
    metrics[3].metric("Timeline transitions", frame.event_count)
    st.caption(run.risk_scope)
    draw_graph(
        frame,
        topology,
        f"{stage}: dependency cascade at T+{frame.timestamp_seconds:02d}s",
        "sim_current_graph",
    )
    st.caption(
        "Red = down; yellow = degraded; green = healthy. Shape identifies entity type. "
        "All displayed health is simulated. Stored dependency arrows and optional dashed edges are preserved."
    )
    st.subheader("Incident timeline")
    visible_events = events[: frame.event_count]
    if not visible_events:
        st.info("Healthy baseline. Select Next step or Play to inject the starting failure.")
    else:
        st.dataframe(
            [
                {
                    "Simulated time": f"T+{e.timestamp_seconds:02d}s",
                    "Entity": e.entity,
                    "Previous": e.previous_status,
                    "Now": e.new_status,
                    "Cause": e.cause,
                    "Hops": e.dependency_path.hops,
                    "Confidence": e.confidence,
                    "Dependency walk": " → ".join(e.dependency_path.node_ids),
                    "Recommended response": e.recommended_response,
                }
                for e in visible_events
            ],
            hide_index=True,
            width="stretch",
        )
        index = st.selectbox(
            "Inspect a transition",
            range(len(visible_events)),
            format_func=lambda i: (
                f"T+{visible_events[i].timestamp_seconds:02d}s "
                + visible_events[i].entity
                + ": "
                + visible_events[i].new_status
            ),
            key=f"sim_event_{run.config.component_id}_{len(visible_events)}",
        )
        event = visible_events[index]
        with st.expander("Why did this transition occur?", expanded=False):
            st.write(event.cause)
            st.code(" → ".join(event.dependency_path.node_ids), language=None)
            st.caption(f"{event.dependency_path.hops} evidence hops • {event.confidence}")
            if event.supporting_edge:
                st.json(event.supporting_edge.model_dump(), expanded=False)
            else:
                st.caption(
                    "The initial failure is a user-selected scenario assumption, not a graph edge."
                )


def render_simulator(topology_json: str) -> None:
    st.subheader("Rehearse the cascade. Rewind the outcome.")
    st.info(
        "Fictional healthy baseline • graph-grounded dependencies • no database writes, infrastructure actions, or LLM calls"
    )
    topology = Topology.model_validate_json(topology_json)
    options = sorted(
        (n for n in topology.nodes if n.label in OWNED_LABELS | {"Region"}), key=lambda n: n.name
    )
    if not options:
        st.warning("Load operational components before running a simulation.")
        return
    names = {n.id: n.name for n in options}
    left, middle, right = st.columns(3)
    selected = left.selectbox(
        "Starting component",
        list(names),
        index=list(names).index("vault") if "vault" in names else 0,
        format_func=lambda value: names[value],
        key="sim_component",
    )
    failure = middle.selectbox("Inject status", ["down", "degraded"], key="sim_status")
    policy = right.selectbox(
        "Optional dependency behavior", ["degrade", "ignore"], key="sim_optional"
    )
    a, b, c = st.columns(3)
    automatic = a.checkbox(
        "Assume graph-declared failover is ready",
        value=True,
        key="sim_auto",
        help="Only existing healthy deployments/replicas qualify; "
        "shared upstream failures still propagate.",
    )
    depth = b.slider("Simulation dependency depth", 1, 8, 8, key="sim_depth")
    speed = c.select_slider(
        "Playback speed",
        options=[0.5, 1.0, 2.0, 4.0],
        value=1.0,
        format_func=lambda value: f"{value:g}×",
        key="sim_speed",
    )
    config = SimulationConfig(
        component_id=selected,
        failure_status=failure,
        optional_policy=policy,
        automatic_failover=automatic,
        depth=depth,
    )
    preview_requested = st.session_state.pop("sim_preview_requested", False)
    if st.button("Build cascade", key="sim_build", type="primary") or preview_requested:
        try:
            with st.spinner("Build deterministic timeline and risk frames…"):
                run = simulation_plan(topology_json, config.model_dump_json())
            reset_playback()
            st.session_state["sim_run"] = run
            st.session_state["sim_snapshot"] = topology_json
            if preview_requested:
                action = "Isolate unhealthy dependency"
                reason = mitigation_eligibility(topology_json, config.model_dump_json())[action]
                if reason is None:
                    st.session_state["sim_mitigation"] = mitigation_plan(
                        topology_json, config.model_dump_json(), run.model_dump_json(), action
                    )
                    st.session_state["sim_cursor"] = len(run.frames)
                else:
                    st.info("Fictional containment is unavailable: " + reason)
        except Exception:
            st.error(
                "Simulation could not be built. Check graph integrity and the selected component."
            )
            return
    run = st.session_state.get("sim_run")
    if run is None:
        st.caption(
            "Start with Token Vault. The graph will reveal the cascade through Payment, Checkout, "
            "Subscription, workflows, and customers. No timings or error rates are fabricated as telemetry."
        )
        return
    if config != run.config or topology_json != st.session_state["sim_snapshot"]:
        st.warning(
            "Showing the last built simulation. Build cascade to apply changed inputs or graph data."
        )
    source = st.session_state["sim_snapshot"]
    interval = 1 / speed if st.session_state.get("sim_playing") else None
    st.fragment(run_every=interval)(playback)(source)
    st.divider()
    st.subheader("Fictional mitigation lab")
    eligibility = mitigation_eligibility(source, run.config.model_dump_json())
    action = st.selectbox("Mitigation policy", list(eligibility), key="sim_action")
    reason = eligibility[action]
    if reason:
        st.caption("Unavailable: " + reason)
    else:
        st.caption(
            "Preview only. This replays a fictional recovery assumption; nothing is executed."
        )
    if st.button("Simulate mitigation", key="sim_mitigate", disabled=bool(reason)):
        try:
            with st.spinner("Replay the policy against the same graph snapshot…"):
                mitigation = mitigation_plan(
                    source, run.config.model_dump_json(), run.model_dump_json(), action
                )
            st.session_state["sim_mitigation"] = mitigation
            st.session_state["sim_playing"] = False
            st.session_state["sim_cursor"] = len(run.frames)
            st.rerun()
        except Exception:
            st.error("The mitigation lacks sufficient graph evidence or could not be simulated.")
    mitigation = st.session_state.get("sim_mitigation")
    st.subheader("Before / peak cascade / after mitigation")
    columns = st.columns(3)
    for column, label, frame, key in zip(
        columns,
        ["Before failure", "Peak cascade", "After fictional mitigation"],
        [run.frames[0], run.peak, mitigation.after if mitigation else None],
        ["sim_before_graph", "sim_peak_graph", "sim_after_graph"],
    ):
        with column:
            st.markdown("**" + label + "**")
            if frame:
                st.metric(
                    label + " risk",
                    f"{frame.risk.score:.2f}",
                    frame.risk.severity,
                    delta_color="off",
                )
                st.caption(f"{len(frame.affected_ids)} affected entities")
                draw_graph(frame, Topology.model_validate_json(source), label, key, compact=True)
            else:
                st.info("Select a graph-supported fictional mitigation to compare its outcome.")
    st.caption(
        "Shared health legend: red down • yellow degraded • green healthy. "
        "The graph topology is identical in every panel."
    )
    if mitigation:
        message = (
            f"Peak → after risk: {run.peak.risk.score:.2f} → {mitigation.after.risk.score:.2f}. "
            f"Additional reduction versus the unmitigated settled state: "
            f"{mitigation.risk_reduction:+.2f} points. "
            f"{len(mitigation.removed_critical_paths)} critical impact paths no longer active."
        )
        (st.success if mitigation.risk_reduction > 0 else st.info)(message)
        st.caption(mitigation.explanation)
        with st.expander("Affected entities before and after mitigation"):
            lookup = {n.id: n.name for n in topology.nodes}
            st.dataframe(
                [
                    {
                        "Entity": lookup[n],
                        "Peak": run.peak.statuses[n],
                        "After": mitigation.after.statuses[n],
                    }
                    for n in sorted(set(run.peak.affected_ids) | set(mitigation.after.affected_ids))
                ],
                hide_index=True,
                width="stretch",
            )
        with st.expander("Critical impact paths neutralized by mitigation"):
            st.dataframe(
                [
                    {
                        "Evidence walk": " → ".join(p.node_ids),
                        "Hops": p.hops,
                        "Weakest criticality": p.criticality,
                    }
                    for p in mitigation.removed_critical_paths
                ],
                hide_index=True,
                width="stretch",
            )
    with st.expander("Score breakdown and simulation assumptions"):
        st.json(
            {
                "before": run.frames[0].risk.model_dump(),
                "peak": run.peak.risk.model_dump(),
                "after": mitigation.after.risk.model_dump() if mitigation else None,
            },
            expanded=False,
        )
        for warning in run.warnings:
            st.write("• " + warning)
    download = {
        "simulation": run.model_dump(mode="json"),
        "mitigation": mitigation.model_dump(mode="json") if mitigation else None,
    }
    st.download_button(
        "Download simulation evidence",
        json.dumps(download, indent=2),
        file_name="blastradius-simulation.json",
        mime="application/json",
    )
