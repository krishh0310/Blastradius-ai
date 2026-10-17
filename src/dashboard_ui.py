"""Streamlit presentation and safe graph caching; reasoning lives in service modules."""

from datetime import datetime, timezone
from html import escape

import plotly.graph_objects as go
import streamlit as st

from src.config import Settings
from src.dashboard_service import SCENARIOS, DashboardResult, prepare_graph, run_investigation
from src.database import DatabaseManager
from src.graph_queries import EvidencePath, GraphQueries, QueryLimits
from src.seed import load_topology, seed
from src.topology import Topology
from src.visualization import COLORS, graph_figure

TABS = [
    "Executive Summary",
    "Interactive Blast Radius",
    "Dependency Paths",
    "Root Cause Analysis",
    "Bottlenecks",
    "Customers and Regions",
    "Runbook and Actions",
    "Graph Evidence",
    "Cypher and Diagnostics",
]
CSS = """<style>
.block-container {max-width:1560px;padding-top:2rem;padding-bottom:3rem;}
h1 {font-size:2.9rem!important;letter-spacing:-0.045em;margin-bottom:0!important;}
h2 {font-size:1.45rem!important;} h3 {font-size:1.13rem!important;}
p,li {line-height:1.55;}
[data-testid="stSidebar"] {border-right:1px solid #293c56;}
[data-testid="stMetric"] {background:#14243b;border:1px solid #304763;
 padding:16px 18px;border-radius:10px;min-height:112px;}
[data-testid="stMetricValue"] {font-size:1.65rem;font-weight:650;}
[data-testid="stMetricValue"] > div {white-space:normal!important;overflow-wrap:break-word;}
[data-testid="stMetricLabel"] {color:#c2d1e7;}
[data-baseweb="tab-list"] {gap:12px;border-bottom:1px solid #304763;padding-bottom:4px;}
[data-baseweb="tab"] {font-weight:600;font-size:0.88rem;}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible {
 outline:3px solid #b9d2ff!important;outline-offset:3px;}
.br-intro {color:#bfd0e8;font-size:1.12rem;max-width:760px;margin:.4rem 0 1.1rem;}
.br-status {color:#dce7f7;background:#14243b;padding:9px 13px;
 border-left:3px solid #64d9e7;margin:0 0 1.3rem;border-radius:4px;}
.br-empty {border:1px solid #304763;border-left:4px solid #8cb4ff;
 padding:28px;border-radius:8px;background:#101e32;margin:20px 0;}
.br-empty h2 {font-size:1.8rem!important;margin:0 0 10px;}
.br-empty p {color:#bfd0e8;max-width:720px;}
.br-legend {display:flex;flex-wrap:wrap;gap:7px 18px;font-size:.8rem;color:#d7e3f6;}
.br-legend span {white-space:nowrap;}
.br-legend i {display:inline-block;width:10px;height:10px;margin-right:6px;
 border:1px solid #ffffff99;border-radius:2px;}
@media(max-width:720px) {
 .block-container {padding:1rem .85rem 2rem;} h1 {font-size:2.1rem!important;}
 [data-testid="stMetric"] {min-height:90px;padding:12px;}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
 [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
 min-width:min(100%,240px)!important;flex:1 1 240px!important;}}
@media(prefers-reduced-motion:reduce) {* {animation:none!important;transition:none!important;}}
</style>"""
DEPENDENCY_CYPHER = """MATCH p=(affected:Component)
-[:DEPENDS_ON|CALLS|READS_FROM|WRITES_TO|PUBLISHES_TO|CONSUMES_FROM*1..8]->
(failed:Component {id: $component_id})
WHERE length(p) <= $depth
RETURN affected.id, [n IN nodes(p) | n.id], length(p)
LIMIT $limit"""


@st.cache_data(ttl=45, max_entries=4, show_spinner=False)
def read_snapshot(host: str, port: int, graph: str) -> tuple[str, str]:
    """Cache facts only; no secret, Settings object, or database handle is cached."""
    settings = Settings(falkordb_host=host, falkordb_port=port, falkordb_graph=graph)
    with DatabaseManager(settings) as database:
        database.test_connection()
        queries = GraphQueries.from_database(database, QueryLimits(depth=8))
    topology = Topology(nodes=list(queries.nodes.values()), relationships=queries.edges)
    return topology.model_dump_json(), datetime.now(timezone.utc).isoformat(timespec="seconds")


@st.cache_data(max_entries=8, show_spinner=False)
def prepared_snapshot(topology_json: str, depth: int):
    return prepare_graph(topology_json, depth)


