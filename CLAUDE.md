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

**PDF Extraction Pipeline** - `include/scripts/extract_pdf_submissions.py`
- Extracts text from PDFs using PyMuPDF
- Chunks into ~800 word segments (100 word overlap) for LLM processing
- Writes to 3 Iceberg tables via PyIceberg + AWS Glue

**Data loaded (17 priority company submissions):**

| Table | Rows | Description |
|-------|------|-------------|
| `kouverk.ai_submissions_metadata` | 17 | Document info (pages, words, size) |
| `kouverk.ai_submissions_text` | 17 | Full extracted text |
| `kouverk.ai_submissions_chunks` | 112 | Chunks ready for LLM extraction |

**Companies processed:** OpenAI, Anthropic, Google, Meta, Microsoft, Amazon, Palantir, IBM, Adobe, Nvidia, Mistral, Cohere, CCIA, TechNet, BSA, ITI, US Chamber of Commerce

**SQL queries ready:** `queries/01_metadata_overview.sql` through `04_table_schemas.sql` for Trino exploration.

### What's NOT Done
- LLM position extraction (the "agentic" part)
- Senate LDA lobbying data ingestion
- dbt models
- Discrepancy scoring
- Dashboard

---

## Next Steps

### Option A: LLM Position Extraction (recommended - core "agentic" feature)
Write a script that sends chunks to Claude API and extracts policy positions.
- **Requires:** `CLAUDE_API_KEY` in `.env`
- **Output:** Structured positions (topic, stance, supporting_quote, confidence)
- **Why now:** This is the "wow factor" - AI extracting insights from text

### Option B: Senate LDA Lobbying API
Explore the second data source - what companies actually lobby for.
- **Requires:** Nothing (public API, no key needed)
- **Output:** Lobbying filings for OpenAI, Anthropic, Google, etc.
- **Why now:** Needed to compare "what they say" vs "what they lobby for"

### Option C: dbt Project Setup
Create dbt folder structure with staging models.
- **Output:** Scaffolding for transformations
- **Why now:** Gets pipeline infrastructure in place

### Option D: Process More Documents
Expand beyond priority companies.
- Could process all ~1,687 named submissions
- Or sample from the 8k anonymous submissions
- **Why now:** More data volume for capstone requirements

---

## Quick Reference

**Run extraction script:**
```bash
./venv/bin/python include/scripts/extract_pdf_submissions.py
```

**Key files:**
- `include/scripts/extract_pdf_submissions.py` - PDF extraction + Iceberg writes
- `.env` - AWS credentials + SCHEMA config
- `queries/` - SQL for Trino exploration

**Config:**
- Schema: `kouverk` (from `.env`)
- Chunking: 800 words, 100 word overlap
- Tables: `ai_submissions_metadata`, `ai_submissions_text`, `ai_submissions_chunks`

---

## Session Log

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
