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
│                         EXTRACT LAYER (to Iceberg)                   │
├─────────────────────────────────────────────────────────────────────┤
│  Scripts (include/scripts/extraction/):                              │
│  - extract_pdf_submissions.py  → ai_submissions_metadata/text/chunks │
│  - extract_lda_filings.py      → lda_filings/activities/lobbyists   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM ANALYSIS LAYER (Agentic)                      │
├─────────────────────────────────────────────────────────────────────┤
│  Scripts (include/scripts/agentic/):                                 │
│  - extract_positions.py         → ai_positions (878 rows)           │
│  - assess_lobbying_impact.py    → lobbying_impact_scores (23 rows)  │
│  - detect_discrepancies.py      → discrepancy_scores (23 rows)      │
│  - analyze_china_rhetoric.py    → china_rhetoric_analysis (14 rows) │
│  - compare_positions.py         → position_comparisons (1 row)      │
│  - map_regulatory_targets.py    → bill_position_analysis (21 rows)  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LOAD LAYER (Iceberg → Snowflake)                   │
├─────────────────────────────────────────────────────────────────────┤
│  Script: export_to_snowflake.py                                      │
│  - Exports all 10 Iceberg tables to Snowflake RAW_* tables          │
│  - Full refresh (truncate + reload)                                  │
│  - Total: 26,567 rows across all tables                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TRANSFORM LAYER (dbt)                           │
├─────────────────────────────────────────────────────────────────────┤
│  Staging (10 views in KOUVERK_AI_INFLUENCE_STAGING):                 │
│  - stg_ai_positions, stg_ai_submissions                              │
│  - stg_lda_filings, stg_lda_activities, stg_lda_lobbyists           │
│  - stg_lobbying_impact_scores, stg_discrepancy_scores               │
│  - stg_china_rhetoric, stg_position_comparisons                      │
│  - stg_bill_position_analysis                                        │
│                                                                      │
│  Marts (6 tables in KOUVERK_AI_INFLUENCE_MARTS):                     │
│  - dim_company (84 companies)                                        │
│  - fct_policy_positions (878 positions)                              │
│  - fct_lobbying_quarterly (970 filings)                              │
│  - fct_lobbying_impact (23 scores)                                   │
│  - fct_company_analysis (30 companies with all scores)               │
│  - fct_bill_coalitions (21 bills)                                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VISUALIZATION LAYER                             │
├─────────────────────────────────────────────────────────────────────┤
│  Streamlit Dashboard (dashboard/app.py):                             │
│  - Executive Summary: Key findings and scores                        │
│  - Company Deep Dive: Per-company analysis                           │
│  - Cross-Company Comparison: Position patterns                       │
│  - Bill-Level Analysis: Quiet lobbying detection                     │
│  - Position Explorer: Browse all positions                           │
│  - Methodology: Data sources and approach                            │
│                                                                      │
│  Data: Reads from Snowflake dbt staging views                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Airflow DAG Structure

### Main Pipeline DAG (`ai_influence_pipeline.py`)

This is the primary orchestration DAG that runs the full pipeline.

```python
# Main Pipeline (Daily or Manual Trigger)
ai_influence_pipeline
│
├── [extract] Task Group
│   ├── extract_pdf_submissions     # PDF text → Iceberg (parallel)
│   └── extract_lda_filings         # LDA API → Iceberg (parallel)
│
├── [llm_extraction] Task Group
│   └── extract_positions           # Claude API → ai_positions
│
├── [llm_analysis] Task Group (parallel with rule_analysis)
│   ├── assess_lobbying_impact      # → lobbying_impact_scores
│   ├── detect_discrepancies        # → discrepancy_scores
│   ├── analyze_china_rhetoric      # → china_rhetoric_analysis
│   └── compare_positions           # → position_comparisons
│
├── [rule_analysis] Task Group (parallel with llm_analysis)
│   └── map_regulatory_targets      # → bill_position_analysis (no LLM)
│
└── [snowflake_sync] Task Group
    ├── export_to_snowflake         # Iceberg → Snowflake RAW
    ├── run_dbt                     # Build staging + marts
    └── test_dbt                    # Validate data quality
```

### Supporting DAGs

| DAG | Purpose | Schedule |
|-----|---------|----------|
| `extract_submissions_dag` | Extract PDFs only | Manual |
| `extract_lda_dag` | Extract LDA only | Manual |
| `llm_extraction_dag` | Position extraction only | Manual |
| `llm_impact_assessment_dag` | Impact scoring only | Manual |
| `snowflake_sync_dag` | Sync + dbt only | Daily |

---

## LLM Prompts

