# Verified phase ledger

## Phase 0

Baseline recorded in `baseline-audit.md`; plan in `implementation-plan.md`.
Commit `0c8b8da`. Files: those two documents. Read-only baseline: 124 tests
passed / 5 skipped; 87.10% coverage; live graph and all scenarios matched.
Limitations: no cloud calls or manual viewport review.

## Phase 1

Files: graph_queries.py, analytics.py, simulator.py, test_parallel_edges.py,
analytics-and-reports.md and this ledger. Central edge priority preserves all
parallel records and chooses required, higher-criticality, unhealthy evidence,
then stable identity. Three new assertions reproduced failures before the fix.
Complete suite with live disposable-graph tests: **133 passed**, **88.41% coverage**.
Ruff and formatting passed. No score weights changed. Simulation runbook selection
is metadata, not a competing dependency edge; it remains unchanged.
Commit: see `git log --oneline` for the phase's specified commit message.
