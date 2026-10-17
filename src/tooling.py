"""Allowlisted typed tool boundary; no arbitrary Cypher, Python, or cloud actions."""

import asyncio
import logging
import re
import threading
from contextlib import contextmanager
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.analytics import Analytics, ComponentAnalysis, Metrics, RiskScore
from src.config import Settings
from src.database import DatabaseError, DatabaseManager
from src.graph_queries import Deployment, EvidencePath, GraphQueries, Impact, QueryLimits
from src.investigator import investigate
from src.native_queries import NativeGraphQueries
from src.reports import path_id
from src.simulator import TimelineEvent
from src.topology import Node, Topology

logger = logging.getLogger(__name__)
TOOL_NAMES = (
    "lookup_component",
    "trace_upstream_dependencies",
    "trace_downstream_blast_radius",
    "find_customer_impact",
    "find_business_workflows",
    "find_critical_paths",
    "detect_bottlenecks",
    "get_owner_and_runbook",
    "calculate_risk",
    "inspect_falkordb_evidence",
    "simulate_fictional_mitigation",
)
ActionName = Literal[
    "activate_declared_replica",
    "reroute_traffic",
    "isolate_unhealthy_dependency",
    "switch_to_read_only_mode",
    "disable_optional_feature",
    "execute_fictional_runbook",
]


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    component: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _./-]*$")
    depth: int = Field(default=6, ge=1, le=8)
    max_paths: int = Field(default=60, ge=1, le=100)
    status: Literal["healthy", "degraded", "unhealthy", "failed", "down"] = "failed"


class SimulationInput(ToolInput):
    action: ActionName
    confirmed: bool = False


class ActionEvidence(BaseModel):
    action: ActionName
    eligible: bool
    reason: str
    paths: list[EvidencePath] = Field(default_factory=list)


class SimulatedState(BaseModel):
    risk: RiskScore
    affected_ids: list[str]
    statuses: dict[str, str]
    timestamp_seconds: int


class SimulationSummary(BaseModel):
    action: str
    before_score: float
    before_affected_ids: list[str]
    after: SimulatedState
    risk_reduction: float
    removed_critical_paths: list[EvidencePath]
    events: list[TimelineEvent]
    explanation: str


class ToolResult(BaseModel):
    """Every successful factual claim has typed original-edge evidence."""

    model_config = ConfigDict(extra="forbid")
    tool: str
    component: Node | None = None
    suggestions: list[Node] = Field(default_factory=list)
    impacts: list[Impact] = Field(default_factory=list)
    customers: list[Impact] = Field(default_factory=list)
    workflows: list[Impact] = Field(default_factory=list)
    owners: list[Impact] = Field(default_factory=list)
    runbooks: list[Impact] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    deployment: Deployment | None = None
    metrics: Metrics | None = None
    analysis: ComponentAnalysis | None = None
    action_eligibility: list[ActionEvidence] = Field(default_factory=list)
    simulation: SimulationSummary | None = None
    query_diagnostics: list[dict] = Field(default_factory=list)
    reasoning_engine: str = "not executed"
    duration_ms: float = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


def sanitize(text: str, settings: Settings) -> str:
    """Redact configured keys and recognized provider-key patterns, never log values."""
    for secret in (settings.gemini_api_key, settings.groq_api_key):
        if secret:
            text = text.replace(secret, "[redacted]")
    return re.sub(r"(?:gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,})", "[redacted]", text)