def apply_scenario() -> None:
    scenario = SCENARIOS.get(st.session_state.get("scenario"))
    if scenario:
        st.session_state.update(
            component=scenario.component_id,
            incident_text=scenario.text,
            assumed_status=scenario.status,
        )


def reset_session() -> None:
    for key in list(st.session_state):
        if key.startswith(("result_", "viz_", "path_", "why_", "sim_")):
            del st.session_state[key]
    st.session_state["scenario"] = "Token Vault timeout"
    apply_scenario()
    st.session_state["depth"] = 6
    st.session_state["use_provider"] = False
    st.session_state["workspace"] = "Investigation"


def run_demo() -> None:
    """One-click deterministic rehearsal; never enables external providers."""
    st.session_state.update(
        scenario="Token Vault timeout",
        depth=6,
        use_provider=False,
        run_demo_requested=True,
        result_show_receipts=False,
        result_action_confirm=False,
    )
    apply_scenario()


def open_mitigation() -> None:
    """The consent checkbox authorizes only the displayed agent recommendation."""
    st.session_state["result_simulate_requested"] = True


def table(rows: list[dict], message: str = "No graph evidence in this category.") -> None:
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info(message)


def impact_rows(items) -> list[dict]:
    return [
        {
            "Component": i.component.name,
            "Type": i.component.label,
            "Hops": i.hops,
            "Exposure": "Required path" if i.required else "Optional-only path",
            "Recorded health": i.component.status,
            "Evidence walk": " → ".join(i.path.node_ids),
        }
        for i in items
    ]


def show_path(path: EvidencePath, title: str = "Supporting path") -> None:
    st.write(title)
    st.code(" → ".join(path.node_ids), language=None)
    st.caption(
        f"{path.hops} hops • {'Required route' if path.required else 'Includes optional dependency'}"
        f" • weakest edge criticality {path.criticality}/5. "
        "Walk order may reverse stored dependencies; the table preserves edge direction."
    )
    table(
        [
            {
                "From": e.source,
                "Relationship": e.type,
                "To": e.target,
                "Required": e.required,
                "Criticality": e.criticality,
            }
            for e in path.edges
        ],
        "The component itself is the zero-hop evidence.",
    )


def why(bundle: DashboardResult, key: str, items=None, factor: str = "blast_radius") -> None:
    with st.expander("Why? View graph evidence"):
        result, analysis = bundle.investigation, bundle.analysis
        if bundle.regional:
            st.warning(bundle.analysis_scope + ". This is not a regional outage score.")
        if analysis:
            st.write(
                f"Graph metric: betweenness {analysis.metrics.betweenness:.5f}; "
                f"articulation: {analysis.metrics.articulation_point}; "
                f"required dependents: {analysis.metrics.required_dependents}."
            )
            match = next((f for f in analysis.risk.factors if f.name == factor), None)
            if match:
                st.write(
                    f"Risk factor: {match.name} = {match.normalized:.3f} × "
                    f"{match.weight:g} = {match.points:.3f} points."
                )
                st.caption(match.explanation)
        paths = items if items is not None else result.direct_impact + result.cascading_impact
        if paths:
            index = st.selectbox(
                "Inspect supporting entity",
                range(len(paths)),
                format_func=lambda n: paths[n].component.name,
                key="why_" + key,
            )
            show_path(paths[index].path)
        else:
            st.info("No dependency path is recorded for this result.")
        st.code(DEPENDENCY_CYPHER, language="cypher")
        st.caption("Read-only example. Parameters are in Cypher and Diagnostics.")


def metric_cards(bundle: DashboardResult) -> None:
    result, analysis = bundle.investigation, bundle.analysis
    impacts = result.direct_impact + result.cascading_impact
    confidence = (
        analysis.root_causes[0].confidence
        if analysis and analysis.root_causes
        else "Insufficient evidence"
    )
    values = [
        (
            "Severity",
            analysis.risk.severity if analysis else "Unknown",
            "Deterministic risk category; see Why.",
        ),
        (
            "Risk score",
            f"{analysis.risk.score:.2f} / 100" if analysis else "Not scored",
            "Normalized factors minus resilience reduction; regional results use a labeled component envelope.",
        ),
        (
            "Affected services",
            str(len({i.component.id for i in impacts if i.component.label == "Service"})),
            "Potential downstream exposure, not confirmed failures.",
        ),
        (
            "Affected customers",
            str(len(result.impacted_customers)),
            "Graph-supported business workflow exposure.",
        ),
        (
            "Affected workflows",
            str(len(result.impacted_workflows)),
            "Business workflows with supporting paths.",
        ),
        (
            "Affected regions",
            str(len(result.impacted_regions)),
            "Deployment exposure, not region-wide outage.",
        ),
        (
            "Maximum hop depth",
            str(max((i.hops for i in impacts + result.impacted_customers), default=0)),
            "Includes workflow/customer joins beyond the dependency traversal budget.",
        ),
        ("Root-cause confidence", confidence, "Topology alone cannot confirm causation."),
    ]
    for offset in (0, 4):
        for column, (label, value, help_text) in zip(st.columns(4), values[offset : offset + 4]):
            column.metric(label, value, help=help_text)
    st.caption(bundle.analysis_scope + f" • completed in {bundle.elapsed_ms:.0f} ms")


