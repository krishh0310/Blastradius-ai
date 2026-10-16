"""Bounded Plotly evidence rendering; no incident reasoning or provider calls."""

from collections import defaultdict
from functools import lru_cache
from html import escape
from math import sqrt

import networkx as nx
import plotly.graph_objects as go

from src.graph_queries import EvidencePath, edge_key
from src.investigator import InvestigationResult
from src.topology import Node, Relationship

COLORS = {
    "Failed scenario": "#ff647c",
    "Critical affected": "#ff9b54",
    "Potential impact": "#f1d46a",
    "Healthy / context": "#60d7a5",
    "Database": "#bb9cff",
    "Customer": "#77aaff",
    "Team": "#64d9e7",
    "External API": "#acb7ca",
}
SYMBOLS = {
    "Service": "circle",
    "Database": "square",
    "Queue": "hexagon",
    "API": "hexagon2",
    "Region": "star",
    "Customer": "diamond",
    "Team": "triangle-up",
    "BusinessFlow": "pentagon",
    "Runbook": "triangle-down",
    "Incident": "x",
}


def node_roles(result: InvestigationResult, assumed_status: str = "failed") -> dict[str, str]:
    """Map existing impact/criticality facts to presentation roles."""
    roles = {}
    for item in result.direct_impact + result.cascading_impact:
        roles[item.component.id] = (
            "Critical affected"
            if item.required
            and item.component.criticality >= 4
            and not (result.matched_component and result.matched_component.label == "Region")
            else "Potential impact"
        )
    for item in result.impacted_customers + result.impacted_workflows:
        roles.setdefault(item.component.id, "Potential impact")
    if result.matched_component:
        roles[result.matched_component.id] = (
            "Failed scenario"
            if assumed_status in {"failed", "down", "unhealthy"}
            else "Critical affected"
            if assumed_status == "degraded"
            else "Healthy / context"
        )
    return roles


@lru_cache(maxsize=16)
def positions(ids: tuple[str, ...], links: tuple[tuple[str, str], ...]) -> dict:
    graph = nx.Graph()
    graph.add_nodes_from(ids)
    graph.add_edges_from(links)
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: (0.0, 0.0)}
    return nx.spring_layout(
        graph, seed=42, k=1.6 / sqrt(len(ids)), iterations=40 if len(ids) < 100 else 20
    )


