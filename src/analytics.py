"""Deterministic dependency analytics and explicitly heuristic incident scoring."""

import argparse
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field

from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import Cycle, EvidencePath, GraphQueries, Impact, evidence_edge_priority
from src.investigator import InvestigationResult, investigate
from src.topology import OWNED_LABELS, Node, Relationship

Severity = Literal["Low", "Medium", "High", "Critical"]
Confidence = Literal["Confirmed", "Strong candidate", "Possible candidate", "Insufficient evidence"]
HEALTH = {"healthy": 0.0, "degraded": 0.5, "unhealthy": 0.8, "failed": 1.0, "down": 1.0}


def severity(score: float) -> Severity:
    """Map the final 0–100 score to the documented severity boundaries."""
    if not 0 <= score <= 100:
        raise ValueError("Risk score must be between 0 and 100")
    return "Low" if score < 25 else "Medium" if score < 50 else "High" if score < 75 else "Critical"


class Factor(BaseModel):
    name: str
    normalized: float = Field(ge=0, le=1)
    weight: float
    points: float
    explanation: str


class Metrics(BaseModel):
    component_id: str
    degree_centrality: float
    in_degree: int
    out_degree: int
    betweenness: float
    pagerank: float
    articulation_point: bool
    required_dependents: int
    optional_only_dependents: int
    single_point_of_failure: bool
    explanation: str


class Resilience(BaseModel):
    healthy_deployment_regions: list[str]
    healthy_replica_ids: list[str]
    alternate_count: int
    reduction: float
    evidence_edges: list[Relationship]
    explanation: str


class RiskScore(BaseModel):
    score: float = Field(ge=0, le=100)
    severity: Severity
    health_assumption: str
    factors: list[Factor]
    resilience: Resilience
    explanation: str


class RootCauseCandidate(BaseModel):
    component: Node
    score: float
    confidence: Confidence
    factors: list[Factor]
    supporting_path: EvidencePath
    historical_incident_ids: list[str]
    explanation: str


class RankedPath(BaseModel):
    path: EvidencePath
    score: float = Field(ge=0, le=1)
    explanation: str


class ComponentAnalysis(BaseModel):
    component: Node
    metrics: Metrics
    risk: RiskScore
    root_causes: list[RootCauseCandidate]
    critical_paths: list[EvidencePath]
    critical_path_rankings: list[RankedPath]
    strongly_connected_components: list[list[str]]
    cycles: list[Cycle]
    warnings: list[str]


