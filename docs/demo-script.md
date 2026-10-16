# Three-minute demonstration package

Target timings, not a claim that a presenter has been recorded or user-tested.
Rehearse with a timer. All infrastructure, customers, incidents, transitions and
mitigation outcomes shown are fictional. Software benchmark timings are separate.

## Before going on stage

Run the [setup and verification](setup.md), seed/validate, then leave the app open
in Investigation with Token Vault timeout selected. Keep **Use configured LLM**
off. Test Docker and power/sleep settings before presenting. Close secret-bearing
terminals and private tabs. Do not seed/reset during the timed presentation.

The seeded topology is not entirely healthy: Orders Database is deliberately
degraded. Token Vault is recorded healthy; failure is a what-if assumption.
Only the simulator uses an explicitly fictional all-healthy initial baseline.

## Main demonstration — 0:00 to 3:00

| Time | Screen action | Spoken focus |
|---|---|---|
| 0:00–0:20 | Landing preview | “A single shared dependency can silently disrupt services, workflows and customers several hops away. During an outage, teams lose time reconstructing that chain.” |
| 0:20–0:45 | Point to recorded fictional topology and Token Vault scenario | “This is a local fictional commerce platform, not a live cloud account. Token Vault is shared by authentication, payments and subscriptions. Let's investigate a hypothetical timeout.” |
| 0:45–1:15 | Click **Run Demo** once; show cards and engine | “FalkorDB resolves bounded dependency paths. The heuristic exposure score is 91.62, Critical, with six potentially exposed customers. These are graph-supported what-if impacts, not confirmed outages or outage probabilities.” |
| 1:15–1:40 | Point to visible customer path, then open executed Cypher receipts | “A direct lookup sees three dependents. This path reaches Subscription, a renewal workflow and Atlas. Every edge keeps its stored type and direction. Ownership is a separate supported branch. SQL could express this recursively; the graph makes the relationships and evidence direct.” |
| 1:40–2:05 | Click **Simulate Mitigation**; build/replay cascade; inspect one event | “These are deterministic presentation steps, not measured outage timings. This event names its supporting relationship. Required dependencies propagate; optional ones have reduced behavior.” |
| 2:05–2:30 | Select fictional **Isolate unhealthy dependency**, then simulate | “Assuming containment works, the settled score changes from 91.62 to 42.62 and 18 critical impact paths are no longer active. We did not execute a command or change the database.” |
| 2:30–2:45 | Return to Investigation; optional analytics scenario; Investigate | “Optional analytics failure scores 27.23, Medium, versus the required shared dependency. The difference comes from graph evidence and the visible scoring factors.” |
| 2:45–3:00 | Show actual deterministic provider label and audience briefing | “The graph remains useful without an LLM. Optional providers prioritize verified evidence for different audiences; they cannot invent infrastructure or confirm causation. Capacity, freshness and live telemetry remain unknown.” |

Scores refer to the verified fixture and unchanged formula. If the graph changes,
read the actual displayed values rather than reciting stale numbers. With this
fixture the maximum returned impact path includes seven hops; dependency controls
and extra business-context hops are different budgets.

Skip detailed tabs during the main demo. Never race a cloud-provider timeout on
stage. If time is short, show one customer path and one mitigation, not all scenarios.

## 30-second pitch

“BlastRadius AI answers a practical outage question: if this shared dependency
fails, which services, workflows and customers are exposed—and why? FalkorDB
returns the actual multi-hop paths. NetworkX finds structural bottlenecks; Python
explains a heuristic score. We can replay a fictional cascade and compare safer
containment assumptions without touching real infrastructure. Optional AI turns
verified evidence into role-specific briefings. No model invents the topology,
and the investigation still works offline without an LLM.”

## One-minute technical explanation

“The fictional topology lives in FalkorDB with typed dependencies, ownership,
deployment, workflow and customer relationships. Native parameterized Cypher
retrieves bounded incident paths and complete cross-domain customer chains.
Depth is allowlisted, results capped and server queries timed out. Returned
evidence preserves direction and parallel-edge properties. Required, critical,
unhealthy edges win evidence ties, without deleting other relationships.
NetworkX receives a bounded global projection for centrality, PageRank,
articulation points and connected components. Python composes those facts into
an explained exposure score and candidate ranking—not causal proof.
The provider can select validated claim IDs and prioritize supplied options;
unsupported references fall back to templates. The simulator is in-memory and
deterministic. The clean-room suite passed 166 tests with 88.97% statement
coverage; real provider calls and manual visual checks remain separately unverified.”

## Five-minute extended demonstration

- 0:00–0:45: Problem, fictional-data disclaimer, direct lookup versus relationships.
- 0:45–1:30: Native FalkorDB paths versus cached NetworkX analytics; show engine.
- 1:30–2:20: Token Vault, customer chain, stored arrows, required/optional evidence.
- 2:20–3:00: Risk factor breakdown and candidate-confidence limits. Optionally show
  Orders Database's recorded degradation and incident association.
- 3:00–3:50: Cascade, event evidence, fictional isolation comparison and reset.
- 3:50–4:20: Optional analytics and declared regional failover. Mumbai's score is
  a worst-case component envelope, not an independent regional model.
