# Architecture & Reference

Detailed technical reference for the AI Influence Tracker. **Read this when you need implementation details.**

**Related docs:**
- [CLAUDE.md](../CLAUDE.md) - Project overview, current state, next steps
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) - Tables, columns, data sources
- [INSIGHTS.md](INSIGHTS.md) - Findings and observations

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTRACT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  Airflow DAGs:                                                       │
│  - federal_register_monitor_dag (daily)                              │
│  - regulations_gov_monitor_dag (daily)                               │
│  - lda_lobbying_sync_dag (weekly)                                    │
│  - opensecrets_refresh_dag (monthly)                                 │
│  - ai_submissions_initial_load_dag (one-time)                        │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TRANSFORM LAYER (dbt)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Staging:                                                            │
│  - stg_submissions (raw document text + metadata)                    │
│  - stg_federal_register (new AI policy documents)                    │
│  - stg_lda_filings (lobbying disclosures)                           │
│  - stg_opensecrets (lobbying spend totals)                          │
│                                                                      │
│  Intermediate:                                                       │
│  - int_llm_position_extraction (Claude API extracts positions)       │
│  - int_entity_resolution (match companies across sources)            │
│                                                                      │
│  Marts:                                                              │
│  - fct_policy_positions                                              │
│  - fct_lobbying_activity                                             │
│  - fct_discrepancy_scores                                            │
│  - dim_company, dim_topic, dim_person                                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LOAD LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│  Iceberg (staging):                                                  │
│  - ai_submissions_metadata, _text, _chunks                           │
│                                                                      │
│  Snowflake (marts):                                                  │
│  - fct_*, dim_* tables                                               │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VISUALIZATION LAYER                             │
├─────────────────────────────────────────────────────────────────────┤
│  Dashboard showing:                                                  │
│  - Company "say vs. lobby" discrepancy scores                       │
│  - Position breakdown by topic                                       │
│  - Lobbying spend trends                                             │
│  - Timeline of policy evolution                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Airflow DAG Structure

```python
# DAG 1: Federal Register Monitor (Daily)
federal_register_monitor_dag
├── check_for_new_ai_documents      # Query API for docs since last run
├── download_new_documents          # Fetch full document content
├── extract_text_from_pdfs          # PDF → text (if needed)
├── load_to_staging                 # Insert to Iceberg
└── trigger_llm_extraction_dag      # Trigger downstream

# DAG 2: Regulations.gov Comments Monitor (Daily)
regulations_gov_monitor_dag
├── check_for_new_comments          # Query for comments on AI dockets
├── download_new_comments           # Fetch comment content
├── load_to_staging
└── trigger_llm_extraction_dag

# DAG 3: Senate LDA Sync (Weekly)
lda_lobbying_sync_dag
├── fetch_new_filings_since_last_run
├── filter_ai_related_filings       # Filter by client name or issue code
├── load_to_staging
├── run_entity_resolution           # Match to dim_company
└── trigger_discrepancy_recalc_dag

# DAG 4: OpenSecrets Refresh (Monthly)
opensecrets_refresh_dag
├── download_bulk_data
├── filter_ai_companies
├── load_to_staging
└── trigger_discrepancy_recalc_dag

# DAG 5: LLM Position Extraction (Triggered)
llm_extraction_dag
├── get_unprocessed_documents       # Query for docs without positions
├── batch_documents                 # Chunks of 10-20 for rate limits
├── call_claude_api                 # With retry/backoff logic
├── validate_llm_output             # Check JSON structure
├── load_positions_to_staging
└── trigger_dbt_run

# DAG 6: Discrepancy Recalculation (Triggered)
discrepancy_recalc_dag
├── get_companies_with_new_data
├── run_dbt_models                  # Rebuild fct_discrepancy_scores
└── refresh_dashboard_cache
```

---

## LLM Prompts

### Position Extraction Prompt

```python
POSITION_EXTRACTION_PROMPT = """
You are analyzing a policy submission to the US government regarding AI regulation.

<document>
{document_text}
</document>

<submitter>
{submitter_name} ({submitter_type})
</submitter>

Extract all distinct policy positions from this document. For each position:

1. topic: Classify into ONE of these categories:
   - ai_safety: Concerns about AI risks, alignment, testing requirements
   - state_regulation: Position on state-level AI laws (e.g., California SB 1047)
   - federal_regulation: Position on federal AI oversight/agencies
   - preemption: Whether federal law should preempt state laws
   - copyright: Training data, fair use, IP issues
   - open_source: Open vs closed model development
   - china_competition: National security, competitiveness framing
   - export_controls: Chip restrictions, model weight controls
   - liability: Who is responsible when AI causes harm
   - workforce: Job displacement, retraining
   - research_funding: Government R&D investment
   - energy_infrastructure: Data centers, power grid
   - other: Doesn't fit above categories

2. stance: One of:
   - strong_support: Explicitly advocates for this
   - support: Generally favorable
   - neutral: Mentions without clear position
   - oppose: Generally unfavorable
   - strong_oppose: Explicitly argues against

3. supporting_quote: A direct quote (under 50 words) that best supports this classification

4. confidence: Your confidence in this classification (0.0-1.0)

Return as a JSON array. If no clear policy positions exist, return empty array [].

Example output:
[
  {
    "topic": "state_regulation",
    "stance": "strong_oppose",
    "supporting_quote": "This patchwork of state regulations risks bogging down innovation and undermining America's competitive position.",
    "confidence": 0.95
  },
  {
    "topic": "china_competition",
    "stance": "strong_support",
    "supporting_quote": "American AI dominance is essential to national security and economic prosperity.",
    "confidence": 0.88
  }
]
"""
```

