# Phase 8: security and reliability

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
complete secret detector and does not inspect Git history. If Git metadata is
absent, it explicitly reports that committed-secret verification is unavailable.
Previously exposed credentials must be revoked, not just removed from files.

`pip-audit` checks known Python advisories at execution time; a clean result does
not prove the absence of undisclosed vulnerabilities. Container/OS CVEs are not
covered by that scan. Image updates require a new digest and regression tests.
Cloud availability, real provider credentials, and production security are not
certified by mocked provider tests. No deployment is included in this phase.

## Verified results — 2026-10-16

- Fresh Python 3.12 environment: declared development dependencies installed;
  `pip check` passed.
- Full suite with `FALKORDB_INTEGRATION=1`: **129 passed, zero skipped**;
  **88.37% source statement coverage**. Coverage is not branch-complete.
- Ruff lint and formatting, compileall, and Bandit passed. The secret-check
  script has two narrowly documented Bandit suppressions for its constant,
  shell-free local Git command.
- `pip-audit` in both existing and fresh environments: no known vulnerabilities.
- Source secret scan: zero findings; Git tracking/history unavailable because
  this workspace has no Git metadata.
- Compose validation passed. After saving and recreating the container, FalkorDB
  became healthy and retained **54 nodes / 141 relationships**, with zero graph
  integrity errors. The intentional dependency cycle remains present.
- Fresh-environment Streamlit started on loopback port 8502; its health endpoint
  returned HTTP 200 / `ok`. UI behavior was checked by the full AppTest suite;
  no new manual browser/viewport inspection was performed in this phase.

## Files changed

Created:

- `pyproject.toml`
- `requirements-dev.txt`
- `.pre-commit-config.yaml`
- `scripts/check_secrets.py`
- `tests/conftest.py`
- `tests/test_hardening.py`
- `tests/test_smoke.py`
- `docs/hardening.md`

Modified for hardening, callers, or documentation:

- `.gitignore`
- `.streamlit/config.toml`
- `docker-compose.yml`
- `README.md`
- `src/config.py`
- `src/database.py`
- `src/graph_queries.py`
- `src/seed.py`
- `src/topology.py`
- `src/simulator.py`
- `src/analytics.py`
- `tests/test_database.py`
- `tests/test_topology.py`

Formatting/import cleanup only:

- `src/dashboard_service.py`
- `src/dashboard_ui.py`
- `src/investigator.py`
- `src/providers.py`
- `src/reports.py`
- `src/simulation_ui.py`
- `src/visualization.py`
- `tests/test_analytics.py`
- `tests/test_dashboard.py`
- `tests/test_investigator.py`
- `tests/test_reports.py`
- `tests/test_simulator.py`

The local `.env`, sample topology, and existing volume were preserved. No project
source files were removed. Test coverage/cache artifacts are Git-ignored.
