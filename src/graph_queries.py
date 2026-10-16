"""Typed, bounded operations over a snapshot read exclusively from FalkorDB."""

from collections import defaultdict, deque
from difflib import SequenceMatcher
from typing import Literal

import networkx as nx
from pydantic import BaseModel, Field

from src.database import DatabaseManager
from src.topology import DEPENDENCIES, Node, Relationship, Topology, integrity


class QueryLimits(BaseModel):
    """Hard bounds prevent incomplete snapshots and unbounded path enumeration."""

    depth: int = Field(default=6, ge=1, le=8)
    max_nodes: int = Field(default=2000, ge=1, le=2000)
    max_edges: int = Field(default=10000, ge=1, le=10000)
    max_paths: int = Field(default=500, ge=1, le=500)
    max_expansions: int = Field(default=20000, ge=1, le=20000)
    search_limit: int = Field(default=5, ge=1, le=100)


class Lookup(BaseModel):
    matched: Node | None = None
    suggestions: list[Node] = Field(default_factory=list)


class EvidencePath(BaseModel):
    """Edges retain stored direction even when traversed in reverse for impact."""

    node_ids: list[str]
    edges: list[Relationship]
    hops: int
    required: bool
    criticality: int


class Impact(BaseModel):
    component: Node
    hops: int
    path: EvidencePath
    required: bool


class Deployment(BaseModel):
    component: Node
    regions: list[Node]
    healthy_regions: list[Node]
    replica_targets: list[Node]
    evidence_edges: list[Relationship]


class EvidenceSubgraph(BaseModel):
    nodes: list[Node]
    edges: list[Relationship]


class Cycle(BaseModel):
    """A strongly connected dependency group, with all its internal edges."""

    node_ids: list[str]
    edges: list[Relationship]


def edge_key(edge: Relationship) -> tuple[str, str, str]:
    return edge.source, edge.type, edge.target


def evidence_edge_priority(edge: Relationship) -> tuple:
    """Required, critical, unhealthy edges first; identity resolves remaining ties."""
    health = {"down": 3, "failed": 3, "unhealthy": 2, "degraded": 1}
    return (
        not edge.required,
        -edge.criticality,
        -health.get(edge.status, 0),
        edge.type,
        edge.source,
        edge.target,
    )


