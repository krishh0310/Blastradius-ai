# Measured local graph benchmark

## Synthetic multi-tenant follow-up — 2026-10-17

The unchanged judge fixture remains 54 nodes / 141 relationships. The separate
deterministic generator in `src/scale.py` clones twenty tenants and connects their
Token Vaults to a required shared secrets service with its own team/runbook:
**1,083 nodes / 2,842 relationships**. All structural validation passed. The new
CLI seeds only a generated `scale_test_UUID` graph, performs read-only queries,
and removes that same disposable graph in `finally`, with at most three cleanup
attempts. It accepts no graph-name argument; it never resets the configured demo
graph. Reports include the exact generated graph name, attempt count and cleanup
status. A persistent cleanup failure produces sanitized JSON and a nonzero exit
code without hiding the original benchmark failure. If the process is forcibly
killed or the server remains unavailable, removal cannot be guaranteed; only the
reported disposable graph may need manual removal after server recovery.

```zsh
python -m scripts.scale_benchmark --tenants 20 --iterations 5 --warmup 1
```

Measured locally on Python 3.12.14/macOS arm64: five measured iterations after one
warm-up, nearest-rank p95. Seed/validation took 1,471.513 ms. Depth six, max 500
paths, snapshot ceiling 2,000 nodes / 10,000 relationships. Native/reference
affected-ID sets matched for both roots, with no traversal warnings; this is not
proof that every alternate route was enumerated. Disposable cleanup completed.

| Operation | Returned components | Median ms | p95 ms |
|---|---:|---:|---:|
| Snapshot retrieval and validation | — | 107.757 | 112.333 |
| Tenant 01 Vault, native | 15 | 4.242 | 4.447 |
| Tenant 01 Vault, cached Python | 15 | 0.034 | 0.040 |
| Shared secrets, native | 300 | 121.158 | 122.038 |
| Shared secrets, cached Python | 300 | 0.821 | 0.896 |

Raw measured samples (ms), in execution order:

```json
{
  "snapshot": [112.333, 100.239, 107.757, 108.323, 105.267],
  "tenant_native": [4.295, 4.108, 4.240, 4.242, 4.447],
  "tenant_cached_python": [0.040, 0.034, 0.033, 0.037, 0.033],
  "shared_native": [121.639, 112.853, 121.158, 122.038, 117.202],
  "shared_cached_python": [0.803, 0.821, 0.813, 0.896, 0.821]
}
```

Repeated fictional tenants are not a production workload. Native timings include
database round-trips and typed decoding; cached Python timings exclude snapshot
download/construction (reported separately). No throughput, concurrent load,
server expansion count, whole-graph analytics, LLM or UI latency is measured.
This is an honest larger-graph exercise, not evidence that FalkorDB beats Python
or SQL, or that the complete dashboard is validated at production scale.

## Native versus Python follow-up

Executed 2026-10-16 on the same local Python/macOS environment and fictional
54-node / 141-relationship graph. Source: e4ba035 plus the small benchmark
extension (no application-module changes). Twenty iterations, two warm-ups;
nearest-rank p95. Both engines use the existing default depth six and limits.

| Operation | Median ms | p95 ms |
|---|---:|---:|
| direct_one_hop | 1.155 | 1.451 |
| native_blast_radius | 4.714 | 8.764 |
| python_blast_radius | 0.035 | 0.044 |
| native_blast_query | 3.753 | 4.282 |
| native_investigation | 24.789 | 31.559 |
| python_investigation | 0.793 | 0.817 |
| networkx_analytics | 0.950 | 0.986 |
| deterministic_report | 0.060 | 0.065 |
| pipeline_without_llm | 32.781 | 41.777 |

Python traversal is faster here because it reads an already downloaded and
constructed in-memory snapshot. Native measurements include database round-trips
and driver decoding; native_blast_radius additionally converts typed evidence.
This is not a fair end-to-end speed contest and does not show a FalkorDB speedup.
Snapshot download/construction is excluded from Python timings; cached snapshots
also have different freshness semantics. Existing live parity tests compare the
returned facts for the seeded fixture; timing alone does not prove parity.
No SQL implementation, operator study, provider latency or large-graph scaling
was measured. The graph advantage demonstrated is path retrieval and evidence
expressiveness at the database boundary, not winning this latency comparison.

