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
- Exports Iceberg tables to Snowflake RAW tables
- Database: `DATAEXPERT_STUDENT.KOUVERK_AI_INFLUENCE`

**5. dbt Models** ✅
- Project: `dbt/ai_influence/`
- 6 staging views + 4 mart tables
- 23 tests passing

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
- `detect_discrepancies.py` - Say vs Do contradiction detection (NEW)

**Data in Iceberg:**

| Table | Rows | Description |
|-------|------|-------------|
| `kouverk.ai_submissions_metadata` | 17 | Document info |
| `kouverk.ai_submissions_text` | 17 | Full extracted text |
| `kouverk.ai_submissions_chunks` | 112 | Chunks for LLM |
| `kouverk.ai_positions` | **633** | Policy asks with taxonomy |
| `kouverk.lda_filings` | **339** | Lobbying filings (2023+) |
| `kouverk.lda_activities` | **869** | Issue codes + descriptions |
| `kouverk.lda_lobbyists` | **2,586** | Individual lobbyists |
| `kouverk.lobbying_impact_scores` | 10 | Concern scores (v1) |
| `kouverk.discrepancy_scores` | 10 | Discrepancy scores (v1) |

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

### What's NOT Done
- Dashboard/visualization layer
- Re-run agentic scripts with v2 prompts (table schemas changed)
- Process more documents (only 17 of 10,000+ available)

---

## Agentic Scripts

### Current Scripts

| Script | Purpose | Output Table |
|--------|---------|--------------|
| `extract_positions.py` | Extract policy asks from PDF chunks | `ai_positions` |
| `assess_lobbying_impact.py` | Score public interest concerns | `lobbying_impact_scores` |
| `detect_discrepancies.py` | Find say-vs-do contradictions | `discrepancy_scores` |

### Run Commands

```bash
# Extract positions (already done)
./venv/bin/python include/scripts/agentic/extract_positions.py --limit=25

# Assess lobbying impact (v2 prompt - re-run with --fresh)
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --fresh --limit=1

# Detect discrepancies (v2 prompt - re-run with --fresh)
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --fresh --limit=1

# Dry run any script
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --dry-run
```

---

## Future AI Analyses

Potential additional agentic scripts to build, ranked by value:

### High Priority

**1. China Rhetoric Analyzer** (`analyze_china_rhetoric.py`)
Deep-dive on the 55 positions using `china_competition` as argument:
- Categorize claim types: capability claims, regulatory comparison, security framing, vague warnings
- Flag verifiable vs unfalsifiable claims
- Map which policy asks the China argument supports
- Compare usage across company types (AI labs vs Big Tech vs trade groups)
- **Why valuable:** OpenAI uses China 16 times, Palantir 6. Are they making the same arguments?

**2. Cross-Company Position Comparator** (`compare_positions.py`)
Direct head-to-head analysis:
- Where do OpenAI and Anthropic agree/disagree?
- Where do AI labs differ from Big Tech?
- What's the "industry consensus" vs outlier positions?
- **Why valuable:** Reveals coalition dynamics and fracture lines

### Medium Priority

**3. Trade Group Aggregator** (`analyze_trade_groups.py`)
Trade groups (CCIA, TechNet, US Chamber) represent multiple companies:
- Identify "lowest common denominator" positions
- Compare trade group positions to member companies
- Flag where trade groups take more aggressive stances than members would publicly
- **Why valuable:** Trade groups can advocate positions individual companies won't say

**4. Regulatory Target Mapper** (`map_regulatory_targets.py`)
The `target` field identifies specific bills/regulations:
- Aggregate positions on specific targets (e.g., "California SB 1047")
- Identify which companies oppose vs support each regulation
- Cross-reference with lobbying on those issues
- **Why valuable:** See coalition patterns on specific legislation

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
- `dbt/ai_influence/` - dbt project
- `.env` - Credentials (AWS, Anthropic, Snowflake)

**Config:**
- Schema: `kouverk` (Iceberg) / `KOUVERK_AI_INFLUENCE` (Snowflake)
- LLM Model: claude-sonnet-4-20250514
- Chunking: 800 words, 100 word overlap

---

## Session Log

### Session 5: January 17, 2025
- Set up Astronomer project (`astro dev init`)
- Updated all 6 DAGs for Astronomer-compatible paths
- Refactored `assess_lobbying_impact.py` to use structured taxonomy (v2 prompt)
- Built `detect_discrepancies.py` for say-vs-do contradiction detection
- Added policy_ask → LDA issue code mapping for systematic comparison
- Documented 6 potential future AI analyses
- Note: Existing score tables use old schema; re-run with `--fresh` for new output

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

*Last updated: January 17, 2025*
