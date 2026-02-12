# CLAUDE.md - AI Influence Tracker

## What Is This?

**AI Influence Tracker** - What AI Companies Say vs. What They Lobby For

A document intelligence pipeline that:
1. Extracts policy positions from government submissions using LLMs
2. Joins to lobbying data from Senate LDA
3. Surfaces discrepancies between public statements and lobbying activity

**Core question:** Do AI companies practice what they preach on safety and regulation?

**Context:** DataExpert.io analytics engineering capstone. Requirements: 2+ data sources, 1M+ rows, Airflow ETL, data quality checks, Astronomer deployment, LLM-powered "agentic action".

---

## Documentation

| File | Purpose |
|------|---------|
| `docs/DATA_DICTIONARY.md` | Tables, columns, data sources |
| `docs/ARCHITECTURE.md` | System design, DAG structure, prompts, API endpoints |
| `docs/INSIGHTS.md` | Findings and observations |
| `queries/README.md` | SQL queries for Trino exploration |

**Read these when you need details. Don't read them all at once.**

---

## Current State

### What's Done

**1. PDF Extraction Pipeline** ✅
- Script: `include/scripts/extraction/extract_pdf_submissions.py`
- Extracts text from PDFs using PyMuPDF
- Chunks into ~800 word segments (100 word overlap) for LLM processing
- Writes to 3 Iceberg tables via PyIceberg + AWS Glue

**2. LLM Position Extraction** ✅
- Script: `include/scripts/agentic/extract_positions.py`
- Sends chunks to Claude API (claude-sonnet-4-20250514)
- Enhanced taxonomy with 30+ policy_ask codes, 15+ argument codes
- Captures: policy_ask, ask_category, stance, target, primary_argument, secondary_argument

**3. Senate LDA Lobbying Data** ✅
- Script: `include/scripts/extraction/extract_lda_filings.py`
- Fetches lobbying disclosures from lda.senate.gov API
- Normalizes into 3 tables: filings, activities, lobbyists

**4. Snowflake Integration** ✅
- Script: `include/scripts/utils/export_to_snowflake.py`
- Exports ALL 10 Iceberg tables to Snowflake RAW tables
- Database: `DATAEXPERT_STUDENT.KOUVERK_AI_INFLUENCE`

**5. dbt Models** ✅
- Project: `dbt/`
- 10 staging views (all source tables)
- 6 mart tables including `fct_company_analysis` and `fct_bill_coalitions`
- Tests on all primary keys

**6. Airflow DAGs** ✅
- 6 DAGs in `dags/` directory
- Main orchestration: `ai_influence_pipeline.py`
- All using Astronomer-compatible `AIRFLOW_HOME` paths

**7. Astronomer Setup** ✅
- Initialized with `astro dev init`
- Dockerfile configured for runtime 3.1-10
- Ready for `astro dev start` (requires Docker)

**8. LLM Analysis Scripts** ✅
- `assess_lobbying_impact.py` - Public interest concern scoring (v2 with taxonomy)
- `detect_discrepancies.py` - Say vs Do contradiction detection
- `analyze_china_rhetoric.py` - China competition rhetoric deep-dive
- `compare_positions.py` - Cross-company position comparison
- `map_regulatory_targets.py` - Bill-level coalition analysis (no LLM)

**Data in Iceberg:**

| Table | Rows | Description |
|-------|------|-------------|
| `kouverk.ai_submissions_metadata` | 30 | Document info |
| `kouverk.ai_submissions_text` | 30 | Full extracted text |
| `kouverk.ai_submissions_chunks` | ~200 | Chunks for LLM |
| `kouverk.ai_positions` | **878** | Policy asks with taxonomy |
| `kouverk.lda_filings` | **970** | Lobbying filings (2023+) |
| `kouverk.lda_activities` | **3,051** | Issue codes + descriptions |
| `kouverk.lda_lobbyists` | **11,518** | Individual lobbyists |
| `kouverk.lobbying_impact_scores` | 23 | Public interest concern scores (v2) |
| `kouverk.discrepancy_scores` | 23 | Say-vs-do contradiction scores |
| `kouverk.china_rhetoric_analysis` | 14 | China rhetoric deep-dive |
| `kouverk.position_comparisons` | 1 | Cross-company comparison |
| `kouverk.bill_position_analysis` | **21** | Bill-level coalition patterns |

**Position Taxonomy:**
- 633 positions with structured codes
- Top policy_asks: `government_ai_adoption` (70), `research_funding` (43), `federal_preemption` (31)
- Top arguments: `competitiveness` (223), `china_competition` (55), `innovation_harm` (87)

**China Framing by Company:**
- OpenAI: 16 positions use china_competition argument (most aggressive)
- Palantir: 6
- TechNet: 5
- IBM: 4
- Anthropic: 2
- Others: 0-1

**Key Findings from Analysis:**

*Concern Scores (0=good, 100=concerning):*
- **Anthropic: 45/100** (lowest - less concerning)
- Most others: 68-72/100
- OpenAI: 72/100