Counts: 33 evidence nodes, 35 evidence relationships, 21 unique impact paths,
maximum seven hops including business/customer context, three direct components,
fifteen total multi-hop-traversal components (including workflows), six customers.

### Follow-up raw samples

```json
{
  "environment": {
    "python": "3.12.14",
    "system": "macOS-26.6.2-arm64-arm-64bit",
    "architecture": "arm64"
  },
  "iterations": 20,
  "warmup": 2,
  "snapshot_nodes": 54,
  "snapshot_relationships": 141,
  "operational_nodes": 29,
  "operational_adjacencies": 37,
  "returned_evidence_nodes": 33,
  "returned_evidence_relationships": 35,
  "returned_unique_impact_paths": 21,
  "maximum_hops": 7,
  "direct_components": 3,
  "multi_hop_components": 15,
  "customers": 6,
  "measurements": {
    "direct_one_hop": {
      "median_ms": 1.155,
      "p95_ms": 1.451,
      "samples_ms": [
        1.141,
        1.434,
        1.451,
        1.195,
        0.948,
        0.986,
        1.161,
        1.337,
        0.992,
        1.001,
        1.038,
        1.033,
        1.15,
        1.482,
        1.335,
        1.174,
        1.123,
        1.223,
        1.211,
        1.07
      ]
    },
    "native_blast_radius": {
      "median_ms": 4.714,
      "p95_ms": 8.764,
      "samples_ms": [
        5.669,
        8.764,
        6.167,
        5.465,
        5.554,
        4.881,
        4.659,
        4.66,
        4.804,
        16.25,
        5.533,
        4.653,
        4.46,
        4.367,
        4.768,
        4.304,
        4.306,
        4.172,
        4.33,
        4.314
      ]
    },
    "python_blast_radius": {
      "median_ms": 0.035,
      "p95_ms": 0.044,
      "samples_ms": [
        0.042,
        0.038,
        0.048,
        0.044,
        0.043,
        0.044,
        0.032,
        0.032,
        0.033,
        0.036,
        0.035,
        0.035,
        0.036,
        0.036,
        0.035,
        0.035,
        0.036,
        0.032,
        0.032,
        0.032
      ]
    },
    "native_blast_query": {
      "median_ms": 3.753,
      "p95_ms": 4.282,
      "samples_ms": [
        3.797,
        3.961,
        3.787,
        3.578,
        3.546,
        3.825,
        3.649,
        4.651,
        3.901,
        3.941,
        3.768,
        3.667,
        3.539,
        3.614,
        3.576,
        3.728,
        3.738,
        4.282,
        3.894,
        3.712
      ]
    },
    "native_investigation": {
      "median_ms": 24.789,
      "p95_ms": 31.559,
      "samples_ms": [
        23.708,
        25.348,
        23.556,
        31.559,
        23.925,
        23.143,
        27.083,
        25.347,
        26.218,
        24.825,
        24.604,
        25.445,
        24.753,
        24.711,
        33.279,
        25.42,
        25.763,
        24.004,
        24.338,
        24.497
      ]
    },
    "python_investigation": {
      "median_ms": 0.793,
      "p95_ms": 0.817,
      "samples_ms": [
        0.824,
        0.817,
        0.788,
        0.802,
        0.793,
        0.811,
        0.802,
        0.791,
        0.816,
        0.809,
        0.796,
        0.801,
        0.789,
        0.792,
        0.793,
        0.776,
        0.781,
        0.79,
        0.782,
        0.784
      ]
    },
    "networkx_analytics": {
      "median_ms": 0.95,
      "p95_ms": 0.986,
      "samples_ms": [
        0.986,
        0.959,
        0.964,
        0.961,
        1.116,
        0.969,
        0.962,
        0.967,
        0.905,
        0.904,
        0.929,
        0.935,
        0.951,
        0.937,
        0.938,
        0.932,
        0.948,
        0.939,
        0.959,
        0.929
      ]
    },
    "deterministic_report": {
      "median_ms": 0.06,
      "p95_ms": 0.065,
      "samples_ms": [
        0.06,
        0.065,
        0.061,
        0.07,
        0.065,
        0.06,
        0.059,
        0.055,
        0.06,
        0.061,
        0.065,
        0.063,
        0.061,
        0.06,
        0.055,
        0.054,
        0.058,
        0.06,
        0.06,
        0.06
      ]
    },
    "pipeline_without_llm": {
      "median_ms": 32.781,
      "p95_ms": 41.777,
      "samples_ms": [
        31.975,
        39.787,
        31.974,
        32.339,
        32.313,
        32.436,
        34.139,
        41.777,
        33.085,
        32.665,
        32.521,
        32.443,
        33.612,
        34.606,
        42.488,
        32.422,
        32.218,
        32.898,
        32.978,
        36.652
      ]
    }
  },
  "limits": "Warm local connection; cached global snapshot; no UI rendering/startup/provider time. Python timings exclude snapshot retrieval/construction; native timings include database round-trips. Pipeline includes fresh native queries, NetworkX, fictional comparison construction and report. Report-only excludes evidence construction. Server nodes examined/expansions are not measured."
}
```