def executive(bundle: DashboardResult) -> None:
    result, analysis, report = bundle.investigation, bundle.analysis, bundle.report
    st.subheader("The graph connects the failure to the business")
    if bundle.regional:
        st.warning("Regional exposure assessment. Alternate deployments may preserve availability.")
        st.write(bundle.analysis_scope)
    elif report:
        st.markdown("**Graph-grounded incident briefing**")
        st.write(report.executive_summary)
        st.caption(
            f"Report editor: {report.provider} / {report.model}. Graph services determine the facts and scores."
        )
        if report.grounding_warnings:
            st.warning(
                "Report used a safe fallback or grounding safeguards. "
                "See Warnings and unknown information for the reason."
            )
        if report.briefings:
            role = st.selectbox(
                "Briefing audience", [item.role for item in report.briefings], key="briefing_role"
            )
            briefing = next(item for item in report.briefings if item.role == role)
            choices = report.briefing_choices
            for identifier in briefing.claim_ids:
                claim = choices["claims"][identifier]
                st.write(claim["text"])
                st.caption(
                    "Evidence: "
                    + identifier
                    + " · "
                    + ", ".join(claim["path_ids"] or claim["entity_ids"])
                )
            st.write("Prioritized validation and response")
            for number in briefing.action_indices:
                st.write(report.immediate_actions[number])
            for number in briefing.question_indices:
                st.caption("Validate: " + choices["questions"][number])
            with st.expander("Compare fictional mitigations — supplied simulation evidence"):
                st.dataframe(
                    [
                        {"action": name, **choices["mitigations"][name]}
                        for name in briefing.mitigation_ids
                    ],
                    hide_index=True,
                )
                st.caption(
                    "Scenario comparison only. No action is executed; human approval is required."
                )
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("**Confirmed graph facts**")
        root = result.matched_component
        st.write(
            f"Recorded: {root.name}; health: {root.status}; criticality: {root.criticality}/5."
        )
        st.write(f"Scenario assumes {bundle.assumed_status}; recorded health is unchanged.")
        if report:
            for claim in report.confirmed_facts[:4]:
                st.write("• " + claim.text)
        st.markdown("**Candidate explanations — not confirmed causes**")
        if analysis:
            for candidate in analysis.root_causes[:3]:
                st.write(f"• {candidate.component.name}: {candidate.confidence}.")
        else:
            st.info("No operational cause ranking is available.")
        st.caption(
            "AI only prioritizes supplied statements."
            if report and report.provider != "deterministic"
            else "Template report. No AI-generated hypotheses are presented as facts."
        )
    with right:
        if analysis:
            factors = list(reversed(analysis.risk.factors))
            figure = go.Figure(
                go.Bar(
                    y=[f.name.replace("_", " ").capitalize() for f in factors],
                    x=[f.points for f in factors],
                    orientation="h",
                    marker_color="#8cb4ff",
                    text=[f"{f.points:.2f}" for f in factors],
                    textposition="outside",
                    cliponaxis=False,
                )
            )
            figure.update_layout(
                title="Risk factor contributions (points)",
                height=340,
                margin=dict(l=0, r=50, t=40, b=0),
                paper_bgcolor="#101e32",
                plot_bgcolor="#101e32",
                font=dict(color="#e6edf7"),
                xaxis=dict(range=[0, 24]),
            )
            st.plotly_chart(
                figure, width="stretch", config={"displayModeBar": False}, key="risk_chart"
            )
            st.caption(
                f"Resilience reduction: −{analysis.risk.resilience.reduction:g} points. "
                + analysis.risk.explanation
            )
    why(bundle, "executive")
    with st.expander("Warnings and unknown information"):
        for warning in sorted(set(result.warnings + (report.unknowns if report else []))):
            st.write("• " + warning)
        if report:
            for warning in report.grounding_warnings:
                st.warning(warning)


