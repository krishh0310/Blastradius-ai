"""Reusable deterministic graph fixtures; no network or credentials required."""

import pytest

from src.graph_queries import GraphQueries
from src.seed import load_topology


@pytest.fixture
def topology():
    return load_topology()


@pytest.fixture
def graph(topology):
    return GraphQueries(topology)
