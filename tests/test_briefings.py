"""Role-specific editing can prioritize evidence but cannot introduce facts."""

from unittest.mock import patch

import pytest

from src.analytics import Analytics
from src.config import Settings
from src.investigator import investigate
from src.reports import build_evidence, generate_report


@pytest.fixture
def briefing_evidence(graph):
    result = investigate(graph, "vault")
    return build_evidence(graph, result, Analytics(graph).analyze(result, "failed"))


def test_three_roles_and_comparisons_are_graph_grounded(briefing_evidence):
    evidence = briefing_evidence
    assert {role.role for role in evidence.catalog.briefings} == {
        "incident commander",
        "service owner",
        "business stakeholder",
    }
    assert len(evidence.briefing_choices["mitigations"]) == 2
    assert all(
        item["after_score"] < item["before_score"]
        for item in evidence.briefing_choices["mitigations"].values()
    )


def test_provider_can_select_distinct_role_narrative(briefing_evidence):
    content = briefing_evidence.catalog.model_copy(deep=True)
    content.briefings[0].claim_ids.reverse()
    content.briefings[0].action_indices = [2, 0, 1]
    with patch("src.reports.generate", return_value=content.model_dump_json()):
        report = generate_report(
            briefing_evidence, Settings(llm_provider="groq", groq_api_key="fake")
        )
    assert report.provider == "groq"
    assert report.briefings[0].action_indices == [2, 0, 1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("claim_ids", ["invented-path"]),
        ("action_indices", [999]),
        ("mitigation_ids", ["guaranteed-99-percent-recovery"]),
    ],
)
def test_unsupported_entities_paths_and_numbers_fall_back(briefing_evidence, field, value):
    content = briefing_evidence.catalog.model_copy(deep=True)
    setattr(content.briefings[0], field, value)
    with patch("src.reports.generate", return_value=content.model_dump_json()):
        report = generate_report(
            briefing_evidence, Settings(llm_provider="groq", groq_api_key="fake")
        )
    assert report.provider == "deterministic"
    assert report.grounding_warnings
