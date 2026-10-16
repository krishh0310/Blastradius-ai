# Phase 3 graph operations and investigation

The investigator reads the selected FalkorDB graph. It never reads the JSON
fixture in production, changes component status, invokes an LLM, or seeds data.
The result describes potential dependency exposure under the supplied failure
assumption. Recorded health remains a separate graph fact.

## Commands

```zsh
source .venv/bin/activate
docker compose up -d --wait
python -m src.investigator --component "Token Vault" --depth 6
python -m src.investigator --component "Orders Database" --depth 6
python -m src.investigator --component "Token Vault" --depth 6 --json
python -m src.investigator --component "Token Vualt"
FALKORDB_INTEGRATION=1 python -m pytest -q
python -m compileall -q src tests app.py
```

Exit codes: 0 means a match and completed bounded investigation, 2 means missing
or ambiguous input, and 1 means configuration/database/validation failure.
Inspect warnings even on exit 0: limits can make results incomplete.
Input matches exact IDs, then case-insensitive full names. The word Db also
matches Database, accommodating the Phase 2 fixture names. Fuzzy suggestions are
never silently promoted to a match. Duplicate names require an exact ID.

## Reusable Python API

```python
from src.config import Settings
from src.database import DatabaseManager
from src.graph_queries import GraphQueries, QueryLimits
from src.investigator import investigate

with DatabaseManager(Settings.from_env()) as db:
    graph = GraphQueries.from_database(db, QueryLimits(depth=6, max_paths=500))

result = investigate(graph, "Token Vault")
print(result.model_dump_json(indent=2))
```

| Operation | Method |
| --- | --- |
| Exact lookup and missing-input suggestions | exact_lookup(value) |
| Case-insensitive substring search | search(text) |
| Fuzzy name/ID candidates | suggestions(text) |
| One-hop providers / consumers | direct_dependencies(id), direct_dependents(id) |
| Multi-hop upstream / downstream | dependencies(id, depth), blast_radius(id, depth) |
| Directed shortest dependency path | shortest_path(source, target, downstream=False) |
| All relevant failed-to-affected paths | impact_paths(failed, affected, depth) |
| General bounded dependency paths | paths(source, target, downstream=False) |
| Required, high-criticality paths | critical_paths(failed, affected, min_criticality=4) |
| Workflows / customers | workflows(impacts), customers(workflows) |
| Deployment exposure / owners / runbooks | regions(impacts), teams(impacts), runbooks(impacts) |
| Region status and declared replica targets | deployment(id) |
| Dependency cycle groups | cycles() |
| Recorded health properties | health(id) |
| Typed evidence extraction | evidence_subgraph(paths, extra_edges, node_ids) |

Methods return Pydantic models or lists of models. Health returns the typed node,
including its stored status and last_checked. Missing IDs return empty results or
None. InvestigationResult includes all requested impact/context fields,
suggestions, deployment details, warnings, and timing.

## Direction and evidence

Dependency edges point consumer to provider. Upstream traversals identify
dependencies, not proven root causes. Downstream traversals follow those edges
in reverse to identify consequences. Path node_ids describe the traversal order;
each evidence edge retains its original source, target, relationship type, and
properties. Use the edge fields, not a textual arrow in the CLI, for stored
direction. Parallel READS_FROM and WRITES_TO edges remain distinct in path
enumeration. Impact lists deduplicate nodes and retain one supporting path.

An impact is required when at least one all-required dependency route is found
within depth. Such a route is preferred for its evidence; its hop count can be
longer than the overall shortest path. Optional-only results indicate reduced
exposure, not a numeric severity score. Path criticality is the minimum edge
criticality (the weakest link); critical paths require every dependency edge to
be required and meet the requested 1–5 criticality threshold.

Depth (1–8) bounds dependency edges. Context joins can add up to two edges
(service → workflow → customer), so customer evidence may have more hops than
the configured dependency depth. SUPPORTS and reverse BusinessFlow DEPENDS_ON
both provide workflow evidence. Region exposure uses DEPLOYED_IN, owners use
OWNED_BY, runbooks use HAS_RUNBOOK. Replica targets use REPLICATES_TO; regional
deployments and healthy region status do not prove ready-to-use failover capacity.
This phase does not simulate regional failure or replication failure propagation.

Cycles are reported as strongly connected dependency groups with their internal
edges. They are not an enumeration of every possible cycle. Traversals never
repeat a node in a path, terminate at depth, and exclude the failed node from its
own impact list.

Evidence nodes and edges include the failed component, every reported path,
context join, relevant cycle, and deployment/replica relationship. All output
ordering is deterministic apart from elapsed time.

## Bounds and consistency

The database layer issues fixed Cypher queries with parameterized LIMIT values.
Names and other user input are compared in Python and never interpolated into
Cypher. NetworkX cycle checks and deterministic graph traversals operate on
these database facts. Defaults: 2,000 nodes, 10,000 edges, 500 enumerated paths
per operation, 20,000 edge expansions per traversal, five suggestions.
CLI exposes depth, max-paths, max-nodes, and max-edges; Python exposes all limits.

Snapshot overflow and structural corruption fail closed. Path/expansion limits
produce explicit warnings rather than claiming exhaustive results. Investigation
critical paths also have an aggregate max_paths cap. Shortest paths are shortest
within depth and available traversal work. If a warning is present, absent
results must not be taken as proof of no dependency.

Node and relationship reads are separate queries; investigate a quiescent graph
for consistent results. Concurrent topology writes are not snapshot-isolated.
The snapshot design is intended for the hackathon graph; larger inventories
will need server-side scoped subgraph retrieval. Structural validation follows
Phase 2 owner and required-property rules.

CLI timing includes database reads and investigation processing. Direct Python
investigate() timing measures investigation processing on the loaded graph.
