"""Presentation only: the official MCP client owns agent and action execution."""

import asyncio

import streamlit as st

from src.agent import AgentRequest, AgentResult, run_agent_mcp, simulate_recommended
from src.config import Settings


def run_request(request: AgentRequest, settings: Settings) -> AgentResult:
    return asyncio.run(run_agent_mcp(request, settings=settings))


def simulate_request(result: AgentResult, request: AgentRequest, settings: Settings) -> AgentResult:
    return asyncio.run(simulate_recommended(result, request, confirmed=True, settings=settings))


def render_agent(result: AgentResult) -> None:
    st.subheader("Agent Tool Trace")
    st.caption(
        "FalkorDB native reasoning · NetworkX structural analytics · "
        "deterministic fallback · fictional action simulation"
    )
    st.write(result.incident)
    st.caption(f"Planner: {result.planner} · Transport: {result.transport}")
    if result.trace:
        st.dataframe(
            [
                {
                    "Order": step.order,
                    "Tool": step.tool,
                    "Why selected": step.reason,
                    "Selected by": step.selector,
                    "Elapsed ms": round(step.output.duration_ms, 2),
                    "Evidence IDs": len(step.output.evidence_ids),
                    "Supporting paths": len(step.output.paths),
                    "Status": step.output.error or "Completed",
                }
                for step in result.trace
            ],
            hide_index=True,
            width="stretch",
        )
    for step in result.trace:
        with st.expander(f"Tool {step.order}: {step.tool} — evidence and query timing"):
            st.write(step.reason)
            st.caption(f"Selected by: {step.selector}; planning: {step.planning_ms:.2f} ms")
            st.json(step.inputs)
            st.caption(f"Reasoning engine: {step.output.reasoning_engine}")
            st.json(step.output.model_dump(mode="json"))
    st.write(f"Stop: {result.stopping_reason}")
    st.caption(f"Confidence: {result.final_confidence}; this is not a confirmed root cause.")
    for warning in result.warnings:
        st.warning(warning)
    if result.recommendation:
        st.write(f"Recommended fictional action: {result.recommendation.action}")
        st.write(result.recommendation.reason)
        for path in result.recommendation.paths:
            st.code(" → ".join(path.node_ids) + f" ({path.hops} hops)")
    else:
        st.info("No evidence-supported recommendation is available within this tool budget.")
    for step in result.trace:
        if step.output.simulation:
            comparison = step.output.simulation
            st.subheader("Fictional mitigation comparison")
            before, after = st.columns(2)
            before.metric("Before risk", f"{comparison.before_score:.2f}")
            after.metric("After risk", f"{comparison.after.risk.score:.2f}")
            st.write(
                f"Affected entities: {len(comparison.before_affected_ids)} before → "
                f"{len(comparison.after.affected_ids)} after. "
                f"Critical paths removed: {len(comparison.removed_critical_paths)}."
            )
            st.write(comparison.explanation)
            st.info("In-memory fictional scenario only. No real infrastructure was repaired.")
