# Measured local graph benchmark

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
