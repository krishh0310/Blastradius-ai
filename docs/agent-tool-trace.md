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
The dashboard demonstration uses deterministic planning. The existing report
provider opt-in is independent. Unknown components, provider errors and database
errors remain visible rather than fabricating evidence.

Completed results are session state, not secret-bearing shared caches. Changing
controls requires a new investigation; mitigation is disabled for stale controls.
Reset clears the trace and comparison without touching FalkorDB. All actions
are in-memory fictional scenarios; see [action gates](graph-gated-actions.md).
