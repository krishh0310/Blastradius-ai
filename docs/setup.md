# Canonical local setup (macOS, zsh, Python 3.12)

Prerequisites: Python 3.12 on PATH, Docker Desktop running with Compose v2, Git,
and optionally VS Code's Python extension. Apple Silicon is supported. Install
Python through your chosen distribution; Homebrew users can use
`brew install python@3.12` and follow its PATH instructions. No fixed Homebrew
path is required. Open the repository root (containing `app.py`) in your terminal.
Check `python3.12 --version`, `docker version`, and `docker compose version`.

## Development and tests

```zsh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
test -e .env || cp .env.example .env
docker compose up -d --wait
python -m src.health
python -m src.seed
python -m src.seed --validate
python -m pytest
python -m streamlit run app.py
```

Seed before validating an empty graph. Normal seed is an idempotent merge, not a
reset. The dotenv command does not overwrite existing configuration.
`requirements-dev.txt` includes runtime requirements and adds quality tools,
including pytest-cov. Install it before invoking pytest with this project's config.
VS Code: select `.venv/bin/python` using **Python: Select Interpreter**.
Dashboard: http://127.0.0.1:8501; Browser: http://127.0.0.1:3000.

## Run-only installation

Use the same environment/Docker/seed commands, but install
`python -m pip install -r requirements.txt`. This runs the application, not the
configured quality checks. No key is required for deterministic reporting.
Keys come only from the process environment; `.env` contains nonsecret settings.

## Verification

The official MCP SDK is included in requirements.txt. After activating the
environment and seeding FalkorDB:

```zsh
python -m src.agent --component 'Token Vault' --depth 6
python -m src.agent --component 'Orders Database' --depth 6 --json
```

For a separate MCP host, see [local MCP configuration](mcp-tooling.md) and
`mcp.example.json`. `python -m src.mcp_server` waits for MCP stdio requests;
it is not a human-readable CLI. The dashboard launches its own local server.
No provider key is sent to that worker. See [trace and consent](agent-tool-trace.md).

```zsh
python -m pip install -r requirements-dev.txt
python -m pip check
ruff check .
ruff format --check .
python -m compileall -q src tests scripts app.py
python -m pytest
FALKORDB_INTEGRATION=1 python -m pytest
bandit -r src scripts -q
python scripts/check_secrets.py
pip-audit --cache-dir .audit-cache --progress-spinner off
```

Integration tests read the selected seeded graph for parity and use uniquely
named disposable graphs for importer tests. Do not target valuable/production data.

## Troubleshooting

| Symptom | Safe next step |
|---|---|
| Docker unavailable | Start Docker Desktop; wait for `docker version` to show a server. |
| Port 6379 occupied | Inspect `lsof -nP -iTCP:6379 -sTCP:LISTEN`. Do not kill unknown processes. Change the Compose host port and matching FALKORDB_PORT if necessary. |
| Port 3000 occupied | Inspect `lsof -nP -iTCP:3000 -sTCP:LISTEN`; choose another Compose browser host port. Database connectivity is separate. |
| Empty graph | Run health, seed without reset, validate, then refresh the UI graph. |
| Missing key | Use deterministic mode or privately export the provider key. Keys in `.env` are deliberately ignored. |
| Quota/auth/model failure | Read sanitized grounding warnings; verify the account/model manually. Deterministic fallback still works. |
| Ollama unavailable | Start Ollama, run `ollama pull qwen3:8b`, and check URL/model settings. Optional for this app. |
| Image pull failure | Check Docker internet access, architecture support and disk space; retry the pinned image. Do not silently substitute an unverified tag. |
| Unrecognized --cov arguments | Activate the correct environment and install requirements-dev.txt. |
| Native query unavailable | UI explicitly labels bounded Python fallback. Refresh health/graph; CLI fails clearly. |
| Stale metrics | Refresh graph. Safe snapshots cache for 45 seconds; completed results retain their own snapshots. |

`docker compose down` retains the named volume. Do not add `-v` unless deliberately
discarding that data. No reset is needed for setup or verification.

## Investigation, reporting and simulation commands

After completing the development setup above:

```zsh
python -m src.investigator --component "Token Vault" --depth 6 --json
python -m src.analytics --component "Token Vault" --status failed
python -m src.reports --component "Token Vault" --status failed --deterministic
python -m src.simulator --component vault --mitigation "Isolate unhealthy dependency"
python -m src.simulator --component payment --no-failover --mitigation "Activate regional replica"
python -m src.simulator --component mumbai --json
```

An explicit status is hypothetical; omitting it in analytics/reports uses recorded
health. Simulator CLI uses exact IDs. `--json` produces structured evidence.
No provider is required for graph queries, analytics or simulation.

In Streamlit, Run Token Vault Demo → View FalkorDB Evidence → Simulate Mitigation
computes the deterministic result, opens query receipts, then prepares fictional
containment. The separate simulator supports Build cascade, Play/Pause, Next step,
Reset simulation and speed controls. Reset discards mitigation and returns to
frame zero. Changed simulation inputs require rebuilding. Playback advances
precomputed frames, not real cloud time.

Controls retain the last completed investigation until Investigate/refresh;
changing controls alone does not change its facts. Snapshots cache for 45 seconds,
and results retain their originating snapshot/depth/time. Refresh invalidates
the snapshot/result. Display caps are 180 nodes / 300 edges with a notice; complete
bounded evidence remains in tables. Shapes, arrows, text labels and dashed optional
edges supplement color. Empty/single-node/filter-empty states are supported.

## Provider setup

Choose deterministic, gemini, groq or ollama through LLM_PROVIDER. Keep API keys
only in process environment variables; keys placed in .env are ignored. Nonsecret
models/URLs/timeouts load from .env or environment; see .env.example and README.
For cloud reporting, privately export GEMINI_API_KEY or GROQ_API_KEY, select that
provider, then opt in using the UI checkbox or the reports CLI. Only fictional
graph evidence is sent; do not store secrets in topology properties.

```zsh
export LLM_PROVIDER=gemini
read -rs "GEMINI_API_KEY?Gemini API key: "
export GEMINI_API_KEY
python -m src.reports --component "Token Vault" --status failed
```

For Groq, use LLM_PROVIDER=groq and privately read/export GROQ_API_KEY instead.
If authentication fails, the existing credential or its permissions must be fixed
in [Groq Console](https://console.groq.com/keys); changing application code cannot
make a rejected credential valid. Replace/revoke an invalid key privately and use
the same Terminal session to launch the app. Do not paste keys into chat, source,
shell command history or screenshots. The zsh `read -rs` prompt hides input:

```zsh
source .venv/bin/activate
read -rs "GROQ_API_KEY?Groq API key: "
export GROQ_API_KEY
printf '\n'
export LLM_PROVIDER=groq
export LLM_FALLBACK_ENABLED=false
docker compose up -d --wait
python -m src.reports --component "Token Vault" --status failed
```

Check the **actual** report provider and grounding warnings. Deterministic output
is not evidence of cloud success. To return to offline reporting, select
`LLM_PROVIDER=deterministic`. Environment exports in a separate Terminal do not
retroactively update an already-running app or coding-assistant process; restart
the app from that same configured Terminal. No real key is stored by these commands.

For local reporting, run `ollama pull qwen3:8b`, start `ollama serve`, then select
LLM_PROVIDER=ollama; OLLAMA_BASE_URL defaults to http://localhost:11434.
Inspect actual provider/model and grounding warnings: HTTP success alone does
not establish a validated report. The last Groq attempt failed authentication and
safely returned deterministic; Gemini/Ollama live success remains unverified.
