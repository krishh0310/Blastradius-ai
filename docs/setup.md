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
