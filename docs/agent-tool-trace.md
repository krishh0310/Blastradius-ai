# Agent tool trace

Run `python -m src.agent --component "Token Vault" --depth 6` from the activated
project environment. Add `--json` for the typed trace. This uses the official MCP
client and launches `python -m src.mcp_server` over local stdio, not a mocked
registry. No LLM key is needed.

In Streamlit, select **Run Token Vault Agent**, **View FalkorDB Evidence**, then
check the fictional-action confirmation and select **Simulate Recommended
Mitigation**. These are three main actions plus explicit safety consent. The
sidebar Investigate button supports the other scenarios and component choices.
The primary Token Vault button selects depth 8 for the full fictional cascade;
the CLI defaults to depth 6. Simulation honors the selected depth and retains
both baseline and mitigation warnings. A depth-limited comparison may omit later
customer transitions; its score is not the headline investigation cohort score.

The Agent Tool Trace panel shows incident, order, selection reason, arguments,
sanitized structured output, original relationship direction/type, required flag,
criticality, hop counts, evidence IDs, native query receipts and elapsed time.
Eligibility and rejection reasons for all six fictional actions appear in the
owner/runbook tool output. The final row reports the stopping reason and
confidence; exposure is not a confirmed cause.

Lookup and deployment inspection happen first. Questions about causes select
upstream traversal; business questions select customer/workflow tools. After
paths exist, structural/risk evidence and owners/runbooks are requested. The
agent stops when evidence is sufficient or its budget is exhausted. Identical
tool/argument calls are never repeated. The default impact demonstration uses
seven calls, reserving the eighth for a confirmed simulation. A longer question
may consume that budget; start a focused investigation instead of bypassing it.

Optional constrained provider selection can choose only among the next safe
tool names; the model cannot provide arguments, Cypher, code or authorization.
The one-click demonstration uses deterministic planning. Independently opt in with
**Use configured LLM for tool selection**, or use:

```zsh
python -m src.agent --component "Token Vault" --depth 8 --use-provider --json
```

At most three provider calls select direction, business-impact evidence and
structural/risk evidence. Each decision receives a bounded typed summary of
observed graph facts: matched ID/type/status/criticality, intent flags,
path/evidence counts, warning presence and remaining budget. Raw incident prose,
graph descriptions, tool arguments and credentials are not sent to the planner.
Lookup and deployment inspection remain mandatory; owner/runbook evidence cannot
be skipped for a recommendation. Invalid choices or provider failures stop further
provider attempts and use the deterministic policy. A later failure retains an
honest hybrid planner label. Each trace identifies the actual selector and planning
latency separately from tool execution. This is bounded selection, not unrestricted
autonomous planning. Longer selections can exhaust all eight calls, leaving no
room for simulation; the budget is never expanded.

The report-provider opt-in is separate. Unknown components, provider errors and
database errors remain visible rather than fabricating evidence. Tests mock every
provider call; live provider planning is not claimed verified.

Completed results are session state, not secret-bearing shared caches. Changing
controls requires a new investigation; mitigation is disabled for stale controls.
Reset clears the trace and comparison without touching FalkorDB. All actions
are in-memory fictional scenarios; see [action gates](graph-gated-actions.md).
