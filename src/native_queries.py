"""Incident-specific Cypher retrieval; no full-graph export for path reasoning."""

from collections import defaultdict
from difflib import SequenceMatcher
from time import perf_counter

from src.database import DatabaseManager
from src.graph_queries import (
    EvidencePath,
    GraphQueries,
    Impact,
    Lookup,
    QueryLimits,
    edge_key,
    evidence_edge_priority,
)
from src.topology import DEPENDENCIES, Node, Relationship, Topology

DEPENDENCY_TYPES = "|".join(sorted(DEPENDENCIES))
SIMPLE_PATH = "all(n IN nodes(p) WHERE single(m IN nodes(p) WHERE m.id = n.id))"


class NativeGraphQueries(GraphQueries):
    """Typed query adapter sharing result semantics, not snapshot traversal."""

    reasoning_engine = "FalkorDB Cypher"

    def __init__(self, db: DatabaseManager, limits: QueryLimits | None = None):
        super().__init__(Topology(nodes=[], relationships=[]), limits)
        self.db = db
        self.diagnostics: list[dict] = []
        self._identities: dict[str, int] = {}
        self._edge_identities: dict[tuple, int] = {}
        self._path_cache: dict[tuple, list[EvidencePath]] = {}

    def _depth(self, depth: int | None) -> int:
        value = self.limits.depth if depth is None else depth
        if type(value) is not int or value not in range(1, 9):
            raise ValueError("Traversal depth must be an integer from 1 to 8")
        return value

    def _node(self, raw) -> Node:
        labels = [label for label in raw.labels if label != "Component"]
        if len(labels) != 1:
            raise ValueError("Component must have exactly one domain label")
        node = Node.model_validate(dict(raw.properties, label=labels[0]))
        if node.id in self._identities and self._identities[node.id] != raw.id:
            raise ValueError("Duplicate component ID in native evidence")
        self._identities[node.id] = raw.id
        self.nodes[node.id] = node
        if len(self.nodes) > self.limits.max_nodes:
            raise ValueError("Native evidence exceeds node limit")
        return node

    def _decode(self, raw) -> EvidencePath:
        raw_nodes = raw.nodes()
        nodes = [self._node(node) for node in raw_nodes]
        ids = {raw.id: node.id for raw, node in zip(raw_nodes, nodes)}
        edges = [
            Relationship.model_validate(
                dict(
                    edge.properties,
                    source=ids[edge.src_node],
                    target=ids[edge.dest_node],
                    type=edge.relation,
                )
            )
            for edge in raw.edges()
        ]
        known = {edge_key(edge): edge for edge in self.edges}
        for edge, raw_edge in zip(edges, raw.edges()):
            key = edge_key(edge)
            if key in self._edge_identities and self._edge_identities[key] != raw_edge.id:
                raise ValueError("Duplicate relationship identity in native evidence")
            self._edge_identities[key] = raw_edge.id
            if key in known and known[key] != edge:
                raise ValueError("Conflicting duplicate relationship evidence")
            known[key] = edge
        if len(known) > self.limits.max_edges:
            raise ValueError("Native evidence exceeds relationship limit")
        self.edges = sorted(known.values(), key=edge_key)
        self.forward, self.reverse = defaultdict(list), defaultdict(list)
        for edge in self.edges:
            if edge.type in DEPENDENCIES:
                self.forward[edge.source].append(edge)
                self.reverse[edge.target].append(edge)
        return self._path([node.id for node in nodes], edges)

    def _query(self, name: str, cypher: str, parameters: dict) -> list:
        started = perf_counter()
        rows = self.db.execute_query(cypher, parameters)
        if name == "component_lookup" and len(rows) > 1:
            raise ValueError("Duplicate component ID in native evidence")
        truncated = len(rows) > self.limits.max_paths
        if truncated:
            self._warn(f"{name}: result limit reached; evidence may be incomplete")
        self.diagnostics.append(
            {
                "name": name,
                "cypher": cypher,
                "parameters": {key: value for key, value in parameters.items() if key != "lookup"},
                "elapsed_ms": round((perf_counter() - started) * 1000, 3),
                "rows_returned": len(rows),
                "truncated": truncated,
            }
        )
        return rows[: self.limits.max_paths]

    def exact_lookup(self, value: str) -> Lookup:
        if len(value) > 512:
            raise ValueError("Component lookup must not exceed 512 characters")
        # IDs take precedence; canonical names mirror the existing DB abbreviation.
        rows = self._query(
            "component_lookup",
            "MATCH (n:Component) WHERE n.id = $lookup RETURN n LIMIT $limit",
            {"lookup": value.strip(), "limit": 2},
        )
        if not rows:
            canonical = " ".join("database" if w == "db" else w for w in value.casefold().split())
            rows = self._query(
                "component_name",
                "MATCH (n:Component) "
                "WHERE toLower(n.name) = $lookup RETURN n ORDER BY n.id LIMIT $limit",
                {"lookup": canonical, "limit": self.limits.search_limit + 1},
            )
        matches = [self._node(row[0]) for row in rows]
        if len(matches) == 1:
            return Lookup(matched=matches[0])
        if matches:
            return Lookup(suggestions=matches[: self.limits.search_limit])
        rows = self.db.execute_query(
            "MATCH (n:Component) RETURN n.id, n.name ORDER BY n.id LIMIT $limit",
            {"limit": self.limits.max_nodes + 1},
        )
        if len(rows) > self.limits.max_nodes:
            self._warn("Suggestion catalog exceeds node limit; suggestions omitted")
            return Lookup()
        scored = [
            (
                max(
                    SequenceMatcher(None, value.casefold(), str(name).casefold()).ratio(),
                    SequenceMatcher(None, value.casefold(), str(identifier).casefold()).ratio(),
                ),
                identifier,
            )
            for identifier, name in rows
        ]
        ids = [
            identifier
            for score, identifier in sorted(scored, key=lambda x: (-x[0], x[1]))
            if score >= 0.45
        ][: self.limits.search_limit]
        if not ids:
            return Lookup()
        rows = self.db.execute_query(
            "MATCH (n:Component) WHERE n.id IN $ids RETURN n ORDER BY n.id LIMIT $limit",
            {"ids": ids, "limit": self.limits.search_limit},
        )
        suggestions = {self._node(row[0]).id: self._node(row[0]) for row in rows}
        return Lookup(suggestions=[suggestions[i] for i in ids if i in suggestions])

    def _dependency_paths(self, source: str, downstream: bool, depth: int) -> list[EvidencePath]:
        depth = self._depth(depth)
        key = (source, downstream, depth)
        if key not in self._path_cache:
            # Only a validated depth from the eight-value allowlist enters syntax.
            relation = f"[:{DEPENDENCY_TYPES}*1..{depth}]"
            pattern = (
                f"(a:Component)<-{relation}-(b:Component)"
                if downstream
                else f"(a:Component)-{relation}->(b:Component)"
            )
            cypher = f"MATCH p={pattern} WHERE a.id = $component_id AND {SIMPLE_PATH} "
            cypher += "RETURN p ORDER BY length(p) LIMIT $limit"
            rows = self._query(
                "downstream" if downstream else "upstream",
                cypher,
                {"component_id": source, "limit": self.limits.max_paths + 1},
            )
            paths = [self._decode(row[0]) for row in rows]
            self._path_cache[key] = sorted(paths, key=self._path_priority)
        return self._path_cache[key]

    @staticmethod
    def _path_priority(path: EvidencePath) -> tuple:
        return (
            not path.required,
            path.hops,
            path.node_ids,
            [evidence_edge_priority(edge) for edge in path.edges],
        )

    def traverse(self, component_id, direction, depth=None) -> list[Impact]:
        paths = self._dependency_paths(component_id, direction == "downstream", self._depth(depth))
        selected = {}
        for path in paths:
            target = path.node_ids[-1]
            if target not in selected:
                selected[target] = Impact(
                    component=self.nodes[target], hops=path.hops, path=path, required=path.required
                )
        return sorted(selected.values(), key=lambda item: (item.hops, item.component.id))

    def paths(
        self,
        source,
        target,
        *,
        downstream=False,
        required_only=False,
        min_criticality=1,
        depth=None,
    ) -> list[EvidencePath]:
        if not 1 <= min_criticality <= 5:
            raise ValueError("Criticality must be between 1 and 5")
        if source == target and source in self.nodes:
            return [self._path([source], [])]
        return [
            p
            for p in self._dependency_paths(source, downstream, self._depth(depth))
            if p.node_ids[-1] == target
            and (not required_only or p.required)
            and p.criticality >= min_criticality
        ]

    def shortest_path(self, source, target, *, downstream=False):
        paths = self.paths(source, target, downstream=downstream)
        return (
            min(
                paths,
                key=lambda p: (p.hops, p.node_ids, [evidence_edge_priority(e) for e in p.edges]),
            )
            if paths
            else None
        )

    def context(self, impacts, relationship, label, *, incoming=False):
        allowed = {
            ("SUPPORTS", "BusinessFlow"),
            ("DEPENDS_ON", "BusinessFlow"),
            ("USED_BY", "Customer"),
            ("DEPLOYED_IN", "Region"),
            ("OWNED_BY", "Team"),
            ("HAS_RUNBOOK", "Runbook"),
        }
        if (relationship, label) not in allowed:
            raise ValueError("Unsupported context relationship")
        if impacts:
            pattern = (
                f"(a:Component)<-[:{relationship}]-(b:{label})"
                if incoming
                else f"(a:Component)-[:{relationship}]->(b:{label})"
            )
            rows = self._query(
                relationship.lower(),
                f"MATCH p={pattern} WHERE a.id IN $ids RETURN p ORDER BY a.id, b.id LIMIT $limit",
                {
                    "ids": sorted({i.component.id for i in impacts}),
                    "limit": self.limits.max_paths + 1,
                },
            )
            for row in rows:
                self._decode(row[0])
        return super().context(impacts, relationship, label, incoming=incoming)

    def deployment(self, component_id):
        rows = self._query(
            "deployment_replicas",
            "MATCH p=(a:Component)"
            "-[:DEPLOYED_IN|REPLICATES_TO*1..2]->(b:Component) WHERE a.id = $component_id "
            "RETURN p ORDER BY length(p) LIMIT $limit",
            {"component_id": component_id, "limit": self.limits.max_paths + 1},
        )
        for row in rows:
            self._decode(row[0])
        return super().deployment(component_id)

    def _business_paths(self, root: str, *, customer: bool) -> list[EvidencePath]:
        """Return the entire technical→workflow→customer chain from Cypher."""
        depth = self._depth(None)
        suffix = "-[:USED_BY]->(customer:Customer)" if customer else ""
        paths = []
        for name, link in [("supports", "-[:SUPPORTS]->"), ("entrypoint", "<-[:DEPENDS_ON]-")]:
            # Avoid zero-length variable paths: this server's mixed-direction
            # zero-hop serialization can reverse later context-edge endpoints.
            for prefix in [
                "(a:Component)",
                f"(a:Component)<-[:{DEPENDENCY_TYPES}*1..{depth}]-(s:Component)",
            ]:
                cypher = (
                    f"MATCH p={prefix}{link}(f:BusinessFlow){suffix} "
                    f"WHERE a.id = $component_id AND {SIMPLE_PATH} "
                    "RETURN p ORDER BY length(p) LIMIT $limit"
                )
                rows = self._query(
                    ("customer_" if customer else "workflow_") + name,
                    cypher,
                    {"component_id": root, "limit": self.limits.max_paths + 1},
                )
                paths.extend(self._decode(row[0]) for row in rows)
        return paths

    def _impacts_from_paths(self, paths: list[EvidencePath]) -> list[Impact]:
        selected = {}
        # Context ties preserve SUPPORTS before workflow-entrypoint evidence,
        # matching the existing context contract; these are not parallel dependencies.
        for path in sorted(paths, key=lambda p: (not p.required, p.hops, p.node_ids)):
            identifier = path.node_ids[-1]
            if identifier not in selected:
                selected[identifier] = Impact(
                    component=self.nodes[identifier],
                    hops=path.hops,
                    path=path,
                    required=path.required,
                )
        return sorted(selected.values(), key=lambda impact: (impact.hops, impact.component.id))

    def workflows(self, impacts):
        if not impacts:
            return []
        paths = [impact.path for impact in impacts if impact.component.label == "BusinessFlow"]
        paths += self._business_paths(impacts[0].path.node_ids[0], customer=False)
        return self._impacts_from_paths(paths)

    def customers(self, workflows):
        if not workflows:
            return []
        # Pure BusinessFlow incidents may start with a zero-hop workflow.
        if workflows[0].path.hops == 0:
            return self.context(workflows, "USED_BY", "Customer")
        paths = self._business_paths(workflows[0].path.node_ids[0], customer=True)
        paths = [
            path
            for path in paths
            if any(
                path.node_ids[:-1] == flow.path.node_ids and path.edges[:-1] == flow.path.edges
                for flow in workflows
            )
        ]
        return self._impacts_from_paths(paths)

    def cycles(self):
        if self.nodes:
            depth = self._depth(None)
            rows = self._query(
                "dependency_cycles",
                f"MATCH p=(a:Component)"
                f"-[:{DEPENDENCY_TYPES}*1..{depth}]->(a) WHERE a.id IN $ids "
                "RETURN p ORDER BY length(p) LIMIT $limit",
                {"ids": sorted(self.nodes), "limit": self.limits.max_paths + 1},
            )
            for row in rows:
                self._decode(row[0])
        return super().cycles()