### Policy Ask Extraction Prompt (ACTIVE)

This prompt extracts **specific policy asks** - concrete things companies want the government to do. Each ask includes the policy action, stance, target regulation, and the arguments used to justify it.

```python
POSITION_EXTRACTION_PROMPT = """
You are analyzing a policy submission to the US government regarding AI regulation.

<document>
{document_text}
</document>

<submitter>
{submitter_name} ({submitter_type})
</submitter>

Extract all **specific policy asks** from this document. A policy ask is a concrete thing
the submitter wants the government to do (or not do).

For each policy ask found, return:

1. policy_ask: The specific policy action requested (see taxonomy in DATA_DICTIONARY.md)
2. ask_category: High-level grouping (regulatory_structure, accountability, intellectual_property,
   national_security, resources, other)
3. stance: support, oppose, or neutral
4. target: Specific regulation/bill being referenced (e.g., "California SB 1047"), or null
5. primary_argument: WHY they support/oppose this (e.g., competitiveness, china_competition,
   innovation_harm, patchwork_problem)
6. secondary_argument: Optional second argument (or null)
7. supporting_quote: Direct quote (≤50 words)
8. confidence: 0.0-1.0

Return as JSON array. If no clear policy asks exist, return [].

Example output:
[
  {
    "policy_ask": "federal_preemption",
    "ask_category": "regulatory_structure",
    "stance": "support",
    "target": "California SB 1047",
    "primary_argument": "patchwork_problem",
    "secondary_argument": "innovation_harm",
    "supporting_quote": "A patchwork of state regulations risks fragmenting the market.",
    "confidence": 0.92
  }
]
"""
```

**Why this prompt matters:** The enhanced schema captures not just WHAT companies want, but WHY they say they want it. This enables queries like:
- "Who uses China competition arguments to oppose regulation?"
- "Which companies want liability shields?"
- "What arguments are used against SB 1047?"

### Lobbying Impact Assessment Prompt (v2 - ACTIVE)

This is the key analysis prompt used by `assess_lobbying_impact.py`. Assesses **public interest implications** of corporate lobbying.

```python
LOBBYING_IMPACT_PROMPT = """
Assess the public interest implications of this company's AI policy lobbying.

<company>{company_name} ({company_type})</company>

<public_policy_positions>
{positions_json}
</public_policy_positions>

<lobbying_activity>
{lobbying_json}
</lobbying_activity>

Return JSON:
{
  "lobbying_agenda_summary": "<2-3 sentences>",
  "concern_score": <0-100>,
  "top_concerning_policy_asks": ["<most concerning asks with evidence>"],
  "public_interest_concerns": [{"concern": "...", "evidence": "...", "who_harmed": "...", "severity": "..."}],
  "regulatory_capture_signals": ["<signs of self-serving regulation shaping>"],
  "china_rhetoric_assessment": "<how they use China competition framing>",
  "accountability_stance": "<position on liability/external oversight>",
  "positive_aspects": ["<genuinely public-interest aligned>"],
  "key_flags": ["<red flags for journalists/regulators>"]
}

Scoring: 0-20=aligned, 21-40=minor concerns, 41-60=moderate, 61-80=significant, 81-100=critical
"""
```

**Output table:** `lobbying_impact_scores` (23 companies scored)

### Discrepancy Detection Prompt (v2 - ACTIVE)

Used by `detect_discrepancies.py` to find say-vs-do contradictions.

```python
DISCREPANCY_PROMPT = """
Compare this company's public policy positions to their lobbying activity.

<public_positions>{positions_json}</public_positions>
<lobbying_activity>{lobbying_json}</lobbying_activity>

Return JSON:
{
  "discrepancy_score": <0-100>,
  "discrepancies": [{"public_position": "...", "lobbying_behavior": "...", "significance": "..."}],
  "consistent_areas": ["<where positions match lobbying>"],
  "lobbying_priorities_vs_rhetoric": "<comparison>",
  "china_rhetoric_analysis": "<how China framing compares to actual lobbying focus>",
  "accountability_contradiction": "<gaps in accountability positions>",
  "key_finding": "<primary takeaway>"
}

Scoring: 0=perfectly consistent, 100=maximum hypocrisy
"""
```

**Output table:** `discrepancy_scores` (23 companies scored)

### China Rhetoric Analysis Prompt (ACTIVE)

Used by `analyze_china_rhetoric.py` for deep-dive on China competition framing.

