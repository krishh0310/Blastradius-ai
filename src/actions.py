"""Evidence gates for fictional counterfactuals; never a remediation executor."""

from src.graph_queries import EvidencePath, GraphQueries, evidence_edge_priority
from src.simulator import SimulationConfig, Simulator
from src.tooling import ActionEvidence, SimulationSummary, ToolResult
from src.topology import DEPENDENCIES, OWNED_LABELS, Topology

ACTION_LABELS = {
    "activate_declared_replica": "Activate regional replica",
    "reroute_traffic": "Reroute traffic",
    "isolate_unhealthy_dependency": "Isolate unhealthy dependency",
    "switch_to_read_only_mode": "Degraded read-only mode",
    "disable_optional_feature": "Disable optional feature",
    "execute_fictional_runbook": "Execute fictional runbook",
}


def action_options(
    graph: GraphQueries, component: str, *, status: str = "failed"
) -> list[ActionEvidence]:
    """Require original graph edges; existence is not operational readiness."""
    root = graph.nodes.get(component)
    rejected = [
        ActionEvidence(
            action=name, eligible=False, reason="No matched operational failure evidence"
        )
        for name in ACTION_LABELS
    ]
    if root is None or root.label not in OWNED_LABELS | {"Region"} or status == "healthy":
        return rejected
    simulator = Simulator(
        Topology(nodes=list(graph.nodes.values()), relationships=graph.edges),
        SimulationConfig(
            component_id=root.id, failure_status="degraded" if status == "degraded" else "down"
        ),
    )
    paths: dict[str, list[EvidencePath]] = {name: [] for name in ACTION_LABELS}
    incoming = sorted(
        [edge for edge in graph.edges if edge.target == root.id and edge.type in DEPENDENCIES],
        key=evidence_edge_priority,
    )
    for edge in incoming:
        name = "isolate_unhealthy_dependency" if edge.required else "disable_optional_feature"
        paths[name].append(graph._path([root.id, edge.source], [edge]))
    outgoing = [edge for edge in graph.edges if edge.source == root.id]
    for edge in outgoing:
        if edge.type == "HAS_RUNBOOK":
            paths["execute_fictional_runbook"].append(graph._path([root.id, edge.target], [edge]))
        elif edge.type in DEPENDENCIES and root.label in {"Service", "Database", "API"}:
            paths["switch_to_read_only_mode"].append(graph._path([root.id, edge.target], [edge]))
    statuses = {node.id: "healthy" for node in graph.nodes.values()}
    statuses[root.id] = simulator.config.failure_status
    sources = [
        edge
        for edge in graph.edges
        if root.label == "Region"
        and edge.type == "DEPLOYED_IN"
        and edge.target == root.id
        and edge.source in simulator.analytics.graph
    ]
    if root.label == "Region":
        for source in sources:
            alternate = simulator.alternate(source.source, statuses)
            if alternate:
                paths["activate_declared_replica"].append(
                    graph._path([root.id, source.source, alternate.target], [source, alternate])
                )
    else:
        alternate = simulator.alternate(root.id, statuses)
        if alternate:
            paths["activate_declared_replica"].append(
                graph._path([root.id, alternate.target], [alternate])
            )
    paths["reroute_traffic"] = list(paths["activate_declared_replica"])
    explanations = {
        "activate_declared_replica": "Declared healthy alternate exists; simulated failover assumes capacity, freshness and routing readiness.",
        "reroute_traffic": "Declared alternate route exists; routing success remains a fictional assumption.",
        "isolate_unhealthy_dependency": "Required consumer edges support fictional containment: direct consumers degrade while further propagation is contained.",
        "switch_to_read_only_mode": "Operational dependency edge exists; fictional read-only capability caps failure at degraded and is not a recorded infrastructure capability.",
        "disable_optional_feature": "Optional consumer edge exists; suppress optional propagation, without repairing required routes.",
        "execute_fictional_runbook": "HAS_RUNBOOK is recorded; successful recovery is a fictional assumption, not execution of that runbook.",
    }
    legacy = simulator.mitigation_options()
    return [
        ActionEvidence(
            action=name,
            eligible=bool(paths[name]) and legacy[label] is None,
            reason=explanations[name]
            if paths[name] and legacy[label] is None
            else legacy[label] or "Required supporting relationship is absent.",
            paths=paths[name][:60] if legacy[label] is None else [],
        )
        for name, label in ACTION_LABELS.items()
    ]


def recommend_action(options: list[ActionEvidence]) -> ActionEvidence | None:
    """Prefer a limited optional change, otherwise containment before assumed recovery."""
    eligible = {item.action: item for item in options if item.eligible}
    order = [
        "activate_declared_replica",
        "isolate_unhealthy_dependency",
        "switch_to_read_only_mode",
        "disable_optional_feature",
        "execute_fictional_runbook",
        "reroute_traffic",
    ]
    if "isolate_unhealthy_dependency" not in eligible:
        order.insert(0, "disable_optional_feature")
    return next((eligible[name] for name in order if name in eligible), None)


def simulate_action(graph: GraphQueries, args, result: ToolResult) -> ToolResult:
    """Revalidate current evidence after confirmation, replay only an in-memory copy."""
    options = action_options(graph, result.component.id, status=args.status)
    result.action_eligibility = options
    selected = next(item for item in options if item.action == args.action)
    result.paths += selected.paths
    if not args.confirmed or not selected.eligible:
        result.error = "action_rejected"
        result.warnings.append("Fictional action rejected: " + selected.reason)
        return result
    simulator = Simulator(
        Topology(nodes=list(graph.nodes.values()), relationships=graph.edges),
        SimulationConfig(
            component_id=result.component.id,
            failure_status="degraded" if args.status == "degraded" else "down",
            automatic_failover=False,
            depth=args.depth,
        ),
    )
    before = simulator.run()
    replay = simulator.mitigate(before, ACTION_LABELS[args.action])
    result.warnings += replay.warnings
    result.simulation = SimulationSummary(
        action=args.action,
        before_score=before.frames[-1].risk.score,
        before_affected_ids=before.frames[-1].affected_ids,
        after=replay.after.model_dump(
            include={"risk", "affected_ids", "statuses", "timestamp_seconds"}
        ),
        risk_reduction=replay.risk_reduction,
        removed_critical_paths=replay.removed_critical_paths,
        events=replay.events,
        explanation=f"Simulation depth {args.depth}: these scores use simulated affected entities, "
        "not the investigation's potential-exposure cohort. Before assumes no automatic failover; "
        "after is an approved fictional policy replay. " + replay.explanation,
    )
    result.warnings.append(
        "Fictional simulation only; seeded graph and real infrastructure are unchanged."
    )
    return result
