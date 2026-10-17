# Security and reliability

The application remains a local, single-operator demo, not an authenticated public
service. Do not expose Streamlit, Redis, or the FalkorDB Browser to the internet.
Both Compose ports and Streamlit bind to loopback. The existing FalkorDB image is
pinned by digest and runs with `no-new-privileges`; its data directory remains on
the existing named volume. Redis snapshot persistence is not a production backup
or a guarantee against loss of the most recent writes during an abrupt failure.
Never run `docker compose down -v` against data you want to retain.

## Security boundaries

- API keys come only from process environment variables, are excluded from
  Pydantic serialization, and never enter database logs or provider URLs.
- Dotenv interpolation is disabled, preventing environment secrets from being
  substituted into nonsecret configuration. `.env` and `.env.*` are ignored;
  `.env.example` is intentionally allowed.
- Cypher values use parameters. The only dynamic labels/types are revalidated
  Pydantic allowlists, including when callers supply mutated model instances.
- Programmatic and CLI destructive resets require the exact graph name as
  confirmation. Normal dashboard seeding is nondestructive and requires its
  existing confirmation. Seeding is idempotent but not a cross-process transaction;
  use one seeding process at a time.
- Provider calls retain size limits, timeouts, no redirects/retries, explicit
  fallback selection, and exact evidence-catalog validation. Incident text cannot
  authorize infrastructure actions. Ollama HTTP is loopback-only; configuring an
  HTTPS remote Ollama endpoint deliberately sends the evidence there.
- Database failures use fixed public errors and structured `event`/`error_type`
  logs, without raw exception bodies or tracebacks. Streamlit error details are
  disabled; recoverable UI errors use existing friendly messages.
- Untrusted topology is JSON/Pydantic, never pickle/eval. Streamlit's internal
  application-generated cache is trusted; do not load external cache artifacts.

## Resource bounds

Topology files: 5 MB. Graph snapshots: 2,000 nodes / 10,000 relationships.
Traversal depth: 1–8. Each path operation: 500 returned paths / 20,000 edge
expansions. Simulation: at most 20,000 scheduled transitions, with an explicit
incomplete-result warning. Component lookup/search: 512 characters. Individual
topology strings: 4,096 characters; latency must be finite. Server queries time
out after 3 seconds; connection and socket limits are 3 and 5 seconds.
Shortest-path lookup now uses breadth-first search rather than enumerating all
paths. Expensive analytics still scale with graph size; these limits are suitable
for the demo, not an internet-facing multi-tenant workload.

## Repeatable checks (macOS / VS Code terminal)

```zsh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
docker compose up -d --wait
python -m src.health
python -m src.seed --validate
FALKORDB_INTEGRATION=1 python -m pytest
ruff check .
ruff format --check .
python -m compileall -q src tests scripts app.py
bandit -r src scripts -q
pip-audit --cache-dir .audit-cache --progress-spinner off
python scripts/check_secrets.py
python -m pip check
python -m streamlit run app.py
```

Pytest enforces 80% source coverage and writes `coverage.xml`. Unit tests need
no credentials or database. Opt-in integration tests create uniquely named test
graphs and delete only those graphs; the read-only end-to-end smoke test uses the
selected seeded graph and verifies it remains unchanged. Existing Streamlit
AppTests cover all five scenarios, empty/single-node plots, error states, seeding
confirmation, reruns, and simulation playback. Provider tests mock every call.

For a fresh setup, create a new Python 3.12 virtual environment, install
`requirements-dev.txt`, copy `.env.example` only if `.env` does not already exist,
then run Compose, health, seed (without reset), and the checks above.
Optional local pre-commit hooks are supplied; install `pre-commit` and run
`pre-commit install` only after initializing/using your intended Git repository.
No hooks are installed automatically.

## Audit limitations

The secret scanner reports locations, never values. It checks recognizable key
formats, currently exported provider keys, and tracked dotenv files. It is not a
complete secret detector. Use `python scripts/check_secrets.py --history` to
add scanning of locally reachable Git commits; the default scans current files. If Git metadata is
absent, it explicitly reports that committed-secret verification is unavailable.
Previously exposed credentials must be revoked, not just removed from files.

`pip-audit` checks known Python advisories at execution time; a clean result does
not prove the absence of undisclosed vulnerabilities. Container/OS CVEs are not
covered by that scan. Image updates require a new digest and regression tests.
Cloud availability, real provider credentials, and production security are not
certified by mocked provider tests. No deployment is included in this phase.

## CI and grounded provider boundary

The [quality workflow](../.github/workflows/quality.yml) installs development
requirements on Python 3.12 and checks Ruff, formatting, compileall, pytest with
80% coverage enforcement, Bandit, current/history secrets and pip consistency.
Provider keys are not required. Checkout uses read-only contents permissions and
does not persist credentials. There is no deployment or publication step.

Disposable integration is a manual workflow_dispatch input: the graph is
ci_<run_id>_<attempt>, never the development graph; importer tests use their own
unique graph names. Local tests are not proof of a remote CI run or passing badge.
For executed outcomes and advisory-scan dates, see [final validation](final-validation.md).

Reports validate a graph-generated catalog of facts, entities, numbers, paths,
severity, actions and unknowns with Pydantic plus exact catalog membership.
Providers may prioritize known claim IDs/action/question indices for three roles
and compare supplied fictional mitigation outcomes; they cannot introduce prose
facts or new numbers. Rejected text is not echoed, and raw incident notes and
timings never enter provider prompts. No model repair call improvises missing facts.

Each selected provider gets one bounded attempt; cross-provider fallback requires
LLM_FALLBACK_ENABLED=true. Otherwise only the active provider is attempted before
the deterministic template. Requests are limited to 300 KB, responses to 1 MB,
output to 8,192 tokens, and socket timeout defaults to 20 seconds (at most 120).
Known keys are checked against outgoing evidence and final reports; this does not
make arbitrary secrets safe to store in graph descriptions. No provider runs
queries, tools, shell commands or infrastructure actions.

[Provider setup](setup.md#provider-setup) and [README configuration](../README.md)
cover Gemini, Groq and Ollama. Groq's documented compatibility URL contains
/openai/v1 but uses no OpenAI service, SDK, model or key. Protocol references:
[Gemini](https://ai.google.dev/api/generate-content),
[Groq](https://console.groq.com/docs/api-reference),
[Ollama](https://docs.ollama.com/api/chat).

## Verification status

The [MCP boundary](mcp-tooling.md) accepts only eleven typed tools, fixed component
syntax, strict depth/path limits and no extra arguments. It exposes no arbitrary
Cypher, shell, Python or cloud executor. The agent caps calls at eight, blocks
duplicates and keeps incident prose out of provider tool-selection prompts.
[Action gates](graph-gated-actions.md) recheck supporting edges after consent;
simulation is in-memory only. An external MCP host must supply its own trusted
human-confirmation UI: a caller-supplied boolean is not remote authentication.
Local stdio is a trusted single-operator boundary, not a public service.
MCP workers do not receive provider keys, and results are sanitized/size-capped.
Per-call snapshots are not transactionally consistent across a whole incident.

[Final validation](final-validation.md) is the canonical dated record for tests,
coverage, live-provider attempts, screenshots, graph integrity and unverified
checks. This document states security boundaries, not a production certification.
