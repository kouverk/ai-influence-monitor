# Project Merge Strategy

> **Status:** Planning - for future implementation

This document outlines options for merging `ai-influence-monitor` and `data-ai-industry-index-tracker` into a unified deployment.

---

## Current State

Two separate projects with the same tech stack:
- **ai-influence-monitor** - AI policy/lobbying analysis
- **data-ai-industry-index-tracker** - Industry index tracking

Both use: Online API → Snowflake → dbt → Snowflake → Streamlit

---

## Option 1: Merge into One Monorepo (Recommended)

Combine both projects into a single repo with shared infrastructure:

```
data-portfolio/
├── projects/
│   ├── ai-influence-monitor/
│   │   ├── scripts/          # Extraction + agentic scripts
│   │   └── dbt/              # dbt models
│   └── ai-industry-index/
│       ├── scripts/
│       └── dbt/
├── dashboard/
│   ├── app.py                # Landing page
│   └── pages/
│       ├── 1_AI_Influence_Tracker.py
│       ├── 2_Company_Deep_Dive.py
│       ├── 3_Industry_Index.py      # From other project
│       └── 4_Index_Analysis.py      # From other project
├── dags/                     # All DAGs in one place
│   ├── ai_influence_pipeline.py
│   └── industry_index_pipeline.py
└── dbt/                      # Single dbt project with both
    └── data_portfolio/
        ├── models/
        │   ├── ai_influence/
        │   └── industry_index/
```

**Pros:** Single deployment for everything, shared Snowflake connection, unified dashboard
**Cons:** More upfront work to merge

---

## Option 2: Keep Separate, Link via Landing Page

Keep both repos but create a simple landing page:

```
# Deploy separately:
ai-influence-monitor.streamlit.app      # Project 1
ai-industry-index.streamlit.app         # Project 2

# Create a simple landing page that links to both
```

**Pros:** No code changes, quick
**Cons:** Two separate deployments, two Astronomer projects

---

## Option 3: Shared Dashboard, Separate Pipelines

Create a third "dashboard-only" repo that reads from both Snowflake schemas:

```
data-portfolio-dashboard/
├── dashboard/
│   ├── app.py
│   └── pages/
│       ├── ai_influence/     # Reads from KOUVERK_AI_INFLUENCE
│       └── industry_index/   # Reads from KOUVERK_INDUSTRY_INDEX
└── requirements.txt
```

**Pros:** One dashboard, pipelines stay separate
**Cons:** Dashboard code divorced from pipeline code

---

## Recommendation

**Go with Option 1 (monorepo)** because:

1. **Single Astronomer deployment** - One place to manage all DAGs
2. **Single Streamlit deployment** - One URL, multi-page navigation
3. **Shared dbt project** - Can reference models across projects
4. **Portfolio presentation** - Shows you can build multiple pipelines

---

## Implementation Steps

1. Create a new repo `data-portfolio` (or rename one of them)
2. Move both project codebases into `projects/` subdirectories
3. Merge DAGs into single `dags/` folder
4. Merge dashboards using Streamlit's multi-page app structure
5. Deploy once to Streamlit Cloud + once to Astronomer

---

## Streamlit Multi-Page App Structure

Streamlit automatically creates navigation from files in `pages/` folder:

```python
# dashboard/app.py - Landing page
import streamlit as st

st.set_page_config(page_title="Data Portfolio", layout="wide")
st.title("Data Analytics Portfolio")
st.markdown("Select a project from the sidebar")

# dashboard/pages/1_AI_Influence_Tracker.py
# dashboard/pages/2_Industry_Index.py
# etc.
```

File naming with numbers (1_, 2_) controls sidebar order.

---

## Astronomer Deployment

Single Astronomer project with all DAGs:

```
dags/
├── ai_influence/
│   ├── ai_influence_pipeline.py
│   ├── extract_submissions_dag.py
│   └── ...
└── industry_index/
    ├── industry_index_pipeline.py
    └── ...
```

---

*Created: February 2, 2026*
