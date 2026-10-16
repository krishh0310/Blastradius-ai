# Native incident reasoning

The investigator CLI and dashboard's operational investigation route incident-specific
dependency and cross-domain path retrieval through `NativeGraphQueries`.
It starts with an empty evidence cache, not a full graph export. FalkorDB returns
typed paths; Python validates their nodes, stored relationship directions,
properties and identities, deduplicates, and formats them. Full bounded snapshots
remain necessary for cached global NetworkX analytics, component selection,
simulation, and the explicitly labeled Python fallback.

Native operations: exact/name lookup, upstream/downstream traversal, bounded
shortest/all-required/critical path selection from returned ordered paths,
complete workflow/customer paths, owner teams, runbooks, regions, deployment and
replica paths, and closed dependency walks for cycle groups. Python SCC formatting
groups cycle evidence; NetworkX continues structural analytics. Context paths
may add workflow/customer hops beyond the 1–8 dependency-hop budget.

Values are parameters. Relationship/label choices are internal allowlists. Only a
validated integer depth 1–8 enters query syntax. Each operation returns at most
500 paths and reads one extra row to detect truncation. The server has a 3-second
query timeout; there is no claim of a measured server expansion count. Local node
and relationship limits remain 2,000 and 10,000. Result caps are per operation,
not a server-wide workload budget. Partial results carry warnings.

Example executed dependency shape (`$component_id = 'vault'`, `$limit = 501`):

```cypher
MATCH p=(a:Component)<-[:CALLS|CONSUMES_FROM|DEPENDS_ON|PUBLISHES_TO|READS_FROM|WRITES_TO*1..6]-(b:Component)
WHERE a.id = $component_id
AND all(n IN nodes(p) WHERE single(m IN nodes(p) WHERE m.id = n.id))
RETURN p ORDER BY length(p) LIMIT $limit
```

The complete customer query continues the technical prefix through SUPPORTS or
the workflow's incoming DEPENDS_ON entrypoint, then USED_BY to a Customer.
These full paths—not invented links—are the customer evidence. Owner teams are
separate branches from operational components, not fabricated customer-to-team edges.

Queries and timings are recorded in `InvestigationResult.query_diagnostics`.
Lookup text is omitted from displayed parameters. Native errors never expose raw
database details. Dashboard connection/query failure uses the displayed bounded
snapshot and labels the result `bounded Python fallback`. Invalid graph evidence
fails validation rather than being silently accepted. The CLI fails clearly if
native retrieval is unavailable. Regional envelope composition remains explicitly
Python-based, rather than claiming an independent native regional risk model.

If observed native node/edge properties differ from the cached analytics snapshot,
the dashboard discards that attempt and explicitly uses consistent snapshot
evidence until refresh. This prevents mixing new entities with old analytics or
report facts. It is not transactional snapshot isolation: deletions elsewhere or
changes between individual queries may remain undetected. Native lookup ambiguity
uses its own budget (at least two matches), never the path-result cap.

Structural cycle discovery has a separate fixed eight-hop bound, independent of
the selected incident impact depth. Thus a one-hop email API investigation can
still explain the known two-node dependency cycle touching an exposed service.
Longer cycles may be omitted; the result states this explicitly. Global NetworkX
SCC analytics remains available on the bounded full projection.

The pinned server exhibited incorrect context-edge endpoints for mixed-direction
paths with a zero-length variable prefix during integration testing. Direct
context branches are therefore separate from positive-length prefixes. Parity
tests compare complete typed customer evidence and catch this regression.

```zsh
python -m pip install -r requirements-dev.txt
FALKORDB_INTEGRATION=1 python -m pytest tests/test_native_queries.py
python -m src.investigator --component 'Token Vault' --depth 6 --json
```

Parity covers Token Vault, Orders Database, analytics cycles, optional email API,
unknown IDs, and depths 1/6/8. The initial schema and scoring weights are unchanged.

## CLI and reusable operations

After [setup](setup.md), run `python -m src.investigator --component 'Token Vault'
--depth 6` (on one shell line); add `--json` for typed evidence. Exit codes: 0 for a
completed bounded match, 2 for missing/ambiguous input, 1 for configuration/database/
validation failure. Inspect warnings even on exit 0. IDs match first, then
case-insensitive full names; Db/Database aliases are supported. Fuzzy suggestions
are never silently promoted to matches. Duplicate names require an exact ID.

`NativeGraphQueries(db, QueryLimits(...))` and the controlled snapshot fallback
return Pydantic models. Their reusable interface includes exact_lookup, search,
suggestions, direct_dependencies, direct_dependents, dependencies, blast_radius,
shortest_path, impact_paths, paths, critical_paths, workflows, customers, regions,
teams, runbooks, deployment, cycles, health and evidence_subgraph.
`investigate(queries, component)` composes these into InvestigationResult.

Dependency evidence retains original source/target/type and every edge property;
node_ids describe traversal order, which can oppose stored dependency direction.
Impact lists deduplicate entities and prefer all-required supporting routes even
when longer than the shortest route. Path criticality is the weakest edge;
critical paths require every dependency to be required and meet the threshold.
Recorded health is never changed by an investigation. Missing results under a cap
are not proof of no dependency. Snapshot reads are separate queries without
transactional isolation; intended use is the bounded, quiescent demo graph.
