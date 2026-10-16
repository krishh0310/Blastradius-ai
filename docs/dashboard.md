# Phase 6: incident workspace

## Run in VS Code / macOS zsh

```zsh
cd "/Users/krish/Documents/graph hack/blastradius-ai"
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d --wait
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501. The .streamlit/config.toml file provides the local dark
theme and disables usage telemetry. It is not deployment configuration.

Select a scenario, optionally adjust component/depth/health assumption, then
Investigate. A component selector supports native type-to-search. Incident notes
are analyst context, not an agent command: component and health controls determine
the graph investigation. Notes never enter provider prompts. Known configured
keys are redacted from notes in downloadable investigation results.

The eight metrics summarize the last completed investigation. Changing controls
does not silently change its results. A notice asks you to Investigate again.
The nine tabs expose executive facts, the interactive graph, directed paths,
cause candidates, bottlenecks, business context, runbooks/actions, raw typed graph
evidence, and parameterized Cypher examples.

## Scenario semantics

| Scenario | Graph component | Assumption |
| --- | --- | --- |
| Token Vault timeout | vault | failed |
| Orders Database latency | orders-db | degraded |
| Mumbai region outage | mumbai | failed regional deployment exposure |
| External payment API degradation | bank-api | degraded |
| Optional analytics dependency failure | analytics | failed |

Component scenarios call the existing investigator, analytics, and grounded report
services. Graph health is never mutated by a scenario. Provider rendering defaults
to deterministic; the separate Use configured LLM checkbox enables a provider call
on the next Investigate only. Existing provider timeout/fallback configuration
applies. Actual provider/model and fallback warnings are visible.

The existing analytics module scores operational components, not entire regions.
The Mumbai view joins stored DEPLOYED_IN relationships to existing dependency
traversals. It distinguishes single-region deployments from healthy alternates.
Regional metric cards explicitly show a worst-case single-region component-failure
envelope (for this fixture, Token Vault), not a new regional risk formula.
Regional root-cause candidates likewise refer to that labeled envelope component.
No provider is invoked for this regional exposure view. This composition does not
claim a globally failed service merely because one deployment region is unavailable.

## Graph semantics and accessibility

Plotly renders NetworkX's seeded spring layout. Stored arrows point consumer to
provider. Impact walks may follow the opposite direction. Hover shows node type,
recorded status, owner, criticality, region, evidence hop count, and impact role.
Owner/deployment hover facts can come from the full loaded graph snapshot even
when those context edges are absent from the selected evidence subgraph.

Failed-scenario focus is red; degraded focus and critical service exposure are
orange. Potential impact is yellow and healthy/context service nodes green.
Database/customer/team/API fills preserve purple/blue/cyan/gray identity, while
their borders show impact. Shapes distinguish types independently of color.
Red thick edges mark critical paths; dashed edges are optional. A textual legend
remains visible even when filters hide every node.

Filters cover node type, impact role, evidence hops, and selected path. Dense
graphs hide node labels but preserve hover. Display is capped at 180 nodes and
300 edges with a visible truncation notice; the complete evidence tables remain
available. Empty/single-node/all-filtered graphs have explicit safe states.
The dark theme uses high-contrast text, native labeled controls and help,
visible focus outlines, responsive wrapping, and reduced-motion CSS. Nine tabs
scroll horizontally at narrow widths; metric values can wrap.

## Performance and safety

- app.py only launches the presentation module.
- dashboard_service.py composes existing investigation/analytics/report operations;
  it does not replace their scoring, ranking, provider, or path logic.
- Read-only graph snapshots have a 45-second cache, keyed by host/port/graph.
  Status is labeled as the last read, not live telemetry.
- Prepared graph metrics and bottleneck rankings are cached by safe graph JSON
  and depth. No settings object, connection, API key, or provider response enters
  shared Streamlit caches.
- Session results retain their original snapshot, depth, and timestamp until a new
  investigation or refresh. Graph filters run in a Streamlit fragment. Cosmetic
  interactions do not repeat provider calls or expensive analytics.
- Refresh graph invalidates the snapshot and clears the completed investigation.
  Reset clears workspace controls/results without deleting database data.
- Seed Demo Graph requires confirmation, uses the existing validated idempotent
  seeder, and disables after successful seeding in that session. Reset does not
  bypass this lock. Seeding merges fixture properties, so use a dedicated demo
  graph. The UI has no destructive graph-reset action.
- Errors expose a recovery message, not stack traces, headers, or keys. Diagnostic
  queries are displayed examples; no arbitrary query execution is offered.

## Verification

```zsh
FALKORDB_INTEGRATION=1 python -m pytest -q
python -m compileall -q src tests app.py
python -m pip check
```

Tests cover all five scenarios using Streamlit AppTest, all nine tab bodies,
live FalkorDB scenario rendering, context-only/empty/error states, graph bounds,
optional edge styling, critical paths, filter reruns, reset, secret redaction,
and one-time confirmed seeding. Existing backend tests remain in the full suite.

Manual visual checklist: open each scenario, Investigate, visit all nine tabs,
filter to no nodes, inspect a path and its directed edges, reset, then repeat at
wide and narrow browser sizes. Browser access was not approved during this
session, so screenshot-level wide/narrow inspection could not be completed.
