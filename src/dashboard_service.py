"""Dashboard orchestration; existing service modules remain the reasoning engine."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from pydantic import BaseModel, Field

from src.analytics import Analytics, ComponentAnalysis
from src.config import Settings
from src.graph_queries import EvidencePath, GraphQueries, Impact, QueryLimits, edge_key
from src.investigator import InvestigationResult, investigate
from src.reports import IncidentReport, build_evidence, generate_report
from src.topology import OWNED_LABELS


class Scenario(BaseModel):
    component_id: str
    status: str
    text: str


SCENARIOS = {
    "Token Vault timeout": Scenario(
        component_id="vault",
        status="failed",
        text="Token Vault requests are timing out during payments and sign-in.",
    ),
    "Orders Database latency": Scenario(
        component_id="orders-db",
        status="degraded",
        text="Orders Database latency is elevated during checkout.",
    ),
    "Mumbai region outage": Scenario(
        component_id="mumbai",
        status="failed",
        text="Mumbai is unavailable. Assess regional exposure and alternate deployments.",
    ),
    "External payment API degradation": Scenario(
        component_id="bank-api",
        status="degraded",
        text="The external bank API is slow during payment authorization.",
    ),
    "Optional analytics dependency failure": Scenario(
        component_id="analytics",
        status="failed",
        text="The optional analytics dependency is unavailable.",
    ),
}


@dataclass
class PreparedGraph:
    queries: GraphQueries
    analytics: Analytics
    bottlenecks: list[ComponentAnalysis]


class DashboardResult(BaseModel):
    investigation: InvestigationResult
    analysis: ComponentAnalysis | None = None
    report: IncidentReport | None = None
    regional: bool = False
    analysis_scope: str
    regional_deployments: list[dict] = Field(default_factory=list)
    elapsed_ms: float
    assumed_status: str


def prepare_graph(topology_json: str, depth: int) -> PreparedGraph:
    """Compute expensive analytics once per safe graph snapshot and depth."""
    from src.topology import Topology

    queries = GraphQueries(Topology.model_validate_json(topology_json), QueryLimits(depth=depth))
    analytics = Analytics(queries)
    top = analytics.highest_risk(min(5, len(analytics.graph))) if analytics.graph else []
    return PreparedGraph(queries, analytics, top)


def regional_exposure(
    prepared: PreparedGraph, region_id: str
) -> tuple[InvestigationResult, list[dict]]:
    """Join deployment evidence to existing impact operations; never invent edges."""
    q = prepared.queries
    result = investigate(q, region_id)
    root = result.matched_component
    if root is None:
        return result, []
    root_impact = Impact(
        component=root,
        hops=0,
        required=True,
        path=EvidencePath(node_ids=[root.id], edges=[], hops=0, required=True, criticality=0),
    )
    deployed = []
    for label in sorted(OWNED_LABELS):
        deployed += q.context([root_impact], "DEPLOYED_IN", label, incoming=True)
    found = {i.component.id: i for i in deployed}
    availability = []
    for item in deployed:
        deployment = q.deployment(item.component.id)
        alternate_regions = [n.id for n in deployment.healthy_regions if n.id != region_id]
        availability.append(
            {
                "id": item.component.id,
                "component": item.component.name,
                "type": item.component.label,
                "recorded_status": item.component.status,
                "alternate_regions": ", ".join(alternate_regions) or "None declared",
                "single_region": not alternate_regions,
            }
        )
        if q.limits.depth > 1:
            for downstream in q.blast_radius(item.component.id, q.limits.depth - 1):
                if region_id in downstream.path.node_ids:
                    continue
                path = EvidencePath(
                    node_ids=[region_id] + downstream.path.node_ids,
                    edges=item.path.edges + downstream.path.edges,
                    hops=downstream.hops + 1,
                    required=item.required and downstream.required,
                    criticality=min(item.path.criticality, downstream.path.criticality),
                )
                candidate = Impact(
                    component=downstream.component,
                    hops=path.hops,
                    path=path,
                    required=path.required,
                )
                previous = found.get(candidate.component.id)
                if previous is None or (candidate.hops, candidate.path.node_ids) < (
                    previous.hops,
                    previous.path.node_ids,
                ):
                    found[candidate.component.id] = candidate
    impacts = sorted(found.values(), key=lambda i: (i.hops, i.component.id))
    direct_ids = {i.component.id for i in deployed}
    affected = [root_impact] + impacts
    result.direct_impact = sorted(deployed, key=lambda i: i.component.id)
    result.cascading_impact = [i for i in impacts if i.component.id not in direct_ids]
    result.impacted_workflows = q.workflows(affected)
    result.impacted_customers = q.customers(result.impacted_workflows)
    result.impacted_regions = q.regions(affected)
    result.impacted_regions = [root_impact] + [
        i for i in result.impacted_regions if i.component.id != region_id
    ]
    result.owner_teams = q.teams(affected)
    result.runbooks = q.runbooks(affected)
    result.shortest_paths = [i.path for i in impacts]
    ids = set(found)
    result.cycles = [c for c in q.cycles() if ids.intersection(c.node_ids)]
    claims = (
        affected + result.impacted_workflows + result.impacted_customers + result.impacted_regions
    )
    claims += result.owner_teams + result.runbooks
    evidence = q.evidence_subgraph(
        [i.path for i in claims],
        extra_edges=[e for c in result.cycles for e in c.edges],
        node_ids=[region_id],
    )
    result.evidence_nodes, result.evidence_edges = evidence.nodes, evidence.edges
    result.warnings = sorted(
        set(
            q.warnings
            + [
                "Regional exposure includes services with alternate deployments; it does not prove global failure.",
                "The regional risk card is a worst-case single-region component envelope, not a regional risk model.",
                "Alternate deployment health does not establish failover capacity or replica readiness.",
            ]
        )
    )
    return result, sorted(availability, key=lambda row: row["id"])


def run_investigation(
    prepared: PreparedGraph,
    component: str,
    incident_text: str,
    status: str,
    settings: Settings,
    use_provider: bool = False,
    progress: Callable[[str], None] | None = None,
    use_native: bool = False,
) -> DashboardResult:
    """Compose verified services; provider execution happens only on explicit submit."""
    started = perf_counter()
    stage = progress or (lambda text: None)
    stage("Traverse dependencies and collect graph evidence")
    if use_native:
        from src.database import DatabaseError, DatabaseManager
        from src.native_queries import NativeGraphQueries

        try:
            with DatabaseManager(settings, read_only=True) as db:
                result = investigate(NativeGraphQueries(db, prepared.queries.limits), component)
            snapshot_edges = {edge_key(edge): edge for edge in prepared.queries.edges}
            if any(
                prepared.queries.nodes.get(node.id) != node for node in result.evidence_nodes
            ) or any(snapshot_edges.get(edge_key(edge)) != edge for edge in result.evidence_edges):
                result = investigate(prepared.queries, component)
                result.warnings.append(
                    "Graph changed since the cached analytics snapshot; using consistent "
                    "snapshot evidence. Refresh graph for current facts."
                )
        except DatabaseError:
            result = investigate(prepared.queries, component)
            result.warnings.append(
                "Native query unavailable; bounded Python fallback uses the displayed snapshot."
            )
    else:
        result = investigate(prepared.queries, component)
    notes = incident_text[:2000]
    for secret in (settings.gemini_api_key, settings.groq_api_key):
        if secret:
            notes = notes.replace(secret, "[redacted]")
    result.incident_input = notes
    if result.matched_component is None:
        return DashboardResult(
            investigation=result,
            analysis_scope="No matched component",
            elapsed_ms=(perf_counter() - started) * 1000,
            assumed_status=status,
        )
    regional = result.matched_component.label == "Region"
    deployments = []
    analysis = None
    report = None
    stage("Compute risk factors, bottlenecks, and candidate causes")
    if regional:
        result, deployments = regional_exposure(prepared, result.matched_component.id)
        candidates = [
            prepared.analytics.analyze(investigate(prepared.queries, row["id"]), status)
            for row in deployments
            if row["single_region"]
        ]
        analysis = (
            min(candidates, key=lambda a: (-a.risk.score, a.component.id)) if candidates else None
        )
        scope = (
            f"Worst-case single-region component failure: {analysis.component.name}"
            if analysis
            else "Regional exposure only; no single-region component score available"
        )
    elif result.matched_component.id in prepared.analytics.graph:
        analysis = prepared.analytics.analyze(result, status)
        scope = f"Component failure scenario: {result.matched_component.name}"
        stage("Validate grounded report and citations")
        report_settings = (
            settings
            if use_provider
            else settings.model_copy(update={"llm_provider": "deterministic"})
        )
        report = generate_report(
            build_evidence(prepared.queries, result, analysis), report_settings
        )
    else:
        scope = "Context entity; operational risk scoring is not applicable"
    return DashboardResult(
        investigation=result,
        analysis=analysis,
        report=report,
        regional=regional,
        analysis_scope=scope,
        regional_deployments=deployments,
        elapsed_ms=(perf_counter() - started) * 1000,
        assumed_status=status,
    )
