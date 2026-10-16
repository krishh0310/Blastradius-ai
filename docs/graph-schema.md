# Phase 2 knowledge graph

All data is fictional and deterministic. FalkorDB is authoritative after seeding;
the JSON file is an import fixture, not the runtime database. Static timestamps
describe the demo snapshot and are not a claim of live cloud monitoring.

Each node has a global string ID, a shared Component label, and exactly one domain
label: Service, Database, Queue, API, Region, Customer, Team, BusinessFlow, Runbook,
or Incident. Nodes have name, status, criticality (1–5), environment, description,
tier, region, and last_checked. DEPLOYED_IN edges are authoritative for multiple
deployments; region is the primary region. A replicated service represents one
logical service deployed in several regions, not separate replica nodes.

Dependencies point from consumer to provider. DEPENDS_ON and CALLS represent
runtime calls; READS_FROM and WRITES_TO connect services to data stores.
PUBLISHES_TO and CONSUMES_FROM connect producers/consumers to queues.
REPLICATES_TO points from source to replica. DEPLOYED_IN points to Region,
OWNED_BY to Team, SUPPORTS from service to BusinessFlow, USED_BY from flow to
Customer, HAS_RUNBOOK from component to Runbook, and AFFECTS from Incident
to component. BusinessFlow DEPENDS_ON Service provides an entry point for impact
traversal. Metadata edges must not be treated as runtime dependencies.

Edges include criticality, latency_ms, status, required, dependency_type, and
last_checked. Optional notification-to-email and notification-to-analytics
dependencies have lower criticality. Phase 2 stores these facts without calculating
incident severity. Orders Database is degraded; the incident records that fact.

The graph has 18 services, 5 databases, 3 queues, 3 regions, 6 customers, 6 teams,
3 APIs, 4 flows, 5 runbooks, and 1 incident: 54 nodes and 141 relationships.
Token Vault, Vault Database, Inventory, Shipping, and Orders Database deploy only
in Mumbai; other infrastructure has a second deployment.

## Import and integrity

Pydantic validates field types, label/type allowlists, and criticality before any
write. Structural checks reject duplicate IDs/edges, missing endpoints, isolated
nodes, and missing owners for services/databases/queues/APIs. Context entities
do not require operational owners. NetworkX reports dependency strongly connected
components (cycles) and articulation points in the undirected dependency projection.
These are structural diagnostics, not incident analytics. The intentional
Notification–Analytics cycle is a warning; it does not make validation fail.

MERGE matches nodes by global ID and edges by source/type/target. A Component.id
index supports lookups. Seed runs are sequential; concurrent importers are not
supported. The index is not a uniqueness constraint: validation detects preexisting
duplicates. Each successful seed prints live totals and integrity results.

The importer updates matching fixture properties but preserves extra data and
does not remove obsolete fixture edges. Re-running repairs a partially completed
import. Imports are not an all-or-nothing transaction. Reset deletes only Component
nodes and their incident relationships, preserving unrelated nodes; use a dedicated
demo graph. Reset requires both --reset and --confirm-reset with the configured
graph name. Never run it against a graph with valuable Component data.

## Demonstration queries

Six-hop dependency chain (one row, six hops):

```cypher
MATCH p=(:Service {id:'web'})-[:DEPENDS_ON*1..8]->(:Service {id:'vault'})
WHERE length(p) = 6
RETURN [n IN nodes(p) | n.name], length(p)
```

Token Vault direct dependents (Authentication, Payment, Subscription):

```cypher
MATCH (s:Service)-[:DEPENDS_ON]->(:Service {id:'vault'}) RETURN s.name
```

Orders Database impact paths (Checkout, Shipping, Notification, Analytics):

```cypher
MATCH p=(s:Service)-[:DEPENDS_ON|READS_FROM*1..4]->(:Database {id:'orders-db'})
WHERE s.id IN ['checkout','shipping','notification','analytics']
RETURN DISTINCT s.name
```

Non-obvious reporting customer dependency (Orbit via reporting, Analytics,
Notification, Order, Orders Database; five hops):

```cypher
MATCH p=(:Customer {id:'orbit'})<-[:USED_BY]-(:BusinessFlow)
 -[:DEPENDS_ON*1..4]->(:Service)-[:READS_FROM]->(:Database {id:'orders-db'})
RETURN [n IN nodes(p) | n.name], length(p)
```