class Analytics:
    """Reuse one FalkorDB-derived graph and one set of NetworkX centralities."""

    def __init__(self, queries: GraphQueries) -> None:
        self.queries = queries
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(
            sorted(n.id for n in queries.nodes.values() if n.label in OWNED_LABELS)
        )
        self.graph.add_edges_from(
            (e.source, e.target)
            for e in queries.edges
            if e.type
            in {"DEPENDS_ON", "CALLS", "READS_FROM", "WRITES_TO", "PUBLISHES_TO", "CONSUMES_FROM"}
            and e.source in self.graph
            and e.target in self.graph
        )
        self.degree = nx.degree_centrality(self.graph)
        self.between = nx.betweenness_centrality(self.graph, normalized=True)
        self.page = nx.pagerank(self.graph, alpha=0.85, tol=1e-10, max_iter=500)
        self.articulations = set(nx.articulation_points(self.graph.to_undirected()))
        self.strongly_connected_components = sorted(
            [sorted(group) for group in nx.strongly_connected_components(self.graph)]
        )

    def shortest_path(self, source: str, target: str) -> EvidencePath | None:
        """NetworkX directed unweighted shortest path, with graph-edge evidence."""
        try:
            ids = nx.shortest_path(self.graph, source, target)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None
        if len(ids) - 1 > self.queries.limits.depth:
            return None
        edges = [
            min((e for e in self.queries.forward[a] if e.target == b), key=evidence_edge_priority)
            for a, b in zip(ids, ids[1:])
        ]
        return EvidencePath(
            node_ids=ids,
            edges=edges,
            hops=len(edges),
            required=all(e.required for e in edges),
            criticality=min((e.criticality for e in edges), default=0),
        )

    def resilience(self, component_id: str) -> Resilience:
        deployment = self.queries.deployment(component_id)
        regions = sorted(n.id for n in deployment.healthy_regions)
        replicas = sorted(n.id for n in deployment.replica_targets if n.status == "healthy")
        alternate_count = max(0, len(regions) - 1) + len(replicas)
        return Resilience(
            healthy_deployment_regions=regions,
            healthy_replica_ids=replicas,
            alternate_count=alternate_count,
            reduction=min(15, 7.5 * alternate_count),
            evidence_edges=deployment.evidence_edges,
            explanation="7.5 points per declared healthy alternate, capped at 15. "
            "Deployment metadata does not confirm automatic failover or spare capacity.",
        )

    def metrics(self, component_id: str) -> Metrics:
        if component_id not in self.graph:
            raise ValueError("Analytics requires a Service, Database, Queue, or API")
        impacts = [
            i for i in self.queries.blast_radius(component_id) if i.component.id in self.graph
        ]
        required = sum(i.required for i in impacts)
        resilience = self.resilience(component_id)
        spof = required >= 2 and resilience.alternate_count == 0
        return Metrics(
            component_id=component_id,
            degree_centrality=self.degree[component_id],
            in_degree=self.graph.in_degree(component_id),
            out_degree=self.graph.out_degree(component_id),
            betweenness=self.between[component_id],
            pagerank=self.page[component_id],
            articulation_point=component_id in self.articulations,
            required_dependents=required,
            optional_only_dependents=len(impacts) - required,
            single_point_of_failure=spof,
            explanation="Candidate single point of failure: at least two required downstream "
            "components and no declared healthy alternate. Articulation uses the "
            "undirected operational dependency projection, excluding context edges.",
        )

    def risk(self, result: InvestigationResult, status: str | None = None) -> RiskScore:
        if result.matched_component is None:
            raise ValueError("Risk scoring requires a matched component")
        root = result.matched_component
        metrics = self.metrics(root.id)
        impacts = result.direct_impact + result.cascading_impact
        operational = [i for i in impacts if i.component.id in self.graph]

        def exposure(items: list[Impact]) -> float:
            return sum(1 if i.required else 0.25 for i in items)

        customer_count = sum(n.label == "Customer" for n in self.queries.nodes.values())
        flow_count = sum(n.label == "BusinessFlow" for n in self.queries.nodes.values())
        required_share = (
            sum(i.required for i in operational) / len(operational) if operational else 0
        )
        health_status = status or root.status
        if status is not None and status not in HEALTH:
            raise ValueError("Unsupported health assumption")
        incoming_criticality = max(
            (e.criticality for e in self.queries.reverse[root.id]), default=root.criticality
        )
        values = [
            (
                "blast_radius",
                min(1, exposure(operational) / 10),
                20,
                "Weighted operational dependents / 10, saturated at 1; optional-only weight 0.25.",
            ),
            (
                "customer_impact",
                exposure(result.impacted_customers) / max(1, customer_count),
                20,
                "Weighted impacted customers / all graph customers.",
            ),
            (
                "workflow_impact",
                exposure(result.impacted_workflows) / max(1, flow_count),
                15,
                "Weighted impacted workflows / all graph workflows.",
            ),
            (
                "dependency_criticality",
                (root.criticality + incoming_criticality) / 10,
                15,
                "Mean of component and strongest incoming dependency criticality, divided by 5.",
            ),
            (
                "betweenness",
                metrics.betweenness / max(max(self.between.values(), default=0), 1e-12),
                10,
                "Directed normalized betweenness / largest value in this graph.",
            ),
            (
                "articulation",
                float(metrics.articulation_point),
                5,
                "1 for an articulation point in the operational undirected projection.",
            ),
            (
                "required_dependencies",
                required_share,
                5,
                "Fraction of reachable operational dependents with an all-required path.",
            ),
            (
                "health",
                HEALTH.get(health_status, 0.5),
                10,
                "healthy=0, degraded=0.5, unhealthy=0.8, failed/down=1; unknown=0.5.",
            ),
        ]
        factors = [
            Factor(
                name=name,
                normalized=value,
                weight=weight,
                points=round(value * weight, 6),
                explanation=explanation,
            )
            for name, value, weight, explanation in values
        ]
        resilience = self.resilience(root.id)
        score = round(max(0, min(100, sum(f.points for f in factors) - resilience.reduction)), 2)
        return RiskScore(
            score=score,
            severity=severity(score),
            health_assumption=health_status,
            factors=factors,
            resilience=resilience,
            explanation="Heuristic exposure score, not an outage probability. "
            "Sum factor points, subtract resilience reduction, clamp 0–100.",
        )

    def root_causes(self, symptom_id: str) -> list[RootCauseCandidate]:
        """Rank upstream candidates without treating correlated incidents as causation."""
        if symptom_id not in self.graph:
            return []
        candidates = [symptom_id] + [
            i.component.id
            for i in self.queries.dependencies(symptom_id)
            if i.component.id in self.graph
        ]
        ranked = []
        for component_id in sorted(set(candidates)):
            node = self.queries.nodes[component_id]
            path = self.shortest_path(symptom_id, component_id)
            if path is None:
                continue
            metrics = self.metrics(component_id)
            deployment = self.queries.deployment(component_id)
            regions = deployment.regions
            unhealthy_region = sum(n.status != "healthy" for n in regions) / max(1, len(regions))
            incidents = sorted(
                e.source
                for e in self.queries.edges
                if e.type == "AFFECTS"
                and e.target == component_id
                and self.queries.nodes[e.source].label == "Incident"
            )
            values = [
                ("unhealthy_status", HEALTH.get(node.status, 0.5), 30),
                ("affected_dependents", min(1, metrics.required_dependents / 10), 15),
                ("symptom_distance", 1 / (path.hops + 1), 10),
                (
                    "edge_criticality",
                    path.criticality / 5 if path.edges else node.criticality / 5,
                    10,
                ),
                ("required_path", float(path.required), 10),
                (
                    "betweenness",
                    metrics.betweenness / max(max(self.between.values(), default=0), 1e-12),
                    10,
                ),
                ("articulation", float(metrics.articulation_point), 5),
                ("region_health", unhealthy_region, 5),
                ("incident_evidence", float(bool(incidents)), 5),
            ]
            factors = [
                Factor(
                    name=name,
                    normalized=value,
                    weight=weight,
                    points=round(value * weight, 6),
                    explanation=f"{name}: {value:.4f} × {weight}",
                )
                for name, value, weight in values
            ]
            score = round(sum(f.points for f in factors), 2)
            unhealthy = (
                node.status in {"degraded", "unhealthy", "failed", "down"} or unhealthy_region > 0
            )
            confidence: Confidence = (
                "Strong candidate"
                if unhealthy and path.required and score >= 45
                else "Possible candidate"
                if unhealthy or incidents
                else "Insufficient evidence"
            )
            ranked.append(
                RootCauseCandidate(
                    component=node,
                    score=score,
                    confidence=confidence,
                    factors=factors,
                    supporting_path=path,
                    historical_incident_ids=incidents,
                    explanation="Reachable upstream or symptom itself; health and topology are "
                    "correlated evidence, not proof of causation. AFFECTS records an "
                    "incident association; timestamp/history and causal attribution may be unknown.",
                )
            )
        return sorted(ranked, key=lambda c: (-c.score, c.component.id))

    def analyze(self, result: InvestigationResult, status: str | None = None) -> ComponentAnalysis:
        if result.matched_component is None:
            raise ValueError("Component not found")
        component = result.matched_component
        rankings = []
        for path in result.critical_paths:
            average = sum(e.criticality for e in path.edges) / max(1, path.hops) / 5
            score = round(0.6 * path.criticality / 5 + 0.3 * average + 0.1 / (path.hops + 1), 6)
            rankings.append(
                RankedPath(
                    path=path,
                    score=score,
                    explanation="Required paths: 60% weakest-edge criticality/5, "
                    "30% mean criticality/5, 10% inverse (hops+1).",
                )
            )
        rankings.sort(key=lambda p: (-p.score, p.path.node_ids, [e.type for e in p.path.edges]))
        return ComponentAnalysis(
            component=component,
            metrics=self.metrics(component.id),
            risk=self.risk(result, status),
            root_causes=self.root_causes(component.id),
            critical_paths=result.critical_paths,
            critical_path_rankings=rankings,
            strongly_connected_components=self.strongly_connected_components,
            cycles=result.cycles,
            warnings=result.warnings,
        )

    def highest_risk(self, limit: int = 5) -> list[ComponentAnalysis]:
        """Rank complete-graph components under the same explicit failure scenario."""
        if not 1 <= limit <= len(self.graph):
            raise ValueError("Limit must be between 1 and the operational node count")
        results = [
            self.analyze(investigate(self.queries, node), "failed") for node in sorted(self.graph)
        ]
        return sorted(results, key=lambda a: (-a.risk.score, a.component.id))[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", default="Token Vault")
    parser.add_argument("--status", choices=sorted(HEALTH))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        with DatabaseManager(Settings.from_env(), read_only=True) as db:
            queries = GraphQueries.from_database(db)
        analytics = Analytics(queries)
        top = analytics.highest_risk(min(5, len(analytics.graph)))
        result = analytics.analyze(investigate(queries, args.component), args.status)
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print("Five highest-risk components (hypothetical failed status):")
            for item in top:
                print(
                    f"  {item.component.name}: {item.risk.score} {item.risk.severity}; "
                    f"candidate SPOF={item.metrics.single_point_of_failure}"
                )
            print(
                f"Analysis: {result.component.name}; status assumption={result.risk.health_assumption}"
            )
            print(f"Risk: {result.risk.score} {result.risk.severity}")
            for factor in result.risk.factors:
                print(
                    f"  {factor.name}: {factor.normalized:.4f} × {factor.weight} = {factor.points}"
                )
            print(f"  resilience reduction: -{result.risk.resilience.reduction}")
            print(f"Cycles: {[c.node_ids for c in result.cycles]}")
            for candidate in result.root_causes[:5]:
                print(
                    f"  Cause candidate: {candidate.component.name}, {candidate.score}, "
                    f"{candidate.confidence}; path={candidate.supporting_path.node_ids}"
                )
        return 0
    except (DatabaseError, ValueError, nx.NetworkXException) as exc:
        print(f"Analytics failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
