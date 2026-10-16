# Final clean-room validation

Date: **2026-10-16**. Tested application/source commit:
**e3096d580206f3b4b3701cb7ee35e209b2c63063**, branch
`improve/hackathon-final`. Subsequent submission documents do not change that
application source. This records executed checks, not inferred outcomes.

## Environment and isolation

- Python 3.12.14; macOS 26.6.2, arm64; Docker daemon 29.7.2.
- Fresh temporary virtual environment and `git archive` source copy, outside the
  working checkout. Development requirements installed successfully from that copy.
- Existing local Docker service/image cache reused; this was not a pristine VM,
  newly downloaded container image, or independent Linux/Windows test.
- The pinned Compose image, loopback bindings and health configuration validated.
- Provider keys removed from the clean-room process; LLM_PROVIDER=deterministic.
- New graph `phase10_clean_e3096d5` was confirmed absent before seeding. The
  development graph was not reset. Both idempotent seed runs returned 54 nodes,
  141 relationships and zero integrity errors. Explicit `src.seed --validate` passed.
- Development graph fingerprint was identical before/after:
  `1b99500fd8123366c63811198508f48a36a0636d27e8062d123375892bf61d71`.

The clean validation graph is intentionally left available, not destructively
deleted. Temporary environments/source copies remain local for reproduction.
No credentials, coverage reports, caches or temporary paths are committed.

## Executed results

| Check | Actual outcome |
|---|---|
| Fresh environment + declared development dependencies | Passed |
| pip check | No broken requirements |
| Compose configuration + existing service start/health | Passed; healthy |
| Seed twice + integrity + counts | Passed; 54 / 141 both times, zero errors |
| Complete pytest suite with live integration enabled | **166 passed, zero skipped**, 31.34 seconds |
| Source statement coverage | **88.97%**, 80% gate passed; not branch-complete coverage |
| Native/reference parity | Passed for five component cases × depths 1/6/8, including suggestions, shortest/critical paths, cycles, business/customer and metadata evidence |
| Parallel edges, ambiguity, optional paths, native truncation | Regression tests passed |
| Observed native/cache drift | New-node and changed-node tests passed; explicit consistent snapshot fallback |
| Ruff + formatting + compileall | Passed |
| Bandit | Passed; narrowly justified local-Git subprocess suppressions only |
| Python dependency audit | No known vulnerabilities reported |
| Archived source secret scan | Zero findings; no Git metadata in an archive is expected |
| Real repository current/history scan | Zero findings; no tracked dotenv beyond .env.example |
| Five deterministic scenarios | Passed, values below |
| Selected Gemini with both keys absent | Actual CLI returned deterministic, three roles, sanitized missing-key/fallback warnings; no external call |
| Streamlit launch from archived source | Passed on loopback; health endpoint HTTP 200 |
| All five scenarios / every tab | Automated Streamlit AppTest passed; not a manual browser inspection |
| Empty graph / single-node plot | Automated regression tests passed |
| Eight-hop simulation boundary | In-memory nine-hop probe: hop 8 down, hop 9 healthy, depth warning emitted; deterministic replay identical |
| Cascade reset / optional propagation / cycle handling | Automated tests passed |
| Fictional mitigation / declared replica comparison | Passed, values below |
| Wide/narrow screenshots or manual visual inspection | **Not performed**; no enabled browser automation surface; capture checklist supplied |
| Real Gemini/Groq/Ollama generation | **Not verified**; no authorized external call/model launch |
| GitHub-hosted CI | Workflow authored and YAML parsed; **not remotely run** |
| Container OS CVEs / production security | **Not verified** |

## Scenario results — scoring weights unchanged

| Fictional scenario | Score | Severity | Customers | Engine |
|---|---:|---|---:|---|
| Token Vault timeout | 91.62 | Critical | 6 | FalkorDB Cypher |
| Orders Database latency | 56.08 | High | 4 | FalkorDB Cypher |
| Mumbai region outage | 91.62 | Critical component envelope | 6 | Bounded Python regional composition |
| External payment API degradation | 67.50 | High | 6 | FalkorDB Cypher |
| Optional analytics failure | 27.23 | Medium | 1 | FalkorDB Cypher |

These exactly reproduce the initial scenario scores. The parallel-edge fix changes
evidence selection on conflicting parallel relationships, not the score formula.
Mumbai remains a worst-case component envelope, not an independently calibrated
regional probability. No provider is invoked for that view.

Fictional comparisons using supplied simulator data:

- Token Vault isolation: settled exposure score **91.62 → 42.62**; **49.00**
  points lower; **18** previously active critical impact paths removed.
- Payment assumed replica failover: **85.26 → 19.26**, final simulated Payment
  status healthy. Structural risk can remain above zero after recovery.
- No graph mutation, infrastructure command, measured recovery time or actual
  outage probability is implied by these numbers.

## Commands and reproduction

The executed checks used the fresh environment's interpreter/tools from the
archived source root. Portable equivalent setup (choose a new clean graph name):

```zsh
BR_CLEAN_DIR="$(mktemp -d)"
git archive e3096d580206f3b4b3701cb7ee35e209b2c63063 | tar -x -C "$BR_CLEAN_DIR"
python3.12 -m venv "$BR_CLEAN_DIR/.venv"
source "$BR_CLEAN_DIR/.venv/bin/activate"
cd "$BR_CLEAN_DIR"
python -m pip install -r requirements-dev.txt
unset GEMINI_API_KEY GROQ_API_KEY
export FALKORDB_HOST=127.0.0.1 FALKORDB_PORT=6379
export FALKORDB_GRAPH="phase10_clean_$(date +%s)" LLM_PROVIDER=deterministic
docker compose config --quiet
# The local FalkorDB service must already be running; start it from the original
# checkout using docker compose up -d --wait, not a conflicting second project.
python -m src.health
python -m src.seed
python -m src.seed
python -m src.seed --validate
FALKORDB_INTEGRATION=1 python -m pytest -q
ruff check .
ruff format --check .
python -m compileall -q src tests scripts app.py
bandit -r src scripts -q
python scripts/check_secrets.py
python -m pip check
pip-audit --cache-dir .audit-cache --progress-spinner off
LLM_PROVIDER=gemini python -m src.reports --component 'Token Vault' --status failed --json
python -m streamlit run app.py --server.port 8505 --server.headless true
```

From a separate terminal, request `http://127.0.0.1:8505/_stcore/health`.
Run `python scripts/check_secrets.py --history` in the real Git checkout, not the
archive. Source/history pattern scans are not proof against every unknown secret
format. No history was rewritten, repository pushed, service deployed or account created.

## Failures encountered and resolved

One full live run had 20 connection failures while Docker Desktop was stopped.
Daemon/socket inspection confirmed the prerequisite failure. Starting Docker and
the existing Compose service restored health; the subsequent full suites passed.
Tests were not skipped or weakened to hide this failure.

A fresh reviewer found name-ambiguity/path-budget coupling and native/cache drift.
Both failures were reproduced and fixed with regressions. Expanded parity then
exposed one-hop structural-cycle omission; its independent bounded discovery
budget fixed that case. These fixes are in the tested source commit above.

Remaining limits: per-query path caps/timeouts; nontransactional reads/import;
observed-drift detection is not snapshot isolation; small warm-graph benchmarks;
catalog-derived role narratives; unknown telemetry/replica readiness; no real
provider or manual visual verification. See native, security and benchmark guides.