class GraphQueries:
    """One bounded snapshot; no file data or inferred infrastructure facts."""

    def __init__(self, topology: Topology, limits: QueryLimits | None = None) -> None:
        self.limits = limits or QueryLimits()
        topology = Topology.model_validate(topology.model_dump())
        if (
            len(topology.nodes) > self.limits.max_nodes
            or len(topology.relationships) > self.limits.max_edges
        ):
            raise ValueError("Graph exceeds snapshot limits; increase limits explicitly")
        errors = integrity(topology)["errors"]
        if errors:
            raise ValueError("Graph integrity failed: " + "; ".join(errors))
        self.nodes = {n.id: n for n in topology.nodes}
        self.edges = sorted(topology.relationships, key=edge_key)
        self.warnings: list[str] = []
        self.forward: dict[str, list[Relationship]] = defaultdict(list)
        self.reverse: dict[str, list[Relationship]] = defaultdict(list)
        for edge in self.edges:
            if edge.type in DEPENDENCIES:
                self.forward[edge.source].append(edge)
                self.reverse[edge.target].append(edge)
        for adjacent in self.forward.values():
            adjacent.sort(key=lambda e: (e.target, evidence_edge_priority(e)))
        for adjacent in self.reverse.values():
            adjacent.sort(key=lambda e: (e.source, evidence_edge_priority(e)))

    @classmethod
    def from_database(
        cls, db: DatabaseManager, limits: QueryLimits | None = None
    ) -> "GraphQueries":
        """Fetch bounded, parameterized rows; reject overflow rather than omit facts."""
        limits = limits or QueryLimits()
        node_rows = db.execute_query(
            "MATCH (n:Component) RETURN [l IN labels(n) WHERE l <> 'Component'], "
            "properties(n) ORDER BY n.id LIMIT $limit",
            {"limit": limits.max_nodes + 1},
        )
        if len(node_rows) > limits.max_nodes:
            raise ValueError("Graph exceeds snapshot limits; increase limits explicitly")
        edge_rows = db.execute_query(
            "MATCH (a:Component)-[r]->(b:Component) "
            "RETURN a.id, b.id, type(r), properties(r) "
            "ORDER BY a.id, type(r), b.id LIMIT $limit",
            {"limit": limits.max_edges + 1},
        )
        if len(node_rows) > limits.max_nodes or len(edge_rows) > limits.max_edges:
            raise ValueError("Graph exceeds snapshot limits; increase limits explicitly")
        if any(len(labels) != 1 for labels, _ in node_rows):
            raise ValueError("Each Component must have exactly one domain label")
        topology = Topology(
            nodes=[dict(props, label=labels[0]) for labels, props in node_rows],
            relationships=[
                dict(props, source=a, target=b, type=kind) for a, b, kind, props in edge_rows
            ],
        )
        return cls(topology, limits)

    def exact_lookup(self, value: str) -> Lookup:
        """Match IDs first, then case-insensitive full names; never guess a match."""
        if len(value) > 512:
            raise ValueError("Component lookup must not exceed 512 characters")
        value = value.strip()
        if value in self.nodes:
            return Lookup(matched=self.nodes[value])

        def canonical(name: str) -> str:
            return " ".join(
                "database" if word == "db" else word for word in name.casefold().split()
            )

        matches = [n for n in self.nodes.values() if canonical(n.name) == canonical(value)]
        if len(matches) == 1:
            return Lookup(matched=matches[0])
        return Lookup(suggestions=sorted(matches, key=lambda n: n.id) or self.suggestions(value))

    def search(self, text: str) -> list[Node]:
        if len(text) > 512:
            raise ValueError("Component search must not exceed 512 characters")
        text = text.strip().casefold()
        if not text:
            return []
        return sorted(
            (
                n
                for n in self.nodes.values()
                if text in n.name.casefold() or text in n.id.casefold()
            ),
            key=lambda n: n.id,
        )[: self.limits.search_limit]

    def suggestions(self, text: str) -> list[Node]:
        if len(text) > 512:
            raise ValueError("Component search must not exceed 512 characters")
        text = text.strip().casefold()
        if not text:
            return []
        scored = [
            (
                max(
                    SequenceMatcher(None, text, n.name.casefold()).ratio(),
                    SequenceMatcher(None, text, n.id.casefold()).ratio(),
                ),
                n,
            )
            for n in self.nodes.values()
        ]
        return [
            n
            for score, n in sorted(scored, key=lambda item: (-item[0], item[1].id))
            if score >= 0.45
        ][: self.limits.search_limit]

    def _depth(self, depth: int | None) -> int:
        depth = self.limits.depth if depth is None else depth
        if not 1 <= depth <= 8:
            raise ValueError("Traversal depth must be between 1 and 8")
        return depth

    def _path(self, ids: list[str], edges: list[Relationship]) -> EvidencePath:
        return EvidencePath(
            node_ids=ids,
            edges=edges,
            hops=len(edges),
            required=all(e.required for e in edges),
            criticality=min((e.criticality for e in edges), default=0),
        )

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def traverse(
        self,
        component_id: str,
        direction: Literal["upstream", "downstream"],
        depth: int | None = None,
    ) -> list[Impact]:
        """Return shortest evidence per node and required-path reachability."""
        depth = self._depth(depth)
        if component_id not in self.nodes:
            return []
        # Keep a shortest path for each required/optional state. A longer required
        # route must not be hidden by a shorter optional route.
        queue = deque([(component_id, [component_id], [], True)])
        seen = {(component_id, True)}
        impacts: dict[str, list[EvidencePath]] = defaultdict(list)
        expansions = 0
        while queue:
            current, ids, edges, required = queue.popleft()
            if len(edges) >= depth:
                continue
            adjacent = self.forward[current] if direction == "upstream" else self.reverse[current]
            for edge in adjacent:
                expansions += 1
                if expansions > self.limits.max_expansions:
                    self._warn(
                        "Traversal expansion limit reached; impact results may be incomplete"
                    )
                    queue.clear()
                    break
                target = edge.target if direction == "upstream" else edge.source
                state = required and edge.required
                if target in ids or (target, state) in seen:
                    continue
                seen.add((target, state))
                path = self._path(ids + [target], edges + [edge])
                impacts[target].append(path)
                queue.append((target, path.node_ids, path.edges, state))
        results = []
        for target, paths in impacts.items():
            # Prefer required evidence if available; hops describe that exact path.
            path = min(paths, key=lambda p: (not p.required, p.hops, p.node_ids))
            results.append(
                Impact(
                    component=self.nodes[target], hops=path.hops, path=path, required=path.required
                )
            )
        return sorted(results, key=lambda i: (i.hops, i.component.id))

    def dependencies(self, component_id: str, depth: int | None = None) -> list[Impact]:
        return self.traverse(component_id, "upstream", depth)

    def blast_radius(self, component_id: str, depth: int | None = None) -> list[Impact]:
        return self.traverse(component_id, "downstream", depth)

    def direct_dependencies(self, component_id: str) -> list[Impact]:
        return self.dependencies(component_id, 1)

    def direct_dependents(self, component_id: str) -> list[Impact]:
        return self.blast_radius(component_id, 1)

    def paths(
        self,
        source: str,
        target: str,
        *,
        downstream: bool = False,
        required_only: bool = False,
        min_criticality: int = 1,
        depth: int | None = None,
    ) -> list[EvidencePath]:
        """Enumerate bounded simple paths, preserving parallel relationship types."""
        depth = self._depth(depth)
        if not 1 <= min_criticality <= 5:
            raise ValueError("Criticality must be between 1 and 5")
        if source not in self.nodes or target not in self.nodes:
            return []
        queue = deque([(source, [source], [])])
        results = []
        expansions = 0
        while queue:
            current, ids, edges = queue.popleft()
            if current == target:
                results.append(self._path(ids, edges))
                if len(results) >= self.limits.max_paths:
                    self._warn("Path limit reached; additional paths may exist")
                    break
                continue
            if len(edges) >= depth:
                continue
            for edge in self.reverse[current] if downstream else self.forward[current]:
                expansions += 1
                if expansions > self.limits.max_expansions:
                    self._warn("Path expansion limit reached; additional paths may exist")
                    return results
                node = edge.source if downstream else edge.target
                if (
                    node in ids
                    or (required_only and not edge.required)
                    or edge.criticality < min_criticality
                ):
                    continue
                queue.append((node, ids + [node], edges + [edge]))
        return results

    def impact_paths(
        self, failed: str, affected: str, depth: int | None = None
    ) -> list[EvidencePath]:
        """All simple downstream evidence paths within depth and resource limits."""
        return self.paths(failed, affected, downstream=True, depth=depth)

    def shortest_path(
        self, source: str, target: str, *, downstream: bool = False
    ) -> EvidencePath | None:
        """Shortest dependency path within configured depth, with deterministic ties."""
        if source not in self.nodes or target not in self.nodes:
            return None
        queue = deque([(source, [source], [])])
        visited = {source}
        expansions = 0
        while queue:
            current, ids, edges = queue.popleft()
            if current == target:
                return self._path(ids, edges)
            if len(edges) >= self.limits.depth:
                continue
            adjacent = self.reverse[current] if downstream else self.forward[current]
            for edge in sorted(
                adjacent,
                key=lambda e: (e.source if downstream else e.target, evidence_edge_priority(e)),
            ):
                expansions += 1
                if expansions > self.limits.max_expansions:
                    self._warn("Path expansion limit reached; additional paths may exist")
                    return None
                node = edge.source if downstream else edge.target
                if node not in visited:
                    visited.add(node)
                    queue.append((node, ids + [node], edges + [edge]))
        return None

    def critical_paths(
        self, source: str, target: str, *, downstream: bool = True, min_criticality: int = 4
    ) -> list[EvidencePath]:
        return sorted(
            self.paths(
                source,
                target,
                downstream=downstream,
                required_only=True,
                min_criticality=min_criticality,
            ),
            key=lambda p: (-p.criticality, p.hops, p.node_ids),
        )

    def context(
        self, impacts: list[Impact], relationship: str, label: str, *, incoming: bool = False
    ) -> list[Impact]:
        """Extend dependency evidence with a typed context edge."""
        found: dict[str, Impact] = {}
        for impact in impacts:
            for edge in self.edges:
                start, end = (edge.target, edge.source) if incoming else (edge.source, edge.target)
                if (
                    edge.type != relationship
                    or start != impact.component.id
                    or self.nodes[end].label != label
                ):
                    continue
                if end in impact.path.node_ids:
                    continue
                path = self._path(impact.path.node_ids + [end], impact.path.edges + [edge])
                item = Impact(
                    component=self.nodes[end], hops=path.hops, path=path, required=path.required
                )
                previous = found.get(end)
                if previous is None or (not item.required, item.hops, item.path.node_ids) < (
                    not previous.required,
                    previous.hops,
                    previous.path.node_ids,
                ):
                    found[end] = item
        return sorted(found.values(), key=lambda i: (i.hops, i.component.id))

    def workflows(self, impacts: list[Impact]) -> list[Impact]:
        candidates = [i for i in impacts if i.component.label == "BusinessFlow"]
        candidates += self.context(impacts, "SUPPORTS", "BusinessFlow")
        candidates += self.context(impacts, "DEPENDS_ON", "BusinessFlow", incoming=True)
        candidates.sort(key=lambda i: (not i.required, i.hops, i.path.node_ids))
        return sorted(
            {i.component.id: i for i in reversed(candidates)}.values(),
            key=lambda i: (i.hops, i.component.id),
        )

    def customers(self, workflows: list[Impact]) -> list[Impact]:
        return self.context(workflows, "USED_BY", "Customer")

    def regions(self, impacts: list[Impact]) -> list[Impact]:
        return self.context(impacts, "DEPLOYED_IN", "Region")

    def teams(self, impacts: list[Impact]) -> list[Impact]:
        return self.context(impacts, "OWNED_BY", "Team")

    def runbooks(self, impacts: list[Impact]) -> list[Impact]:
        return self.context(impacts, "HAS_RUNBOOK", "Runbook")

    def deployment(self, component_id: str) -> Deployment | None:
        if component_id not in self.nodes:
            return None
        edges = [
            e
            for e in self.edges
            if e.source == component_id and e.type in {"DEPLOYED_IN", "REPLICATES_TO"}
        ]
        regions = sorted(
            (self.nodes[e.target] for e in edges if e.type == "DEPLOYED_IN"), key=lambda n: n.id
        )
        replicas = sorted(
            (self.nodes[e.target] for e in edges if e.type == "REPLICATES_TO"), key=lambda n: n.id
        )
        return Deployment(
            component=self.nodes[component_id],
            regions=regions,
            healthy_regions=[n for n in regions if n.status == "healthy"],
            replica_targets=replicas,
            evidence_edges=edges,
        )

    def cycles(self) -> list[Cycle]:
        graph = nx.DiGraph()
        graph.add_edges_from((e.source, e.target) for e in self.edges if e.type in DEPENDENCIES)
        cycles = []
        for group in nx.strongly_connected_components(graph):
            if len(group) > 1 or any(graph.has_edge(n, n) for n in group):
                cycles.append(
                    Cycle(
                        node_ids=sorted(group),
                        edges=[
                            e
                            for e in self.edges
                            if e.type in DEPENDENCIES and e.source in group and e.target in group
                        ],
                    )
                )
        return sorted(cycles, key=lambda c: c.node_ids)

    def health(self, component_id: str) -> Node | None:
        return self.nodes.get(component_id)

    def evidence_subgraph(
        self,
        paths: list[EvidencePath],
        extra_edges: list[Relationship] | None = None,
        node_ids: list[str] | None = None,
    ) -> EvidenceSubgraph:
        edges = {edge_key(e): e for p in paths for e in p.edges}
        edges.update({edge_key(e): e for e in extra_edges or []})
        ids = set(node_ids or []) | {n for p in paths for n in p.node_ids}
        ids.update(n for e in edges.values() for n in (e.source, e.target))
        return EvidenceSubgraph(
            nodes=[self.nodes[n] for n in sorted(ids)], edges=[edges[k] for k in sorted(edges)]
        )
