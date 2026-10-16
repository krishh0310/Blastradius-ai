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

## Phase 2

Phase 1 commit: `a7a774f`. Phase 2 files: native_queries.py, investigator.py,
dashboard_service.py, dashboard_ui.py, test_native_queries.py, native-falkordb.md.
Native typed paths, strict parameter/depth boundaries, explicit fallback,
diagnostics and cross-domain traversal added. Red decoder/boundary tests preceded
implementation. Live typed parity checks pass at depths 1/6/8 for five components.
The entire suite passes: **150 tests, 88.44% coverage**; Ruff/format pass.
Limitations and the observed zero-length-prefix workaround are documented in
native-falkordb.md. Global analytics still uses a bounded snapshot by design.

## Phase 3

Phase 2 commit: `fc8a3ab`. Files: evidence_ui.py, dashboard_ui.py,
test_evidence_panel.py and this ledger. The above-tabs FalkorDB Evidence section
shows returned counts, engine, timings, limit warnings, complete customer path,
separate owner branch, flat-versus-multi-hop comparison and actual query receipts.
Evidence selection/empty/partial regressions first failed, then passed.
Complete nonintegration suite: **132 passed, 20 skipped**, **84.75% coverage**;
Ruff/format passed. Live parity was verified in Phase 2; UI still needs fresh
manual viewport review. No claim of server nodes examined is made.
