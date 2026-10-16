# Phase 7: deterministic cascading-failure rehearsal

## Run the dashboard

```zsh
cd "/Users/krish/Documents/graph hack/blastradius-ai"
source .venv/bin/activate
docker compose up -d --wait
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and choose **Cascade simulation** in the workspace
selector. Select Token Vault, inject down, and Build cascade. Play, Pause,
Next step, Reset simulation, and 0.5×/1×/2×/4× speed control playback.
Playback advances precomputed frames; changing speed never changes event times
or outcomes. Reset returns immediately to frame zero and discards mitigation.
Changing inputs requires Build cascade, so a completed plan cannot silently
change underneath a presentation.

The graph before failure, current cascade graph, peak graph, and mitigation graph
share the same topology and seeded layout. Red/yellow/green represent simulated
down/degraded/healthy states; node shapes retain type. Hover explicitly labels
health as simulated. Original dependency direction and optional dashed edges
remain visible. Every transition can be inspected with its original supporting
edge, evidence path, hop count, confidence, and recommended validation response.

## CLI demonstrations

```zsh
python -m src.simulator --component vault --mitigation "Execute fictional runbook"
python -m src.simulator --component payment --no-failover --mitigation "Activate regional replica"
python -m src.simulator --component mumbai
python -m src.simulator --component vault --json
FALKORDB_INTEGRATION=1 python -m pytest -q
```

CLI components use exact graph IDs. --json returns one JSON document containing
the simulation and optional mitigation. No API key is required.

## State and clock rules

Simulator copies the validated topology into memory. It does not contain a write,
save, infrastructure execution, or provider call path. Seeded properties, including
the degraded Orders Database status, remain unchanged. For a visually comparable
rehearsal, all entities start at an explicitly fictional healthy baseline.

The user-selected starting component changes at T+00s. Its zero-hop event is a
scenario assumption, not a measured graph fact. Each following edge costs three
simulated seconds by default (configurable through SimulationConfig). These delays
are deterministic presentation steps, not measured latency or predicted outage
timing. No fabricated error-rate thresholds are presented.

Dependency propagation follows DEPENDS_ON, CALLS, READS_FROM, WRITES_TO,
PUBLISHES_TO, and CONSUMES_FROM in reverse: provider failure affects consumer.
BusinessFlow DEPENDS_ON edges, forward SUPPORTS, and forward USED_BY connect the
operational failure to workflows and customers. Reverse DEPLOYED_IN connects
regional failure to deployments. Duplicate routes do not create duplicate
same-state transitions. A later required route supersedes optional-only evidence.

Required edges propagate down or degraded. Optional edges either cap impact at
degraded or block it according to the selected policy. Degraded sources cannot
propagate a down state. Paths never repeat a node. Worsening-only transitions,
single failover attempts, depth 1–8, and an event cap prevent endless cycles.
Limit warnings mean the plan may be incomplete.

## Replica and region handling

Failover must be explicitly assumed ready in the UI or requested as a fictional
mitigation. It can use only:

- A healthy alternate DEPLOYED_IN region.
- An explicit REPLICATES_TO target with healthy recorded status and a healthy
  recorded deployment region.

Alternates must also be healthy in the current simulated state. A nonregional
starting failure is treated as a primary/local-deployment failure when failover
is enabled. Regional failures can move qualifying deployments out of the failed
region. The starting down state remains visible before recovery one step later.

A service replica cannot repair an unhealthy shared required provider. If a
failover attempt is blocked by that provider, its failure continues propagating
instead of disappearing. Thus Mumbai can demonstrate successful failover of
queues/data stores while Token Vault remains a shared single-region bottleneck.
No undeclared Token Vault replica is invented.

Replica freshness, capacity, and successful routing are assumptions, not facts.
The graph establishes the alternate's existence and recorded health only.

## Fictional mitigation policies

| Action | Gate and modeled behavior |
| --- | --- |
| Activate regional replica | Requires a graph-declared healthy alternate; enables failover |
| Reroute traffic | Same graph-supported alternate gate; no new route is invented |
| Isolate unhealthy dependency | Assume a circuit breaker leaves direct consumers degraded and contains further propagation |
| Degraded read-only mode | For Service/Database/API, assume the starting failure can be capped at degraded |
| Disable optional feature | Ignore optional consumer edges; required consumers still fail |
| Execute fictional runbook | Requires HAS_RUNBOOK; assume recovery of the starting component succeeds |

Containment/read-only capabilities and runbook success are fictional control
assumptions, not capabilities asserted by the seeded schema. Actions are replayed
from the same baseline; their final status differences are recorded at a single
counterfactual mitigation checkpoint after the unmitigated timeline.
The checkpoint is not a prediction of actual recovery speed.

No real runbook is executed, traffic rerouted, dependency disconnected, replica
activated, or graph edge deleted. The UI has no persistence option.

## Risk and comparison

Frames reuse the Phase 4 Analytics.risk formula and its typed factor breakdown.
The original graph supplies centrality, criticality, required-edge facts, and
declared resilience. Frame-specific active affected entities and the scoring
component's simulated health supply changing exposure factors.

Healthy baseline and recovered states can retain structural risk points:
criticality, centrality, and articulation do not disappear after recovery.
For Token Vault this residual is 21.62 (Low), not zero. Its seeded-topology
cascade reaches 91.62 (Critical), with 22 affected entities including the root.
The linked fictional runbook returns the scenario to zero active affected
entities and 21.62 residual risk: a 70-point reduction.

Regional scores use a clearly labeled operational-component exposure envelope;
they are not a calibrated region-wide risk model. Existing declared-resilience
discounts remain metadata-based, not proof of live failover capacity.

Comparison shows baseline, peak cascade, and settled counterfactual after
mitigation. It separately reports incremental score reduction against the
unmitigated settled state. This prevents natural automatic failover recovery
from being falsely attributed to a redundant mitigation.

"Critical paths neutralized" means formerly active critical impact paths no
longer carry the simulated impact. The permanent topology is identical.

## Performance and verification

Plans and mitigation replays are cached by graph snapshot and validated inputs;
these caches contain no credentials. Playback uses a timed Streamlit fragment and
a session cursor, without sleeping or rerunning graph analytics on each tick.
The existing Phase 6 investigation workspace remains available unchanged.

Tests cover reproducibility, original-topology invariance, required/optional
propagation, healthy/unhealthy replicas, shared-provider failover blocking, cycle
termination, event bounds, transition evidence, mitigation score changes, timeline
order, UI next/play/pause/speed/reset, and live FalkorDB read-before/read-after
invariance. Streamlit AppTest provides UI checks without requiring cloud keys.