## Prior reviewed-source repeat

Repeated on 2026-10-16 using archived application commit `e3096d5` and the fresh
clean-room environment: 20 measured iterations after two warm-ups, same graph
and exclusions below. These predate the follow-up comparison above; the earlier run
and its raw samples remain below for transparency. Timing variation is expected.

| Operation | Median ms | p95 ms |
|---|---:|---:|
| direct_one_hop | 0.699 | 1.459 |
| native_blast_radius | 4.549 | 5.601 |
| native_blast_query | 3.699 | 3.844 |
| native_investigation | 25.031 | 34.793 |
| networkx_analytics | 1.021 | 1.062 |
| deterministic_report | 0.061 | 0.066 |
| pipeline_without_llm | 33.167 | 43.279 |

Counts were unchanged: 54 nodes / 141 relationships; 33 returned evidence nodes,
35 evidence relationships, 21 unique impact paths, maximum seven context hops,
three direct components, fifteen multi-hop components and six customers.

## Earlier measurement and retained raw samples

Measured 2026-10-16 on macOS-26.6.2-arm64-arm-64bit, Python 3.12.14, arm64.
Source base: a473542 plus the benchmark addition. 2 warm-up runs and 20
measured iterations per operation. p95 uses nearest rank (ceil(0.95 × N)).

| Operation | Median ms | p95 ms |
|---|---:|---:|
| direct_one_hop | 0.740 | 1.240 |
| native_blast_radius | 4.394 | 7.028 |
| native_blast_query | 3.786 | 4.488 |
| native_investigation | 24.773 | 32.090 |
| networkx_analytics | 0.962 | 0.990 |
| deterministic_report | 0.058 | 0.066 |
| pipeline_without_llm | 32.130 | 39.792 |

The graph contained 54 nodes and 141 relationships;
NetworkX processed 29 operational nodes and 37
collapsed directed adjacencies. Token Vault returned 33 evidence
nodes, 35 relationships, 21
unique impact paths and at most 7 hops including customer context.
Direct lookup found 3 exposed components; bounded multi-hop retrieval
found 15 (including workflow entities) and 6 customers.
These are different questions, not equivalent workloads or a claimed speedup.

Reproduce from the repository root, after canonical development setup and seeding:

```zsh
python -m scripts.benchmark --iterations 20 --warmup 2
```

Warm local connection; cached global snapshot; no UI rendering/startup/provider time. Pipeline includes fresh native queries, NetworkX, fictional comparison construction and report. Report-only excludes evidence construction. Server nodes examined/expansions are not measured.

native_blast_query is query round-trip plus driver deserialization, not isolated
server CPU time. native_blast_radius adds typed path conversion and selection.
The pipeline includes fictional mitigation evidence construction but excludes
Plotly rendering, application startup, global snapshot download and provider calls.
A warm reused local connection and small seeded graph do not predict production
latency or large-graph scaling. Individual outliers remain in the raw samples.
No PostgreSQL implementation or manual operator study was measured. No provider
latency was measured because no external call was authorized or made.

## Relational comparison: structural, not a performance benchmark