class ToolService:
    """One serialized worker; timed-out read-only work cannot spawn more workers."""

    def __init__(self, settings: Settings, *, queries: GraphQueries | None = None):
        self.settings = settings
        self.queries = queries
        self.timeout_seconds = 15.0
        self.max_result_bytes = 120_000
        self._busy = threading.Lock()

    @contextmanager
    def session(self, args: ToolInput):
        limits = QueryLimits(depth=args.depth, max_paths=args.max_paths)
        if self.queries is not None:
            graph = GraphQueries(
                Topology(nodes=list(self.queries.nodes.values()), relationships=self.queries.edges),
                limits,
            )
            yield graph, lambda: graph
        else:
            with DatabaseManager(self.settings) as db:
                yield NativeGraphQueries(db, limits), lambda: GraphQueries.from_database(db, limits)

    def call(self, name: str, arguments: dict) -> ToolResult:
        started = perf_counter()
        if name not in TOOL_NAMES:
            return ToolResult(
                tool="unknown", error="unknown_tool", warnings=["Tool is not allowlisted"]
            )
        try:
            cls = SimulationInput if name == "simulate_fictional_mitigation" else ToolInput
            args = cls.model_validate(arguments)
        except ValidationError:
            return ToolResult(
                tool=name,
                error="invalid_input",
                warnings=["Arguments do not match the bounded tool schema"],
            )
        if isinstance(args, SimulationInput) and not args.confirmed:
            return ToolResult(
                tool=name,
                error="confirmation_required",
                warnings=["Explicit human confirmation is required before fictional simulation"],
            )
        try:
            with self.session(args) as (q, snapshot):
                result = self._perform(name, args, q, snapshot)
                result.reasoning_engine = getattr(q, "reasoning_engine", "bounded Python fallback")
                result.query_diagnostics = list(getattr(q, "diagnostics", []))
                result.warnings = sorted(set(result.warnings + q.warnings))
            result.duration_ms = round((perf_counter() - started) * 1000, 3)
            for field in ("impacts", "customers", "workflows", "owners", "runbooks"):
                items = getattr(result, field)
                if len(items) > args.max_paths:
                    setattr(result, field, items[: args.max_paths])
                    result.warnings.append("Tool entity result limit reached")
            if any(path.hops for path in result.paths):
                result.paths = [path for path in result.paths if path.hops]
            unique = {path_id(path): path for path in result.paths}
            if len(unique) > args.max_paths:
                result.warnings.append("Tool path result limit reached")
            result.paths = [unique[key] for key in sorted(unique)][: args.max_paths]
            result.evidence_ids = [path_id(path) for path in result.paths]
            clean = sanitize(result.model_dump_json(), self.settings)
            if len(clean.encode()) > self.max_result_bytes:
                return ToolResult(
                    tool=name,
                    error="result_limit",
                    warnings=["Tool result cap reached; evidence omitted, not complete"],
                )
            logger.info("event=tool_complete tool=%s duration_ms=%.3f", name, result.duration_ms)
            return ToolResult.model_validate_json(clean)
        except (DatabaseError, ValueError, KeyError, TypeError, RuntimeError):
            logger.warning("event=tool_failed tool=%s", name)
            return ToolResult(
                tool=name,
                error="unavailable",
                warnings=[
                    "Tool unavailable or evidence failed validation; no infrastructure changes made"
                ],
            )

    def _perform(self, name, args, q, snapshot):
        lookup = q.exact_lookup(args.component)
        root = lookup.matched
        result = ToolResult(tool=name, component=root, suggestions=lookup.suggestions)
        if root is None:
            result.warnings.append("Component not uniquely matched; choose an exact ID")
            return result
        zero = EvidencePath(
            node_ids=[root.id], edges=[], hops=0, required=True, criticality=root.criticality
        )
        result.paths = [zero]
        if name == "lookup_component":
            return result
        if name == "inspect_falkordb_evidence":
            result.deployment = q.deployment(root.id)
            for edge in result.deployment.evidence_edges:
                result.paths.append(q._path([edge.source, edge.target], [edge]))
        elif name == "trace_upstream_dependencies":
            result.impacts = q.dependencies(root.id)
        elif name == "trace_downstream_blast_radius":
            result.impacts = q.blast_radius(root.id)
        elif name in {"find_customer_impact", "find_business_workflows", "get_owner_and_runbook"}:
            affected = [Impact(component=root, hops=0, path=zero, required=True)] + q.blast_radius(
                root.id
            )
            if name == "get_owner_and_runbook":
                result.owners, result.runbooks = q.teams(affected), q.runbooks(affected)
                from src.actions import action_options

                graph = snapshot()
                if graph.nodes.get(root.id) != root:
                    raise ValueError("Action evidence changed")
                result.action_eligibility = action_options(graph, root.id, status=args.status)
                for action in result.action_eligibility:
                    result.paths += action.paths
            else:
                result.workflows = q.workflows(affected)
                if name == "find_customer_impact":
                    result.customers = q.customers(result.workflows)
        elif name == "find_critical_paths":
            for impact in q.blast_radius(root.id):
                result.paths += q.critical_paths(root.id, impact.component.id)
                if len(result.paths) >= args.max_paths:
                    result.warnings.append("Critical path result limit reached")
                    break
        elif name in {"detect_bottlenecks", "calculate_risk"}:
            graph = snapshot()
            analysis = Analytics(graph)
            if root.id not in analysis.graph:
                result.warnings.append(
                    "Structural/risk scoring applies to operational components, not an independent regional model"
                )
            elif name == "detect_bottlenecks":
                result.metrics = analysis.metrics(root.id)
                result.impacts = q.blast_radius(root.id)
            else:
                investigation = investigate(q, root.id)
                if any(graph.nodes.get(node.id) != node for node in investigation.evidence_nodes):
                    raise ValueError("Snapshot changed during tool call")
                result.analysis = analysis.analyze(investigation, args.status)
                result.paths += investigation.shortest_paths + investigation.critical_paths
                result.customers, result.workflows = (
                    investigation.impacted_customers,
                    investigation.impacted_workflows,
                )
        elif name == "simulate_fictional_mitigation":
            from src.actions import simulate_action

            graph = snapshot()
            if graph.nodes.get(root.id) != root:
                raise ValueError("Action evidence changed")
            return simulate_action(graph, args, result)
        for impact in (
            result.impacts + result.customers + result.workflows + result.owners + result.runbooks
        ):
            result.paths.append(impact.path)
        return result

    def _worker(self, name, arguments):
        try:
            return self.call(name, arguments)
        finally:
            self._busy.release()

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        if not self._busy.acquire(blocking=False):
            return ToolResult(
                tool="busy",
                error="busy",
                warnings=["Previous bounded tool work is still finishing"],
            )
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._worker, name, arguments), self.timeout_seconds
            )
        except TimeoutError:
            return ToolResult(
                tool="timeout",
                error="timeout",
                warnings=["Tool deadline reached; no writes or cloud actions performed"],
            )
