# Knowledge graph, analytics and scoring

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

## Algorithms and projections

Only Service, Database, Queue, and API nodes enter centrality calculations.
Directed dependency edges point consumer to provider. Context entities, ownership,
deployment, replication, and business workflow edges do not distort centrality.
Parallel relationships collapse to one directed adjacency for metrics; original
edge types and directions remain in evidence paths.

For a fixed node pair, evidence prefers required over optional, then higher
criticality, then explicitly unhealthy status (down/failed, unhealthy, degraded),
then lexicographic relationship type/source/target. All original parallel edges
remain available for exhaustive paths. This policy is shared by shortest-path
evidence, traversal adjacency and simulation scheduling; no scoring weights change.

- Degree centrality uses NetworkX's directed degree normalization (total degree
  divided by N−1); in-degree counts consumers, out-degree counts providers.
- Directed betweenness is unweighted and normalized. PageRank uses damping 0.85,
  tolerance 1e-10, and at most 500 iterations. SciPy is required by NetworkX PageRank.
- Articulation points use an undirected projection of operational dependencies.
  An articulation point is structural evidence, not sufficient proof of outage.
- Strongly connected components identify cycle groups. Each group includes its
  original dependency edges; the known Analytics–Notification feedback cycle is
  detected without enumerating infinitely many walks.
- NetworkX shortest paths are directed and unweighted, bounded by configured depth.
  Equal-length ties follow sorted graph insertion order.
- Critical paths require all dependencies to be required and have criticality at
  least 4. Rankings use 60% minimum edge criticality/5, 30% mean edge criticality/5,
  and 10% inverse (hops+1). Higher scores prioritize critical, short required paths.
- Candidate single point of failure: at least two required downstream operational
  dependents and no declared healthy alternate deployment or replica.

Cycle groups, path counts, and impacts inherit bounded traversal limits and
warnings. These deterministic heuristics are not calibrated outage probabilities.

## Risk score

Sum the factor points below, subtract regional resilience reduction, clamp to
0–100, and round to two decimals. All normalized inputs are in [0,1].

| Factor | Weight | Normalization |
| --- | ---: | --- |
| Blast radius | 20 | Weighted downstream operational dependents / 10, capped at 1 |
| Customers | 20 | Weighted exposed customers / all graph customers |
| Workflows | 15 | Weighted exposed workflows / all graph workflows |
| Dependency criticality | 15 | Mean of component criticality and strongest incoming dependency criticality, divided by 5 |
| Betweenness | 10 | Directed normalized betweenness / maximum in this snapshot |
| Articulation | 5 | 1 if articulation point, else 0 |
| Required exposure | 5 | Required downstream operational dependents / all downstream operational dependents |
| Health | 10 | Healthy 0; degraded 0.5; unhealthy 0.8; failed/down 1; unknown 0.5 |

Weighted exposure assigns 1 to an all-required route and 0.25 to optional-only
exposure. A reachable entity counts once. When both routes exist, required
exposure takes precedence. No dependents means a required-exposure factor of 0.
Zero customer/workflow populations use denominator 1, yielding no impact points.

Resilience subtracts 7.5 points for each additional healthy deployment region
beyond the first, plus each explicit healthy REPLICATES_TO target, capped at 15.
This is a modest metadata-based discount: region health does not prove an
individual service replica is ready, and a healthy replica node does not prove
replication freshness or failover capacity. The report states those unknowns.
Shared failure domains across explicit replicas are not inferred.

Severity is Low below 25, Medium below 50, High below 75, and Critical at 75–100.
The typed result includes every normalized value, weight, contribution, reduction,
and health assumption. Changing the graph can legitimately change scores.

## Root-cause ranking

Candidates are the symptom component and its reachable upstream operational
providers. Each candidate includes the symptom-to-provider supporting path,
factor contributions, stored health, and incident association IDs.

| Evidence | Weight | Normalization |
| --- | ---: | --- |
| Unhealthy status | 30 | Same health scale as risk |
| Required downstream dependents | 15 | Count / 10, capped at 1 |
| Symptom distance | 10 | 1/(hops+1) |
| Edge criticality | 10 | Weakest path edge / 5; root itself uses node criticality |
| Required path | 10 | All edges required = 1, otherwise 0 |
| Betweenness | 10 | Relative to snapshot maximum |
| Articulation | 5 | Boolean |
| Region health | 5 | Nonhealthy deployment regions / known deployment regions |
| Incident association | 5 | At least one Incident AFFECTS candidate = 1 |

Strong candidate requires unhealthy node/region evidence, a required supporting
route, and score ≥45. Other health or incident evidence yields Possible candidate;
otherwise Insufficient evidence. The model supports Confirmed, but the current implementation
never assigns it because the schema has no explicit confirmed causal relationship.
AFFECTS alone confirms neither causality nor historical chronology.

## Simulated cascade and mitigation

The simulator copies the validated topology into memory and has no database-write,
provider-call or infrastructure-action path. All entities start at a deliberately
fictional healthy baseline; stored health, including Orders Database degradation,
is unchanged. The starting failure occurs at T+00s; each edge costs three simulated
seconds by default. These are deterministic presentation steps, not measured latency.

Provider failure propagates to consumers in reverse dependency direction.
BusinessFlow DEPENDS_ON, forward SUPPORTS and USED_BY connect exposure to workflows
and customers; reverse DEPLOYED_IN connects region failures to deployments.
Required edges propagate down/degraded. Optional edges cap impact at degraded or
are ignored according to policy. Degraded sources cannot propagate down. Paths
never repeat a node; depth, event/scheduling caps and warnings bound cycles/work.

Failover uses only healthy alternate DEPLOYED_IN regions or explicit healthy
REPLICATES_TO targets with healthy deployment regions. Simulated state must also
permit recovery. A replica cannot repair an unhealthy shared required provider.
Freshness, routing, capacity and readiness remain assumptions, not graph facts.

| Fictional action | Evidence gate / assumed behavior |
|---|---|
| Activate regional replica / reroute traffic | Requires a graph-declared healthy alternate |
| Isolate unhealthy dependency | Assume circuit breaking degrades direct consumers and contains further propagation |
| Degraded read-only mode | Service/Database/API only; assume failure capped at degraded |
| Disable optional feature | Ignore optional edges; required consumers still fail |
| Execute fictional runbook | Requires HAS_RUNBOOK; assume starting-component recovery succeeds |

Actions replay the same baseline. Status differences appear at a counterfactual
checkpoint, not a prediction of recovery speed. Comparison distinguishes baseline,
peak and settled mitigation outcome and reports incremental reduction against the
unmitigated settled state, so natural failover is not credited to mitigation.
Neutralized critical paths are no longer active impact paths; no edges are deleted.
Healthy/recovered states can retain structural risk; the formula above is unchanged.
Regional risk is a labeled operational-component envelope, not a calibrated region model.