The schema has 13 relationship types. A relational design could use a generic
edge table, or normalized tables for dependencies, deployments, ownership,
workflow support, customer usage, runbooks, replication and incident associations
(eight conceptual relationship groups). Thirteen separate tables are not required.
Variable-depth impact requires recursive traversal and preserving the relationship
sequence across those domains. SQL can express it; native graph paths make this
changing relationship question more direct. No relative latency claim is made.

## Raw measured samples

```json
{
  "environment": {
    "python": "3.12.14",
    "system": "macOS-26.6.2-arm64-arm-64bit",
    "architecture": "arm64"
  },
  "iterations": 20,
  "warmup": 2,
  "snapshot_nodes": 54,
  "snapshot_relationships": 141,
  "operational_nodes": 29,
  "operational_adjacencies": 37,
  "returned_evidence_nodes": 33,
  "returned_evidence_relationships": 35,
  "returned_unique_impact_paths": 21,
  "maximum_hops": 7,
  "direct_components": 3,
  "multi_hop_components": 15,
  "customers": 6,
  "measurements": {
    "direct_one_hop": {
      "median_ms": 0.74,
      "p95_ms": 1.24,
      "samples_ms": [
        1.24,
        1.279,
        1.181,
        0.981,
        0.766,
        0.716,
        0.742,
        0.738,
        0.768,
        0.722,
        0.71,
        0.815,
        0.703,
        0.84,
        0.692,
        0.927,
        0.658,
        0.657,
        0.648,
        0.647
      ]
    },
    "native_blast_radius": {
      "median_ms": 4.394,
      "p95_ms": 7.028,
      "samples_ms": [
        4.691,
        7.028,
        4.576,
        4.562,
        4.21,
        4.429,
        4.418,
        4.368,
        4.152,
        12.013,
        5.055,
        4.463,
        4.303,
        4.312,
        4.409,
        4.281,
        4.378,
        4.293,
        4.353,
        4.34
      ]
    },
    "native_blast_query": {
      "median_ms": 3.786,
      "p95_ms": 4.488,
      "samples_ms": [
        3.683,
        3.964,
        3.724,
        3.647,
        3.779,
        3.767,
        4.488,
        3.798,
        3.821,
        3.661,
        3.78,
        3.842,
        3.768,
        3.96,
        4.965,
        4.077,
        3.698,
        4.263,
        3.789,
        3.783
      ]
    },
    "native_investigation": {
      "median_ms": 24.773,
      "p95_ms": 32.09,
      "samples_ms": [
        23.54,
        24.977,
        24.018,
        24.26,
        25.042,
        24.512,
        24.185,
        24.261,
        32.318,
        24.613,
        24.288,
        25.868,
        24.992,
        24.933,
        25.068,
        25.072,
        25.692,
        24.372,
        32.09,
        24.425
      ]
    },
    "networkx_analytics": {
      "median_ms": 0.962,
      "p95_ms": 0.99,
      "samples_ms": [
        1.004,
        0.99,
        0.968,
        0.974,
        0.952,
        0.963,
        0.97,
        0.967,
        0.989,
        0.968,
        0.958,
        0.97,
        0.953,
        0.962,
        0.947,
        0.904,
        0.919,
        0.936,
        0.934,
        0.951
      ]
    },
    "deterministic_report": {
      "median_ms": 0.058,
      "p95_ms": 0.066,
      "samples_ms": [
        0.058,
        0.057,
        0.066,
        0.073,
        0.055,
        0.055,
        0.055,
        0.055,
        0.055,
        0.059,
        0.06,
        0.06,
        0.06,
        0.06,
        0.06,
        0.06,
        0.055,
        0.054,
        0.057,
        0.06
      ]
    },
    "pipeline_without_llm": {
      "median_ms": 32.13,
      "p95_ms": 39.792,
      "samples_ms": [
        31.659,
        33.184,
        31.451,
        39.792,
        33.02,
        31.722,
        32.115,
        32.145,
        32.342,
        31.289,
        40.141,
        31.714,
        32.442,
        31.93,
        31.538,
        31.137,
        39.392,
        31.786,
        34.195,
        33.399
      ]
    }
  },
  "limits": "Warm local connection; cached global snapshot; no UI rendering/startup/provider time. Pipeline includes fresh native queries, NetworkX, fictional comparison construction and report. Report-only excludes evidence construction. Server nodes examined/expansions are not measured."
}
```
