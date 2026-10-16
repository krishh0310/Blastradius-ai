"""Benchmark summaries must use measured samples and bounded iteration counts."""

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
