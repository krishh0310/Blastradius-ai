# Hackathon-final implementation plan

Goal: improve the existing project honestly, without replacing its architecture.
Spec: the user's supplied thirteen-phase improvement request (phases 0–12).
Execution: sequential, tests before nontrivial behavior changes; commit only
verified phases. No deployment, publication, credential use or graph reset.

Architecture: FalkorDB incident-specific typed paths; NetworkX bounded global
metrics; Python validation/scoring/orchestration; constrained provider briefings;
Streamlit evidence-first presentation. Keep scoring weights unchanged.

## File and interface plan

- [x] 0. `docs/baseline-audit.md`: Git, checks, live graph and scenario baseline.
- [x] 1. `src/graph_queries.py`, `analytics.py`, `simulator.py`, tests:
  centralized deterministic evidence-edge priority; required, criticality,
  unhealthy status, then relationship identity. Reproduce failure first.
- [x] 2. `src/native_queries.py`, `investigator.py`, dashboard service:
  bounded Cypher paths returning typed evidence, operation diagnostics and
  explicit engine; live parity tests against snapshot implementation.
- [x] 3. Dashboard evidence section: executed templates, safe parameters,
  timings/counts/truncation, visible customer path and flat-lookup comparison.
- [x] 4. Reports: validated role-specific briefings, prioritized catalog actions,
  evidence references, unknowns and supplied mitigation comparisons. Mocked
  provider tests; no automatic external calls.
- [x] 5. Canonical development/run-only setup and troubleshooting; safe dotenv copy.
- [x] 6. Product README, Mermaid, actual MIT license, explicit placeholders.
- [x] 7. Evidence-first UI shortcuts/preview; real screenshots only if permitted,
  otherwise capture checklist. AppTest wide/narrow behavior is not visual proof.
- [x] 8. Repeatable warmup/median/p95 benchmark with actual measurements.
- [x] 9. Key-free Python 3.12 CI; safe current/history secret checks.
- [x] 10. Fresh-environment complete verification and `docs/final-validation.md`.
- [x] 11. `docs/demo-script.md`: three-minute demo, pitches, questions, backups.
- [x] 12. Read-only evidence-based scoring in `docs/final-audit.md`.

## Verification gates

Each behavior change: failing regression, minimal implementation, green complete
suite, lint/format/security as relevant. Native tests cover depths 1/6/8, cycles,
parallel/optional edges, unknown/empty, overflow and deterministic path order.
Known failure classes: missing DB, partial native failure, truncated graph, stale
cached snapshots, untrusted provider numbers/entities. Do not silently return
apparently complete results when a query is incomplete. Keep original Python
engine available as explicitly labeled fallback.

Ruling: work in the requested new branch in the existing clean checkout; no
additional worktree or scaffold. The supplied written design and instruction to
continue automatically govern execution; no intervening design approval needed.
Phase outcomes and commit identifiers are recorded as work progresses.

Completion covers safe local deliverables and the screenshot-checklist alternative.
Manual assets, provider opt-in and remote CI remain explicitly unverified.