@st.fragment
def interactive_graph(
    bundle: DashboardResult, centrality: dict[str, float], queries: GraphQueries
) -> None:
    result = bundle.investigation
    st.subheader("Follow the cascade. Inspect the evidence.")
    types = sorted({n.label for n in result.evidence_nodes})
    first, second = st.columns(2)
    with first:
        selected_types = st.multiselect("Node types", types, default=types, key="viz_types")
    with second:
        selected_roles = st.multiselect(
            "Impact / severity", list(COLORS), default=list(COLORS), key="viz_roles"
        )
    max_hops = max(
        [i.hops for i in result.direct_impact + result.cascading_impact + result.impacted_customers]
        + [1]
    )
    a, b = st.columns([1, 2])
    with a:
        hops = st.slider("Maximum evidence hops", 0, max_hops, max_hops, key="viz_hops")
    with b:
        paths = result.shortest_paths + result.critical_paths
        chosen = st.selectbox(
            "Path focus",
            range(len(paths) + 1),
            format_func=lambda i: "All evidence" if i == 0 else " → ".join(paths[i - 1].node_ids),
            key="viz_path",
        )
    figure, note = graph_figure(
        result.evidence_nodes,
        result.evidence_edges,
        result,
        centrality,
        selected_types,
        selected_roles,
        hops,
        paths[chosen - 1] if chosen else None,
        result.critical_paths,
        assumed_status=bundle.assumed_status,
        context_nodes=list(queries.nodes.values()),
        context_edges=queries.edges,
    )
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key="blast_graph",
        config={
            "displaylogo": False,
            "scrollZoom": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )
    legend = "".join(
        f'<span><i style="background:{color}"></i>{escape(name)}</span>'
        for name, color in COLORS.items()
    )
    st.html('<div class="br-legend" role="note" aria-label="Graph legend">' + legend + "</div>")
    st.caption(note)
    st.caption(
        "Shapes: circle service; square database; diamond customer; triangle team; "
        "star region; hexagon queue/API. Typed node fills stay identifiable; borders show "
        "exposure. Red thick edges mark critical paths."
    )
    why(bundle, "graph")


def paths_view(bundle: DashboardResult) -> None:
    result = bundle.investigation
    st.subheader("Upstream causes and downstream consequences")
    direction = st.radio(
        "Path direction",
        ["Downstream impact", "Upstream dependencies", "Critical paths"],
        horizontal=True,
        key="path_direction",
    )
    paths = (
        result.critical_paths
        if direction == "Critical paths"
        else [i.path for i in result.dependencies]
        if direction == "Upstream dependencies"
        else result.shortest_paths
    )
    if not paths:
        st.info("No paths in this category within the selected traversal depth.")
    else:
        chosen = st.selectbox(
            "Evidence path",
            range(len(paths)),
            format_func=lambda i: f"{paths[i].hops} hops: " + " → ".join(paths[i].node_ids),
            key="path_inspector",
        )
        show_path(paths[chosen])
    table(
        impact_rows(
            result.dependencies
            if direction == "Upstream dependencies"
            else result.direct_impact + result.cascading_impact
        )
    )
    why(bundle, "paths")


def causes_view(bundle: DashboardResult) -> None:
    st.subheader("Evidence ranks candidates. It does not confirm causation.")
    analysis = bundle.analysis
    if not analysis or not analysis.root_causes:
        st.info("No operational root-cause candidates are available.")
        return
    if bundle.regional:
        st.warning(
            "Candidates describe the envelope component, not the cause of a regional outage."
        )
    table(
        [
            {
                "Candidate": c.component.name,
                "Confidence": c.confidence,
                "Score": c.score,
                "Recorded health": c.component.status,
                "Hops from symptom": c.supporting_path.hops,
                "Incident associations": ", ".join(c.historical_incident_ids) or "None",
            }
            for c in analysis.root_causes
        ]
    )
    chosen = st.selectbox(
        "Why this candidate?",
        range(len(analysis.root_causes)),
        format_func=lambda i: analysis.root_causes[i].component.name,
        key="why_cause",
    )
    candidate = analysis.root_causes[chosen]
    st.caption(candidate.explanation)
    show_path(candidate.supporting_path)
    table(
        [
            {
                "Factor": f.name,
                "Normalized": round(f.normalized, 4),
                "Weight": f.weight,
                "Points": f.points,
            }
            for f in candidate.factors
        ]
    )


