"""Idempotent fictional graph seeding and live integrity validation."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import GraphQueries
from src.topology import Topology, integrity

DEFAULT_TOPOLOGY = Path(__file__).resolve().parents[1] / "data" / "topology.json"


def load_topology(path: Path = DEFAULT_TOPOLOGY) -> Topology:
    """Validate all input before performing database writes."""
    if path.stat().st_size > 5_000_000:
        raise ValueError("Topology file exceeds the 5 MB limit")
    topology = Topology.model_validate_json(path.read_text())
    report = integrity(topology)
    if report["errors"]:
        raise ValueError("; ".join(report["errors"]))
    return topology


def snapshot(db: DatabaseManager) -> Topology:
    """Read authoritative node and edge properties from FalkorDB."""
    graph = GraphQueries.from_database(db)
    return Topology(nodes=list(graph.nodes.values()), relationships=graph.edges)


def seed(
    db: DatabaseManager,
    topology: Topology,
    *,
    reset: bool = False,
    confirm_reset: str | None = None,
) -> dict:
    """Merge by global ID and directed edge identity; reset only managed entities."""
    topology = Topology.model_validate(topology.model_dump())
    report = integrity(topology)
    if report["errors"]:
        raise ValueError("; ".join(report["errors"]))
    if reset:
        if confirm_reset != db.settings.falkordb_graph:
            raise ValueError("Reset requires confirmation matching the configured graph")
        db.execute_query("MATCH (n:Component) DETACH DELETE n")
    # Labels and types come exclusively from Pydantic Literal allowlists.
    indexes = db.execute_query(
        "CALL db.indexes() YIELD label, properties, entitytype RETURN label, properties, entitytype"
    )
    if not any(
        label == "Component" and "id" in properties and kind == "NODE"
        for label, properties, kind in indexes
    ):
        db.execute_query("CREATE INDEX FOR (n:Component) ON (n.id)")
    for node in topology.nodes:
        properties = node.model_dump(exclude={"label"})
        db.execute_query(
            f"MERGE (n:Component {{id: $id}}) SET n:{node.label} SET n += $properties",
            {"id": node.id, "properties": properties},
        )
    for edge in topology.relationships:
        db.execute_query(
            "MATCH (a:Component {id: $source}), (b:Component {id: $target}) "
            f"MERGE (a)-[r:{edge.type}]->(b) SET r += $properties",
            {
                "source": edge.source,
                "target": edge.target,
                "properties": edge.model_dump(exclude={"source", "target", "type"}),
            },
        )
    stored = snapshot(db)
    return {
        "nodes": len(stored.nodes),
        "relationships": len(stored.relationships),
        **integrity(stored),
    }


def main() -> int:
    """Seed or validate the selected graph, with an explicit reset confirmation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="Validate the live graph only")
    parser.add_argument("--file", type=Path, default=DEFAULT_TOPOLOGY)
    parser.add_argument(
        "--reset", action="store_true", help="Delete Component nodes before seeding"
    )
    parser.add_argument("--confirm-reset", metavar="GRAPH", help="Must equal the configured graph")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.reset and (args.validate or args.confirm_reset != settings.falkordb_graph):
            parser.error(
                "--reset requires --confirm-reset matching FALKORDB_GRAPH; cannot validate"
            )
        topology = None if args.validate else load_topology(args.file)
        with DatabaseManager(settings) as db:
            if args.validate:
                stored = snapshot(db)
                report = {
                    "nodes": len(stored.nodes),
                    "relationships": len(stored.relationships),
                    **integrity(stored),
                }
                if not stored.nodes:
                    report["errors"].append("Graph is empty; run the seed command first")
            else:
                report = seed(db, topology, reset=args.reset, confirm_reset=args.confirm_reset)
        print(json.dumps(report, indent=2))
        return int(bool(report["errors"]))
    except (OSError, ValueError, ValidationError, DatabaseError) as exc:
        print(f"Phase 2 failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
