# Technology decisions: official FalkorDB references

Reviewed 2026-10-17 against the current Track 01 application. No repository was
cloned, vendored or built, and no dependency was installed or upgraded.

## Decisions

| Technology | Decision | Reason |
|---|---|---|
| FalkorDB engine | Keep pinned Docker image | Native dependency/path queries already provide the factual context. No source build or server migration is justified. |
| Official Python client | Keep `FalkorDB==1.8.0`; use `Graph.ro_query` for reads | Adds server-enforced write rejection without another package or a query rewrite. |
| GraphRAG-SDK | Do not install | The current demo has structured topology and runbook nodes, not a document corpus or document retrieval requirement. No demonstrated incremental benefit. |
| NetworkX | Keep existing projections and algorithms | Retains tested dependency direction, optional-edge policy, risk factors and reproducible rankings. |
| Official MCP Python SDK | Keep existing eleven typed tools | The application already has real stdio discovery, bounded selection, evidence traces and confirmation-gated fictional simulation. |
| General FalkorDB MCP server | Reference only; do not install | A second server/runtime does not improve the existing incident-specific allowlisted tools. |

## Official client and native Cypher

The [database repository](https://github.com/FalkorDB/FalkorDB) demonstrates Docker
and `FalkorDB(...).select_graph(...)`. The [official Python client](https://github.com/FalkorDB/falkordb-py)
provides parameter binding, typed graph results and `ro_query`. Its installed
1.8.0 distribution declares Python >=3.10 and works in this Python 3.12 project.
The client is [MIT-licensed](https://github.com/FalkorDB/falkordb-py/blob/master/LICENSE).
The engine has its own license; it is not relicensed by this application's MIT
license. No engine source is incorporated. Reassess deployment/licensing separately
before offering a hosted database service.

`DatabaseManager(..., read_only=True)` now selects the existing client's
`Graph.ro_query`, documented under [GRAPH.RO_QUERY](https://docs.falkordb.com/commands/graph.ro-query).
The server rejects write queries. It never retries them through `Graph.query`.
Parameter binding, three-second query timeout, safe errors and connection closing
remain unchanged. MCP tools, dashboard retrieval, investigator/analytics/report/
simulation CLIs and benchmark reads opt in. Seeding and its confirmed UI control
remain write-capable; the default manager API is backward-compatible.

This improves the old application-level read-only convention with a server check.
It is not database authentication, a read-only credential, protection from arbitrary
Redis commands, or transactional isolation. Seed an absent graph before reading it.

Native query parity tests execute the current Cypher on the pinned server, not
merely compare text with current upstream documentation. Manual `Graph.explain`
checks compiled the actual downstream/deployment query shapes and an exact-ID
lookup; those plans used the existing Component ID index. No index or scoring
change was needed. [GRAPH.EXPLAIN](https://docs.falkordb.com/commands/graph.explain)
does not execute the query. These checks do **not** establish a latency improvement;
the [existing benchmark](benchmark.md) remains historical.

## GraphRAG-SDK assessment

The [SDK](https://github.com/FalkorDB/GraphRAG-SDK) supports document ingestion,
extraction and source-linked retrieval. Those capabilities would matter for real
runbook/postmortem documents, but the current `HAS_RUNBOOK` relationships already
provide the structured evidence the demonstration needs. No document benchmark
was run, so no comparative speed or retrieval-quality gain is claimed.

Its inspected [package metadata](https://github.com/FalkorDB/GraphRAG-SDK/blob/main/graphrag_sdk/pyproject.toml)
declares Python >=3.10 and [Apache-2.0](https://github.com/FalkorDB/GraphRAG-SDK/blob/main/LICENSE).
Python 3.12 is within that range; actual installation/transitive compatibility
was not tested because the package was rejected. The license is not the reason
for rejection; any later adoption must retain required license notices and review
the selected extras and their licenses.

Base dependencies include GLiNER, hnswlib and tiktoken beyond our current needs.
OpenAI is an optional extra, not a mandatory base requirement; upstream example
provider choices must not be confused with this project's provider policy.
No OpenAI package, API, extra or configuration was introduced.

Estimated maintenance cost is moderate-to-high relative to this bounded demo:
document versioning, extraction review, entity reconciliation, embeddings/models,
index lifecycle, provenance validation and additional prompt-injection tests.
Download size, installation time and monetary cost were not measured.

Reconsider only with a real document corpus and a measurable acceptance test:
retrieve the correct source passage/version, attach provenance to a known service
or runbook, reject unsupported claims and improve a labeled evaluation set over
the existing structured baseline. Keep document claims separate from authoritative
topology; never let extraction overwrite infrastructure facts. Audit provider
dependencies and Python/license compatibility again before adoption.

## Algorithms and MCP

[Official algorithm documentation](https://docs.falkordb.com/algorithms) is useful
reference, not proof that every procedure is available in this pinned image or
equivalent to our dependency-only projection. No procedure replacement is made
without server-version checks, projection/result parity and a reproducible benefit.
Existing `detect_bottlenecks`, `calculate_risk` and `find_critical_paths` tools
already expose structural reasoning with bounded results and path evidence.

The [official FalkorDB MCP server](https://github.com/FalkorDB/FalkorDB-MCPServer)
supports general graph operations and read-only mode. It was inspected as guidance,
not copied or installed. Our [MCP layer](mcp-tooling.md) stays narrower: typed
incident tools, no arbitrary model-supplied Cypher, no graph administration,
maximum eight agent calls and explicit confirmation before fictional simulation.
Gemini, Groq, Ollama and deterministic reporting are unchanged.

## Verification

Executed on 2026-10-17: **223 tests passed, zero skipped; 89.44% statement
coverage**, 44.55 seconds. This includes real FalkorDB native/MCP tests, all five
dashboard scenarios, the new disposable-graph write-rejection test and mocked
provider tests. The focused live database/native/MCP run passed 42 tests.
Ruff, formatting, compileall, Bandit, pip check and whitespace checks passed.
Source secret scan: zero findings. All 60 local Markdown target/heading
references resolved. No new dependency advisory scan was run; dependencies did
not change, and the earlier dated audit remains in the validation record.

`tests/test_database.py` covers read-only dispatch with/without parameters and
sanitized errors. Its opt-in live test creates a unique disposable graph, confirms
a write is rejected and that the record count is unchanged, then deletes **only
that test graph**. The seeded demo topology is never reset by this check.
Existing native parity, real MCP, five-scenario UI, simulation and mocked-provider
tests exercise the changed callers.

```zsh
source .venv/bin/activate
docker compose up -d --wait
env -u GEMINI_API_KEY -u GROQ_API_KEY LLM_PROVIDER=deterministic FALKORDB_INTEGRATION=1 python -m pytest -q
ruff check .
ruff format --check .
python -m compileall -q src tests scripts app.py
bandit -r src scripts -q
python -m pip check
```

No new cloud-provider call, manual browser test, screenshot, video, production
load test or GraphRAG installation is part of this review. Prior provider/video
limitations in [final validation](final-validation.md) still apply.
