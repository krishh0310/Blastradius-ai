# Phases 4 and 5: analytics and grounded reports

## Graph-grounded incident briefings

Providers now select evidence IDs for three audiences: incident commander,
service owner and business stakeholder. They can prioritize known claims,
approved action indices and validation questions, and compare two supplied
fictional mitigation outcomes. The UI reconstructs each concise narrative from
validated statements and displays claim/path IDs. Main factual report fields
remain exact-catalog validated. This is deliberate constrained editing, not
unrestricted prose generation or autonomous diagnosis.

Mitigation scores come from the deterministic simulator, explicitly assuming a
fictional healthy starting baseline. They are not measured recovery predictions.
Unknown entities, references, numerical indices and missing audiences cause safe
fallback. Arbitrary additional text/numbers are rejected by the response schema.
All provider tests are mocked. No external request is made by validation scripts.

Manual opt-in cloud verification, only if you authorize sending fictional graph
evidence to Groq and using your configured quota:

```zsh
# Export GROQ_API_KEY privately; never paste it into a tracked file.
LLM_PROVIDER=groq python -m src.reports --component 'Token Vault' --status failed --json
```

Check the returned `provider` and `grounding_warnings`: successful HTTP alone is
not verified grounded-provider success. A deterministic provider value means the
cloud output did not pass the complete validation boundary.

FalkorDB remains authoritative. Analytics reads Phase 3's bounded database snapshot;
NetworkX computes operational dependency metrics. Reports never execute graph
queries, tools, shell commands, or remediation actions.

## Run

```zsh
# Run from the repository root after docs/setup.md.
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
docker compose up -d --wait
python -m src.analytics --component "Token Vault" --status failed
python -m src.analytics --component "Orders Database" --status degraded --json
python -m src.reports --component "Token Vault" --status failed --deterministic
python -m src.reports --component "Token Vault" --status failed --deterministic --json
FALKORDB_INTEGRATION=1 python -m pytest -q
python -m compileall -q src tests app.py
```

An explicit status is a hypothetical scenario, not a graph mutation. Omitting
--status uses recorded health. The five-component bottleneck ranking compares
the same hypothetical failed status for every operational component. It is an
exposure ranking, not a list of actual outages.

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

Cycle groups, path counts, and impacts inherit Phase 3 traversal limits and
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
otherwise Insufficient evidence. The model supports Confirmed, but this phase
never assigns it because the schema has no explicit confirmed causal relationship.
AFFECTS alone confirms neither causality nor historical chronology.

## Provider configuration

The default is deterministic. Choose one provider with LLM_PROVIDER:

```zsh
export LLM_PROVIDER=gemini
read -rs "GEMINI_API_KEY?Gemini API key: "
export GEMINI_API_KEY
python -m src.reports --component "Token Vault" --status failed
```

Or use Groq:

```zsh
export LLM_PROVIDER=groq
read -rs "GROQ_API_KEY?Groq API key: "
export GROQ_API_KEY
python -m src.reports --component "Token Vault" --status failed
```

Keys are read only from process environment variables. Keys in .env are ignored.
Nonsecret configuration still loads from .env, with process environment taking
precedence. Keys are excluded from Settings repr, serialization, error display,
evidence, reports, and logs; they travel only in the selected provider auth header.
No real keys are written by the application.

| Variable | Default / purpose |
| --- | --- |
| LLM_PROVIDER | deterministic; select gemini, groq, ollama, or deterministic |
| GEMINI_API_KEY | Environment only; required for Gemini |
| GEMINI_MODEL | gemini-2.5-flash |
| GROQ_API_KEY | Environment only; required for Groq |
| GROQ_MODEL | llama-3.3-70b-versatile |
| OLLAMA_BASE_URL | http://localhost:11434 |
| OLLAMA_MODEL | qwen3:8b |
| LLM_TIMEOUT_SECONDS | 20; socket timeout, positive and at most 120 |
| LLM_FALLBACK_ENABLED | false; enables cross-provider fallback |

Gemini is the intended primary cloud option and Groq the secondary. With fallback
enabled, try the active provider once, then remaining providers in Gemini → Groq
→ Ollama order. Each provider gets at most one attempt; no automatic repair calls
or retry loop. Without fallback, only the active provider is attempted. Missing
keys, timeouts, auth failures, quota errors, unavailable models, downtime,
oversized responses, and malformed data yield a visible deterministic fallback.
Provider/model fields identify the actual report editor, not the failed attempt.

Optional local setup:

```zsh
ollama pull qwen3:8b
ollama serve
# In a second terminal:
export LLM_PROVIDER=ollama
python -m src.reports --component "Token Vault" --status failed
```

HTTP Ollama URLs are limited to loopback; remote endpoints require HTTPS.
Redirects are refused. Requests are capped at 300 KB, responses at 1 MB, and
outputs at 8,192 tokens. Gemini uses its native REST endpoint; Groq uses Groq's
own documented REST endpoint (its URL includes a compatibility /openai/v1 path,
but no OpenAI service, model, SDK, or key is used). Ollama uses /api/chat with
streaming disabled and qwen3 thinking disabled for structured output.

## Grounding boundary and structured output

EvidencePackage contains the matched component/status, upstream and downstream
claims, customers, workflows, regions, teams, runbooks, shortest/critical paths,
metrics, factor breakdowns, candidate causes, unknowns, nodes, and original edges.
Provider payloads remove repeated path properties, not unique evidence.

The graph generates an approved statement catalog and stable path IDs first.
Providers edit by prioritizing/reordering that catalog, rather than inventing
free-form infrastructure prose. ReportContent is Pydantic-validated; exact catalog
membership then checks every factual sentence, entity ID, citation, summary,
severity, action, and unknown. This catches invented statuses or metrics even
when an entity itself exists. All approved statements must remain present.
Raw incident text and elapsed-time values never enter provider prompts.

Malformed or unsupported outputs are discarded, with grounding_warnings stating
why the deterministic report was used. Rejected prose is not echoed back: it may
contain secrets or injection content. No repair model is asked to improvise facts.
Known configured keys are checked against prompts and final reports as an
additional guard; do not put unrelated secrets into graph descriptions or names.

IncidentReport includes executive_summary, severity, confirmed_facts,
likely_root_causes, affected_entities, supporting_paths, immediate_actions,
validation_steps, longer_term_recommendations, unknowns, provider, model,
grounding_warnings, and resolved evidence_paths. Statements carry entity IDs and
path IDs, preserving the graph's stored edge direction. Hypotheses remain
explicit even inside a structured report.

All provider tests mock the HTTP boundary. Real provider availability is not
required for graph investigations, analytics, deterministic reports, or tests.
Live Groq verification in this session returned an authentication failure and
correctly used the deterministic fallback; Gemini and Ollama have mock coverage.

Official protocol references:

- [Gemini generateContent](https://ai.google.dev/api/generate-content)
- [Groq chat completions](https://console.groq.com/docs/api-reference)
- [Ollama chat API](https://docs.ollama.com/api/chat)