def bottlenecks_view(bundle: DashboardResult, prepared) -> None:
    st.subheader("Shared dependencies deserve disproportionate attention")
    st.caption("Whole-graph comparison: every component uses the same hypothetical failed status.")
    table(
        [
            {
                "Component": a.component.name,
                "Risk": a.risk.score,
                "Severity": a.risk.severity,
                "Candidate SPOF": a.metrics.single_point_of_failure,
                "In-degree": a.metrics.in_degree,
                "Out-degree": a.metrics.out_degree,
                "Betweenness": round(a.metrics.betweenness, 5),
                "PageRank": round(a.metrics.pagerank, 5),
                "Articulation": a.metrics.articulation_point,
            }
            for a in prepared.bottlenecks
        ]
    )
    if prepared.bottlenecks:
        index = st.selectbox(
            "Why this bottleneck?",
            range(len(prepared.bottlenecks)),
            format_func=lambda i: prepared.bottlenecks[i].component.name,
            key="why_bottleneck",
        )
        item = prepared.bottlenecks[index]
        st.caption(item.metrics.explanation)
        table(
            [
                {
                    "Factor": f.name,
                    "Normalized": round(f.normalized, 4),
                    "Weight": f.weight,
                    "Contribution": f.points,
                }
                for f in item.risk.factors
            ]
        )
        st.write(f"Resilience reduction: {item.risk.resilience.reduction:g} points.")
        if item.critical_paths:
            show_path(item.critical_paths[0], "One critical supporting path")
    st.markdown("**Dependency cycles**")
    for cycle in bundle.investigation.cycles:
        st.write("Cycle group: " + " ↔ ".join(cycle.node_ids))
        table(
            [
                {"From": e.source, "Type": e.type, "To": e.target, "Required": e.required}
                for e in cycle.edges
            ]
        )
    if not bundle.investigation.cycles:
        st.info("No dependency cycle intersects this investigation.")


def customers_view(bundle: DashboardResult) -> None:
    result = bundle.investigation
    st.subheader("Translate dependency exposure into business context")
    st.markdown("**Customers and workflows**")
    table(impact_rows(result.impacted_customers + result.impacted_workflows))
    st.markdown("**Deployment regions**")
    table(impact_rows(result.impacted_regions))
    st.caption("Deployment exposure does not confirm that a region or its services are down.")
    if bundle.regional_deployments:
        st.markdown("**Regional deployments and alternate availability**")
        table(bundle.regional_deployments)
    if bundle.analysis:
        r = bundle.analysis.risk.resilience
        st.write("Declared healthy regions: " + (", ".join(r.healthy_deployment_regions) or "None"))
        st.write(
            "Declared healthy replica targets: " + (", ".join(r.healthy_replica_ids) or "None")
        )
        st.caption(r.explanation)
    why(
        bundle,
        "customers",
        result.impacted_customers + result.impacted_workflows,
        "customer_impact",
    )


def actions_view(bundle: DashboardResult) -> None:
    result, report = bundle.investigation, bundle.report
    st.subheader("Validate first. Recover with the owner.")
    table(impact_rows(result.owner_teams + result.runbooks))
    if report:
        for title in ("immediate_actions", "validation_steps", "longer_term_recommendations"):
            st.markdown("**" + title.replace("_", " ").capitalize() + "**")
            for number, action in enumerate(getattr(report, title), 1):
                st.write(f"{number}. {action}")
    else:
        st.info(
            "Validate region telemetry and alternate capacity with the graph-listed owners. "
            "Review associated runbooks before proposing changes."
        )
    st.warning(
        "Recommendations only. Failover, restarts, and destructive actions require human approval."
    )
    why(bundle, "actions", result.owner_teams + result.runbooks)


def evidence_view(bundle: DashboardResult) -> None:
    result = bundle.investigation
    st.subheader("Every claim can be traced back to the graph")
    st.write(
        f"{len(result.evidence_nodes)} evidence nodes • {len(result.evidence_edges)} directed edges"
    )
    table([n.model_dump() for n in result.evidence_nodes])
    table([e.model_dump() for e in result.evidence_edges])
    st.download_button(
        "Download investigation JSON",
        result.model_dump_json(indent=2),
        file_name="blastradius-investigation.json",
        mime="application/json",
    )
    if bundle.report:
        st.download_button(
            "Download grounded report JSON",
            bundle.report.model_dump_json(indent=2),
            file_name="blastradius-report.json",
            mime="application/json",
        )


