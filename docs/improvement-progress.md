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

## Phase 4

Phase 3 commit: `7f5ac05`. Files: briefings.py, reports.py, dashboard_ui.py,
test_briefings.py, analytics-and-reports.md. Role-specific narratives select known
claim IDs; providers prioritize approved actions/questions and supplied fictional
mitigation outcomes. Main factual grounding is unchanged; free-form unsupported
numbers/entities cannot enter through the new schema. Five new regressions
passed after first demonstrating missing functionality. Entire nonintegration
suite: **137 passed, 20 skipped; 85.08% coverage**, Ruff/format pass.
No real provider call made. Narrative wording remains catalog-derived by design;
provider value is role selection/prioritization, not unconstrained prose.

## Phase 5

Phase 4 commit: `3e56c86`. Files: README and setup/dashboard/simulation/
investigation/analytics documentation. One canonical PATH-based Python 3.12 setup
installs requirements-dev.txt (which includes runtime requirements), preserves
existing dotenv configuration and seeds before validating an empty graph.
Machine-specific paths removed from the edited guides; troubleshooting added.
A fresh temporary virtual environment installed declared dependencies, passed
pip check and **137 tests / 20 skips, 85.08% coverage**. No provider calls.

## Phase 6

Phase 5 commit: `ce37a95`. File: README.md and this ledger. Product-first README
now documents all requested architecture/schema/algorithm/setup/provider/security/
demo/license sections, with truthful capture/team/video placeholders. All cloud
and customer data is explicitly fictional. Native versus global snapshot roles,
limits, region-envelope semantics and constrained AI value are explicit.
Local README links resolve; Ruff and formatting pass. Setup was exercised in
Phase 5. No screenshot, cloud-provider or production claim is fabricated.

## Phase 7

Phase 6 commit: `b52a429`. Files: dashboard_ui.py, test_demo_shortcuts.py,
README, screenshots.md and assets/.gitkeep. One-click Run Demo disables cloud
providers; evidence anchor and simulation navigation added; fictional preview
does not fabricate measured results. Shortcut regression failed before the change
and now passes. Entire nonintegration suite: **138 passed / 20 skips; 85.14%
coverage**. Ruff/format pass. Real Streamlit launch requested for startup check.
Browser inventory has no enabled browser surfaces; actual captures and manual
wide/narrow checks remain checklist items, not claimed as completed.

## Phase 8

Phase 7 commit: `a473542`. Files: scripts/benchmark.py, test_benchmark.py,
benchmark.md, README and ledger. Bounded timing helper had failing tests before
implementation. Twenty actual iterations per operation after two warm-ups;
raw samples, medians and nearest-rank p95 recorded. Native blast query median
3.786 ms; full no-LLM pipeline 32.130 ms. No SQL/user-study/provider comparison
was invented. Complete nonintegration suite: **140 passed, 20 skipped, 85.14%
coverage**. Benchmark helper tests, Ruff/format passed. Small warm graph only.

## Phase 9

Phase 8 commit: `e5b439d`. Files: quality.yml, check_secrets.py,
test_history_scan.py, repository-quality.md, README and ledger. Key-free Python
3.12 quality CI plus manually triggered disposable-graph integration added.
Historical scan regression first failed, then passed; safe current/history
scan reports zero findings. YAML parsed and jobs inspected; Ruff/format/Bandit
passed. Complete nonintegration suite: **141 passed / 20 skipped, 85.14%
coverage**. No workflow was pushed or executed on GitHub; no badge claims otherwise.

## Pre-clean-room review fixes

Phase 9 commit: `f27c0a6`. A fresh read-only reviewer found lookup ambiguity
under max_paths=1 and inconsistent native/cache facts after topology changes.
Both regressions reproduced failures before fixes. Lookup budgets now preserve
ambiguity independently; observed drift explicitly uses one labeled snapshot.
Expanded parity added suggestions, shortest/critical paths and cycles, exposing
a depth-one structural-cycle omission; cycle discovery now has its own bounded
eight-hop budget and a longer-cycle warning. Added native parallel/truncation
checks. Files: native_queries.py, dashboard_service.py, evidence_ui.py,
test_native_queries.py, test_snapshot_drift.py, native-falkordb.md, ledger.
Full live suite: **166 passed, zero skipped, 88.97% coverage**; Ruff/format pass.
One attempted live run had 20 connection failures because Docker Desktop had
stopped; daemon/socket inspection established the cause. Starting Docker and
the existing Compose service restored health; no development graph reset.
Remaining limitation: observed-drift checks are not transactional isolation.

## Phase 10

Reviewed-fix commit: `e3096d5`. Files: final-validation.md, README and ledger.
Archive of that commit plus a fully fresh second virtual environment passed
**166 tests, zero skipped, 88.97% coverage**. Separate unused graph seeded twice
with identical 54/141 totals and zero integrity errors. All quality/security
commands passed; no known Python advisories, no current/history secret findings.
All five native/deterministic scenarios matched baseline. Streamlit launched from
the archive and returned HTTP 200. Actual missing-key CLI fallback passed.
Maximum-depth assertion and fictional mitigation/failover comparisons passed.
Development graph fingerprint unchanged. Detailed commands and honest unverified
items are in final-validation.md; no cloud call, public CI run or manual screenshot.

## Phase 11

Phase 10 commit: `ac8ae6d`. Files: demo-script.md, submission-checklist.md,
README and ledger. Target three-minute flow, 30-second/one-minute pitches,
five-minute extension, fifteen accurate judge answers, failure backups and
forbidden claims added. Values use executed validation, not invented outcomes.
The opening explicitly corrects the all-healthy-topology assumption: recorded
Orders Database is degraded; the simulator's baseline is fictional healthy.
Local document links checked. Actual presenter timing/recording, screenshots,
team details, provider opt-in and publication remain owner actions.

## Phase 12

Phase 11 commit: `8afb7d9`. Added the final read-only audit: internal score 89/100,
category evidence, weaknesses, full-mark requirements and submission priorities.
Re-ran the benchmark on reviewed source e3096d5 in the fresh environment:
native query median 3.699 ms, pipeline 33.167 ms; counts unchanged. Earlier raw
benchmark samples remain labeled separately. README/demo figures refreshed.
No application source changed since the fully verified clean-room commit.
Manual screenshots, presentation timing, live providers and remote CI are not claimed.

## Approved follow-up — benchmark

Base e4ba035, clean main; improvement branch fast-forwarded without losing commits.
Read-only baseline: 146 passed / 20 skipped, 85.59% statement coverage; Ruff,
format and pip check passed. Added live regression first: failed with missing
python_blast_radius measurement. Two existing Python operations added; full live
suite then passed **167 tests, zero skipped, 88.97% coverage** (16.53 seconds).
Twenty actual timing samples per operation after two warm-ups recorded, including
Python traversal/investigation. Native query median 3.753 ms; cached Python blast
radius 0.035 ms; no-LLM pipeline 32.781 ms. No native speedup claim.
Ruling: retain approved in-place improvement branch rather than create another
worktree — preserves the requested branch and existing verified environment;
cost: no additional filesystem isolation from future user edits.
