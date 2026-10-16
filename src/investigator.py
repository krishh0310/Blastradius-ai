"""Deterministic incident foundation: graph facts and explicit supporting evidence."""

import argparse
from time import perf_counter

from pydantic import BaseModel, Field

from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import (
    Cycle,
    Deployment,
    EvidencePath,
    GraphQueries,
    Impact,
    Node,
    QueryLimits,
)
from src.topology import Relationship


class InvestigationResult(BaseModel):
    incident_input: str
    matched_component: Node | None = None
    suggestions: list[Node] = Field(default_factory=list)
    direct_impact: list[Impact] = Field(default_factory=list)
    cascading_impact: list[Impact] = Field(default_factory=list)
    dependencies: list[Impact] = Field(default_factory=list)
    impacted_customers: list[Impact] = Field(default_factory=list)
    impacted_workflows: list[Impact] = Field(default_factory=list)
    impacted_regions: list[Impact] = Field(default_factory=list)
    owner_teams: list[Impact] = Field(default_factory=list)
    runbooks: list[Impact] = Field(default_factory=list)
    shortest_paths: list[EvidencePath] = Field(default_factory=list)
    critical_paths: list[EvidencePath] = Field(default_factory=list)
    cycles: list[Cycle] = Field(default_factory=list)
    deployment: Deployment | None = None
    evidence_nodes: list[Node] = Field(default_factory=list)
    evidence_edges: list[Relationship] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    query_execution_ms: float = 0
    reasoning_engine: str = "bounded Python fallback"
    query_diagnostics: list[dict] = Field(default_factory=list)


def investigate(queries: GraphQueries, component: str) -> InvestigationResult:
    """Investigate hypothetical failure; recorded health remains unchanged."""
    started = perf_counter()
    queries.warnings.clear()
    lookup = queries.exact_lookup(component)
    result = InvestigationResult(
        incident_input=component,
        matched_component=lookup.matched,
        suggestions=lookup.suggestions,
        reasoning_engine=getattr(queries, "reasoning_engine", "bounded Python fallback"),
        query_diagnostics=getattr(queries, "diagnostics", []),
    )
    if lookup.matched is None:
        result.warnings.append(
            "Component not uniquely matched; select an exact ID or suggested name"
        )
        result.query_execution_ms = (perf_counter() - started) * 1000
        return result
    root = lookup.matched
    impacts = queries.blast_radius(root.id)
    result.direct_impact = queries.direct_dependents(root.id)
    result.cascading_impact = [
        i for i in impacts if i.component.id not in {d.component.id for d in result.direct_impact}
    ]
    result.dependencies = queries.dependencies(root.id)
    root_impact = Impact(
        component=root,
        hops=0,
        path=EvidencePath(node_ids=[root.id], edges=[], hops=0, required=True, criticality=0),
        required=True,
    )
    affected = [root_impact] + impacts
    result.impacted_workflows = queries.workflows(affected)
    result.impacted_customers = queries.customers(result.impacted_workflows)
    result.impacted_regions = queries.regions(affected)
    result.owner_teams = queries.teams(affected)
    result.runbooks = queries.runbooks(affected)
    result.deployment = queries.deployment(root.id)
    path_budget = queries.limits.max_paths
    for item in impacts:
        path = queries.shortest_path(root.id, item.component.id, downstream=True)
        if path:
            result.shortest_paths.append(path)
        remaining = path_budget - len(result.critical_paths)
        if remaining > 0:
            result.critical_paths.extend(
                queries.critical_paths(root.id, item.component.id)[:remaining]
            )
        else:
            queries._warn("Investigation critical-path limit reached")
    result.critical_paths.sort(key=lambda p: (-p.criticality, p.hops, p.node_ids))
    ids = {root.id} | {i.component.id for i in impacts + result.dependencies}
    result.cycles = [c for c in queries.cycles() if ids.intersection(c.node_ids)]
    claims = (
        affected
        + result.direct_impact
        + result.dependencies
        + result.impacted_workflows
        + result.impacted_customers
        + result.impacted_regions
        + result.owner_teams
        + result.runbooks
    )
    extra = [e for c in result.cycles for e in c.edges]
    extra += result.deployment.evidence_edges if result.deployment else []
    evidence = queries.evidence_subgraph(
        [i.path for i in claims] + result.shortest_paths + result.critical_paths,
        extra_edges=extra,
        node_ids=[root.id],
    )
    result.evidence_nodes, result.evidence_edges = evidence.nodes, evidence.edges
    result.warnings = sorted(
        set(
            queries.warnings
            + [
                "Impact is potential exposure inferred from dependencies, not a confirmed outage.",
                "Regions indicate deployment exposure, not a region-wide outage.",
                "Healthy regions and replica targets do not prove failover capacity or readiness.",
                "Required paths propagate required exposure; optional-only paths indicate reduced exposure.",
            ]
        )
    )
    result.query_execution_ms = (perf_counter() - started) * 1000
    result.query_diagnostics = list(getattr(queries, "diagnostics", []))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--max-paths", type=int, default=500)
    parser.add_argument("--max-nodes", type=int, default=2000)
    parser.add_argument("--max-edges", type=int, default=10000)
    parser.add_argument(
        "--json", action="store_true", help="Print the complete typed result as JSON"
    )
    args = parser.parse_args()
    started = perf_counter()
    try:
        limits = QueryLimits(
            depth=args.depth,
            max_paths=args.max_paths,
            max_nodes=args.max_nodes,
            max_edges=args.max_edges,
        )
        with DatabaseManager(Settings.from_env()) as db:
            from src.native_queries import NativeGraphQueries

            result = investigate(NativeGraphQueries(db, limits), args.component)
        result.query_execution_ms = (perf_counter() - started) * 1000
        if args.json:
            print(result.model_dump_json(indent=2))
        elif result.matched_component is None:
            print("Component not found or ambiguous.")
            print("Suggestions: " + ", ".join(n.name for n in result.suggestions))
        else:
            print(
                f"Component: {result.matched_component.name} "
                f"(recorded status: {result.matched_component.status})"
            )
            for name in [
                "direct_impact",
                "cascading_impact",
                "dependencies",
                "impacted_customers",
                "impacted_workflows",
                "impacted_regions",
                "owner_teams",
                "runbooks",
            ]:
                items = getattr(result, name)
                print(name.replace("_", " ").capitalize() + f" ({len(items)}):")
                for item in items:
                    print(
                        f"  {item.component.name}: {item.hops} hops, "
                        f"{'required' if item.required else 'optional-only'}; "
                        + " -> ".join(item.path.node_ids)
                    )
            print(
                f"Critical paths: {len(result.critical_paths)}; cycles: "
                + str([c.node_ids for c in result.cycles])
            )
            print(
                f"Evidence: {len(result.evidence_nodes)} nodes, {len(result.evidence_edges)} edges"
            )
            print(f"Query and investigation time: {result.query_execution_ms:.2f} ms")
            for warning in result.warnings:
                print("Warning: " + warning)
        return 0 if result.matched_component else 2
    except (DatabaseError, ValueError) as exc:
        print(f"Investigation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