```python
CHINA_RHETORIC_PROMPT = """
Analyze how this company uses China competition rhetoric in their AI policy positions.

<company>{company_name}</company>
<positions_using_china_argument>{china_positions_json}</positions_using_china_argument>
<all_positions>{all_positions_json}</all_positions>

Return JSON:
{
  "rhetoric_intensity": <0-100>,
  "claim_categorization": [{"claim_type": "capability|regulatory|security|vague", "example": "..."}],
  "rhetoric_patterns": ["<patterns in how China is invoked>"],
  "policy_asks_supported": ["<which policy asks use China rhetoric>"],
  "rhetoric_assessment": "<overall assessment>",
  "comparison_to_other_arguments": "<how China compares to other arguments used>",
  "notable_quotes": ["<key quotes>"],
  "key_finding": "<primary takeaway>"
}

Scoring: 0=minimal China framing, 100=heavy reliance on China rhetoric
"""
```

**Output table:** `china_rhetoric_analysis` (14 companies with China rhetoric analyzed)

**Key findings:** OpenAI scores 85/100 (most aggressive), Google scores 2/100 (barely uses it).

**See:** [INSIGHTS.md](INSIGHTS.md) for the full analysis framework.

---

## Scoring Methodology

### Discrepancy Score (0-100)

The discrepancy score measures the gap between what companies **say publicly** vs. what they **lobby for**.

**Inputs:**
```
Public Positions (from ai_positions):
- policy_ask: what they want (e.g., "federal_preemption")
- stance: support/oppose
- primary_argument: why they claim to want it
- target: specific bill/regulation

Lobbying Activity (from lda_activities):
- general_issue_code: what they're lobbying on
- specific_lobbying_issues: actual bills mentioned
- client_name: who's paying
```

**Scoring Logic (LLM-assessed):**

| Score Range | Interpretation | Example |
|-------------|----------------|---------|
| 0-20 | Highly consistent | Positions align with lobbying focus |
| 21-40 | Minor gaps | Some lobbying on issues not publicly discussed |
| 41-60 | Moderate discrepancy | Lobbying priorities differ from public messaging |
| 61-80 | Significant gaps | Lobbying contradicts stated positions |
| 81-100 | Maximum hypocrisy | Public statements opposite of lobbying activity |

**Key Factors Influencing Score:**
1. **Topic mismatch**: Lobbying on antitrust while public positions focus on AI safety
2. **Stance contradiction**: Supporting regulation publicly, lobbying against it
3. **Volume asymmetry**: Heavy lobbying on issues with zero public positions ("quiet lobbying")
4. **Timing gaps**: Recent lobbying contradicts older public statements

**Example Analysis (Google, score: 72/100):**
```
Public positions: AI safety, responsible development
Lobbying focus: Antitrust defense, government procurement, Section 230
Gap: Safety messaging doesn't match lobbying priorities
```

### Concern Score (0-100)

Measures **public interest implications** of a company's lobbying agenda.

**Factors:**
- Self-serving vs. public-interest alignment
- Accountability stance (liability shields, audit exemptions)
- Regulatory capture signals
- Who benefits vs. who's harmed

### China Rhetoric Intensity (0-100)

Measures **reliance on China competition framing** to justify policy positions.

**Factors:**
- % of positions using china_competition argument
- Specificity of claims (concrete vs. vague fear-mongering)
- Correlation with deregulation asks

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
# AWS/Iceberg (required for extraction to staging layer)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-west-2
AWS_S3_BUCKET_TABULAR=
SCHEMA=kouverk

# Snowflake (required for dbt models and dashboard)
SNOWFLAKE_ACCOUNT=              # e.g., abc12345.us-east-1
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_WAREHOUSE=            # e.g., COMPUTE_WH
SNOWFLAKE_DATABASE=             # e.g., DATAEXPERT_STUDENT
SNOWFLAKE_SCHEMA=               # e.g., KOUVERK_AI_INFLUENCE

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

**`assess_lobbying_impact.py`** - Lobbying impact assessment (THE KEY ANALYSIS!)
- Joins `ai_positions` with `lda_filings` + `lda_activities` by company
- Matches companies using `config.py` mapping (submitter_name → lda_name)
- Sends paired data to Claude API with `LOBBYING_IMPACT_PROMPT`
- Analyzes: What are they lobbying for? Who benefits/harmed? What's concerning?
- Writes to Iceberg: `lobbying_impact_scores`
- **Idempotent**: Tracks processed companies, uses `append()`
- **Output fields**: concern_score (0-100), lobbying_agenda_summary, top_concerning_policy_asks, public_interest_concerns, regulatory_capture_signals, china_rhetoric_assessment, accountability_stance, positive_aspects, key_flags

```bash
# Usage
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py           # Process all
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --limit=1  # Process one
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --dry-run  # Preview matches
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --fresh    # Clear and reprocess all
```

