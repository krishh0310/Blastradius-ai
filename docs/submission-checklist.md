# Submission-day checklist

## Verified locally

Current MCP-enabled results supersede historical baseline counts below; see the
dated [validation record](final-validation.md). Prior screenshots do not show
the new trace. **The owner-recorded working video is still incomplete.**

- [x] Required improvement branch created; logical local commits retained.
- [x] Parallel-edge and native/cache consistency regressions fixed.
- [x] Native FalkorDB incident/customer paths and reference parity exercised.
- [x] All five scenarios and real no-key deterministic fallback verified.
- [x] Fresh archived source/environment passed 166 tests, 88.97% coverage.
- [x] Ruff, formatting, compileall, Bandit, pip check and Python advisory audit passed.
- [x] Current/reachable-history secret scans reported zero findings.
- [x] Docker health and idempotent isolated seeding verified; development graph unchanged.
- [x] Streamlit started and health returned HTTP 200; automated UI scenarios passed.
- [x] Fictional-data and heuristic/causality/replica caveats documented.
- [x] MIT license preserved; no deployment, publication or visibility change performed.

## Owner actions before submission

- [ ] Confirm team name, contributors, roles and any eligibility requirements.
- [ ] Check current official hackathon rules/deadline/track requirements manually.
- [ ] Complete narrow-layout visual checks below; inspect any new capture for secrets.
- [ ] Rehearse/record the three-minute script with an actual timer.
- [ ] Record the working demo and add a judge-accessible link: required for this undeployed project. Follow [video checklist](video-checklist.md); screenshots are not a substitute.
- [ ] If cloud success is desired, repair credentials privately and authorize a new check; the previous Groq attempt failed authentication.
- [ ] If a provider fails, retain the honest deterministic fallback demonstration.
- [ ] Review commits and run the final commands on the intended submission checkout.
- [ ] Manually push only after review; inspect real quality CI results.
- [ ] Optionally trigger disposable FalkorDB integration CI; never use the demo graph.
- [ ] Add a status badge only after observing the relevant workflow outcome.
- [ ] Set repository description/topics if desired; confirm visibility yourself.
- [ ] Submit links/files through the official process yourself.

Deployment is optional and not configured. Prefer a local screen-share/recording;
any hosted demo needs a separate authentication/TLS/private-database design.
The submission is not a production SRE service or a promise of prize placement.

## Screenshots and visual checks

Five unaltered desktop screenshots were captured from the running local app in
Brave on 2026-10-16, after the owner temporarily granted access. They show only
the fictional demo and local browser chrome and were checked for visible keys.

| Existing capture | Evidence |
|---|---|
| [Overview](assets/dashboard-overview.png) | Landing state and three demo actions |
| [Token Vault result](assets/token-vault-investigation.png) | Critical 91.62, eleven services, six customers, native engine |
| [Cypher receipts](assets/falkordb-evidence.png) | Actual templates, safe parameters and durations |
| [Customer path](assets/customer-evidence.png) | Token Vault → Subscription Service → Renewal → Atlas; three hops |
| [Cascade simulation](assets/cascade-simulation.png) | Fictional after-mitigation state, graph and playback controls |

The three-click desktop flow was exercised. Narrow/mobile layouts, every hover,
keyboard-only navigation and WCAG compliance were not established by these images.
Additional checks: about 390×844 viewport, wrapped controls, accessible sidebar,
scrolling tables/graph, visible focus, readable legend, empty/single-node/filter-empty
states. Automated AppTest covers behavior but not pixel appearance.
Store only genuine inspected PNG/WebP captures in assets/, link with descriptive
captions/alt text, and keep credentials, account panels and unrelated tabs out.
