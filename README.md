# AI Influence Tracker

**What AI Companies Say vs. What They Lobby For**

A document intelligence pipeline that processes 10,000+ government policy submissions, extracts structured positions using LLMs, and joins them to federal lobbying disclosures to surface discrepancies between public statements and lobbying activity.

---

## The Question

Do AI companies practice what they preach on safety and regulation?

OpenAI's CEO calls for AI regulation in congressional testimony. Then OpenAI lobbies against California's AI safety bill. This pipeline systematically tracks and quantifies these gaps across the entire AI industry.

---

## What It Does

1. **Ingests government documents** - AI Action Plan submissions (10,068 docs), Federal Register filings, Regulations.gov comments
2. **Extracts policy positions** - LLM reads each document and extracts structured positions (topic, stance, supporting quote)
3. **Pulls lobbying data** - Senate LDA filings, OpenSecrets spend data
4. **Matches entities** - Resolves "OpenAI" vs "OpenAI, Inc." vs "OpenAI LP" across sources
5. **Calculates discrepancy scores** - Compares stated positions to lobbying activity
6. **Monitors continuously** - Daily/weekly jobs catch new filings as they drop

---

## Data Sources

| Source | Type | Schedule | Content |
|--------|------|----------|---------|
| [AI Action Plan Submissions](https://www.nitrd.gov/coordination-areas/ai/90-fr-9088-responses/) | Bulk download | One-time | 10,068 policy submissions to Trump admin |
| [Federal Register API](https://www.federalregister.gov/api/v1/) | REST API | Daily | New AI-related RFIs, rules, notices |
| [Regulations.gov API](https://api.regulations.gov/v4/) | REST API | Daily | Public comments on AI regulatory dockets |
| [Senate LDA API](https://lda.senate.gov/api/v1/) | REST API | Weekly | Lobbying disclosure filings |
| [OpenSecrets](https://www.opensecrets.org/open-data/bulk-data) | Bulk CSV | Monthly | Aggregated lobbying spend |

---

## Architecture

```
Extract (Airflow)          Transform (dbt + LLM)           Load
─────────────────          ────────────────────           ─────
                           
Federal Register ─┐        ┌─ stg_submissions             
Regulations.gov ──┼──────▶ ├─ stg_federal_register ─┐     
AI Submissions ───┤        ├─ stg_lda_filings       │     
Senate LDA ───────┤        └─ stg_opensecrets       │     
OpenSecrets ──────┘                                 │     
                                                    ▼     
                           ┌─ int_llm_positions ────┐     
                           └─ int_entity_resolution─┤     
                                                    ▼     
                           ┌─ fct_policy_positions  │     
                           ├─ fct_lobbying_activity ┼───▶ Snowflake
                           ├─ fct_discrepancy_scores│     
                           └─ dim_company, dim_topic┘     
```

---

## Key Features

### LLM-Powered Position Extraction
Claude reads policy documents and extracts structured JSON:
```json
{
  "topic": "state_regulation",
  "stance": "strong_oppose",
  "supporting_quote": "This patchwork of regulations risks bogging down innovation",
  "confidence": 0.95
}
```

### Discrepancy Scoring
Quantifies the gap between what companies say publicly and what they lobby for:
- **0-20:** Consistent - lobbying matches stated positions
- **21-40:** Minor gaps
- **41-60:** Mixed signals
- **61-80:** Significant contradictions
- **81-100:** Lobbying directly opposes public statements

### Continuous Monitoring
Not a one-time analysis. Airflow DAGs run daily/weekly to catch new filings as the policy landscape evolves.

---

## Tech Stack

- **Orchestration:** Airflow (Astronomer)
- **Transformation:** dbt
- **Warehouse:** Snowflake
- **LLM:** Claude API (Anthropic)
- **PDF Processing:** Reducto.ai / PyMuPDF
- **Language:** Python

---

## Project Structure

```
ai-influence-tracker/
├── airflow/dags/           # Airflow DAGs for each data source
├── dbt/models/             # Staging, intermediate, mart models
├── scripts/                # One-time scripts (download, extraction)
├── notebooks/              # Exploration and testing
├── CLAUDE.md               # Context file for Claude Code
└── README.md               # This file
```

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/[you]/ai-influence-tracker
cd ai-influence-tracker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Download AI submissions (one-time, 600MB)
python scripts/download_ai_submissions.py

# Set up environment variables
cp .env.example .env
# Add your API keys: CLAUDE_API_KEY, SENATE_LDA_API_KEY, etc.

# Run Airflow locally or deploy to Astronomer
astro dev start
```

---

## Why This Matters

The AI policy debate is happening right now. Companies are simultaneously:
- Calling for "responsible AI development" in public
- Lobbying to kill safety regulations behind closed doors
- Framing everything as "beating China" to avoid oversight

This pipeline creates accountability by making the gaps visible and quantifiable.

---

## Broader Application

The same architecture applies to:
- **Legal tech** - Contract analysis, due diligence
- **RegTech** - Regulatory compliance monitoring
- **GovTech** - Government document processing
- **Investigative journalism** - Following the money

The document intelligence market is $10B+ and growing 30% annually.

---

## Status

🚧 **In Development** - Capstone project for DataExpert.io analytics engineering bootcamp

---

## License

MIT
