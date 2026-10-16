"""Constrained role narratives: select evidence IDs, never generate new facts."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RoleBriefing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["incident commander", "service owner", "business stakeholder"]
    claim_ids: list[str] = Field(max_length=8)
    action_indices: list[int] = Field(max_length=3)
    question_indices: list[int] = Field(max_length=3)
    mitigation_ids: list[str] = Field(max_length=2)


def statement_id(statement) -> str:
    text = json.dumps(statement.model_dump(), sort_keys=True, separators=(",", ":"))
    return "claim-" + hashlib.sha256(text.encode()).hexdigest()[:16]


def briefing_choices(queries, result, catalog) -> tuple[list[RoleBriefing], dict]:
    """Compute fictional options once; provider only prioritizes supplied choices."""
    statements = catalog.confirmed_facts + catalog.likely_root_causes + catalog.affected_entities
    claims = {statement_id(item): item.model_dump() for item in statements}
    questions = [
        "Is the recorded health current according to independent telemetry?",
        "Which declared alternate has verified freshness and spare capacity?",
        "Do the required and optional edges match observed runtime behavior?",
    ]
    mitigations = {}
    if result.matched_component and result.matched_component.label in {
        "Service",
        "Database",
        "Queue",
        "API",
    }:
        from src.simulator import SimulationConfig, Simulator
        from src.topology import Topology

        simulator = Simulator(
            Topology(nodes=list(queries.nodes.values()), relationships=queries.edges),
            SimulationConfig(component_id=result.matched_component.id),
        )
        before = simulator.run().frames[-1]
        for action in ["Isolate unhealthy dependency", "Degraded read-only mode"]:
            if simulator.mitigation_options()[action] is None:
                after = simulator.run(action).frames[-1]
                mitigations[action] = {
                    "before_score": before.risk.score,
                    "after_score": after.risk.score,
                    "before_entities": len(before.affected_ids),
                    "after_entities": len(after.affected_ids),
                    "basis": "Fictional simulation, not verified recovery; all initial health assumed healthy.",
                }
    roles = []
    selections = [
        catalog.confirmed_facts[:1] + catalog.affected_entities[:2],
        catalog.likely_root_causes[:2] + catalog.confirmed_facts[:2],
        [item for item in catalog.affected_entities if "customer" in item.text][:3],
    ]
    for index, role in enumerate(["incident commander", "service owner", "business stakeholder"]):
        roles.append(
            RoleBriefing(
                role=role,
                claim_ids=[statement_id(item) for item in selections[index]],
                action_indices=[0, 1, 2] if index != 1 else [1, 0, 2],
                question_indices=[0, 1, 2],
                mitigation_ids=list(mitigations),
            )
        )
    return roles, {"claims": claims, "questions": questions, "mitigations": mitigations}


def validate_briefings(roles: list[RoleBriefing], choices: dict, actions: list[str]) -> list[str]:
    """IDs and indices eliminate unsupported entities, numbers and free-form claims."""
    expected = {"incident commander", "service owner", "business stakeholder"}
    if len(roles) != 3 or {item.role for item in roles} != expected:
        return ["Missing or duplicated briefing audience"]
    for role in roles:
        if (
            any(identifier not in choices["claims"] for identifier in role.claim_ids)
            or any(type(i) is not int or not 0 <= i < len(actions) for i in role.action_indices)
            or any(
                type(i) is not int or not 0 <= i < len(choices["questions"])
                for i in role.question_indices
            )
            or any(identifier not in choices["mitigations"] for identifier in role.mitigation_ids)
        ):
            return ["Unsupported briefing claim, path, action, number or mitigation reference"]
        if len(role.claim_ids) != len(set(role.claim_ids)):
            return ["Duplicated briefing claim"]
    return []
