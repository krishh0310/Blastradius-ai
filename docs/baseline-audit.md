# Improvement baseline — 2026-10-16

Before code changes: branch `main`, commit
`2c152daa92b65de76c893a18adb2ec56909ddc87`, clean working tree.
Work continues on `improve/hackathon-final`. No original files were changed
before recording this baseline. Local `.env` and seeded graph are preserved.

Python 3.12.14; pip dependency consistency, Ruff, formatting, compileall,
source secret scan and recognized-key/known-environment-key scan of all reachable
Git commits passed. No tracked dotenv files (except `.env.example`) or detected
historical keys. Pattern scanning is not proof that no unknown secret exists.
No credentials printed and no cloud provider contacted.

Baseline tests: **124 passed, 5 integration tests skipped**, **87.10% statement
coverage**. Integration writes were disabled for the read-only baseline.
FalkorDB health and live graph integrity passed: 54 nodes, 141 relationships,
zero errors; intentional Analytics–Notification cycle present. No graph reset.

| Fictional scenario | Risk | Severity | Customers |
|---|---:|---|---:|
| Token Vault | 91.62 | Critical | 6 |
| Orders Database | 56.08 | High | 4 |
| Mumbai | 91.62 | Critical component envelope | 6 |
| External payment API | 67.50 | High | 6 |
| Optional analytics | 27.23 | Medium | 1 |

Recognized initial gaps: parallel-edge evidence selection, snapshot-based runtime
traversal, restrictive report editing, scattered setup commands, missing submission
narrative/assets/benchmarks/CI. The repository now contains an MIT license and
local Git history; the earlier audit's missing-Git/license observations are stale.
No GitHub workflow files or screenshots exist at baseline.

Scope: local fictional demo, not production telemetry, causal confirmation,
or real infrastructure remediation. Starting audit score: 78/100, subjective.
