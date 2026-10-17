# Local MCP tooling

BlastRadius uses the [official Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk),
pinned to 2.3.0 (Python 3.11+, compatible with this project's Python 3.12).
Its low-level Server handles initialization, discovery, typed schemas and stdio;
our handler validates arguments itself so validation errors cannot echo inputs.
No HTTP listener, arbitrary Cypher/Python executor or cloud action is exposed.

Activate the development environment, install requirements-dev.txt and seed the
local graph using setup.md. Start with `python -m src.mcp_server` from the project
root. Standard output is protocol-only; diagnostics go to standard error.
`mcp.example.json` is a local host configuration example: launch from the project
root with the activated environment's Python, or privately set an absolute Python
path and cwd in your MCP host. Never put provider keys in the tracked example.

## Registry and schemas

| Tool | Graph-backed result |
|---|---|
| lookup_component | Exact ID/name or suggestions; recorded health |
| inspect_falkordb_evidence | Deployment/region/replica evidence and query receipts |
| trace_upstream_dependencies | Native upstream supporting paths |
| trace_downstream_blast_radius | Native downstream supporting paths |
| find_customer_impact | Complete workflow/customer evidence paths |
| find_business_workflows | Workflow evidence without requiring customer lookup |
| find_critical_paths | Required critical paths selected from native returned paths |
| detect_bottlenecks | NetworkX structural metrics with graph-backed dependent evidence |
| calculate_risk | Existing deterministic factor breakdown and native incident evidence |
| get_owner_and_runbook | Recorded ownership/runbook paths |
| simulate_fictional_mitigation | Confirmation-required in-memory simulation boundary |

ToolInput requires component (1–128 letters/digits/spaces/_./-), strict integer
depth 1–8 and max_paths 1–100 (defaults 6/60), and an allowlisted status (default
failed). Unknown fields, coercions and injection-like component syntax are rejected.
SimulationInput additionally requires an allowlisted action and confirmed boolean.
Discovery publishes the Pydantic JSON input/output schemas; outputs are ToolResult.

Each result includes original-edge paths, relationship types, hops, required flag,
criticality, stable evidence IDs, query diagnostics, engine, elapsed time and warnings.
Known key material is redacted before output; errors use fixed categories.
Results above 120 KB fail closed rather than imply complete evidence. Path/entity
caps warn. Default tool wait deadline is 15 seconds; server query timeout remains
three seconds. A timed-out worker can finish read-only bounded work, but a single
worker gate refuses more requests until it finishes. This is not a hard CPU kill.

Unit fixtures explicitly use a labeled Python snapshot. Production tools use
FalkorDB native queries; structural calculations and simulation use bounded graph
snapshots. Per-call reads are not a transaction or a persistent agent memory.
