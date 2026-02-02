"""
AI Influence Tracker Dashboard

What AI Companies Say vs. What They Lobby For

A Streamlit dashboard visualizing:
- Policy positions extracted from AI Action Plan submissions
- Lobbying activity from Senate LDA disclosures
- Discrepancies between public statements and lobbying behavior
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import load_all_data

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

        leaderboard = leaderboard.sort_values("discrepancy_score")

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

    # Company selector
    companies = sorted(positions_df["submitter_name"].unique())
    default_idx = companies.index("OpenAI") if "OpenAI" in companies else 0
    selected_company = st.selectbox("Select Company", companies, index=default_idx)

    if not selected_company:
        return

    st.divider()

    # Company scorecard
    col1, col2, col3, col4 = st.columns(4)

    # Get scores for this company
    company_discrepancy = discrepancy_df[discrepancy_df["company_name"] == selected_company]
    company_impact = impact_df[impact_df["company_name"] == selected_company]
    company_china = china_df[china_df["company_name"] == selected_company]
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
                total_spend = company_filings["expenses"].sum()
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
        st.caption("Who's concerning AND hypocritical?")

        if not discrepancy_df.empty and not impact_df.empty:
            merged = discrepancy_df.merge(
                impact_df[["company_name", "concern_score"]],
                on="company_name",
                how="inner"
            )

            if not merged.empty:
                fig = px.scatter(
                    merged,
                    x="concern_score",
                    y="discrepancy_score",
                    text="company_name",
                    color="company_type",
                    size_max=15
                )
                fig.update_traces(textposition="top center")
                fig.update_layout(
                    height=500,
                    xaxis_title="Concern Score (0=aligned, 100=concerning)",
                    yaxis_title="Discrepancy Score (0=consistent, 100=hypocrite)"
                )
                # Add quadrant lines
                fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
                fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)

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
        companies = ["All"] + sorted(positions_df["submitter_name"].unique().tolist())
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

    tab1, tab2, tab3, tab4 = st.tabs(["Policy Asks", "Arguments", "Scoring", "Data Sources"])

    with tab1:
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

    with tab2:
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

    with tab3:
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

    with tab4:
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

        st.markdown("### LLM Analysis")
        st.markdown("""
        - **Model:** Claude claude-sonnet-4-20250514 (Anthropic)
        - **Tasks:** Position extraction, discrepancy detection, impact assessment
        - **Extraction:** 633 positions from 112 text chunks
        """)


def main():
    """Main app entry point."""
    # Load data
    with st.spinner("Loading data..."):
        data = get_data()

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Executive Summary", "Company Deep Dive", "Cross-Company Comparison", "Position Explorer", "Methodology"]
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
    st.sidebar.caption("Built for DataExpert.io Capstone")

    # Render selected page
    if page == "Executive Summary":
        render_executive_summary(data)
    elif page == "Company Deep Dive":
        render_company_deep_dive(data)
    elif page == "Cross-Company Comparison":
        render_cross_company_comparison(data)
    elif page == "Position Explorer":
        render_position_explorer(data)
    elif page == "Methodology":
        render_methodology()


if __name__ == "__main__":
    main()
