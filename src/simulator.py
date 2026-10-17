"""Deterministic, in-memory failure rehearsal. This module has no database write path."""

import argparse
import heapq
import json
from typing import Literal

from pydantic import BaseModel, Field

from src.analytics import Analytics, RiskScore
from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import (
    EvidencePath,
    GraphQueries,
    Impact,
    QueryLimits,
    edge_key,
    evidence_edge_priority,
)
from src.investigator import InvestigationResult, investigate
from src.topology import DEPENDENCIES, OWNED_LABELS, Relationship, Topology

Status = Literal["healthy", "degraded", "down"]
Action = Literal[
    "Activate regional replica",
    "Reroute traffic",
    "Isolate unhealthy dependency",
    "Degraded read-only mode",
    "Disable optional feature",
    "Execute fictional runbook",
]
ACTIONS = [
    "Activate regional replica",
    "Reroute traffic",
    "Isolate unhealthy dependency",
    "Degraded read-only mode",
    "Disable optional feature",
    "Execute fictional runbook",
]
RANK = {"healthy": 0, "degraded": 1, "down": 2}


class SimulationConfig(BaseModel):
    component_id: str
    failure_status: Literal["degraded", "down"] = "down"
    step_seconds: int = Field(default=3, ge=1, le=30)
    depth: int = Field(default=8, ge=1, le=8)
    optional_policy: Literal["degrade", "ignore"] = "degrade"
    automatic_failover: bool = True
    max_events: int = Field(default=1000, ge=1, le=5000)


class TimelineEvent(BaseModel):
    timestamp_seconds: int
    entity_id: str
    entity: str
    previous_status: Status
    new_status: Status
    cause: str
    dependency_path: EvidencePath
    supporting_edge: Relationship | None = None
    confidence: Literal["Scenario assumption", "Graph-supported simulation", "Fictional mitigation"]
    recommended_response: str


class SimulationFrame(BaseModel):
    timestamp_seconds: int
    statuses: dict[str, Status]
    affected_ids: list[str]
    event_count: int
    risk: RiskScore
    investigation: InvestigationResult


class SimulationRun(BaseModel):
    config: SimulationConfig
    frames: list[SimulationFrame]
    events: list[TimelineEvent]
    risk_subject_id: str
    risk_scope: str
    critical_paths: list[EvidencePath]
    warnings: list[str]

    @property
    def peak(self) -> SimulationFrame:
        return max(
            self.frames, key=lambda f: (f.risk.score, len(f.affected_ids), f.timestamp_seconds)
        )


class MitigationResult(BaseModel):
    action: Action
    after: SimulationFrame
    events: list[TimelineEvent]
    removed_critical_paths: list[EvidencePath]
    risk_reduction: float
    unmitigated_settled_risk: float
    explanation: str
    warnings: list[str] = Field(default_factory=list)


def evidence_path(ids: list[str], edges: list[Relationship]) -> EvidencePath:
    return EvidencePath(
        node_ids=ids,
        edges=edges,
        hops=len(edges),
        required=all(e.required for e in edges),
        criticality=min((e.criticality for e in edges), default=0),
    )


