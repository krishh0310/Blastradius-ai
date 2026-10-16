# Repository quality and manual publication choices

The local workflow runs Python 3.12 dependency installation, Ruff, formatting,
compileall, tests with 80% coverage enforcement, Bandit, current/history secret
checks and pip consistency. It uses first-party [checkout](https://github.com/actions/checkout)
and [setup-python](https://github.com/actions/setup-python) actions, contents-read
permissions and no persisted checkout credentials. No provider keys are required.
No deploy step, remote settings change or publication is included.

Integration is an optional workflow_dispatch input. Its service is disposable;
the selected graph is ci_<run_id>_<attempt>, never blast_radius. Importer tests
use their own UUID graph names. The service is discarded by the runner after
the job, retaining no development data. This workflow has not been executed on
GitHub until you explicitly push and run it; local checks are not a remote badge.

The history scan reads locally reachable commits, prints commit/path only and
never rewrites history. Recognized-key patterns and currently exported provider
keys are checked; unknown credential formats can escape a pattern scanner.
If a historical key is detected, revoke it first and review history remediation
manually. Do not automatically force-push rewritten history.

Manual repository description suggestion:
“Graph-grounded cloud dependency investigation and fictional failure rehearsal,
powered by FalkorDB, NetworkX and Streamlit.”

Suggested topics: falkordb, graph-database, incident-response, explainable-ai,
streamlit, connected-data, hackathon. These are suggestions, not changed settings.
The existing MIT license is preserved. Team and recording placeholders require
owner confirmation. No status badge claims a remote successful run.

Manual deployment choices after approval:

1. Keep the local Docker/Streamlit demo and submit a sanitized recording.
2. Screen-share the local demo without exposing database/browser ports.
3. Separately design an authenticated private hosted demonstration with TLS,
   secrets handling and a private database network. This is not configured or
   verified here; do not simply expose the current local services publicly.
