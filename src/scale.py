"""Deterministic fictional scale fixture; never changes the 54-node judge dataset."""

from src.seed import load_topology
from src.topology import Node, Relationship, Topology, integrity


def build_scale_topology(tenants: int = 20) -> Topology:
    """Clone isolated tenants joined by one required shared secrets dependency."""
    if type(tenants) is not int or not 1 <= tenants <= 30:
        raise ValueError("Use an integer tenant count from 1 to 30")
    baseline = load_topology()
    nodes = []
    edges = []
    for tenant in range(1, tenants + 1):
        prefix = f"tenant{tenant:02d}-"
        ids = {node.id: prefix + node.id for node in baseline.nodes}
        nodes.extend(
            node.model_copy(
                update={
                    "id": ids[node.id],
                    "name": f"{node.name} (tenant {tenant:02d})",
                    "region": ids.get(node.region, node.region),
                }
            )
            for node in baseline.nodes
        )
        edges.extend(
            edge.model_copy(update={"source": ids[edge.source], "target": ids[edge.target]})
            for edge in baseline.relationships
        )
    common = dict(
        status="healthy",
        criticality=5,
        environment="demo",
        tier="shared",
        region="global",
        last_checked="2026-01-01T00:00:00Z",
    )
    for identifier, label, name in (
        ("shared-secrets", "Service", "Shared Secrets Control Plane"),
        ("shared-platform", "Team", "Shared Platform Team"),
        ("shared-recovery", "Runbook", "Fictional Shared Secrets Recovery"),
    ):
        nodes.append(
            Node(
                id=identifier,
                label=label,
                name=name,
                description="Synthetic benchmark entity; no real infrastructure.",
                **common,
            )
        )
    links = [
        ("shared-secrets", "shared-platform", "OWNED_BY"),
        ("shared-secrets", "shared-recovery", "HAS_RUNBOOK"),
    ]
    links += [
        (f"tenant{tenant:02d}-vault", "shared-secrets", "DEPENDS_ON")
        for tenant in range(1, tenants + 1)
    ]
    edges.extend(
        Relationship(
            source=source,
            target=target,
            type=kind,
            criticality=5,
            latency_ms=2,
            status="healthy",
            required=True,
            dependency_type="synthetic shared context",
            last_checked=common["last_checked"],
        )
        for source, target, kind in links
    )
    topology = Topology(nodes=nodes, relationships=edges)
    if integrity(topology)["errors"]:
        raise ValueError("Synthetic topology integrity failed")
    return topology