### Discrepancy Scoring Prompt

```python
DISCREPANCY_SCORING_PROMPT = """
Analyze consistency between a company's public policy statements and their lobbying activity.

<company>{company_name}</company>

<public_positions>
{positions_json}
</public_positions>

<lobbying_activity>
{lobbying_json}
</lobbying_activity>

Evaluate consistency and return JSON:

{
  "discrepancy_score": <0-100 integer>,
  "reasoning": "<2-3 sentence explanation>",
  "key_inconsistencies": [
    {
      "topic": "<topic>",
      "public_stance": "<what they said>",
      "lobbying_action": "<what they lobbied for/against>",
      "severity": "<minor|moderate|major>"
    }
  ],
  "consistent_areas": ["<topics where positions match lobbying>"]
}

Scoring guide:
- 0-20: Highly consistent - lobbying aligns with stated positions
- 21-40: Mostly consistent - minor gaps or ambiguities
- 41-60: Mixed - some positions contradicted by lobbying
- 61-80: Inconsistent - significant contradictions
- 81-100: Highly inconsistent - lobbying directly opposes stated positions
"""
```

### China Rhetoric Classification Prompt (Planned)

```python
CHINA_RHETORIC_PROMPT = """
Analyze how this policy position uses China/competition framing.

<position>
{position_json}
</position>

<original_quote>
{supporting_quote}
</original_quote>

Classify the China-related claim and return JSON:

{
  "claim_type": "<capability|regulatory_comparison|security_framing|vague_competitiveness>",
  "specific_claim": "<one sentence describing what is being claimed about China>",
  "verifiable": <true|false>,
  "verification_approach": "<how this claim could be fact-checked, or 'unfalsifiable' if not possible>",
  "regulation_opposed": "<specific regulation being argued against, or 'none' if general>",
  "rhetorical_devices": ["<list of persuasion techniques used>"]
}

Claim type definitions:
- capability: Claims about China's AI capabilities ("China will overtake us", "China is ahead")
- regulatory_comparison: Claims about China's regulatory environment ("China doesn't regulate")
- security_framing: National security arguments ("essential for defense", "strategic importance")
- vague_competitiveness: Generic competition language without specific claims ("we must compete")

Verifiability guide:
- TRUE if claim references specific, checkable facts (publications, patents, laws, investments)
- FALSE if claim is predictive, hypothetical, or uses unmeasurable concepts
"""
```

**Purpose:** This prompt enables systematic analysis of how companies use "China threat" framing in policy arguments. The goal is to categorize rhetoric patterns, not to prove/disprove whether China is actually a threat.

**See:** [INSIGHTS.md](INSIGHTS.md) for the full analysis framework.

---

## API Endpoints Reference

### Federal Register
```
Base: https://www.federalregister.gov/api/v1

# Search for AI-related documents
GET /documents.json?conditions[term]=artificial+intelligence&conditions[type]=NOTICE

# Get specific document
GET /documents/{document_number}.json

Docs: https://www.federalregister.gov/developers/documentation/api/v1
```

### Regulations.gov
```
Base: https://api.regulations.gov/v4

# Search documents
GET /documents?filter[searchTerm]=artificial%20intelligence&api_key={key}

# Get comments on a docket
GET /comments?filter[docketId]={docket_id}&api_key={key}

Docs: https://open.gsa.gov/api/regulationsgov/
Requires: API key registration
```

### Senate LDA
```
Base: https://lda.senate.gov/api/v1

# Search filings
GET /filings/?client_name=OpenAI

# Get filing details
GET /filings/{filing_uuid}/

# List lobbyists
GET /lobbyists/

Docs: https://lda.senate.gov/api/
Note: No API key required (public data)
```

---

## Entity Resolution

Companies appear with different names across sources. Build alias mapping:

```python
COMPANY_ALIASES = {
    "openai": [
        "OpenAI",
        "OpenAI, Inc.",
        "OpenAI, Inc",
        "OpenAI LP",
        "OpenAI Global LLC",
        "Open AI",
    ],
    "anthropic": [
        "Anthropic",
        "Anthropic, PBC",
        "Anthropic PBC",
    ],
    "google": [
        "Google",
        "Google LLC",
        "Google Inc.",
        "Alphabet",
        "Alphabet Inc.",
        "Google DeepMind",
        "DeepMind",
    ],
    # ... etc
}
```

