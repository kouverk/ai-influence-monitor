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

**2. LLM Position Extraction** ✅ (THE AGENTIC PART!)
- Script: `include/scripts/agentic/extract_positions.py`
- Sends chunks to Claude API (claude-sonnet-4-20250514)
- Extracts structured policy positions: topic, stance, supporting_quote, confidence
- Idempotent/incremental - tracks processed chunks, safe to re-run

**3. Senate LDA Lobbying Data** ✅
- Script: `include/scripts/extraction/extract_lda_filings.py`
- Fetches lobbying disclosures from lda.senate.gov API
- Normalizes into 3 tables: filings, activities, lobbyists

**Data currently in Iceberg:**

| Table | Rows | Description |
|-------|------|-------------|
| `kouverk.ai_submissions_metadata` | 17 | Document info (pages, words, size) |
| `kouverk.ai_submissions_text` | 17 | Full extracted text |
| `kouverk.ai_submissions_chunks` | 112 | Chunks for LLM processing |
| `kouverk.ai_positions` | **607** | LLM-extracted policy positions ✅ |
| `kouverk.lda_filings` | **339** | Lobbying quarterly filings (2023+, AI-relevant) |
| `kouverk.lda_activities` | **869** | Issue codes + descriptions |
| `kouverk.lda_lobbyists` | **2,586** | Individual lobbyists |

**Companies processed:** OpenAI, Anthropic, Google, Meta, Microsoft, Amazon, Palantir, IBM, Adobe, Nvidia, Mistral, Cohere, CCIA, TechNet, BSA, ITI, BCBSA

**Position breakdown:**
- 94 positions on `china_competition` topic (see China Rhetoric Analysis below)
- 5.4 avg positions per chunk
- Topics: ai_safety, federal_regulation, state_regulation, preemption, copyright, open_source, etc.

**China Rhetoric Analysis** (new analysis angle):
- 94 positions invoke China/competition framing
- **Two distinct approaches:**
  - **Rhetoric Analysis (PRIMARY):** Categorize *how* companies use China framing (all 94 positions)
  - **Fact-Checking (OPTIONAL):** Verify *whether* specific claims are true (only verifiable claims, requires FARA/CSET)
- Rhetoric analysis comes first because every claim can be categorized, but only some can be fact-checked
- See [INSIGHTS.md](docs/INSIGHTS.md) for full framework and distinction

### What's NOT Done
- dbt models (transform layer)
- Discrepancy scoring (LLM compares positions to lobbying)
- China rhetoric deep-dive (categorize and analyze the 94 positions)
- Dashboard
- Optional: FARA/CSET data for fact-checking specific claims

---

## Next Steps

### Option A: dbt Project Setup (recommended)
Create dbt models to transform Iceberg data → analytics-ready tables.
- Staging models for submissions, positions, lobbying
- Entity resolution to match companies across sources
- Marts: `fct_policy_positions`, `fct_lobbying_activity`, `dim_company`
- **Why now:** Core ETL infrastructure for capstone

### Option B: Discrepancy Scoring
Build the "hypocrite detector" - compare stated positions to lobbying activity.
- LLM prompt that takes positions + lobbying → discrepancy score
- Output: 0-100 score + reasoning + key inconsistencies
- **Why now:** The "aha moment" of the project

### Option C: China Rhetoric Analysis
Analyze *how companies use China framing* in policy arguments (not whether China is a threat).
- Pull and review the 94 `china_competition` positions
- Categorize claim types: capability, regulatory comparison, security framing, vague
- Flag verifiable claims vs unfalsifiable rhetoric
- Map China invocations to specific regulations being opposed
- Compare usage patterns across AI labs vs Big Tech vs trade groups
- **Why now:** Adds depth to the "say vs lobby" story
- **See:** [INSIGHTS.md](docs/INSIGHTS.md) for full analysis framework

### Option D: Process More Documents
Expand beyond 17 priority companies.
- ~1,687 named submissions available
- ~8,000 anonymous submissions
- **Why now:** More data volume for capstone requirements

### Option E: Airflow DAGs
Convert scripts into proper Airflow DAGs for Astronomer deployment.
- DAGs for each extraction pipeline
- Scheduling for live API sources
- **Why now:** Required for capstone submission

---

## Quick Reference

**Run scripts:**
```bash
# PDF extraction (already complete)
./venv/bin/python include/scripts/extraction/extract_pdf_submissions.py

# LLM position extraction (already complete)
./venv/bin/python include/scripts/agentic/extract_positions.py --limit=25

# LDA lobbying data (already complete)
./venv/bin/python include/scripts/extraction/extract_lda_filings.py

# Check progress across all tables
./venv/bin/python include/scripts/utils/check_progress.py
```

**Key files:**
- `include/config.py` - Shared company lists and LDA filter settings
- `include/scripts/extraction/` - Data loading scripts (PDF, LDA)
- `include/scripts/agentic/` - LLM-powered extraction
- `include/scripts/utils/` - Helper scripts (progress tracking)
- `.env` - AWS credentials + SCHEMA + ANTHROPIC_API_KEY
- `queries/` - SQL for Trino exploration

**Config:**
- Schema: `kouverk` (from `.env`)
- Chunking: 800 words, 100 word overlap
- LLM Model: claude-sonnet-4-20250514

---

## Session Log

### Session 4: January 14, 2025
- Created shared `include/config.py` for company lists and LDA filters
- Aligned PDF and LDA extraction scripts to use same 16 priority companies
- Added LDA filters: 2023+ AND AI-relevant issue codes (CPI, SCI, CPT, CSP, DEF, HOM)
- Re-ran LDA extraction: 339 filings, 869 activities, 2,586 lobbyists
- 3 rate limit errors (Meta, Microsoft, Cohere partial) - can backfill later

### Session 3: January 14, 2025 (continued)
- **Completed LLM position extraction!** 607 positions from 112 chunks
- Fixed JSON parsing to handle Claude responses with markdown/explanatory text
- Created `include/scripts/utils/check_progress.py` for monitoring
- Loaded Senate LDA lobbying data (110 filings, 236 activities, 624 lobbyists)
- Researched China data sources for fact-checking "China threat" claims
- Documented FARA (foreign agents) and Georgetown CSET as future data sources
- Notable finding: 94 positions on `china_competition` topic

### Session 2: January 14, 2025
- Created PDF extraction pipeline following bootcamp pyiceberg pattern
- Implemented 3-table design for query efficiency
- Processed 17 priority company submissions → 112 chunks
- Created SQL queries folder for Trino exploration
- Split documentation into separate files

### Session 1: January 2025
- Downloaded AI Action Plan submissions (10,068 PDFs, 746MB)
- Set up Python venv with PyMuPDF
- Explored data structure and file formats

---

*Last updated: January 14, 2025*
