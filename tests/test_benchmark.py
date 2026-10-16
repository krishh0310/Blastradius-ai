"""Benchmark summaries must use measured samples and bounded iteration counts."""

import os
from importlib import import_module
from unittest.mock import patch

import pytest


def test_measurement_excludes_warmup_and_reports_real_percentiles():
    module = import_module("scripts.benchmark")
    calls = []
    with patch.object(module, "perf_counter", side_effect=[0, 0.001, 1, 1.004, 2, 2.002]):
        result = module.measure(lambda: calls.append(1), iterations=3, warmup=2)
    assert len(calls) == 5
    assert result["median_ms"] == pytest.approx(2)
    assert result["p95_ms"] == pytest.approx(4)


def test_benchmark_rejects_unbounded_iterations():
    module = import_module("scripts.benchmark")
    with pytest.raises(ValueError):
        module.measure(lambda: None, iterations=101, warmup=2)


@pytest.mark.skipif(
    os.environ.get("FALKORDB_INTEGRATION") != "1", reason="Requires seeded local FalkorDB"
)
def test_live_benchmark_measures_python_fallback_alongside_native():
    module = import_module("scripts.benchmark")
    result = module.run(iterations=3, warmup=0)
    for name in (
        "native_blast_radius",
        "python_blast_radius",
        "native_investigation",
        "python_investigation",
    ):
        measurement = result["measurements"][name]
        assert len(measurement["samples_ms"]) == 3
        assert 0 <= measurement["median_ms"] <= measurement["p95_ms"]
    assert result["snapshot_nodes"] == 54
    assert result["snapshot_relationships"] == 141