def graph_figure(
    nodes: list[Node],
    edges: list[Relationship],
    result: InvestigationResult | None = None,
    centrality: dict[str, float] | None = None,
    node_types: list[str] | None = None,
    roles_filter: list[str] | None = None,
    max_hops: int = 10,
    path_filter: EvidencePath | None = None,
    critical_paths: list[EvidencePath] | None = None,
    assumed_status: str = "failed",
    context_nodes: list[Node] | None = None,
    context_edges: list[Relationship] | None = None,
    status_overrides: dict[str, str] | None = None,
) -> tuple[go.Figure, str]:
    """Render up to 180 nodes/300 edges; filtering keeps original edge direction."""
    roles = node_roles(result, assumed_status) if result else {}
    if status_overrides is not None:
        roles = {
            node: "Failed scenario"
            if status == "down"
            else "Potential impact"
            if status == "degraded"
            else "Healthy / context"
            for node, status in status_overrides.items()
        }
    hops = {}
    if result:
        groups = (
            result.direct_impact
            + result.cascading_impact
            + result.dependencies
            + result.impacted_customers
            + result.impacted_workflows
            + result.impacted_regions
            + result.owner_teams
            + result.runbooks
        )
        for item in groups:
            hops[item.component.id] = min(hops.get(item.component.id, item.hops), item.hops)
        if result.matched_component:
            hops[result.matched_component.id] = 0

    def role(node: Node) -> str:
        if status_overrides is not None:
            return roles.get(node.id, "Healthy / context")
        if result and result.matched_component and node.id == result.matched_component.id:
            return roles[node.id]
        typed = {
            "Database": "Database",
            "Customer": "Customer",
            "Team": "Team",
            "API": "External API",
        }.get(node.label)
        if typed:
            return typed
        if node.id in roles:
            return roles[node.id]
        return {
            "Database": "Database",
            "Customer": "Customer",
            "Team": "Team",
            "API": "External API",
        }.get(node.label, "Healthy / context")

    visible = [
        n
        for n in sorted(nodes, key=lambda n: (n.id not in roles, n.id))
        if (node_types is None or n.label in node_types)
        and (roles_filter is None or roles.get(n.id, role(n)) in roles_filter)
        and hops.get(n.id, 0) <= max_hops
        and (path_filter is None or n.id in path_filter.node_ids)
    ]
    all_count = len(visible)
    visible = visible[:180]
    ids = {n.id for n in visible}
    path_edges = {edge_key(e) for e in path_filter.edges} if path_filter else None
    links = [
        e
        for e in edges
        if e.source in ids and e.target in ids and (path_edges is None or edge_key(e) in path_edges)
    ]
    total_edges = len(links)
    links = links[:300]
    coords = positions(tuple(sorted(ids)), tuple(sorted({(e.source, e.target) for e in links})))
    critical = {edge_key(e) for p in critical_paths or [] for e in p.edges}
    owners = defaultdict(list)
    regions = defaultdict(list)
    lookup = {n.id: n for n in context_nodes or nodes}
    for edge in context_edges if context_edges is not None else edges:
        if edge.type == "OWNED_BY" and edge.target in lookup:
            owners[edge.source].append(lookup[edge.target].name)
        if edge.type == "DEPLOYED_IN" and edge.target in lookup:
            regions[edge.source].append(lookup[edge.target].name)
    figure = go.Figure()
    grouped_edges = defaultdict(lambda: ([], []))
    mid_x, mid_y, mid_text = [], [], []
    annotations = []
    for edge in links:
        x0, y0 = coords[edge.source]
        x1, y1 = coords[edge.target]
        style = (
            "critical"
            if edge_key(edge) in critical
            else "required"
            if edge.required
            else "optional"
        )
        xs, ys = grouped_edges[style]
        xs.extend([float(x0), float(x1), None])
        ys.extend([float(y0), float(y1), None])
        mid_x.append(float((x0 + x1) / 2))
        mid_y.append(float((y0 + y1) / 2))
        mid_text.append(
            escape(
                f"{edge.source} → {edge.target} | {edge.type} | "
                f"{'required' if edge.required else 'optional'} | criticality {edge.criticality}"
            )
        )
        annotations.append(
            dict(
                x=float(x0 + 0.80 * (x1 - x0)),
                y=float(y0 + 0.80 * (y1 - y0)),
                ax=float(x0 + 0.60 * (x1 - x0)),
                ay=float(y0 + 0.60 * (y1 - y0)),
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowwidth=2 if style == "critical" else 1,
                arrowcolor="#ff647c" if style == "critical" else "#8598b4",
            )
        )
    for style, (xs, ys) in sorted(grouped_edges.items()):
        figure.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=style.capitalize() + " dependency",
                line=dict(
                    color="#ff647c" if style == "critical" else "#6b819d",
                    width=3 if style == "critical" else 1.2,
                    dash="dash" if style == "optional" else "solid",
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=mid_x,
            y=mid_y,
            text=mid_text,
            mode="markers",
            marker=dict(size=9, opacity=0),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )
    for category, color in COLORS.items():
        selected = [n for n in visible if role(n) == category]
        figure.add_trace(
            go.Scatter(
                x=[float(coords[n.id][0]) for n in selected] or [None],
                y=[float(coords[n.id][1]) for n in selected] or [None],
                mode="markers+text" if len(visible) <= 45 else "markers",
                name=category,
                text=[escape(n.name) for n in selected],
                textposition="top center",
                textfont=dict(size=11, color="#e6edf7"),
                marker=dict(
                    color=color,
                    size=[
                        17
                        + 28 * (centrality or {}).get(n.id, 0)
                        + (8 if roles.get(n.id) == "Failed scenario" else 0)
                        for n in selected
                    ]
                    or [15],
                    symbol=[SYMBOLS.get(n.label, "circle") for n in selected] or ["circle"],
                    line=dict(
                        color=[COLORS.get(roles.get(n.id), "#d5e3f7") for n in selected]
                        or ["#d5e3f7"],
                        width=[3 if n.id in roles else 1 for n in selected] or [1],
                    ),
                ),
                customdata=[
                    [
                        escape(n.label),
                        escape((status_overrides or {}).get(n.id, n.status)),
                        escape(", ".join(sorted(owners[n.id])) or "Not in this evidence"),
                        n.criticality,
                        escape(", ".join(sorted(regions[n.id])) or n.region),
                        str(hops[n.id]) if n.id in hops else "Context",
                        escape(roles.get(n.id, role(n))),
                    ]
                    for n in selected
                ],
                hovertemplate=(
                    "<b>%{text}</b><br>Type: %{customdata[0]}<br>"
                    + ("Simulated health" if status_overrides is not None else "Recorded health")
                    + ": %{customdata[1]}"
                    "<br>Owner: %{customdata[2]}<br>Criticality: %{customdata[3]}/5"
                    "<br>Regions: %{customdata[4]}<br>Evidence hops: %{customdata[5]}"
                    "<br>Role: %{customdata[6]}<extra></extra>"
                ),
                showlegend=True,
            )
        )
    if not visible:
        annotations.append(
            dict(
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                text="No nodes match these filters.",
                showarrow=False,
                font=dict(color="#cbd8eb", size=16),
            )
        )
    figure.update_layout(
        title=dict(text="Directed cloud dependency evidence", font=dict(size=16, color="#e6edf7")),
        paper_bgcolor="#101e32",
        plot_bgcolor="#101e32",
        font=dict(color="#dbe6f6"),
        height=640,
        margin=dict(l=15, r=15, t=55, b=115),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        annotations=annotations,
        legend=dict(orientation="h", y=-0.06, x=0, font=dict(size=11), bgcolor="#101e32"),
        hoverlabel=dict(bgcolor="#233853", font=dict(color="#ffffff")),
        uirevision="evidence",
        dragmode="pan",
    )
    note = (
        f"Showing {len(visible)} nodes and {len(links)} edges. "
        "Arrows follow stored dependency direction (consumer → provider); dashed edges are optional."
    )
    if all_count > 180 or total_edges > 300:
        note += " Display cap reached; use filters or the full evidence tables."
    return figure, note