**`detect_discrepancies.py`** - Say-vs-Do contradiction detection
- Compares public policy positions to lobbying activity
- Finds gaps between what companies say publicly and what they lobby for
- Writes to Iceberg: `discrepancy_scores`
- **Output fields**: discrepancy_score (0-100), discrepancies, consistent_areas, lobbying_priorities_vs_rhetoric, china_rhetoric_analysis, accountability_contradiction, key_finding

```bash
# Usage
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --fresh  # Full reprocess
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --dry-run  # Preview only
```

**`analyze_china_rhetoric.py`** - China competition rhetoric deep-dive
- Analyzes how companies use China competition arguments
- Filters positions that use `china_competition` as primary/secondary argument
- Writes to Iceberg: `china_rhetoric_analysis`
- **Output fields**: rhetoric_intensity (0-100), claim_categorization, rhetoric_patterns, policy_asks_supported, rhetoric_assessment, comparison_to_other_arguments, notable_quotes, key_finding

```bash
# Usage
./venv/bin/python include/scripts/agentic/analyze_china_rhetoric.py --fresh  # Full reprocess
./venv/bin/python include/scripts/agentic/analyze_china_rhetoric.py --dry-run  # Preview only
```

**`compare_positions.py`** - Cross-company position comparison
- Analyzes positions across all companies to find patterns
- Identifies industry consensus, outliers, and strategic positioning
- Writes to Iceberg: `position_comparisons` (1 row - comprehensive analysis)
- **Output fields**: unanimous_positions, contested_positions, outlier_positions, strategic_patterns, cross_company_themes, key_finding

```bash
# Usage
./venv/bin/python include/scripts/agentic/compare_positions.py --fresh  # Full reprocess
```

**`map_regulatory_targets.py`** - Bill-level coalition analysis (NO LLM)
- Rule-based analysis of positions by regulatory target
- Groups positions by target bill/regulation
- Identifies companies supporting vs opposing each target
- Writes to Iceberg: `bill_position_analysis`
- **Output fields**: target_name, supporters, opposers, is_contested, coalition_dynamics

```bash
# Usage
./venv/bin/python include/scripts/agentic/map_regulatory_targets.py --fresh  # Full reprocess
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

**`export_to_snowflake.py`** - Iceberg → Snowflake export
- Exports all 10 Iceberg tables to Snowflake RAW_* tables
- Full refresh strategy (truncate + reload)
- Uses Snowflake connector with pandas
- Total: ~26,567 rows across all tables

```bash
./venv/bin/python include/scripts/utils/export_to_snowflake.py
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
│   ├── config.py                # Company lists, LDA filters, name mappings
│   └── scripts/
│       ├── extraction/          # Data loading scripts
│       │   ├── extract_pdf_submissions.py
│       │   └── extract_lda_filings.py
│       ├── agentic/             # LLM-powered analysis (6 scripts)
│       │   ├── extract_positions.py
│       │   ├── assess_lobbying_impact.py
│       │   ├── detect_discrepancies.py
│       │   ├── analyze_china_rhetoric.py
│       │   ├── compare_positions.py
│       │   └── map_regulatory_targets.py
│       ├── exploration/         # API exploration / research
│       │   └── explore_lda_api.py
│       └── utils/               # Helper scripts
│           ├── check_progress.py
│           └── export_to_snowflake.py
├── dashboard/                   # Streamlit dashboard
│   ├── app.py                   # Main dashboard entry point
│   ├── data_loader.py           # Snowflake data loading
│   └── pages/                   # Dashboard pages
│       ├── executive_summary.py
│       ├── company_deep_dive.py
│       ├── cross_company.py
│       ├── bill_analysis.py
│       ├── position_explorer.py
│       └── methodology.py
├── dags/                        # Airflow DAGs (6 DAGs)
│   ├── ai_influence_pipeline.py # Main orchestration DAG
│   ├── extract_submissions_dag.py
│   ├── extract_lda_dag.py
│   ├── llm_extraction_dag.py
│   ├── llm_impact_assessment_dag.py
│   └── snowflake_sync_dag.py
├── dbt/                         # dbt project
│   └── ai_influence/
│       ├── models/
│       │   ├── staging/         # 10 staging views
│       │   └── marts/           # 6 mart tables
│       └── dbt_project.yml
├── queries/                     # SQL for Trino exploration
├── data/                        # Downloaded PDFs (gitignored)
├── .env                         # Config (AWS, Snowflake, Anthropic)
├── requirements.txt
├── Dockerfile                   # Astronomer config
└── packages.txt                 # Astronomer system packages
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