Use fuzzy matching (rapidfuzz) for unmatched entities, then manually verify.

---

## Key Companies to Track

### Tier 1: AI Labs (must include)
- OpenAI, Anthropic, Google DeepMind, Meta AI, xAI, Mistral, Cohere

### Tier 2: Big Tech
- Microsoft, Amazon (AWS), Apple, Nvidia, IBM, Oracle, Salesforce, Palantir

### Tier 3: Trade Groups
- BSA | The Software Alliance, ITI, TechNet, CCIA, Chamber of Commerce

### Tier 4: Other Notable
- Academic institutions, Civil society / nonprofits, Individual researchers

---

## Environment Variables

```bash
# AWS/Iceberg (required for extraction)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-west-2
AWS_S3_BUCKET_TABULAR=
SCHEMA=kouverk

# Snowflake (for marts later)
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=
SNOWFLAKE_DATABASE=
SNOWFLAKE_SCHEMA=

# APIs
ANTHROPIC_API_KEY=              # Required for LLM extraction
REGULATIONS_GOV_API_KEY=        # Future: for regulations.gov API
```

---

## Scripts

### Extraction Scripts (`include/scripts/extraction/`)

**`extract_pdf_submissions.py`** - PDF text extraction
- Reads PDFs from `data/90-fr-9088-combined-responses/`
- Extracts text using PyMuPDF
- Chunks text (800 words, 100 word overlap)
- Writes to Iceberg: `ai_submissions_metadata`, `ai_submissions_text`, `ai_submissions_chunks`
- Idempotent via `overwrite()` - safe to re-run

**`extract_lda_filings.py`** - Senate LDA lobbying data
- Fetches filings from `https://lda.senate.gov/api/v1/`
- Normalizes nested JSON into 3 tables
- Writes to Iceberg: `lda_filings`, `lda_activities`, `lda_lobbyists`
- Idempotent via `overwrite()` - safe to re-run

### Agentic Scripts (`include/scripts/agentic/`)

**`extract_positions.py`** - LLM position extraction
- Reads unprocessed chunks from `ai_submissions_chunks`
- Sends to Claude API with position extraction prompt
- Writes to Iceberg: `ai_positions`
- **Idempotent**: Tracks processed chunk_ids, uses `append()` not `overwrite()`
- **Incremental**: Safe to run multiple times, only processes new chunks
- **Rate limited**: 1 second delay between API calls
- **Retry logic**: 3 retries with 5 second backoff

```bash
# Usage
./venv/bin/python include/scripts/agentic/extract_positions.py           # Process all
./venv/bin/python include/scripts/agentic/extract_positions.py --limit=10  # Process 10
./venv/bin/python include/scripts/agentic/extract_positions.py --dry-run   # Preview only
```

### Exploration Scripts (`include/scripts/exploration/`)

**`explore_lda_api.py`** - Quick LDA API exploration
- Queries multiple companies, reports summary stats

### Utility Scripts (`include/scripts/utils/`)

**`check_progress.py`** - Progress report across all tables
- Shows row counts for all Iceberg tables
- Shows position extraction progress (chunks processed vs total)
- Breaks down positions by submitter

```bash
./venv/bin/python include/scripts/utils/check_progress.py
```

---

## Project Structure

```
ai-influence-monitor/
├── CLAUDE.md                    # Quick context (overview, status, next steps)
├── docs/
│   ├── DATA_DICTIONARY.md       # Tables, columns, sources
│   ├── ARCHITECTURE.md          # This file - detailed reference
│   └── INSIGHTS.md              # Findings and observations
├── include/
│   └── scripts/
│       ├── extraction/          # Data loading scripts
│       │   ├── extract_pdf_submissions.py
│       │   └── extract_lda_filings.py
│       ├── agentic/             # LLM-powered extraction
│       │   └── extract_positions.py
│       ├── exploration/         # API exploration / research
│       │   └── explore_lda_api.py
│       └── utils/               # Helper scripts
│           └── check_progress.py
├── queries/                     # SQL for Trino exploration
├── dags/                        # Airflow DAGs (future)
├── dbt/                         # dbt project (future)
├── data/                        # Downloaded PDFs (gitignored)
├── .env                         # Config
└── requirements.txt
```

---

## Resources

- AI Action Plan Submissions: https://www.nitrd.gov/coordination-areas/ai/90-fr-9088-responses/
- Senate LDA API Docs: https://lda.senate.gov/api/
- Federal Register API: https://www.federalregister.gov/developers/documentation/api/v1
- Regulations.gov API: https://open.gsa.gov/api/regulationsgov/
- OpenSecrets Bulk Data: https://www.opensecrets.org/open-data/bulk-data
- dbt Docs: https://docs.getdbt.com/
- Astronomer: https://www.astronomer.io/
