# BlastRadius AI

Phase 8 adds security regression tests, bounded operations, local-only services,
Ruff formatting/linting, coverage enforcement, and repeatable security checks.
See [hardening and verification](docs/hardening.md) for exact commands and limits.

BlastRadius AI is an explainable cloud dependency investigation agent. Phase 1
provides validated environment configuration, local FalkorDB infrastructure, a
reusable database manager, a CLI health check, and a minimal Streamlit status
page. Phases 2–5 add graph data, typed investigations, explainable analytics, and
optional graph-grounded reports. Phase 6 adds the dark incident workspace with
interactive graph evidence, five demo scenarios, and nine investigation tabs.

## Streamlit dashboard

```zsh
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d --wait
python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501, choose Token Vault timeout, and select Investigate.
See [dashboard guide](docs/dashboard.md) for scenario semantics, caching, seeding
confirmation, visualization controls, and test commands.

## Cascade simulation

Phase 7 adds a separate **Cascade simulation** workspace with deterministic
playback, an evidence-backed incident timeline, fictional mitigation, and
before/peak/after comparison. It makes no topology or infrastructure changes.
See [simulation rules and demos](docs/simulation.md).

```zsh
python -m src.simulator --component vault --mitigation "Execute fictional runbook"
python -m src.simulator --component payment --no-failover --mitigation "Activate regional replica"
```

Phase 2 adds the fictional infrastructure fixture, idempotent importer, and live
graph integrity checks. See [graph schema](docs/graph-schema.md) for directions,
ownership rules, demonstration queries, and reset limitations.

```zsh
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d --wait
python -m src.seed
python -m src.seed
python -m src.seed --validate
FALKORDB_INTEGRATION=1 python -m pytest -q
```

Explicit destructive reset of only the selected graph's Component nodes:

```zsh
python -m src.seed --reset --confirm-reset blast_radius
```

## Phase 3 investigation

See [investigation API and evidence semantics](docs/investigation.md).

```zsh
python -m src.investigator --component "Token Vault" --depth 6
python -m src.investigator --component "Orders Database" --depth 6 --json
FALKORDB_INTEGRATION=1 python -m pytest -q
```

## Prerequisites

- macOS with Docker Desktop
- Python 3.12
- VS Code with the Python extension

## Analytics and grounded reports

See [scoring, root-cause evidence, provider setup, and grounding rules](docs/analytics-and-reports.md).

```zsh
python -m src.analytics --component "Token Vault" --status failed
python -m src.reports --component "Token Vault" --status failed --deterministic
python -m src.reports --component "Token Vault" --status failed --json
```

The analytics CLI prints the five highest-risk components under a common
hypothetical failure assumption. Reports use the configured provider and fall back
to templates if generation fails. Cross-provider fallback requires an explicit
LLM_FALLBACK_ENABLED=true setting.

## Setup

Run these commands from `blastradius-ai` in a zsh terminal:

```zsh
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
docker compose up -d
```

The database listens on `localhost:6379`. FalkorDB Browser is available at
<http://localhost:3000>. The named Docker volume `falkordb-data` preserves data
between container restarts.

Do not add real API keys to source files. Export GEMINI_API_KEY or GROQ_API_KEY
in your terminal environment; keys in .env are ignored. The .env file remains
Git-ignored for nonsecret configuration. No API key is needed while
LLM_PROVIDER=deterministic.

## Verify and run

```zsh
python -m src.health
python -m pip install -r requirements-dev.txt
python -m pytest
streamlit run app.py
```

In VS Code, open the `blastradius-ai` directory and select
`blastradius-ai/.venv/bin/python` with **Python: Select Interpreter**. Use the
integrated terminal for the commands above.

Stop FalkorDB without deleting its persistent volume:

```zsh
docker compose down
```

To inspect container status and logs:

```zsh
docker compose ps
docker compose logs falkordb
```

## Phase 1 layout

```text
app.py                 Thin Streamlit dashboard entry point
src/config.py          Validated environment settings
src/database.py        FalkorDB connection and query manager
src/health.py          CLI and structured health report
tests/test_database.py Configuration, database, and health tests
docker-compose.yml     Local FalkorDB and persistent volume
```
