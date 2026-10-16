"""Topology models and integrity checks shared by file and database validation."""

from collections import Counter
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

Label = Literal[
    "Service",
    "Database",
    "Queue",
    "API",
    "Region",
    "Customer",
    "Team",
    "BusinessFlow",
    "Runbook",
    "Incident",
]
Relation = Literal[
    "DEPENDS_ON",
    "CALLS",
    "READS_FROM",
    "WRITES_TO",
    "PUBLISHES_TO",
    "CONSUMES_FROM",
    "DEPLOYED_IN",
    "USED_BY",
    "OWNED_BY",
    "SUPPORTS",
    "HAS_RUNBOOK",
    "AFFECTS",
    "REPLICATES_TO",
]
DEPENDENCIES = {"DEPENDS_ON", "CALLS", "READS_FROM", "WRITES_TO", "PUBLISHES_TO", "CONSUMES_FROM"}
OWNED_LABELS = {"Service", "Database", "Queue", "API"}


class Node(BaseModel):
    """One fictional infrastructure or context entity."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, str_max_length=4096, hide_input_in_errors=True
    )
    id: str = Field(min_length=1)
    label: Label
    name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    criticality: int = Field(ge=1, le=5)
    environment: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    region: str = Field(min_length=1)
    last_checked: str = Field(min_length=1)


class Relationship(BaseModel):
    """Directed relationship; dependency direction is consumer to provider."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_max_length=4096,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: Relation
    criticality: int = Field(ge=1, le=5)
    latency_ms: float = Field(ge=0)
    status: str = Field(min_length=1)
    required: bool
    dependency_type: str = Field(min_length=1)
    last_checked: str = Field(min_length=1)


class Topology(BaseModel):
    """Validated transport format for the readable JSON fixture."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    nodes: list[Node] = Field(max_length=2000)
    relationships: list[Relationship] = Field(max_length=10000)


def integrity(topology: Topology) -> dict:
    """Find structural errors and report intentional cycles without rejecting them."""
    errors = []
    ids = Counter(n.id for n in topology.nodes)
    errors.extend(f"Duplicate ID: {key}" for key, count in ids.items() if count > 1)
    nodes = {n.id: n for n in topology.nodes}
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    dependencies = nx.DiGraph()
    dependencies.add_nodes_from(nodes)
    owners = set()
    seen = set()
    for edge in topology.relationships:
        key = (edge.source, edge.type, edge.target)
        if key in seen:
            errors.append(f"Duplicate relationship: {key}")
        seen.add(key)
        if edge.source not in nodes or edge.target not in nodes:
            errors.append(f"Missing endpoint: {key}")
            continue
        graph.add_edge(edge.source, edge.target)
        if edge.type == "OWNED_BY":
            if nodes[edge.target].label != "Team":
                errors.append(f"Owner must be a Team: {edge.source}")
            else:
                owners.add(edge.source)
        if edge.type in DEPENDENCIES:
            dependencies.add_edge(edge.source, edge.target)
    errors.extend(f"Isolated node: {key}" for key in nx.isolates(graph))
    errors.extend(
        f"Missing owner: {n.id}"
        for n in topology.nodes
        if n.label in OWNED_LABELS and n.id not in owners
    )
    cycles = [
        sorted(component)
        for component in nx.strongly_connected_components(dependencies)
        if len(component) > 1 or any(dependencies.has_edge(n, n) for n in component)
    ]
    return {
        "errors": sorted(errors),
        "dependency_cycles": sorted(cycles),
        "dependency_articulation_points": sorted(
            nx.articulation_points(dependencies.to_undirected())
        ),
    }
