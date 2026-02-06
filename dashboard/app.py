"""
AI Influence Tracker Dashboard

What AI Companies Say vs. What They Lobby For

A Streamlit dashboard visualizing:
- Policy positions extracted from AI Action Plan submissions
- Lobbying activity from Senate LDA disclosures
- Discrepancies between public statements and lobbying behavior
"""

import sys
from pathlib import Path

# Add dashboard directory to path for imports (needed for Streamlit Cloud)
dashboard_dir = Path(__file__).parent
if str(dashboard_dir) not in sys.path:
    sys.path.insert(0, str(dashboard_dir))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import load_all_data, get_canonical_name

# Page config
st.set_page_config(
    page_title="AI Influence Tracker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .score-good { color: #28a745; }
    .score-moderate { color: #ffc107; }
    .score-bad { color: #dc3545; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def get_data():
    """Load and cache all data."""
    return load_all_data()


def score_color(score: int, reverse: bool = False) -> str:
    """Return color class based on score (0-100)."""
    if reverse:
        score = 100 - score
    if score <= 40:
        return "score-good"
    elif score <= 60:
        return "score-moderate"
    else:
        return "score-bad"


def render_executive_summary(data: dict):
    """Section 1: Executive Summary / Landing Page."""
    st.title("AI Influence Tracker")
    st.markdown("### What AI Companies Say vs. What They Lobby For")

    positions_df = data["positions"]
    impact_df = data["impact_scores"]
    discrepancy_df = data["discrepancy_scores"]
    china_df = data["china_rhetoric"]

    # Headline stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Policy Positions Analyzed",
            value=f"{len(positions_df):,}"
        )

    with col2:
        st.metric(
            label="Companies Tracked",
            value=len(positions_df["submitter_name"].unique())
        )

    with col3:
        if not discrepancy_df.empty:
            avg_discrepancy = discrepancy_df["discrepancy_score"].mean()
            st.metric(
                label="Avg Discrepancy Score",
                value=f"{avg_discrepancy:.0f}/100"
            )

    with col4:
        if not china_df.empty:
            china_users = len(china_df[china_df["rhetoric_intensity"] > 20])
            st.metric(
                label="Companies Using China Rhetoric",
                value=f"{china_users}"
            )

    st.divider()

    # Key Findings
    st.subheader("Key Findings")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Say-vs-Do Consistency")
        if not discrepancy_df.empty:
            # Most consistent
            most_consistent = discrepancy_df.loc[discrepancy_df["discrepancy_score"].idxmin()]
            least_consistent = discrepancy_df.loc[discrepancy_df["discrepancy_score"].idxmax()]

            st.success(f"**Most Consistent:** {most_consistent['company_name']} ({most_consistent['discrepancy_score']:.0f}/100)")
            st.error(f"**Biggest Gap:** {least_consistent['company_name']} ({least_consistent['discrepancy_score']:.0f}/100)")

        st.markdown("#### Public Interest Concern")
        if not impact_df.empty:
            least_concern = impact_df.loc[impact_df["concern_score"].idxmin()]
            most_concern = impact_df.loc[impact_df["concern_score"].idxmax()]

            st.success(f"**Least Concerning:** {least_concern['company_name']} ({least_concern['concern_score']:.0f}/100)")
            st.warning(f"**Most Concerning:** {most_concern['company_name']} ({most_concern['concern_score']:.0f}/100)")

    with col2:
        st.markdown("#### China Rhetoric Usage")
        if not china_df.empty:
            china_sorted = china_df.sort_values("rhetoric_intensity", ascending=False)
            top_china = china_sorted.head(3)

            for _, row in top_china.iterrows():
                intensity = row["rhetoric_intensity"]
                if intensity >= 70:
                    st.error(f"**{row['company_name']}:** {intensity:.0f}/100 intensity")
                elif intensity >= 40:
                    st.warning(f"**{row['company_name']}:** {intensity:.0f}/100 intensity")
                else:
                    st.info(f"**{row['company_name']}:** {intensity:.0f}/100 intensity")

        st.markdown("#### Top Policy Asks")
        if not positions_df.empty:
            top_asks = positions_df["policy_ask"].value_counts().head(5)
            for ask, count in top_asks.items():
                st.write(f"• **{ask.replace('_', ' ').title()}**: {count} positions")

    st.divider()

    # Company Leaderboard
    st.subheader("Company Scorecard")

    if not discrepancy_df.empty and not impact_df.empty:
        # Merge scores for leaderboard
        leaderboard = discrepancy_df[["company_name", "company_type", "discrepancy_score"]].copy()

        if not impact_df.empty:
            impact_merge = impact_df[["company_name", "concern_score"]]
            leaderboard = leaderboard.merge(impact_merge, on="company_name", how="left")

        if not china_df.empty:
            china_merge = china_df[["company_name", "rhetoric_intensity"]]
            leaderboard = leaderboard.merge(china_merge, on="company_name", how="left")
            leaderboard["rhetoric_intensity"] = leaderboard["rhetoric_intensity"].fillna(0)

        # Add sort order: ai_lab first (1), big_tech second (2), trade_group third (3)
        type_sort_order = {"ai_lab": 1, "big_tech": 2, "trade_group": 3}
        leaderboard["_sort_order"] = leaderboard["company_type"].map(type_sort_order).fillna(4)
        leaderboard = leaderboard.sort_values(["_sort_order", "discrepancy_score"])
        leaderboard = leaderboard.drop(columns=["_sort_order"])

        # Display as styled table
        st.dataframe(
            leaderboard.rename(columns={
                "company_name": "Company",
                "company_type": "Type",
                "discrepancy_score": "Discrepancy (0=consistent)",
                "concern_score": "Concern (0=aligned)",
                "rhetoric_intensity": "China Rhetoric"
            }),
            use_container_width=True,
            hide_index=True
        )


def render_company_deep_dive(data: dict):
    """Section 2: Company Deep Dive."""
    st.header("Company Deep Dive")

    positions_df = data["positions"]
    impact_df = data["impact_scores"]
    discrepancy_df = data["discrepancy_scores"]
    china_df = data["china_rhetoric"]
    filings_df = data["filings"]
    activities_df = data["activities"]

    # Company selector - sorted by type (ai_lab first, then big_tech, then trade_group)
    type_sort_order = {"ai_lab": 1, "big_tech": 2, "trade_group": 3}
    company_names = positions_df["submitter_name"].unique()

    # Get company types from discrepancy or impact scores
    company_types = {}
    if not discrepancy_df.empty:
        company_types = dict(zip(discrepancy_df["company_name"], discrepancy_df["company_type"]))
    elif not impact_df.empty:
        company_types = dict(zip(impact_df["company_name"], impact_df["company_type"]))

    # Sort: by type order first, then alphabetically within each type
    companies = sorted(
        company_names,
        key=lambda x: (type_sort_order.get(company_types.get(x, ""), 4), x)
    )
    default_idx = companies.index("OpenAI") if "OpenAI" in companies else 0
    selected_company = st.selectbox("Select Company", companies, index=default_idx)

    if not selected_company:
        return

    st.divider()

    # Company scorecard
    col1, col2, col3, col4 = st.columns(4)

    # Get scores for this company
    # Convert submitter_name to canonical name for matching scores
    # (e.g., "Anthropic-AI" -> "Anthropic")
    canonical_name = get_canonical_name(selected_company)
    company_discrepancy = discrepancy_df[discrepancy_df["company_name"] == canonical_name]
    company_impact = impact_df[impact_df["company_name"] == canonical_name]
    company_china = china_df[china_df["company_name"] == canonical_name]
    company_positions = positions_df[positions_df["submitter_name"] == selected_company]

    with col1:
        if not company_discrepancy.empty:
            score = company_discrepancy.iloc[0]["discrepancy_score"]
            st.metric("Discrepancy Score", f"{score:.0f}/100", help="0=consistent, 100=hypocrite")
        else:
            st.metric("Discrepancy Score", "N/A")

    with col2:
        if not company_impact.empty:
            score = company_impact.iloc[0]["concern_score"]
            st.metric("Concern Score", f"{score:.0f}/100", help="0=public interest aligned, 100=concerning")
        else:
            st.metric("Concern Score", "N/A")

    with col3:
        if not company_china.empty:
            score = company_china.iloc[0]["rhetoric_intensity"]
            st.metric("China Rhetoric", f"{score:.0f}/100", help="0=minimal, 100=heavy use")
        else:
            st.metric("China Rhetoric", "0/100")

    with col4:
        st.metric("Positions Extracted", len(company_positions))

    st.divider()

    # Two columns: What they say vs What they lobby for
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("What They Say")
        st.caption("Top policy positions from their AI Action Plan submission")

        if not company_positions.empty:
            # Top policy asks
            top_asks = company_positions["policy_ask"].value_counts().head(8)

            fig = px.bar(
                x=top_asks.values,
                y=top_asks.index,
                orientation="h",
                labels={"x": "Count", "y": "Policy Ask"},
                color_discrete_sequence=["#1f77b4"]
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(autorange="reversed")
            )
            st.plotly_chart(fig, use_container_width=True)

            # Top arguments
            st.markdown("**Primary Arguments Used:**")
            top_args = company_positions["primary_argument"].value_counts().head(5)
            for arg, count in top_args.items():
                if arg:
                    st.write(f"• {arg.replace('_', ' ').title()}: {count}")

    with col2:
        st.subheader("What They Lobby For")
        st.caption("From Senate LDA lobbying disclosures")

        # Get lobbying data for this company (need to match by LDA name)
        from data_loader import get_lda_name, get_lda_aliases
        lda_name = get_lda_name(selected_company)

        if lda_name and not filings_df.empty:
            # Get all aliases for this company's LDA name
            aliases = get_lda_aliases(lda_name)
            company_filings = filings_df[filings_df["client_name"].str.upper().isin([a.upper() for a in aliases])]

            if not company_filings.empty:
                total_spend = company_filings["lobbying_expenses"].sum()
                filing_count = len(company_filings)

                st.metric("Total Lobbying Spend", f"${total_spend:,.0f}")
                st.metric("Filings (2023+)", filing_count)

                # Issue codes
                if not activities_df.empty:
                    filing_uuids = company_filings["filing_uuid"].tolist()
                    company_activities = activities_df[activities_df["filing_uuid"].isin(filing_uuids)]

                    if not company_activities.empty:
                        st.markdown("**Issues Lobbied On:**")
                        issue_counts = company_activities["issue_code_display"].value_counts().head(5)
                        for issue, count in issue_counts.items():
                            st.write(f"• {issue}: {count}")
            else:
                st.info("No lobbying filings found for this company")
        else:
            st.info("No lobbying data available")

    st.divider()

    # Discrepancy details
    st.subheader("Say vs. Do Analysis")

    if not company_discrepancy.empty:
        row = company_discrepancy.iloc[0]

        # Key finding
        if "key_finding" in row.index and row["key_finding"]:
            st.info(row["key_finding"])

        # Discrepancies
        if "discrepancies" in row.index and row["discrepancies"]:
            st.markdown("**Key Discrepancies:**")
            try:
                import json
                discrepancies = row["discrepancies"]
                if isinstance(discrepancies, str):
                    discrepancies = json.loads(discrepancies)
                if isinstance(discrepancies, list):
                    for d in discrepancies[:3]:
                        if isinstance(d, dict):
                            # Format the discrepancy nicely
                            disc_type = d.get('type', '').replace('_', ' ').title()
                            policy = d.get('policy_ask', '').replace('_', ' ').title()
                            interpretation = d.get('interpretation', '')
                            severity = d.get('severity', '')

                            if severity == 'significant':
                                st.error(f"**{policy}** ({disc_type}): {interpretation}")
                            elif severity == 'moderate':
                                st.warning(f"**{policy}** ({disc_type}): {interpretation}")
                            else:
                                st.info(f"**{policy}** ({disc_type}): {interpretation}")
                        else:
                            st.warning(f"• {d}")
                else:
                    st.write(discrepancies)
            except Exception:
                st.write(row["discrepancies"])

        # Lobbying priorities vs rhetoric
        if "lobbying_priorities_vs_rhetoric" in row.index and row["lobbying_priorities_vs_rhetoric"]:
            st.markdown("**Lobbying vs. Rhetoric:**")
            try:
                import json
                lvr = row["lobbying_priorities_vs_rhetoric"]
                if isinstance(lvr, str):
                    lvr = json.loads(lvr)
                if isinstance(lvr, dict):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("*Top Lobbying Areas:*")
                        for area in lvr.get("top_lobbying_areas", []):
                            st.write(f"• {area}")
                    with col2:
                        st.markdown("*Top Stated Priorities:*")
                        for priority in lvr.get("top_stated_priorities", []):
                            st.write(f"• {priority.replace('_', ' ').title()}")

                    assessment = lvr.get("alignment_assessment", "")
                    if assessment:
                        st.markdown(f"*Assessment:* {assessment}")
                else:
                    st.write(lvr)
            except Exception:
                st.write(row["lobbying_priorities_vs_rhetoric"])
    else:
        st.info("No discrepancy analysis available for this company")


def render_cross_company_comparison(data: dict):
    """Section 3: Cross-Company Comparison."""
    st.header("Cross-Company Comparison")

    discrepancy_df = data["discrepancy_scores"]
    impact_df = data["impact_scores"]
    china_df = data["china_rhetoric"]
    positions_df = data["positions"]

    tab1, tab2, tab3 = st.tabs(["Score Comparisons", "Policy Positions", "Company Types"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Discrepancy Scores")
            st.caption("Say-vs-Do gap: 0 = consistent, 100 = hypocritical")

            if not discrepancy_df.empty:
                df_sorted = discrepancy_df.sort_values("discrepancy_score", ascending=False)

                fig = px.bar(
                    df_sorted,
                    x="discrepancy_score",
                    y="company_name",
                    orientation="h",
                    color="discrepancy_score",
                    color_continuous_scale=["green", "yellow", "red"],
                    range_color=[0, 100]
                )
                fig.update_layout(
                    height=400,
                    showlegend=False,
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("China Rhetoric Intensity")
            st.caption("How heavily companies invoke China competition")

            if not china_df.empty:
                df_sorted = china_df.sort_values("rhetoric_intensity", ascending=False)

                fig = px.bar(
                    df_sorted,
                    x="rhetoric_intensity",
                    y="company_name",
                    orientation="h",
                    color="rhetoric_intensity",
                    color_continuous_scale=["green", "yellow", "red"],
                    range_color=[0, 100]
                )
                fig.update_layout(
                    height=400,
                    showlegend=False,
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)

        # Scatter plot: Concern vs Discrepancy
        st.subheader("Concern vs. Discrepancy")
        st.caption("Who's concerning AND hypocritical? Hover for details.")

        if not discrepancy_df.empty and not impact_df.empty:
            merged = discrepancy_df.merge(
                impact_df[["company_name", "concern_score"]],
                on="company_name",
                how="inner"
            )

            if not merged.empty:
                import numpy as np

                # Add jitter to separate overlapping points
                np.random.seed(42)  # Reproducible jitter
                merged = merged.copy()
                merged["concern_jittered"] = merged["concern_score"] + np.random.uniform(-3, 3, len(merged))
                merged["discrepancy_jittered"] = merged["discrepancy_score"] + np.random.uniform(-2, 2, len(merged))

                # Assign text positions to spread labels out
                # Cycle through positions based on row index
                positions = ["top center", "bottom center", "top right", "bottom left",
                             "top left", "bottom right", "middle right", "middle left"]
                merged["text_position"] = [positions[i % len(positions)] for i in range(len(merged))]

                fig = go.Figure()

                # Add points by company type for legend
                for company_type in merged["company_type"].unique():
                    df_type = merged[merged["company_type"] == company_type]
                    fig.add_trace(go.Scatter(
                        x=df_type["concern_jittered"],
                        y=df_type["discrepancy_jittered"],
                        mode="markers+text",
                        name=company_type,
                        text=df_type["company_name"],
                        textposition=df_type["text_position"].tolist(),
                        textfont=dict(size=10),
                        marker=dict(size=14),
                        hovertemplate="<b>%{text}</b><br>" +
                                      "Concern: %{customdata[0]}<br>" +
                                      "Discrepancy: %{customdata[1]}<br>" +
                                      "Type: " + company_type + "<extra></extra>",
                        customdata=list(zip(df_type["concern_score"], df_type["discrepancy_score"]))
                    ))

                fig.update_layout(
                    height=550,
                    xaxis_title="Concern Score (0=aligned, 100=concerning)",
                    yaxis_title="Discrepancy Score (0=consistent, 100=hypocrite)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )

                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Policy Position Distribution")

        if not positions_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Most Common Policy Asks**")
                ask_counts = positions_df["policy_ask"].value_counts().head(10)

                fig = px.bar(
                    x=ask_counts.values,
                    y=ask_counts.index,
                    orientation="h",
                    labels={"x": "Count", "y": "Policy Ask"}
                )
                fig.update_layout(
                    height=400,
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Most Common Arguments**")
                arg_counts = positions_df["primary_argument"].value_counts().head(10)

                fig = px.bar(
                    x=arg_counts.values,
                    y=arg_counts.index,
                    orientation="h",
                    labels={"x": "Count", "y": "Argument"},
                    color_discrete_sequence=["#ff7f0e"]
                )
                fig.update_layout(
                    height=400,
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("AI Labs vs. Big Tech vs. Trade Groups")

        if not positions_df.empty:
            # Policy asks by company type
            type_asks = positions_df.groupby(["submitter_type", "policy_ask"]).size().reset_index(name="count")

            # Get top 8 policy asks overall
            top_asks = positions_df["policy_ask"].value_counts().head(8).index.tolist()
            type_asks_filtered = type_asks[type_asks["policy_ask"].isin(top_asks)]

            fig = px.bar(
                type_asks_filtered,
                x="policy_ask",
                y="count",
                color="submitter_type",
                barmode="group",
                labels={"policy_ask": "Policy Ask", "count": "Count", "submitter_type": "Company Type"}
            )
            fig.update_layout(
                height=400,
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig, use_container_width=True)

            # Arguments by company type
            st.markdown("**Argument Usage by Company Type**")
            type_args = positions_df.groupby(["submitter_type", "primary_argument"]).size().reset_index(name="count")
            top_args = positions_df["primary_argument"].value_counts().head(6).index.tolist()
            type_args_filtered = type_args[type_args["primary_argument"].isin(top_args)]

            fig = px.bar(
                type_args_filtered,
                x="primary_argument",
                y="count",
                color="submitter_type",
                barmode="group",
                labels={"primary_argument": "Argument", "count": "Count", "submitter_type": "Company Type"}
            )
            fig.update_layout(
                height=400,
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig, use_container_width=True)


def render_position_explorer(data: dict):
    """Section 4: Policy Position Explorer."""
    st.header("Policy Position Explorer")

    positions_df = data["positions"]

    if positions_df.empty:
        st.info("No position data available")
        return

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        # Sort companies by type (ai_lab first, then big_tech, then trade_group)
        type_sort_order = {"ai_lab": 1, "big_tech": 2, "trade_group": 3}
        discrepancy_df = data.get("discrepancy_scores", pd.DataFrame())
        company_types = {}
        if not discrepancy_df.empty:
            company_types = dict(zip(discrepancy_df["company_name"], discrepancy_df["company_type"]))

        company_names = positions_df["submitter_name"].unique().tolist()
        sorted_companies = sorted(
            company_names,
            key=lambda x: (type_sort_order.get(company_types.get(x, ""), 4), x)
        )
        companies = ["All"] + sorted_companies
        selected_company = st.selectbox("Company", companies, key="explorer_company")

    with col2:
        categories = ["All"] + sorted(positions_df["ask_category"].dropna().unique().tolist())
        selected_category = st.selectbox("Category", categories)

    with col3:
        arguments = ["All"] + sorted(positions_df["primary_argument"].dropna().unique().tolist())
        selected_argument = st.selectbox("Argument", arguments)

    # Apply filters
    filtered = positions_df.copy()

    if selected_company != "All":
        filtered = filtered[filtered["submitter_name"] == selected_company]

    if selected_category != "All":
        filtered = filtered[filtered["ask_category"] == selected_category]

    if selected_argument != "All":
        filtered = filtered[filtered["primary_argument"] == selected_argument]

    st.write(f"Showing {len(filtered):,} positions")

    st.divider()

    # Aggregations
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Policy Ask Distribution**")
        ask_dist = filtered["policy_ask"].value_counts().head(10)

        fig = px.pie(
            values=ask_dist.values,
            names=ask_dist.index,
            hole=0.4
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Stance Distribution**")
        stance_dist = filtered["stance"].value_counts()

        colors = {"support": "green", "oppose": "red", "neutral": "gray"}
        fig = px.pie(
            values=stance_dist.values,
            names=stance_dist.index,
            hole=0.4,
            color=stance_dist.index,
            color_discrete_map=colors
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data table
    st.subheader("Position Details")

    display_cols = [
        "submitter_name",
        "policy_ask",
        "stance",
        "primary_argument",
        "supporting_quote"
    ]

    available_cols = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[available_cols].rename(columns={
            "submitter_name": "Company",
            "policy_ask": "Policy Ask",
            "stance": "Stance",
            "primary_argument": "Argument",
            "supporting_quote": "Quote"
        }),
        use_container_width=True,
        hide_index=True,
        height=400
    )


def render_methodology():
    """Section 5: Methodology - taxonomy definitions and scoring explanation."""
    st.header("Methodology")
    st.markdown("How we analyze AI company policy positions and lobbying activity.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Entity Types", "Policy Asks", "Arguments", "Scoring", "Data Sources"])

    with tab1:
        st.subheader("Entity Type Classification")
        st.markdown("We classify submitters into three main categories to understand different incentive structures.")

        st.markdown("### Definitions")

        entity_types = {
            "AI Lab": "**Pure-play AI companies** whose core business is developing AI models and systems. These companies have the most direct stake in AI regulation since it affects their primary product. *Examples: OpenAI, Anthropic, Cohere, Mistral*",
            "Big Tech": "**Diversified technology giants** where AI is one of many business lines. These companies may have conflicting internal interests—for example, Amazon's cloud AI business vs. their content/media businesses on copyright issues. *Examples: Google, Amazon, Microsoft, Apple, Meta*",
            "Trade Group": "**Industry associations** that represent multiple member companies collectively. Trade groups are not companies—they advocate on behalf of their members' shared interests. *Examples: U.S. Chamber of Commerce, TechNet, CCIA, BSA*",
        }

        for entity_type, definition in entity_types.items():
            st.markdown(f"**{entity_type}**: {definition}")

        st.divider()

        st.markdown("### Why Trade Groups Matter")
        st.markdown("""
Trade groups deserve special attention in lobbying analysis because:

1. **Collective Voice**: Organizations like the U.S. Chamber of Commerce represent hundreds of member companies speaking with one voice

2. **Deniable Advocacy**: Trade groups often advocate more aggressive positions than individual member companies would state publicly, allowing members to benefit without direct attribution

3. **Lowest Common Denominator**: Trade group positions typically represent what all members can agree on, which often skews toward deregulation

**Example**: A tech company might publicly support "responsible AI regulation" while their trade group simultaneously lobbies against specific accountability measures. This project's discrepancy analysis attempts to surface these gaps.
        """)

    with tab2:
        st.subheader("Policy Ask Taxonomy")
        st.markdown("Policy asks are specific things companies want the government to do (or not do).")

        st.markdown("### Categories")

        categories = {
            "regulatory_structure": "How AI should be governed (federal vs state, new vs existing agencies)",
            "accountability": "Liability, audits, transparency, incident reporting",
            "intellectual_property": "Training data, copyright, open source",
            "national_security": "Export controls, China competition, defense AI",
            "resources": "Funding, infrastructure, immigration, workforce",
        }

        for cat, desc in categories.items():
            st.markdown(f"**{cat.replace('_', ' ').title()}**: {desc}")

        st.divider()

        st.markdown("### Policy Asks by Category")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Regulatory Structure**")
            reg_asks = {
                "federal_preemption": "Federal law should override state laws",
                "state_autonomy": "States should be able to regulate",
                "new_federal_agency": "Create new AI oversight body",
                "existing_agency_authority": "Use existing agencies (FTC/FDA/etc)",
                "self_regulation": "Industry-led standards without mandates",
                "international_harmonization": "Align with EU/international standards",
            }
            for ask, desc in reg_asks.items():
                st.markdown(f"• `{ask}`: {desc}")

            st.markdown("**Accountability**")
            acc_asks = {
                "liability_shield": "Protect developers from lawsuits",
                "liability_framework": "Define who's responsible for AI harms",
                "mandatory_audits": "Require third-party testing",
                "voluntary_commitments": "Support industry self-commitments",
                "transparency_requirements": "Mandate disclosures",
                "incident_reporting": "Require breach/incident reporting",
            }
            for ask, desc in acc_asks.items():
                st.markdown(f"• `{ask}`: {desc}")

        with col2:
            st.markdown("**Intellectual Property**")
            ip_asks = {
                "training_data_fair_use": "Allow copyrighted data for training",
                "creator_compensation": "Pay content creators",
                "model_weight_protection": "Treat weights as trade secrets",
                "open_source_protection": "Don't restrict open source",
            }
            for ask, desc in ip_asks.items():
                st.markdown(f"• `{ask}`: {desc}")

            st.markdown("**National Security**")
            ns_asks = {
                "export_controls_strict": "More chip/model restrictions",
                "export_controls_loose": "Fewer restrictions",
                "government_ai_adoption": "More federal AI use",
                "defense_ai_investment": "Military AI funding",
            }
            for ask, desc in ns_asks.items():
                st.markdown(f"• `{ask}`: {desc}")

            st.markdown("**Resources**")
            res_asks = {
                "research_funding": "Government R&D money",
                "compute_infrastructure": "Data center support",
                "energy_infrastructure": "Power grid for AI",
                "immigration_reform": "AI talent visas",
                "workforce_training": "Retraining programs",
            }
            for ask, desc in res_asks.items():
                st.markdown(f"• `{ask}`: {desc}")

    with tab3:
        st.subheader("Argument Types")
        st.markdown("Arguments are HOW companies justify their policy asks.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Economic Arguments**")
            econ_args = {
                "innovation_harm": '"Kills startups/innovation"',
                "competitiveness": '"Must stay ahead economically"',
                "job_creation": '"Creates jobs"',
                "cost_burden": '"Too expensive to comply"',
            }
            for arg, desc in econ_args.items():
                st.markdown(f"• `{arg}`: {desc}")

            st.markdown("**Security Arguments**")
            sec_args = {
                "china_competition": '"China will win if we don\'t"',
                "national_security": '"Defense/security requires this"',
                "adversary_benefit": '"Helps bad actors"',
            }
            for arg, desc in sec_args.items():
                st.markdown(f"• `{arg}`: {desc}")

        with col2:
            st.markdown("**Practical Arguments**")
            prac_args = {
                "technical_infeasibility": '"Can\'t be done technically"',
                "patchwork_problem": '"State-by-state is chaos"',
                "duplicative": '"Already regulated elsewhere"',
                "premature": '"Too early to regulate"',
            }
            for arg, desc in prac_args.items():
                st.markdown(f"• `{arg}`: {desc}")

            st.markdown("**Rights/Values Arguments**")
            rights_args = {
                "free_speech": "First Amendment concerns",
                "consumer_protection": "Protect users",
                "creator_rights": "Protect artists/creators",
                "civil_liberties": "Privacy, bias, fairness",
                "safety_concern": "AI safety/alignment risks",
            }
            for arg, desc in rights_args.items():
                st.markdown(f"• `{arg}`: {desc}")

    with tab4:
        st.subheader("How Scores Are Calculated")

        st.markdown("### Discrepancy Score (0-100)")
        st.markdown("""
        Measures the gap between what companies **say** in public policy submissions
        vs. what they **do** in their lobbying activity.

        - **0 = Fully consistent**: Lobbying aligns with stated positions
        - **50 = Moderate gap**: Some misalignment between rhetoric and lobbying
        - **100 = Major contradiction**: Lobbying contradicts stated positions

        **How it works:**
        1. Extract policy positions from AI Action Plan submissions
        2. Map positions to expected LDA issue codes
        3. Compare to actual lobbying filings
        4. LLM analyzes patterns and assigns score
        """)

        st.markdown("### Concern Score (0-100)")
        st.markdown("""
        Assesses public interest implications of a company's lobbying agenda.

        - **0 = Public interest aligned**: Lobbying supports accountability, safety
        - **50 = Mixed**: Some concerning and some positive aspects
        - **100 = Critical concern**: Lobbying actively harms public interest

        **Factors considered:**
        - Regulatory capture signals (writing rules that benefit themselves)
        - Safety vs. profit tensions
        - Accountability avoidance (liability shields, opposing audits)
        - Transparency opposition
        """)

        st.markdown("### China Rhetoric Intensity (0-100)")
        st.markdown("""
        Measures how heavily a company invokes "China competition" to justify positions.

        - **0 = Minimal use**: Rarely mentions China
        - **50 = Moderate**: Uses China framing for some positions
        - **100 = Heavy reliance**: China is a primary justification

        **Why it matters:**
        China rhetoric can be a legitimate concern OR a rhetorical strategy to
        avoid regulation. High intensity + low substantiation = potential red flag.
        """)

    with tab5:
        st.subheader("Data Sources")

        st.markdown("### AI Action Plan RFI Submissions")
        st.markdown("""
        - **What:** Public responses to Trump administration's Request for Information on AI policy
        - **Citation:** 90 FR 9088 (Federal Register)
        - **Volume:** 10,068 total submissions, 17 priority companies analyzed
        - **URL:** [NITRD AI Action Plan](https://files.nitrd.gov/90-fr-9088/)
        """)

        st.markdown("### Senate LDA Lobbying Database")
        st.markdown("""
        - **What:** Quarterly lobbying disclosure filings
        - **Contents:** Who lobbied, for whom, on what issues, how much spent
        - **Filter:** 2023+ filings, AI-relevant issue codes (CPI, SCI, CPT, CSP, DEF, HOM)
        - **URL:** [LDA Senate API](https://lda.senate.gov/api/)
        """)

        st.divider()

        st.markdown("### Why Compare These Two Sources?")
        st.markdown("""
        These data sources reveal fundamentally different things:

        | Source | What It Reveals | Enforcement |
        |--------|-----------------|-------------|
        | **RFI Submissions** | What companies are *willing to say publicly* | None - advisory only |
        | **LDA Filings** | What companies are *actually paying to influence* | Mandatory disclosure |

        **RFI comments are PR.** Anyone can submit. Agencies "consider" them but aren't bound by them.
        They're a company's public face—what they want you to think they believe.

        **Lobbying is action.** Companies spend $10-100M+ annually on lobbyists because it *works*.
        LDA filings reveal where the money actually goes.

        **The insight:** When these diverge, that's the story. A company saying "we support AI safety"
        while spending millions lobbying against safety regulations reveals the gap between
        rhetoric and reality. That gap is what this dashboard measures.
        """)

        st.divider()

        st.markdown("### LLM Analysis")
        st.markdown("""
        - **Model:** Claude claude-sonnet-4-20250514 (Anthropic)
        - **Tasks:** Position extraction, discrepancy detection, impact assessment
        - **Extraction:** 633 positions from 112 text chunks
        """)


def render_bill_analysis(data: dict):
    """Section 6: Bill-Level Coalition Analysis - Quiet Lobbying patterns."""
    st.header("Bill-Level Analysis")
    st.markdown("### Who's lobbying without speaking? Who's speaking without lobbying?")

    bill_df = data["bill_analysis"]

    if bill_df.empty:
        st.info("No bill analysis data available. Run map_regulatory_targets.py to generate.")
        return

    import json

    # Parse JSON columns
    def safe_json_load(val):
        if pd.isna(val):
            return []
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except Exception:
            return []

    bill_df["quiet_lobbying_list"] = bill_df["quiet_lobbying"].apply(safe_json_load)
    bill_df["lobbying_companies_list"] = bill_df["lobbying_companies"].apply(safe_json_load)
    bill_df["supporting_list"] = bill_df["companies_supporting"].apply(safe_json_load)
    bill_df["opposing_list"] = bill_df["companies_opposing"].apply(safe_json_load)

    # Headline stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Bills Analyzed", len(bill_df))

    with col2:
        bills_with_lobbying = len(bill_df[bill_df["lobbying_filing_count"] > 0])
        st.metric("Bills with Lobbying", bills_with_lobbying)

    with col3:
        total_quiet = bill_df["quiet_lobbying_list"].apply(len).sum()
        st.metric("Quiet Lobbying Instances", int(total_quiet))

    with col4:
        contested = len(bill_df[(bill_df["supporting_list"].apply(len) > 0) & (bill_df["opposing_list"].apply(len) > 0)])
        st.metric("Contested Bills", contested)

    st.divider()

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["Lobbying vs Positions", "Quiet Lobbying Leaderboard", "Bill Details"])

    with tab1:
        # First chart: Total lobbying filings by bill
        st.subheader("Lobbying Volume by Bill")
        st.caption("Total lobbying filings per bill (sorted by volume)")

        filings_df = bill_df[bill_df["lobbying_filing_count"] > 0].copy()
        filings_df = filings_df.sort_values("lobbying_filing_count", ascending=True)

        if not filings_df.empty:
            fig_volume = px.bar(
                filings_df,
                x="lobbying_filing_count",
                y="bill_name",
                orientation="h",
                labels={"lobbying_filing_count": "Total Filings", "bill_name": ""},
                color="lobbying_filing_count",
                color_continuous_scale=["#fee8c8", "#e34a33"],
            )
            fig_volume.update_layout(
                height=350,
                showlegend=False,
                coloraxis_showscale=False,
                xaxis_title="Total Lobbying Filings"
            )
            st.plotly_chart(fig_volume, use_container_width=True)

            # Summary stat
            total_filings = filings_df["lobbying_filing_count"].sum()
            top_bill = filings_df.iloc[-1]  # Last row after ascending sort = highest
            st.info(f"**{total_filings} total lobbying filings** across {len(filings_df)} bills. **{top_bill['bill_name']}** has the most activity with {top_bill['lobbying_filing_count']} filings.")

        st.divider()

        # Second chart: Who's lobbying quietly
        st.subheader("Who's Lobbying Quietly?")
        st.caption("Companies lobbying WITH vs WITHOUT a public position on that bill")

        chart_df = bill_df[bill_df["lobbying_filing_count"] > 0].copy()

        # Normalize company names for matching (LDA uses "MICROSOFT CORPORATION", RFI uses "Microsoft-AI")
        def normalize_name(name):
            """Normalize company name to canonical form for matching."""
            if not name:
                return ""
            n = name.lower().strip()
            for suffix in [", inc.", ", inc", " inc.", " inc", " corporation", " corp.", " corp",
                          " llc", ", llc", " l.l.c.", " plc", ", plc", " technologies",
                          " platforms", "-ai", "_ai", " ai"]:
                if n.endswith(suffix):
                    n = n[:-len(suffix)].strip()
            n = n.replace(",", "").replace(".", "").replace("(", "").replace(")", "")
            mappings = {
                "meta": "meta",
                "meta platforms": "meta",
                "google": "google",
                "google llc": "google",
                "microsoft": "microsoft",
                "intel": "intel",
                "intel corporation": "intel",
                "amazon": "amazon",
                "amazoncom": "amazon",
                "anthropic": "anthropic",
                "anthropic pbc": "anthropic",
                "openai": "openai",
                "openai opco": "openai",
                "technet": "technet",
                "technology network": "technet",
                "technology network aka technet": "technet",
                "workday": "workday",
                "cloudflare": "cloudflare",
            }
            if n in mappings:
                return mappings[n]
            for key, val in mappings.items():
                if key in n or n in key:
                    return val
            return n

        def normalize_set(names):
            return {normalize_name(n) for n in names if n}

        def get_position_companies(row):
            return normalize_set(row["supporting_list"]) | normalize_set(row["opposing_list"])

        def get_lobbying_set(row):
            return normalize_set(row["lobbying_companies_list"])

        chart_df["position_companies"] = chart_df.apply(get_position_companies, axis=1)
        chart_df["lobbying_set"] = chart_df.apply(get_lobbying_set, axis=1)

        chart_df["lobbied_with_position"] = chart_df.apply(
            lambda r: r["lobbying_set"] & r["position_companies"], axis=1
        )
        chart_df["lobbied_quietly"] = chart_df.apply(
            lambda r: r["lobbying_set"] - r["position_companies"], axis=1
        )

        chart_df["n_lobbying_companies"] = chart_df["lobbying_set"].apply(len)
        chart_df["n_with_position"] = chart_df["lobbied_with_position"].apply(len)
        chart_df["n_quiet"] = chart_df["lobbied_quietly"].apply(len)

        chart_df = chart_df.sort_values("lobbying_filing_count", ascending=True)  # Sort by filings to match chart above

        if not chart_df.empty:
            fig = go.Figure()

            fig.add_trace(go.Bar(
                y=chart_df["bill_name"],
                x=chart_df["n_with_position"],
                name="Lobbied + Took Public Position",
                orientation="h",
                marker_color="#2ca02c",
                hovertemplate="%{y}<br>%{x} companies lobbied AND took public position<extra></extra>"
            ))

            fig.add_trace(go.Bar(
                y=chart_df["bill_name"],
                x=chart_df["n_quiet"],
                name="Lobbied Quietly (no public position)",
                orientation="h",
                marker_color="#d62728",
                hovertemplate="%{y}<br>%{x} companies lobbied WITHOUT public position<extra></extra>"
            ))

            max_x = max(
                chart_df["n_with_position"].max(),
                chart_df["n_quiet"].max()
            )

            fig.update_layout(
                height=400,
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
                xaxis_title="Number of Companies",
                xaxis=dict(
                    dtick=1,
                    tick0=0,
                    range=[0, max_x + 1]
                ),
                yaxis_title=""
            )

            st.plotly_chart(fig, use_container_width=True)

            total_quiet = chart_df["n_quiet"].sum()
            total_lobbying = chart_df["n_lobbying_companies"].sum()
            quiet_pct = (total_quiet / total_lobbying * 100) if total_lobbying > 0 else 0
            st.info(f"**{quiet_pct:.0f}% of company-bill lobbying is 'quiet'** — {total_quiet} of {total_lobbying} company-bill pairs had no public position on that specific bill.")

    with tab2:
        st.subheader("Quiet Lobbying Leaderboard")
        st.caption("Companies lobbying on bills WITHOUT taking public positions")

        # Build leaderboard
        quiet_counts = {}
        for _, row in bill_df.iterrows():
            for company in row["quiet_lobbying_list"]:
                # Clean up company name
                clean = company.replace("TECHNOLOGY NETWORK AKA TECHNET", "TechNet").replace("AKA ", "")
                if clean not in quiet_counts:
                    quiet_counts[clean] = {"bills": [], "count": 0}
                quiet_counts[clean]["bills"].append(row["bill_name"])
                quiet_counts[clean]["count"] += 1

        if quiet_counts:
            # Sort by count
            leaderboard = sorted(quiet_counts.items(), key=lambda x: x[1]["count"], reverse=True)

            # Display as table
            leaderboard_data = []
            for company, info in leaderboard[:15]:
                leaderboard_data.append({
                    "Company": company,
                    "Bills Lobbying Without Position": info["count"],
                    "Bills": ", ".join(info["bills"][:3]) + ("..." if len(info["bills"]) > 3 else "")
                })

            st.dataframe(
                pd.DataFrame(leaderboard_data),
                use_container_width=True,
                hide_index=True
            )

            # Chart
            chart_data = pd.DataFrame([
                {"company": k, "quiet_bills": v["count"]}
                for k, v in leaderboard[:10]
            ])

            fig = px.bar(
                chart_data,
                x="quiet_bills",
                y="company",
                orientation="h",
                labels={"quiet_bills": "Bills with Quiet Lobbying", "company": ""},
                color="quiet_bills",
                color_continuous_scale=["yellow", "orange", "red"],
            )
            fig.update_layout(
                height=350,
                showlegend=False,
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("The Section 230 Silence")
        st.markdown("""
        **115 lobbying filings. Zero public positions.**

        Companies spending money to influence Section 230 but refusing to state their position publicly:
        """)

        section_230_row = bill_df[bill_df["bill_id"] == "section_230"]
        if not section_230_row.empty:
            quiet = section_230_row.iloc[0]["quiet_lobbying_list"]
            if quiet:
                cols = st.columns(min(4, len(quiet)))
                for i, company in enumerate(quiet[:4]):
                    clean = company.replace("TECHNOLOGY NETWORK AKA TECHNET", "TechNet").replace("COMPUTER & COMMUNICATIONS INDUSTRY ASSOCIATION", "CCIA")
                    with cols[i % 4]:
                        st.warning(f"**{clean}**")

    with tab3:
        st.subheader("Bill Details")

        # Bill selector
        bill_names = bill_df["bill_name"].tolist()
        selected_bill = st.selectbox("Select Bill", bill_names)

        if selected_bill:
            row = bill_df[bill_df["bill_name"] == selected_bill].iloc[0]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Lobbying Filings", row["lobbying_filing_count"])

            with col2:
                st.metric("Public Positions", row["position_count"])

            with col3:
                spend = row.get("lobbying_spend_estimate", 0)
                if spend and spend > 0:
                    st.metric("Est. Lobbying Spend", f"${spend:,.0f}")
                else:
                    st.metric("Est. Lobbying Spend", "N/A")

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Companies Supporting:**")
                supporting = row["supporting_list"]
                if supporting:
                    for c in supporting:
                        st.success(f"• {c}")
                else:
                    st.info("No public support positions")

                st.markdown("**Companies Opposing:**")
                opposing = row["opposing_list"]
                if opposing:
                    for c in opposing:
                        st.error(f"• {c}")
                else:
                    st.info("No public opposition positions")

            with col2:
                st.markdown("**Companies Lobbying:**")
                lobbying = row["lobbying_companies_list"]
                if lobbying:
                    for c in lobbying[:10]:
                        clean = c.replace("TECHNOLOGY NETWORK AKA TECHNET", "TechNet")
                        st.write(f"• {clean}")
                    if len(lobbying) > 10:
                        st.write(f"... and {len(lobbying) - 10} more")
                else:
                    st.info("No lobbying filings found")

                st.markdown("**Quiet Lobbying (no public position):**")
                quiet = row["quiet_lobbying_list"]
                if quiet:
                    for c in quiet:
                        clean = c.replace("TECHNOLOGY NETWORK AKA TECHNET", "TechNet")
                        st.warning(f"• {clean}")
                else:
                    st.info("None - all lobbyists have public positions")


def main():
    """Main app entry point."""
    # Load data
    with st.spinner("Loading data..."):
        data = get_data()

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Executive Summary", "Company Deep Dive", "Cross-Company Comparison", "Bill-Level Analysis", "Position Explorer", "Methodology"]
    )

    st.sidebar.divider()
    st.sidebar.markdown("### About")
    st.sidebar.markdown(
        "This dashboard analyzes AI companies' policy positions from "
        "government submissions and compares them to lobbying activity."
    )
    st.sidebar.markdown("**Data sources:**")
    st.sidebar.markdown("• AI Action Plan RFI submissions (17 companies)")
    st.sidebar.markdown("• Senate LDA lobbying disclosures (2023+)")

    st.sidebar.divider()

    # Render selected page
    if page == "Executive Summary":
        render_executive_summary(data)
    elif page == "Company Deep Dive":
        render_company_deep_dive(data)
    elif page == "Cross-Company Comparison":
        render_cross_company_comparison(data)
    elif page == "Bill-Level Analysis":
        render_bill_analysis(data)
    elif page == "Position Explorer":
        render_position_explorer(data)
    elif page == "Methodology":
        render_methodology()


if __name__ == "__main__":
    main()
