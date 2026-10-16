"""Judge-facing evidence must expose real paths, limits and execution origin."""

from importlib import import_module

from src.investigator import InvestigationResult, investigate


def test_evidence_summary_uses_real_customer_and_owner_paths(graph):
    result = investigate(graph, "vault")
    summary = import_module("src.evidence_ui").evidence_summary(result)
    assert summary["customer_path"].hops >= 3
    assert summary["customer_path"].node_ids[0] == "vault"
    assert summary["customer_path"].node_ids[-1] in {
        i.component.id for i in result.impacted_customers
    }
    assert summary["owner_path"].node_ids[-2] in summary["customer_path"].node_ids
    assert summary["nodes_returned"] == len(result.evidence_nodes)
    assert not summary["truncated"]


def test_empty_and_partial_evidence_summary():
    result = InvestigationResult(incident_input="missing", warnings=["Path limit reached"])
    summary = import_module("src.evidence_ui").evidence_summary(result)
    assert summary["customer_path"] is None
    assert summary["truncated"]
    assert summary["nodes_returned"] == 0
