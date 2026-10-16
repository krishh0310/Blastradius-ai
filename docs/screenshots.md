# Real screenshot / visual verification checklist

No screenshots were fabricated or generated. The available computer-use inventory
reported no enabled browser automation surfaces during this pass; no manual
browser/viewport verification is claimed. Streamlit AppTest checks behavior, not
pixel appearance. Capture these views manually before submission.

Use the real application at 127.0.0.1:8501. Keep **Use configured LLM** off for
the offline demo; hide terminal, account panels, local paths and secret inputs.
Before committing each image, inspect it at full resolution for sensitive data.
Save compressed PNG or WebP in `docs/assets/`, then add the real image links to
README. Do not label an illustration or generated mockup as a screenshot.

| Capture / check | Suggested filename | Acceptance |
|---|---|---|
| Landing preview and Run Demo | landing-desktop.png | Value and primary action readable immediately |
| Token Vault result | token-vault-investigation.png | Engine, Critical heuristic score, exposed customers visible |
| Interactive graph | blast-radius-graph.png | Legend, arrows, optional edges, readable hover |
| Three-plus-hop customer and owner branch | customer-evidence.png | Real path and exact hop count; no invented customer-team edge |
| Bottleneck/articulation analysis | bottlenecks.png | Projection and heuristic caveats visible |
| Risk breakdown | risk-breakdown.png | Factors, weights and replica discount readable |
| Actual Cypher receipts | falkordb-evidence.png | Engine, safe parameters, timing, truncation status |
| Cascade timeline | cascade-timeline.png | Fictional simulated timestamps and supporting edge |
| Before/after mitigation | mitigation-comparison.png | Same topology, fictional assumption, score/count comparison |
| No-key fallback | deterministic-briefing.png | Actual provider says deterministic; no key panel |
| Wide desktop, around 1440×900 | desktop-layout.png | No overlapping cards, usable navigation and main path |
| Narrow viewport, around 390×844 | narrow-layout.png | Sidebar reachable, controls wrap, graph/tables scroll, readable contrast |

Keyboard check: tab through controls, visible focus, label-based status rather
than color alone. Check empty graph, no matching component, single node, provider
failure and partial-result warnings. No claim of WCAG certification is made.

Once captured, include a short descriptive caption/alt text identifying the
fictional scenario and whether the view shows facts, heuristics or simulation.
Screenshots/video and team confirmations remain manual submission tasks.