def diagnostics_view(bundle: DashboardResult, snapshot_time: str, graph_name: str) -> None:
    st.subheader("Reproduce the reasoning")
    st.write(
        f"Graph: {graph_name}; snapshot: {snapshot_time}; investigation: {bundle.elapsed_ms:.0f} ms"
    )
    st.caption("Read-only query examples. This page does not execute arbitrary Cypher.")
    st.code("MATCH (n:Component {id: $component_id}) RETURN properties(n)", language="cypher")
    st.code(DEPENDENCY_CYPHER, language="cypher")
    st.json(
        {
            "component_id": bundle.investigation.matched_component.id,
            "depth": st.session_state.get("result_controls", ("", 6, ""))[1],
            "limit": 500,
        },
        expanded=False,
    )
    st.code(
        "MATCH (n:Component {id: $component_id})-[:DEPLOYED_IN]->(r:Region) RETURN r.id",
        language="cypher",
    )
    if bundle.analysis:
        with st.expander("Metrics and risk breakdown JSON"):
            st.json(
                {
                    "scope": bundle.analysis_scope,
                    "metrics": bundle.analysis.metrics.model_dump(),
                    "risk": bundle.analysis.risk.model_dump(),
                },
                expanded=False,
            )
    for warning in bundle.investigation.warnings + (
        bundle.report.grounding_warnings if bundle.report else []
    ):
        st.warning(warning)


def seed_controls(settings: Settings) -> None:
    with st.sidebar.expander("Demo graph maintenance"):
        st.caption(
            "Merge fictional data into the selected graph. No graph is deleted. Use a dedicated demo graph."
        )
        confirmed = st.checkbox("I confirm this graph is for demo data", key="seed_confirm")
        done = st.session_state.get("seed_complete") == settings.falkordb_graph
        if st.button(
            "Seed Demo Graph", disabled=not confirmed or done, key="seed_button", width="stretch"
        ):
            try:
                with st.spinner("Validate topology and merge demo graph…"):
                    with DatabaseManager(settings) as database:
                        summary = seed(database, load_topology())
                st.session_state["seed_complete"] = settings.falkordb_graph
                st.session_state["seed_message"] = (
                    f"Demo graph ready: {summary['nodes']} nodes, {summary['relationships']} relationships."
                )
                read_snapshot.clear()
                prepared_snapshot.clear()
                st.session_state.pop("result_bundle", None)
                st.rerun()
            except Exception:
                st.error("Demo seeding failed. Check FalkorDB connectivity and run CLI validation.")
        if done:
            st.caption(
                "Seed completed in this session. Reload the page to deliberately enable another merge."
            )