- 4:20–5:00: Change briefing audience, show claim/path IDs and deterministic
  provider label; finish with limits, measured software timing and next steps.

## Fifteen likely judge questions

1. **Why FalkorDB instead of PostgreSQL?** SQL can implement recursive traversal.
   Here changing, mixed-type, cyclic relationships and exact path provenance are
   first-class. We measured no SQL speed comparison and claim none.
2. **What executes inside FalkorDB?** Incident-specific dependency paths,
   full workflow/customer paths, metadata/deployment/replica retrieval and bounded
   closed walks. Python validates/selects returned paths; it does not invent edges.
3. **Why retain NetworkX?** Global structural algorithms are different from
   incident retrieval. Its bounded projection computes centrality, PageRank,
   articulation and connected components without claiming they run in Cypher.
4. **How are parallel relationships handled?** Original typed edges are retained.
   A shared evidence policy prefers required, higher criticality, unhealthy status,
   then stable type/identity. Regressions cover optional reads versus required writes.
5. **How do you prevent hallucinations?** Factual fields must match a verified
   catalog. New role narratives reference known claim IDs, approved options and
   supplied simulation data. Invalid entities, references or numbers are rejected.
   This is constrained generation, not proof that arbitrary natural language is safe.
6. **What confirms a root cause?** Reachability and health do not. Independent
   telemetry, validated change/incident evidence and human investigation would be
   needed. This demo emits candidates, never confirmed causal diagnoses. A Critical
   what-if exposure score can coexist with insufficient evidence of actual cause.
7. **Why these weights?** They are documented demonstration heuristics, not learned
   probabilities. Every factor is visible. Production calibration would require
   real incident outcomes and operator validation, which we have not collected.
8. **What if the topology is stale?** Snapshot time is shown. Observed native/cache
   mismatch triggers a consistent labeled snapshot fallback and a refresh warning.
   Reads are not transactionally isolated; unseen changes may remain undetected.
9. **Does a replica prove failover?** No. The graph establishes a declared alternate
   and recorded health, not spare capacity, freshness or successful traffic routing.
10. **How would AWS/Azure/GCP data enter?** Future read-only inventory/tracing
    adapters would map stable IDs into this validated schema, track timestamps and
    provenance, and require explicit permissions. None are implemented here.
11. **What works without an LLM?** Native retrieval, analytics, scoring, path
    evidence, reports, visualization and simulation. Missing keys were tested via
    the real report CLI; provider tests use mocks.
12. **What prevents destructive remediation?** There is no cloud executor.
    Simulations alter copied in-memory state only. Explicit graph resets require
    exact graph-name confirmation; normal demos use nondestructive merges.
13. **How do cycles and limits work?** Simple impact paths never repeat a node;
    depth is 1–8, results bounded, queries timed out. Structural cycle walks use
    an independent eight-hop bound; longer cycles may be omitted. Warnings are shown.
14. **Why is Mumbai's score the same as Token Vault?** It is the worst-case
    single-region component envelope in this fixture, not a separate regional risk
    formula. The UI labels that scope; regional exposure alone is not global failure.
15. **What did you actually measure?** Local warm-graph software timings over
    20 runs after two warm-ups: native blast query median 3.786 ms, no-LLM pipeline
    32.130 ms. UI/startup/global snapshot download/provider time are excluded.
    No operator study, real outage recovery, Linux CI run or provider success was measured.

## Backup plans

| Failure | Honest response |
|---|---|
| Internet fails mid-demo | Use installed dependencies and local Docker graph with deterministic reporting. Initial downloads still need connectivity. |
| Groq quota/auth/downtime | Show the sanitized failure/fallback label; uncheck provider use and reinvestigate. Do not claim Groq generated a template. |
| Gemini unavailable | Same deterministic route; do not silently change cloud providers or claim success. |
| Ollama not running/model absent | Do not download a model on stage. It is optional; use deterministic mode. |
| FalkorDB stopped | Start Docker Desktop, then `docker compose up -d --wait`, health and validation. No reset. Cached/exported evidence must be labeled recorded, not fresh. |
| Container cannot recover within time | Use a previously recorded real app walkthrough or sanitized exports, explicitly identifying them as recordings. Never fabricate a live success. |

## Claims that must not be made

- “This will win” or an externally validated 92–95 score.
- “SQL cannot do this” or an unmeasured speedup over PostgreSQL.
- “Production monitoring”, “live cloud telemetry”, or real AWS/Azure/GCP integration.
- Confirmed causation, calibrated outage probability or invented error-rate thresholds.
- Verified replica readiness, recovery capacity or measured outage timings.
- Real remediation execution or a successful cloud-provider call that did not happen.
- “All reasoning runs in FalkorDB”; global NetworkX and Python formatting are explicit.
- “All paths/impacts are complete” after hitting a limit or outside the stated budgets.
- Real screenshot/manual viewport verification when only AppTest was used.
- A successful GitHub CI badge before the actual workflow has run.

Use the [submission-day checklist](submission-checklist.md) and
[final validation evidence](final-validation.md) before recording or submitting.
