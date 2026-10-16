# Conceptual reference review

Reviewed 2026-10-16 using the supplied projects' public GitHub descriptions and
README pages. This is a conceptual comparison, not an execution, source-code
audit or reproduction of their results. No external code, wording, screenshots,
logos, datasets or branding was incorporated. No dependency was added.

License labels below are what the available repository page advertised, not a
legal clearance for every file. Direct license retrieval failed for several
projects; only PyRCA's license text was successfully inspected. Any future reuse
requires inspecting the exact file/commit license and attribution obligations.
No license was inferred from a repository being public.

| Reference / primary source | Observed concept | Decision for BlastRadius AI | License/access observation |
|---|---|---|---|
| [RootTrace](https://github.com/VivekReddy2001/roottrace) | Injected faults, graph-aware candidate ranking and held-out top-k evaluation | Keep upstream candidates separate from downstream exposure; future independent fault fixtures should evaluate ranking accuracy, not just latency. Do not import Neo4j code or claim its published scores. | Repository page advertises MIT; direct license fetch unavailable. |
| [GraphOps](https://github.com/amarmantry/GraphOps) | User suggested dependency intelligence and feature grouping | No finding attributed to the implementation: repeated page/API retrieval failed. Treat the user's concept list as a research lead only. | Unverified; no reuse. |
| [Infrastructure Knowledge Graph](https://github.com/manuelbomi/infra-knowledge-graph) | Reconciliation of topology, discovery and health sources with different freshness | Document snapshot consistency limits; keep live discovery and reconciliation outside this fictional demo's scope. | Page advertises MIT; direct license fetch unavailable. |
| [BlastRadiusBench](https://github.com/edgedelta/blast-radius-bench) | Evaluates origin identification separately from directed propagation-path recovery | Preserve physical relationship direction and distinguish potential exposure from proven causation. Future evaluation should score both candidate identity and path correctness on held-out fixtures. | Page advertises Apache-2.0; direct license fetch unavailable. |
| [Trace-wise / NetRCA](https://github.com/meghabyte-og/trace-wise) | Reachability-based separation of originating faults from alarm cascades; fault simulator | Retain deterministic simulator and required/optional/replica assumptions; do not claim telemetry collection or verified automatic diagnosis. | No license identified in retrieved root page; reuse prohibited pending clarification. |
| [Root-Teller](https://github.com/YijenChan/Root_Teller_RCA) | Provenance-linked evidence, progressive investigation and feedback memory | Retain evidence-linked unknowns and validation questions. Do not add multi-agent state, telemetry pipelines or historical memory to this narrow project. | Page advertises MIT; attempted main-branch license URL unavailable. |
| [PyRCA](https://github.com/salesforce/PyRCA) | Metric-based RCA, causal-graph methods, random walks and evaluation | Keep current score explicitly heuristic. Causal calibration requires suitable telemetry and ground truth, not an algorithm-name substitution. No ML framework added. | [BSD-3-Clause license text inspected](https://github.com/salesforce/PyRCA/blob/main/LICENSE). No code reused. |
| [AWS blast-radius CLI](https://github.com/pfrederiksen/blast-radius) | Resource dependency discovery, bounded depth and annotated missing permissions | Keep readable CLI output and explicit unavailable evidence. AWS discovery remains future scope; never use local cloud credentials for this demo. | Page advertises Apache-2.0; direct license fetch unavailable. |
| [Dependency-health UI](https://github.com/Tftlegal/tools-dephealth-ui) | Directed topology, health/latency states, grouping and cascade presentation | Preserve accessible text labels and honest unknown/failure states. Do not import its UI, assets, Prometheus stack or real-time monitoring claims. | README states Apache-2.0; direct license fetch unavailable. |
| [Octopus](https://github.com/aint/octopus) | Architecture-wide dependency visualization and impact exploration | Keep filtering and readable layouts in the existing Plotly view; no rewrite or copied visualization code. | Page advertises Apache-2.0; direct license fetch unavailable. |

## What this changes—and does not

These lessons support existing choices in native_queries.py, analytics.py,
reports.py, simulator.py and the evidence UI; they do not establish that those
modules were derived from these references. This follow-up changes only benchmark
instrumentation, tests and documentation. Current risk weights, candidate ranking,
topology and visual design are unchanged.

The benchmark now times cached Python fallback and native retrieval separately.
It is a runtime microbenchmark, not an RCA-accuracy benchmark. We did not run any
reference project's benchmark, adopt its data, compare its reported scores with
ours, or substantiate large-graph/production performance claims.

Unfinished research: GraphOps access; exact licenses for any future reuse;
independent, held-out fault/topology evaluation; operator review. These do not
justify marking the current demo as confirmed causal analysis.
