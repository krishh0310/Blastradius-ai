"""Presentation-only, judge-facing evidence summaries and query receipts."""

import streamlit as st

from src.investigator import InvestigationResult


def evidence_summary(result: InvestigationResult) -> dict:
    """Select existing evidence, never infer new infrastructure relationships."""
    candidates = [impact for impact in result.impacted_customers if impact.hops >= 3]
    customer = min(candidates, key=lambda item: (item.hops, item.component.id), default=None)
    path = customer.path if customer else None
    owners = [
        impact.path
        for impact in result.owner_teams
        if path and impact.path.hops and impact.path.node_ids[-2] in path.node_ids
    ]
    owner = max(owners, key=lambda item: (item.hops, item.node_ids), default=None)
    return {
        "customer_path": path,
        "owner_path": owner,
        "nodes_returned": len(result.evidence_nodes),
        "relationships_returned": len(result.evidence_edges),
        "maximum_hops": max(
            (
                i.hops
                for i in result.direct_impact + result.cascading_impact + result.impacted_customers
            ),
            default=0,
        ),
        "truncated": any(
            "limit" in warning.lower() or "truncat" in warning.lower()
            for warning in result.warnings
        ),
    }


def render_evidence(result: InvestigationResult) -> None:
    """Keep graph value visible without touring the detailed tabs."""
    summary = evidence_summary(result)
    st.subheader("FalkorDB Evidence")
    st.caption(
        f"Reasoning engine: {result.reasoning_engine} · investigation {result.query_execution_ms:.0f} ms"
    )
    if summary["truncated"]:
        st.warning(
            "Partial evidence: a configured limit was reached. Counts are bounded, not complete totals."
        )
    st.caption(
        f"Returned evidence: {summary['nodes_returned']} nodes · "
        f"{summary['relationships_returned']} relationships · "
        f"maximum {summary['maximum_hops']} hops · truncation: {summary['truncated']}"
    )
    left, right = st.columns(2)
    with left:
        st.write("Flat lookup: direct dependencies only")
        st.write(
            f"{len(result.direct_impact)} directly exposed components; business impact requires following more relationships."
        )
    with right:
        st.write("Graph traversal: bounded multi-hop evidence")
        st.write(
            f"{len(result.impacted_customers)} potentially exposed customers through recorded workflows."
        )
    names = {node.id: node.name for node in result.evidence_nodes}
    path = summary["customer_path"]
    if path:
        st.code(
            " → ".join(names.get(identifier, identifier) for identifier in path.node_ids),
            language=None,
        )
        st.caption(
            f"{path.hops} hops · {'required' if path.required else 'optional-only'} path · "
            f"minimum edge criticality {path.criticality}/5. Potential impact, not confirmed outage."
        )
        if summary["owner_path"]:
            owner = summary["owner_path"]
            st.write(
                "Responsible owner branch: " + " → ".join(names.get(n, n) for n in owner.node_ids)
            )
        with st.expander("Exact path relationships"):
            st.dataframe([edge.model_dump() for edge in path.edges], hide_index=True)
    else:
        st.info("No three-plus-hop customer path is recorded within these limits.")
    st.caption(
        "FalkorDB resolves this cross-domain question through relationship traversal. "
        "A relational design would require recursive joins across infrastructure, ownership, "
        "workflow and customer associations. SQL can do this; graph traversal makes the changing relationships more direct."
    )
    with st.expander("Executed Cypher and safe query receipts", expanded=False):
        if not result.query_diagnostics:
            st.info(
                "No native query receipts support this result. It uses the labeled Python snapshot."
            )
        for query in result.query_diagnostics:
            st.write(
                f"{query['name']} · {query['elapsed_ms']:.3f} ms · {query['rows_returned']} rows"
            )
            st.code(query["cypher"], language="cypher")
            st.json(query["parameters"])
            if query["truncated"]:
                st.warning("This operation reached its result cap.")
        st.caption(
            "Counts describe returned evidence, not server nodes examined. Database expansion counts are not measured."
        )
