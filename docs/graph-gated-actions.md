# Graph-gated fictional actions

Simulation honors the tool's selected depth 1–8 and surfaces baseline and policy
replay warnings. The primary Token Vault demo selects 8; CLI/default tool requests
use 6. Do not compare a depth-limited simulated cohort directly with the separate
potential-exposure investigation card or imply that truncated impact is complete.

The agent inspects ownership/runbook and action evidence before recommending a
policy. It never auto-confirms or runs simulation while investigating. The normal
seven-call plan leaves the eighth call for human-confirmed simulation; a completed
eight-call plan must be rerun more narrowly instead of exceeding the budget.

| Action | Required graph evidence / fictional assumption |
|---|---|
| activate_declared_replica | Existing healthy alternate deployment or REPLICATES_TO target; assumes freshness/capacity/readiness |
| reroute_traffic | Same graph-supported healthy alternate; assumes successful routing |
| isolate_unhealthy_dependency | Required incoming consumer dependency; assumes circuit breaking degrades direct consumers and contains propagation |
| switch_to_read_only_mode | Service/Database/API with recorded provider dependency; read-only capability itself is a fictional assumption |
| disable_optional_feature | Optional incoming consumer dependency; never bypasses required dependencies |
| execute_fictional_runbook | Existing HAS_RUNBOOK; success is assumed, no runbook command is executed |

Each gate returns the exact original relationship(s), traversal order, type,
required flag, criticality and hop count. Stored arrows remain consumer-to-provider
even when failure-impact walks travel in reverse. Missing evidence or a healthy
scenario rejects the action. The gate is rerun against current FalkorDB facts
when simulation is requested; prior eligibility is not permanent authorization.

The policy prefers disabling a purely optional feature; otherwise a declared
alternate, then containment, then read-only/runbook assumptions. This is a
transparent deterministic preference, not a claim of optimal or safe real-world
remediation. Its reason and all eligible/rejected options are visible.

## Confirmation and MCP trust boundary

The application requires a user confirmation checkbox and an explicit simulation
button. The planner cannot generate tool arguments or set confirmed. The MCP
simulation tool independently requires strict confirmed=true and a currently
eligible allowlisted action. External MCP hosts must obtain actual human approval
before sending that assertion: the local stdio protocol cannot cryptographically
prove a human clicked a remote host's button. Do not expose this server publicly.

Only the existing in-memory Simulator is called. No database writes, cloud APIs,
shell commands or executable runbook contents are exposed. Before assumes a
fictional healthy starting topology with no automatic failover; the approved
policy changes the counterfactual. This avoids crediting already automatic
recovery to the action. Scores use the unchanged risk formula.

The bounded typed result contains before/after scores and affected IDs, after
statuses, transition events, neutralized critical paths and the score breakdown.
It does not repeat the entire investigation object at every simulation frame.
The result cap still fails closed if a large graph cannot fit. Reset clears the
session result, never the seeded graph. No real infrastructure is repaired.