class Simulator:
    """A single fictional incident starting from an explicitly healthy demo baseline."""

    def __init__(self, topology: Topology, config: SimulationConfig):
        self.topology = topology.model_copy(deep=True)
        self.config = config
        self.queries = GraphQueries(self.topology, QueryLimits(depth=config.depth))
        self.analytics = Analytics(self.queries)
        root = self.queries.nodes.get(config.component_id)
        if root is None or root.label not in OWNED_LABELS | {"Region"}:
            raise ValueError("Select an operational component or Region from the graph")
        self.root = root
        if root.label == "Region":
            candidates = sorted(
                {
                    e.source
                    for e in self.queries.edges
                    if e.type == "DEPLOYED_IN"
                    and e.target == root.id
                    and self.queries.nodes[e.source].label in OWNED_LABELS
                }
            )
            if not candidates:
                raise ValueError("Region has no recorded operational deployments")
            self.subject = max(
                candidates,
                key=lambda node: (
                    self.analytics.risk(investigate(self.queries, node), "down").score,
                    node,
                ),
            )
            self.scope = (
                "Regional exposure envelope, scored using component "
                + self.queries.nodes[self.subject].name
                + "; not a regional probability"
            )
        else:
            self.subject = root.id
            self.scope = "Residual scenario exposure for " + root.name
        self.links: dict[str, list[tuple[str, Relationship]]] = {}
        for edge in self.queries.edges:
            if edge.type in DEPENDENCIES:
                provider, consumer = edge.target, edge.source
            elif edge.type in {"SUPPORTS", "USED_BY"}:
                provider, consumer = edge.source, edge.target
            elif edge.type == "DEPLOYED_IN" and self.queries.nodes[edge.target].label == "Region":
                provider, consumer = edge.target, edge.source
            else:
                continue
            self.links.setdefault(provider, []).append((consumer, edge))
        for adjacent in self.links.values():
            adjacent.sort(key=lambda item: (item[0], evidence_edge_priority(item[1])))

    def alternate(self, node_id: str, statuses: dict[str, Status]) -> Relationship | None:
        """Return only graph-declared, currently and originally healthy alternatives."""
        regions = [
            e
            for e in self.queries.edges
            if e.source == node_id
            and e.type == "DEPLOYED_IN"
            and statuses[e.target] == "healthy"
            and self.queries.nodes[e.target].status == "healthy"
        ]
        # A nonregional component failure is assumed local to one of its deployments.
        if len(regions) >= (1 if self.root.label == "Region" else 2):
            return regions[-1]
        for edge in self.queries.edges:
            if (
                edge.source != node_id
                or edge.type != "REPLICATES_TO"
                or statuses[edge.target] != "healthy"
                or self.queries.nodes[edge.target].status != "healthy"
            ):
                continue
            target_regions = [
                e.target
                for e in self.queries.edges
                if e.source == edge.target and e.type == "DEPLOYED_IN"
            ]
            if target_regions and any(
                statuses[r] == "healthy" and self.queries.nodes[r].status == "healthy"
                for r in target_regions
            ):
                return edge
        return None

    def mitigation_options(self) -> dict[str, str | None]:
        """None means available; otherwise explain why evidence does not permit it."""
        statuses: dict[str, Status] = {n.id: "healthy" for n in self.topology.nodes}
        statuses[self.root.id] = self.config.failure_status
        alternate = (
            any(
                self.alternate(node, statuses)
                for node in self.analytics.graph
                if any(
                    e.source == node and e.target == self.root.id and e.type == "DEPLOYED_IN"
                    for e in self.queries.edges
                )
            )
            if self.root.label == "Region"
            else self.alternate(self.root.id, statuses)
        )
        has_optional = any(
            e.target == self.root.id and e.type in DEPENDENCIES and not e.required
            for e in self.queries.edges
        )
        has_runbook = any(
            e.source == self.root.id and e.type == "HAS_RUNBOOK" for e in self.queries.edges
        )
        return {
            "Activate regional replica": None
            if alternate
            else "No healthy graph-declared alternate is available.",
            "Reroute traffic": None
            if alternate
            else "No graph-declared alternate route is available.",
            "Isolate unhealthy dependency": None,
            "Degraded read-only mode": None
            if self.root.label in {"Service", "Database", "API"}
            else "Read-only behavior is not modeled for this entity type.",
            "Disable optional feature": None
            if has_optional
            else "No optional consumer edge references this component.",
            "Execute fictional runbook": None
            if has_runbook
            else "No associated runbook is recorded.",
        }

    def _frame(
        self,
        time: int,
        statuses: dict[str, Status],
        events: list[TimelineEvent],
        paths: dict[str, EvidencePath],
    ) -> SimulationFrame:
        q = self.queries
        active = sorted(n for n, status in statuses.items() if status != "healthy")
        impacts = [
            Impact(
                component=q.nodes[n].model_copy(update={"status": statuses[n]}),
                hops=paths[n].hops,
                path=paths[n],
                required=paths[n].required,
            )
            for n in active
            if n != self.root.id and n in paths
        ]
        result = InvestigationResult(
            incident_input=self.root.id, matched_component=q.nodes[self.subject]
        )
        result.direct_impact = [i for i in impacts if i.hops == 1]
        result.cascading_impact = [i for i in impacts if i.hops > 1]
        result.impacted_customers = [i for i in impacts if i.component.label == "Customer"]
        result.impacted_workflows = [i for i in impacts if i.component.label == "BusinessFlow"]
        result.shortest_paths = [i.path for i in impacts]
        # Keep the original full graph for centrality/criticality, but score only
        # active simulated exposure using the existing normalized risk formula.
        risk = self.analytics.risk(result, statuses[self.subject])
        visual = result.model_copy(deep=True)
        visual.matched_component = q.nodes[self.root.id]
        visual.evidence_nodes = list(q.nodes.values())
        visual.evidence_edges = q.edges
        return SimulationFrame(
            timestamp_seconds=time,
            statuses=dict(sorted(statuses.items())),
            affected_ids=active,
            event_count=len(events),
            risk=risk,
            investigation=visual,
        )

    def run(self, action: Action | None = None) -> SimulationRun:
        """Build all frames once; playback changes only a cursor into this immutable plan."""
        if action is not None:
            if action not in ACTIONS:
                raise ValueError("Unknown mitigation")
            reason = self.mitigation_options()[action]
            if reason:
                raise ValueError(reason)
        cfg, q = self.config, self.queries
        statuses: dict[str, Status] = {n: "healthy" for n in sorted(q.nodes)}
        events: list[TimelineEvent] = []
        paths = {self.root.id: evidence_path([self.root.id], [])}
        frames = [self._frame(0, statuses, events, paths)]
        warnings = [
            "All initial health is a fictional healthy baseline; seeded status is never changed.",
            f"Each hop costs {cfg.step_seconds} simulated seconds; these are not measured outage timings.",
            "Declared failover assumes spare capacity and freshness for rehearsal only.",
            "Residual risk uses the original graph metrics and current simulated affected entities; "
            "structural criticality can keep the score above zero after recovery.",
        ]
        # time, priority, stable sequence, entity, requested status, evidence, cause,
        # supporting edge, terminal (bounded degradation / failover brownout)
        queue = []
        sequence = 0

        def schedule(time, priority, node, status, path, cause, edge, terminal=False):
            nonlocal sequence
            if sequence >= q.limits.max_expansions:
                message = "Simulation expansion limit reached; the cascade is incomplete."
                if message not in warnings:
                    warnings.append(message)
                return
            sequence += 1
            heapq.heappush(
                queue, (time, priority, sequence, node, status, path, cause, edge, terminal)
            )

        def propagate(time: int, node: str, state: Status, path: EvidencePath) -> None:
            if path.hops >= cfg.depth:
                if self.links.get(node):
                    warnings.append(
                        "Traversal depth reached; additional downstream exposure may exist."
                    )
                return
            for consumer, relation in self.links.get(node, []):
                if consumer in path.node_ids:
                    continue
                if not relation.required and (
                    cfg.optional_policy == "ignore" or action == "Disable optional feature"
                ):
                    continue
                desired = state if relation.required else "degraded"
                stop = action == "Isolate unhealthy dependency" and node == self.root.id
                if stop:
                    desired = "degraded"
                next_path = evidence_path(path.node_ids + [consumer], path.edges + [relation])
                schedule(
                    time + cfg.step_seconds,
                    1,
                    consumer,
                    desired,
                    next_path,
                    (
                        "Fictional circuit breaker contains downstream propagation"
                        if stop
                        else f"{q.nodes[node].name} is {state}; "
                        f"{'required' if relation.required else 'optional'} {relation.type} evidence"
                    ),
                    relation,
                    stop,
                )

        root_status: Status = (
            "healthy"
            if action == "Execute fictional runbook"
            else "degraded"
            if action == "Degraded read-only mode"
            else cfg.failure_status
        )
        schedule(
            0,
            1,
            self.root.id,
            root_status,
            paths[self.root.id],
            "Injected fictional starting-component failure",
            None,
        )
        auto_failover = cfg.automatic_failover or action in {
            "Activate regional replica",
            "Reroute traffic",
        }
        handled_failovers = set()
        current_time = 0
        while queue:
            time, priority, _, node, requested, path, cause, edge, terminal = heapq.heappop(queue)
            if time != current_time:
                frames.append(self._frame(current_time, statuses, events, paths))
                current_time = time
            if len(events) >= cfg.max_events:
                warnings.append("Event limit reached; the cascade is incomplete.")
                break
            recovery = priority == 0
            if recovery:
                # A replica cannot fix an outage in a shared required provider.
                blocked = any(
                    e.required and statuses[e.target] != "healthy" for e in q.forward[node]
                )
                if blocked:
                    warnings.append(
                        "A failover attempt was blocked by an unhealthy shared required provider."
                    )
                    propagate(time, node, statuses[node], paths[node])
                    continue
            elif path.hops:
                provider = path.node_ids[-2]
                if statuses[provider] == "healthy":
                    continue
                if statuses[provider] == "degraded":
                    requested = "degraded"
            previous = statuses[node]
            if requested == previous:
                old_path = paths.get(node)
                if not recovery and path.required and old_path and not old_path.required:
                    paths[node] = path
                    if not terminal:
                        propagate(time, node, requested, path)
                continue
            if not recovery and RANK[requested] < RANK[previous]:
                continue
            statuses[node] = requested
            paths[node] = path
            events.append(
                TimelineEvent(
                    timestamp_seconds=time,
                    entity_id=node,
                    entity=q.nodes[node].name,
                    previous_status=previous,
                    new_status=requested,
                    cause=cause,
                    dependency_path=path,
                    supporting_edge=edge,
                    confidence="Scenario assumption"
                    if edge is None
                    else "Graph-supported simulation",
                    recommended_response="Validate live health with the owner; review associated runbooks "
                    "and approve any real infrastructure change separately.",
                )
            )
            if requested == "healthy" or terminal:
                continue
            # Only regional placement failure or the injected primary failure can
            # use location failover. Dependency-caused logical failure cannot.
            placement_failure = node == self.root.id or (edge and edge.type == "DEPLOYED_IN")
            alternate = (
                self.alternate(node, statuses) if auto_failover and placement_failure else None
            )
            if alternate and node not in handled_failovers:
                handled_failovers.add(node)
                schedule(
                    time + cfg.step_seconds,
                    0,
                    node,
                    "healthy",
                    path,
                    "Fictional failover to the healthy alternate declared in the graph",
                    alternate,
                )
                continue
            propagate(time, node, requested, path)
        if events or len(frames) == 1:
            frames.append(self._frame(current_time, statuses, events, paths))
        critical = []
        for frame in frames:
            for path in frame.investigation.shortest_paths:
                if path.required and path.criticality >= 4:
                    critical.append(path)
        unique = {tuple(edge_key(e) for e in p.edges): p for p in critical}
        return SimulationRun(
            config=cfg,
            frames=frames,
            events=events,
            risk_subject_id=self.subject,
            risk_scope=self.scope,
            critical_paths=[unique[k] for k in sorted(unique)],
            warnings=sorted(set(warnings)),
        )

    def mitigate(self, run: SimulationRun, action: Action) -> MitigationResult:
        """Rehearse a fictional policy and compare residual exposure at quiescence."""
        if run.config != self.config:
            raise ValueError("Simulation configuration does not match")
        alternate = self.run(action)
        before, after = run.frames[-1], alternate.frames[-1].model_copy(deep=True)
        after.timestamp_seconds = before.timestamp_seconds + self.config.step_seconds
        changed = [n for n in sorted(before.statuses) if before.statuses[n] != after.statuses[n]]
        original_paths = {e.entity_id: e.dependency_path for e in run.events}
        alternative_paths = {e.entity_id: e.dependency_path for e in alternate.events}
        changes = []
        for node in sorted(
            changed, key=lambda n: (original_paths.get(n, evidence_path([n], [])).hops, n)
        ):
            path = (
                original_paths.get(node) or alternative_paths.get(node) or evidence_path([node], [])
            )
            supporting = path.edges[-1] if path.edges else None
            if node == self.root.id:
                if action == "Execute fictional runbook":
                    supporting = next(
                        e
                        for e in self.queries.edges
                        if e.source == node and e.type == "HAS_RUNBOOK"
                    )
                elif action in {"Activate regional replica", "Reroute traffic"}:
                    supporting = self.alternate(node, before.statuses)
                if supporting is None:
                    supporting = next(
                        (
                            e
                            for e in self.queries.edges
                            if e.source == node
                            and e.type in {"HAS_RUNBOOK", "OWNED_BY", "DEPLOYED_IN"}
                        ),
                        None,
                    )
            changes.append(
                TimelineEvent(
                    timestamp_seconds=after.timestamp_seconds,
                    entity_id=node,
                    entity=self.queries.nodes[node].name,
                    previous_status=before.statuses[node],
                    new_status=after.statuses[node],
                    cause=f"Fictional policy replay: {action}",
                    dependency_path=path,
                    supporting_edge=supporting,
                    confidence="Fictional mitigation",
                    recommended_response="This is a rehearsal assumption, not a verified recovery. "
                    "Validate capacity and obtain human approval before real action.",
                )
            )
        after.event_count = len(run.events) + len(changes)
        remaining = {
            tuple(edge_key(e) for e in p.edges)
            for p in alternate.critical_paths
            if any(after.statuses[n] != "healthy" for n in p.node_ids[1:])
        }
        removed = [
            p for p in run.critical_paths if tuple(edge_key(e) for e in p.edges) not in remaining
        ]
        return MitigationResult(
            action=action,
            after=after,
            events=changes,
            removed_critical_paths=removed,
            risk_reduction=round(before.risk.score - after.risk.score, 2),
            unmitigated_settled_risk=before.risk.score,
            warnings=sorted(set(run.warnings + alternate.warnings)),
            explanation="Counterfactual replay from the same healthy baseline. Runbook recovery assumes "
            "success; isolation assumes a graceful-degradation circuit breaker. No edge is "
            "deleted and no real action is executed. Required consumers are never bypassed "
            "merely because an optional feature is disabled.",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", default="vault", help="Exact graph component ID")
    parser.add_argument("--no-failover", action="store_true")
    parser.add_argument("--mitigation", choices=ACTIONS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        with DatabaseManager(Settings.from_env()) as database:
            q = GraphQueries.from_database(database)
        simulator = Simulator(
            Topology(nodes=list(q.nodes.values()), relationships=q.edges),
            SimulationConfig(component_id=args.component, automatic_failover=not args.no_failover),
        )
        run = simulator.run()
        mitigation = simulator.mitigate(run, args.mitigation) if args.mitigation else None
        if args.json:
            print(
                json.dumps(
                    {
                        "simulation": run.model_dump(mode="json"),
                        "mitigation": mitigation.model_dump(mode="json") if mitigation else None,
                    },
                    indent=2,
                )
            )
        else:
            print(run.risk_scope)
            for event in run.events + (mitigation.events if mitigation else []):
                print(
                    f"T+{event.timestamp_seconds:02d}s {event.entity}: {event.previous_status} "
                    f"→ {event.new_status}; {event.cause}; path={event.dependency_path.node_ids}"
                )
            print(
                f"Risk baseline={run.frames[0].risk.score}, peak={run.peak.risk.score}"
                + (f", after={mitigation.after.risk.score}" if mitigation else "")
            )
            print(
                f"Peak affected={len(run.peak.affected_ids)}"
                + (f", after={len(mitigation.after.affected_ids)}" if mitigation else "")
            )
            if mitigation:
                print(
                    f"Incremental mitigation reduction={mitigation.risk_reduction}; "
                    f"critical impact paths neutralized={len(mitigation.removed_critical_paths)}"
                )
        return 0
    except (ValueError, DatabaseError):
        print(
            "Simulation unavailable. Check graph connectivity, component ID, and mitigation eligibility."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