*Discrepancy Scores (0=consistent, 100=hypocrite):*
- **Anthropic: 25/100** (most consistent)
- OpenAI, Adobe, IBM, CCIA, TechNet: 35/100
- **Google, Amazon: 75/100** (biggest gap between say vs do)

*China Rhetoric Intensity (0=minimal, 100=heavy reliance):*
- **OpenAI: 85/100** (most aggressive China framing)
- Meta: 75/100
- Palantir, TechNet, IBM, Microsoft, Cohere: 25/100
- Anthropic: 15/100 (minimal use)
- **Google: 2/100** (barely uses China framing)

*Cross-Company Insights:*
1. "Incumbent protection" pattern - leaders support high compliance costs they can absorb
2. Safety positions correlate with marketing positioning, not just altruism
3. Trade groups do "dirty work" of aggressive deregulation advocacy
4. Universal support for government AI adoption reveals industry growth strategy
5. Diversified tech giants face internal policy conflicts (Amazon opposes training data fair use due to content businesses)

**9. Streamlit Dashboard** ✅
- App: `dashboard/app.py`
- 6 sections: Executive Summary, Company Deep Dive, Cross-Company Comparison, Bill-Level Analysis, Position Explorer, Methodology
- Reads from Snowflake dbt staging views (not Iceberg)
- **Live:** https://ai-influence-monitor-kouverk.streamlit.app/

### What's NOT Done
- Process more documents (only 30 of 10,000+ available)

---

## Agentic Scripts

### Current Scripts

| Script | Purpose | Output Table |
|--------|---------|--------------|
| `extract_positions.py` | Extract policy asks from PDF chunks | `ai_positions` |
| `assess_lobbying_impact.py` | Score public interest concerns | `lobbying_impact_scores` |
| `detect_discrepancies.py` | Find say-vs-do contradictions | `discrepancy_scores` |
| `analyze_china_rhetoric.py` | Deep-dive China competition framing | `china_rhetoric_analysis` |
| `compare_positions.py` | Cross-company position comparison | `position_comparisons` |
| `map_regulatory_targets.py` | Bill-level coalition analysis | `bill_position_analysis` |

### Run Commands

```bash
# Extract positions (already done - 633 positions from 17 companies)
./venv/bin/python include/scripts/agentic/extract_positions.py --limit=25

# Assess lobbying impact (v2 - completed for 10 companies)
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --fresh

# Detect discrepancies (completed for 10 companies)
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --fresh

# Analyze China rhetoric (completed for 11 companies)
./venv/bin/python include/scripts/agentic/analyze_china_rhetoric.py --fresh

# Cross-company comparison (completed)
./venv/bin/python include/scripts/agentic/compare_positions.py --fresh

# Bill-level coalition analysis (no LLM - rule-based)
./venv/bin/python include/scripts/agentic/map_regulatory_targets.py --fresh

# Dry run any script
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --dry-run
```

---

## Future AI Analyses

Potential additional agentic scripts to build:

### Completed ✅

**1. China Rhetoric Analyzer** (`analyze_china_rhetoric.py`) - DONE
- Analyzed 11 companies with China rhetoric
- Key finding: OpenAI has 85/100 rhetoric intensity, Anthropic only 15/100, Google 2/100

**2. Cross-Company Position Comparator** (`compare_positions.py`) - DONE
- Analyzed 17 companies, 633 positions
- Key finding: Trade groups do "dirty work" of aggressive advocacy that individual companies won't do publicly

**3. Regulatory Target Mapper** (`map_regulatory_targets.py`) - DONE
- Analyzed 21 bills/regulations comparing public positions to lobbying activity
- Key finding: "Quiet lobbying" pattern - Section 230 has 115 lobbying filings but ZERO public positions
- Only contested bill: EU AI Act (TechNet/CCIA support, Google/Meta oppose)

### Medium Priority

**4. Trade Group Aggregator** (`analyze_trade_groups.py`)
Trade groups (CCIA, TechNet, US Chamber) represent multiple companies:
- Identify "lowest common denominator" positions
- Compare trade group positions to member companies
- Flag where trade groups take more aggressive stances than members would publicly
- **Why valuable:** Trade groups can advocate positions individual companies won't say

### Lower Priority

**5. Argument Effectiveness Scorer** (`score_argument_effectiveness.py`)
Analyze which arguments companies use most:
- `patchwork_problem` → almost always supports `federal_preemption`
- `innovation_harm` → liability shields, audit opposition
- `china_competition` → national security, export controls
- **Why valuable:** Understand the rhetorical playbook

**6. Submission Quality Assessor** (`assess_submission_quality.py`)
Score depth of policy engagement:
- Generic/boilerplate vs specific recommendations
- Which companies actually engage vs checking a box
- **Why valuable:** Quality signal for policy seriousness

---

## Quick Reference

**Key files:**
- `include/config.py` - Company lists and LDA filter settings
- `include/scripts/extraction/` - Data loading (PDF, LDA)
- `include/scripts/agentic/` - LLM-powered analysis
- `include/scripts/utils/` - Helpers (progress, export)
- `dags/` - Airflow DAGs
- `dbt/` - dbt project
- `.env` - Credentials (AWS, Anthropic, Snowflake)

