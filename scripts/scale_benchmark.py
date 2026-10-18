"""Bounded synthetic benchmark in a uniquely owned disposable FalkorDB graph."""

import argparse
import json
from time import perf_counter
from uuid import uuid4

from scripts.benchmark import measure
from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import GraphQueries, QueryLimits
from src.native_queries import NativeGraphQueries
from src.scale import build_scale_topology
from src.seed import seed


class BenchmarkError(DatabaseError):
    """Sanitized failure report, retaining cleanup status without SDK details."""

    def __init__(self, report: dict) -> None:
        self.report = report
        super().__init__("Scale benchmark failed; inspect the sanitized report")


def run(tenants: int = 20, iterations: int = 5, warmup: int = 1) -> dict:
    """Never select the configured graph for writes; remove only this run's UUID graph."""
    topology = build_scale_topology(tenants)
    if (
        type(iterations) is not int
        or not 3 <= iterations <= 100
        or type(warmup) is not int
        or not 0 <= warmup <= 5
    ):
        raise ValueError("Use 3–100 iterations and 0–5 warm-ups")
    owned_name = "scale_test_" + uuid4().hex
    settings = Settings.from_env().model_copy(update={"falkordb_graph": owned_name})
    result = {
        "tenants": tenants,
        "iterations": iterations,
        "warmup": warmup,
        "queries": {},
        "graph": owned_name,
        "warnings": [],
        "cleanup_attempts": 0,
        "cleanup_completed": False,
    }
    with DatabaseManager(settings) as writer:
        try:
            started = perf_counter()
            seeded = seed(writer, topology)
            if seeded["errors"]:
                raise ValueError("Stored synthetic graph failed validation")
            result.update(
                nodes=seeded["nodes"],
                relationships=seeded["relationships"],
                seed_ms=round((perf_counter() - started) * 1000, 3),
            )
            limits = QueryLimits(depth=6, max_paths=500)
            with DatabaseManager(settings, read_only=True) as reader:
                graph = GraphQueries.from_database(reader, limits)
                result["snapshot_retrieval"] = measure(
                    lambda: GraphQueries.from_database(reader, limits),
                    iterations=iterations,
                    warmup=warmup,
                )
                for component in ("tenant01-vault", "shared-secrets"):
                    native = NativeGraphQueries(reader, limits)
                    native_impacts = native.blast_radius(component)
                    graph.warnings.clear()
                    reference = graph.blast_radius(component)
                    warnings = sorted(set(native.warnings + graph.warnings))
                    result["queries"][component] = {
                        "returned_components": len(native_impacts),
                        "same_affected_ids": {i.component.id for i in native_impacts}
                        == {i.component.id for i in reference},
                        "complete_within_limits": not warnings,
                        "warnings": warnings,
                        "native": measure(
                            lambda: NativeGraphQueries(reader, limits).blast_radius(component),
                            iterations=iterations,
                            warmup=warmup,
                        ),
                        "cached_python": measure(
                            lambda: graph.blast_radius(component),
                            iterations=iterations,
                            warmup=warmup,
                        ),
                    }
            result["limits"] = limits.model_dump()
            result["scope"] = (
                "Synthetic repeated tenants, not production scale. Native timings include round-trips; cached Python excludes snapshot retrieval. Returned parity is not a server-expansion or load-test guarantee. No provider calls or UI rendering."
            )
        except Exception:
            result["error"] = "benchmark_failed"
        finally:
            for attempt in range(1, 4):
                result["cleanup_attempts"] = attempt
                try:
                    writer.connect().delete()
                except Exception:
                    result["cleanup_completed"] = False
                else:
                    result["cleanup_completed"] = True
                    break
            if not result["cleanup_completed"]:
                result.setdefault("error", "cleanup_failed")
                result["warnings"].append(
                    "Cleanup could not be confirmed after three attempts. "
                    "Only the disposable graph named in this report may require manual removal."
                )
    if "error" in result:
        raise BenchmarkError(result) from None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenants", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.tenants, args.iterations, args.warmup), indent=2))
        return 0
    except BenchmarkError as exc:
        print(json.dumps(exc.report, indent=2))
        return 1
    except (DatabaseError, ValueError):
        print("Scale benchmark unavailable; check local FalkorDB and bounded arguments.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