def main() -> None:
    st.set_page_config(
        page_title="BlastRadius AI | Incident workspace", page_icon="◉", layout="wide"
    )
    st.html(CSS)
    st.title("BlastRadius AI")
    st.html('<p class="br-intro">One failure. Every dependency. Evidence at every hop.</p>')
    try:
        settings = Settings.from_env()
    except Exception:
        st.error("Configuration is invalid. Check environment variables and .env.example.")
        return
    st.sidebar.title("Incident workspace")
    st.sidebar.caption("FalkorDB is the source of truth.")
    st.sidebar.caption(f"Graph: {settings.falkordb_graph} • provider: {settings.llm_provider}")
    workspace = st.sidebar.radio(
        "Workspace",
        ["Investigation", "Cascade simulation"],
        key="workspace",
        on_change=lambda: st.session_state.update(sim_playing=False),
    )
    seed_controls(settings)
    try:
        with st.spinner("Read infrastructure graph…"):
            snapshot_json, snapshot_time = read_snapshot(
                settings.falkordb_host, settings.falkordb_port, settings.falkordb_graph
            )
            topology = Topology.model_validate_json(snapshot_json)
    except Exception:
        st.error(
            "FalkorDB is unavailable or graph integrity validation failed. Start Docker, then refresh."
        )
        st.code("docker compose up -d --wait\npython -m src.seed --validate", language="bash")
        if st.button("Retry connection"):
            read_snapshot.clear()
            st.rerun()
        return
    st.html(
        '<div class="br-status">● FalkorDB connected at last read &nbsp; | &nbsp; Graph: '
        + escape(settings.falkordb_graph)
        + " &nbsp; | &nbsp; Configured report provider: "
        + escape(settings.llm_provider)
        + "</div>"
    )
    st.sidebar.caption("Read-only snapshot: " + snapshot_time)
    if st.sidebar.button("Refresh graph", width="stretch"):
        read_snapshot.clear()
        st.session_state.pop("result_bundle", None)
        st.rerun()
    if st.session_state.get("seed_message"):
        st.success(st.session_state["seed_message"])
    if not topology.nodes:
        st.info("The graph is empty. Confirm and use Seed Demo Graph in the sidebar to begin.")
        for tab in st.tabs(TABS):
            with tab:
                st.info("Seed a demo graph to explore this view.")
        return
    if workspace == "Cascade simulation":
        from src.simulation_ui import render_simulator

        render_simulator(snapshot_json)
        return
    if "scenario" not in st.session_state:
        st.session_state["scenario"] = "Token Vault timeout"
        apply_scenario()
    st.sidebar.selectbox(
        "Demo scenario",
        list(SCENARIOS) + ["Custom investigation"],
        key="scenario",
        on_change=apply_scenario,
    )
    choices = sorted(topology.nodes, key=lambda n: (n.label != "Service", n.name))
    names = {n.id: f"{n.name} · {n.label}" for n in choices}
    if st.session_state.get("component") not in names:
        st.session_state["component"] = choices[0].id
    st.sidebar.selectbox(
        "Component — type to search",
        list(names),
        format_func=lambda value: names[value],
        key="component",
    )
    st.sidebar.text_area(
        "Incident notes",
        key="incident_text",
        height=115,
        max_chars=2000,
        help="Analyst context only. Select the component explicitly; notes never enter provider prompts.",
    )
    st.sidebar.selectbox(
        "Scenario health assumption",
        ["failed", "degraded", "unhealthy", "healthy"],
        key="assumed_status",
        help="What-if assumption; recorded graph health is unchanged.",
    )
    depth = st.sidebar.slider(
        "Dependency traversal depth", 1, 8, key="depth", value=st.session_state.get("depth", 6)
    )
    use_provider = st.sidebar.checkbox(
        "Use configured LLM for report",
        key="use_provider",
        help="On Investigate only: send graph evidence to the configured provider. "
        "Otherwise use a deterministic template.",
    )
    if use_provider:
        st.sidebar.caption(
            f"Provider: {settings.llm_provider}; fallback "
            f"{'enabled' if settings.llm_fallback_enabled else 'disabled'}."
        )
    submitted = st.sidebar.button(
        "Investigate",
        type="primary",
        width="stretch",
        key="investigate",
        on_click=lambda: st.session_state.update(result_action_confirm=False),
    )
    st.sidebar.button("Reset", on_click=reset_session, width="stretch", key="reset")
    st.sidebar.caption("Reset clears this workspace, not the database.")
    demo, evidence, simulate = st.columns(3)
    demo.button("Run Token Vault Agent", key="run_demo", on_click=run_demo, width="stretch")
    evidence.button(
        "View FalkorDB Evidence",
        key="view_evidence",
        width="stretch",
        on_click=lambda: st.session_state.update(result_show_receipts=True),
    )
    agent = st.session_state.get("result_agent")
    request = st.session_state.get("result_agent_request")
    current_controls = (st.session_state["component"], depth, st.session_state["assumed_status"])
    action_available = bool(
        agent
        and request
        and agent.recommendation
        and agent.recommendation.eligible
        and len(agent.trace) < request.max_calls
        and st.session_state.get("result_controls") == current_controls
    )
    simulate.button(
        "Simulate Recommended Mitigation",
        key="open_mitigation",
        on_click=open_mitigation,
        width="stretch",
        disabled=not (action_available and st.session_state.get("result_action_confirm", False)),
    )
    st.checkbox(
        "I confirm the recommended in-memory fictional mitigation (no real infrastructure action)",
        key="result_action_confirm",
        disabled=not action_available,
    )
    submitted = submitted or st.session_state.pop("run_demo_requested", False)
    st.caption("Token Vault demo reporting: deterministic; no API key or cloud call required.")
    origin = (settings.falkordb_host, settings.falkordb_port, settings.falkordb_graph)
    if st.session_state.get("result_origin") not in (None, origin):
        st.session_state.pop("result_bundle", None)
    previous = st.session_state.get("result_bundle")
    source_json = (
        st.session_state.get("result_snapshot", snapshot_json)
        if previous and not submitted
        else snapshot_json
    )
    source_depth = (
        st.session_state.get("result_controls", ("", depth, ""))[1]
        if previous and not submitted
        else depth
    )
    try:
        with st.spinner("Prepare dependency metrics…"):
            prepared = prepared_snapshot(source_json, source_depth)
    except Exception:
        st.error("Analytics could not be prepared. Refresh the graph and check integrity.")
        return
    if submitted:
        try:
            from src.agent import AgentRequest
            from src.agent_ui import run_request

            st.session_state.pop("result_agent", None)
            st.session_state.pop("result_agent_request", None)
            with st.status("Investigating graph evidence…", expanded=True) as status_box:
                for key in list(st.session_state):
                    if key.startswith(("viz_", "path_", "why_")):
                        del st.session_state[key]
                bundle = run_investigation(
                    prepared,
                    st.session_state["component"],
                    st.session_state["incident_text"],
                    st.session_state["assumed_status"],
                    settings,
                    use_provider,
                    progress=lambda stage: st.write("✓ " + stage),
                    use_native=True,
                )
                st.session_state["result_bundle"] = bundle
                request = AgentRequest(
                    component=st.session_state["component"],
                    depth=depth,
                    status=st.session_state["assumed_status"],
                    incident=st.session_state["incident_text"],
                )
                st.write("Select bounded tools through the local MCP server…")
                st.session_state["result_agent"] = run_request(request, settings)
                st.session_state["result_agent_request"] = request
                st.session_state["result_origin"] = origin
                st.session_state["result_snapshot"] = snapshot_json
                st.session_state["result_snapshot_time"] = snapshot_time
                st.session_state["result_controls"] = (
                    st.session_state["component"],
                    depth,
                    st.session_state["assumed_status"],
                )
                status_box.update(
                    label="Graph investigation complete", state="complete", expanded=False
                )
            st.rerun()
        except Exception:
            st.session_state.pop("result_bundle", None)
            st.error(
                "Investigation could not finish. Refresh the graph or use a deterministic report. "
                "No infrastructure changes were made."
            )
            return
    bundle = st.session_state.get("result_bundle")
    from src.agent_ui import render_agent, simulate_request

    agent = st.session_state.get("result_agent")
    if st.session_state.pop("result_simulate_requested", False) and action_available:
        if st.session_state.get("result_action_confirm", False):
            with st.spinner("Recheck graph gate and simulate fictional mitigation through MCP…"):
                agent = simulate_request(agent, request, settings)
                st.session_state["result_agent"] = agent
            st.rerun()
    if agent:
        render_agent(agent)
    if bundle is None:
        st.html(
            '<section class="br-empty"><h2>See the outage before it spreads.</h2>'
            "<p>Start with Token Vault. Follow dependencies through payments, checkout, "
            "and business workflows to the customers they serve. Every impact has a path.</p>"
            "<p>Choose a scenario in the sidebar, then select <strong>Investigate</strong>.</p></section>"
        )
        st.info(
            "Fictional preview: shared dependency timeout → technical exposure → customer workflow → "
            "graph evidence → compare containment. Run Demo calculates the actual bounded result; "
            "no cloud provider or real infrastructure action is involved."
        )
        st.caption(
            f"Loaded {len(topology.nodes)} nodes and {len(topology.relationships)} relationships. "
            "No report provider has been called."
        )
        for tab in st.tabs(TABS):
            with tab:
                st.info("Your investigation will appear here. Select Investigate to begin.")
        return
    if bundle.investigation.matched_component is None:
        st.warning("Component not found. Refresh the graph and select a component.")
        return
    if (
        st.session_state["component"],
        depth,
        st.session_state["assumed_status"],
    ) != st.session_state.get("result_controls"):
        st.info(
            "Showing the last completed investigation. Select Investigate to apply changed controls."
        )
    st.subheader(bundle.investigation.matched_component.name)
    metric_cards(bundle)
    if bundle.report:
        st.caption(f"Report provider: {bundle.report.provider} · model: {bundle.report.model}")
    from src.evidence_ui import render_evidence

    render_evidence(
        bundle.investigation,
        expand_receipts=st.session_state.get("result_show_receipts", False),
    )
    tabs = st.tabs(TABS)
    with tabs[0]:
        executive(bundle)
    with tabs[1]:
        interactive_graph(bundle, prepared.analytics.degree, prepared.queries)
    with tabs[2]:
        paths_view(bundle)
    with tabs[3]:
        causes_view(bundle)
    with tabs[4]:
        bottlenecks_view(bundle, prepared)
    with tabs[5]:
        customers_view(bundle)
    with tabs[6]:
        actions_view(bundle)
    with tabs[7]:
        evidence_view(bundle)
    with tabs[8]:
        diagnostics_view(
            bundle,
            st.session_state.get("result_snapshot_time", snapshot_time),
            settings.falkordb_graph,
        )
