"""Read-only, key-free local benchmark. Outputs measured JSON, never writes files."""

import argparse
import json
import math
import platform
import statistics
from collections.abc import Callable
from time import perf_counter

from src.analytics import Analytics
from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import GraphQueries, edge_key
from src.investigator import investigate
from src.native_queries import NativeGraphQueries
from src.reports import build_evidence, generate_report


def measure(operation: Callable[[], object], *, iterations: int, warmup: int) -> dict:
    """Median and nearest-rank p95 in milliseconds, excluding warm-up samples."""
    if not 3 <= iterations <= 100 or not 0 <= warmup <= 5:
        raise ValueError("Use 3–100 measured iterations and 0–5 warm-up iterations")
    for _ in range(warmup):
        operation()
    samples = []
    for _ in range(iterations):
        started = perf_counter()
        operation()
        samples.append((perf_counter() - started) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 3),
        "p95_ms": round(sorted(samples)[math.ceil(0.95 * len(samples)) - 1], 3),
        "samples_ms": [round(value, 3) for value in samples],
    }


def run(iterations: int = 20, warmup: int = 2) -> dict:
    """Read the configured demo graph; no provider call or graph write path."""
    with DatabaseManager(Settings.from_env()) as db:
        graph = GraphQueries.from_database(db)
        result = investigate(NativeGraphQueries(db), "vault")
        if result.matched_component is None:
            raise ValueError("Seed the fictional graph before benchmarking")
        analysis = Analytics(graph)
        evidence = build_evidence(graph, result, analysis.analyze(result, "failed"))
        downstream = next(
            query for query in result.query_diagnostics if query["name"] == "downstream"
        )

        def pipeline():
            native = investigate(NativeGraphQueries(db), "vault")
            metrics = Analytics(graph).analyze(native, "failed")
            return generate_report(build_evidence(graph, native, metrics), Settings())

        operations = {
            "direct_one_hop": lambda: NativeGraphQueries(db).direct_dependents("vault"),
            "native_blast_radius": lambda: NativeGraphQueries(db).blast_radius("vault"),
            "native_blast_query": lambda: db.execute_query(
                downstream["cypher"], downstream["parameters"]
            ),
            "native_investigation": lambda: investigate(NativeGraphQueries(db), "vault"),
            "networkx_analytics": lambda: Analytics(graph).analyze(result, "failed"),
            "deterministic_report": lambda: generate_report(evidence, Settings()),
            "pipeline_without_llm": pipeline,
        }
        measurements = {
            name: measure(operation, iterations=iterations, warmup=warmup)
            for name, operation in operations.items()
        }
        impacts = result.direct_impact + result.cascading_impact
        paths = [
            impact.path
            for impact in impacts + result.impacted_customers + result.impacted_workflows
        ]
        return {
            "environment": {
                "python": platform.python_version(),
                "system": platform.platform(),
                "architecture": platform.machine(),
            },
            "iterations": iterations,
            "warmup": warmup,
            "snapshot_nodes": len(graph.nodes),
            "snapshot_relationships": len(graph.edges),
            "operational_nodes": analysis.graph.number_of_nodes(),
            "operational_adjacencies": analysis.graph.number_of_edges(),
            "returned_evidence_nodes": len(result.evidence_nodes),
            "returned_evidence_relationships": len(result.evidence_edges),
            "returned_unique_impact_paths": len(
                {tuple(edge_key(e) for e in p.edges) for p in paths}
            ),
            "maximum_hops": max((p.hops for p in paths), default=0),
            "direct_components": len(result.direct_impact),
            "multi_hop_components": len(impacts),
            "customers": len(result.impacted_customers),
            "measurements": measurements,
            "limits": "Warm local connection; cached global snapshot; no UI rendering/startup/provider time. "
            "Pipeline includes fresh native queries, NetworkX, fictional comparison construction and report. "
            "Report-only excludes evidence construction. Server nodes examined/expansions are not measured.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.iterations, args.warmup), indent=2))
        return 0
    except (DatabaseError, ValueError):
        print("Benchmark unavailable: check local graph health, seed data and iteration limits.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
