# Native incident reasoning

The CLI and dashboard's operational investigation route incident-specific
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