**Config:**
- Schema: `kouverk` (Iceberg) / `KOUVERK_AI_INFLUENCE` (Snowflake)
- LLM Model: claude-sonnet-4-20250514
- Chunking: 800 words, 100 word overlap

**Key Concepts:** *(Full definitions in [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md#glossary))*
- **Quiet Lobbying:** Companies file LDA lobbying disclosures but take NO public position on that legislation. Reveals hidden priorities. Example: Section 230 has 115 lobbying filings but zero public positions.
- **All Talk:** Companies take public positions but DON'T lobby on those bills. May indicate virtue signaling or low-priority positions.
- **Discrepancy Score:** 0-100 measuring say-vs-do gap. Anthropic: 25 (consistent), Google/Amazon: 72 (biggest gap).
- **Concern Score:** 0-100 for public interest implications of lobbying agenda. Trade groups: 72, Anthropic: 45.

---

## Session Log

### Session 9: February 2, 2026
- **Major architecture refactor: Snowflake as single source of truth**
- Updated `export_to_snowflake.py` to export all 10 tables (added `bill_position_analysis`)
- Created 4 new dbt staging models: `stg_discrepancy_scores`, `stg_china_rhetoric`, `stg_position_comparisons`, `stg_bill_position_analysis`
- Fixed `stg_lobbying_impact_scores` schema to match v2 column names
- Created 2 new dbt marts: `fct_company_analysis` (combines all scores), `fct_bill_coalitions`
- Updated `dashboard/data_loader.py` to read from Snowflake instead of Iceberg
- Updated Airflow pipeline DAG to include ALL 6 agentic scripts with proper dependencies
- Pipeline flow: Extract → LLM Extraction → [LLM Analysis + Rule Analysis] → Snowflake → dbt

### Session 8: February 2, 2026
- Built and ran `map_regulatory_targets.py` (Regulatory Target Mapper)
- Created `bill_position_analysis` table with 21 bills analyzed
- Key finding: "Quiet lobbying" pattern - Section 230 has 115 filings, 0 public positions
- Added Glossary section to DATA_DICTIONARY.md (quiet lobbying, all talk, scores)
- Added Bill-Level Analysis section to dashboard (3 tabs)
- Updated INSIGHTS.md with Bill-Level Coalition Analysis findings

### Session 7: February 2, 2026
- Completed LDA extraction for failed companies (Palantir: 55, Adobe: 13, Intel: 92 filings)
- Final LDA totals: 970 filings, 3,051 activities, 11,518 lobbyists
- Re-ran all 4 agentic scripts with updated data:
  - `assess_lobbying_impact.py`: 23 companies scored
  - `detect_discrepancies.py`: 23 companies analyzed
  - `analyze_china_rhetoric.py`: 14 companies analyzed
  - `compare_positions.py`: 30 companies, 878 positions
- Updated INSIGHTS.md with comprehensive findings
- Key insight: Market expansion policies (government AI adoption) achieve unanimous support

### Session 6: January 17, 2025
- Re-ran `assess_lobbying_impact.py` with v2 prompt (10 companies, new schema)
- Re-ran `detect_discrepancies.py` with v2 prompt (10 companies)
- Built and ran `analyze_china_rhetoric.py` (11 companies with China framing)
- Built and ran `compare_positions.py` (cross-company analysis)
- Added `--fresh` flag to agentic scripts for clean reruns
- Key findings:
  - Anthropic lowest concern (45/100) and most consistent (25/100 discrepancy)
  - Google/Amazon highest discrepancy (75/100) - biggest say-vs-do gap
  - OpenAI most aggressive on China rhetoric (85/100), Google barely uses it (2/100)
  - Trade groups advocate aggressive positions companies won't say publicly

### Session 5: January 17, 2025
- Set up Astronomer project (`astro dev init`)
- Updated all 6 DAGs for Astronomer-compatible paths
- Refactored `assess_lobbying_impact.py` to use structured taxonomy (v2 prompt)
- Built `detect_discrepancies.py` for say-vs-do contradiction detection
- Added policy_ask → LDA issue code mapping for systematic comparison
- Documented 6 potential future AI analyses

### Session 4: January 14, 2025
- Created shared `include/config.py` for company lists and LDA filters
- Aligned PDF and LDA extraction scripts to use same 16 priority companies
- Added LDA filters: 2023+ AND AI-relevant issue codes (CPI, SCI, CPT, CSP, DEF, HOM)
- Re-ran LDA extraction: 339 filings, 869 activities, 2,586 lobbyists

### Session 3: January 14, 2025
- Completed LLM position extraction: 633 positions from 112 chunks
- Fixed JSON parsing for Claude responses
- Created `check_progress.py` for monitoring
- Loaded Senate LDA lobbying data
- Notable finding: 55 positions use `china_competition` argument

### Session 2: January 14, 2025
- Created PDF extraction pipeline
- Implemented 3-table design for query efficiency
- Processed 17 priority company submissions → 112 chunks

### Session 1: January 2025
- Downloaded AI Action Plan submissions (10,068 PDFs, 746MB)
- Set up Python venv with PyMuPDF

---

*Last updated: February 2, 2026 (Session 9)*
