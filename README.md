# AI Influence Tracker

**What AI Companies Say vs. What They Lobby For**

A document intelligence pipeline that analyzes 10,000+ government policy submissions, extracts structured positions using LLMs, and compares them to federal lobbying disclosures to surface discrepancies between public statements and lobbying activity.

---

## The Question

Do AI companies practice what they preach on safety and regulation?

OpenAI's CEO calls for AI regulation in congressional testimony. Then OpenAI lobbies against California's AI safety bill. This pipeline systematically tracks and quantifies these gaps across the entire AI industry.

---

## Key Findings

| Finding | Evidence |
|---------|----------|
| **Anthropic is most consistent** | Lowest discrepancy (25/100), lowest concern (45/100), minimal China rhetoric (15/100) |
| **Google/Amazon have biggest say-vs-do gap** | Both score 72/100 discrepancy - talk AI policy, lobby on antitrust/procurement |
| **OpenAI most aggressive on China framing** | 85/100 rhetoric intensity, uses China in 29% of positions |
| **Trade groups do the "dirty work"** | More aggressive on deregulation than their member companies |
| **Section 230 is the silent elephant** | 115 lobbying filings, ZERO public positions - everyone lobbies, no one speaks publicly |

---

## Data Scale

| Dataset | Count | Description |
|---------|-------|-------------|
| AI Action Plan submissions | 10,068 PDFs | Trump admin RFI responses (Feb 2025) |
| Priority companies processed | 30 | LLM extraction complete |
| Policy positions extracted | 878 | Structured with taxonomy |
| LDA lobbying filings | 970 | Senate disclosures (2023+) |
| LDA activities | 3,051 | Specific lobbying issues |
| Bills/regulations analyzed | 21 | Coalition pattern analysis |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTRACT LAYER (to Iceberg)                  │
├─────────────────────────────────────────────────────────────────────┤
│  - extract_pdf_submissions.py  → ai_submissions_metadata/text/chunks│
│  - extract_lda_filings.py      → lda_filings/activities/lobbyists   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM ANALYSIS LAYER (6 Agentic Scripts)           │
├─────────────────────────────────────────────────────────────────────┤
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
│                   LOAD LAYER (Iceberg → Snowflake)                  │
├─────────────────────────────────────────────────────────────────────┤
│  - export_to_snowflake.py → 10 RAW_* tables (~26,500 rows total)    │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TRANSFORM LAYER (dbt)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Staging: 10 views    │  Marts: 6 tables                            │
│  - stg_ai_positions   │  - dim_company (84 companies)               │
│  - stg_lda_filings    │  - fct_policy_positions (878 positions)     │
│  - stg_lda_activities │  - fct_lobbying_impact (23 scores)          │
│  - etc.               │  - fct_company_analysis (30 companies)      │
│                       │  - fct_bill_coalitions (21 bills)           │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VISUALIZATION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  Streamlit Dashboard (6 sections):                                  │
│  - Executive Summary, Company Deep Dive, Cross-Company Comparison   │
│  - Bill-Level Analysis, Position Explorer, Methodology              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### LLM-Powered Position Extraction

Claude reads policy documents and extracts structured JSON with enhanced taxonomy:

```json
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
```

### Three Analysis Scores

| Score | Range | What It Measures |
|-------|-------|------------------|
| **Concern Score** | 0-100 | Public interest implications (0=aligned, 100=concerning) |
| **Discrepancy Score** | 0-100 | Say-vs-do gap (0=consistent, 100=hypocrite) |
| **China Rhetoric Intensity** | 0-100 | Reliance on China framing (0=minimal, 100=heavy) |

### "Quiet Lobbying" Detection

Identifies companies that heavily lobby on legislation without taking public positions - revealing priorities they don't want publicly associated with their brand.

**Example:** Section 230 has 115 lobbying filings but ZERO public positions from any company.

---

## Tech Stack

| Component | Technology | Why This Choice |
|-----------|------------|-----------------|
| **Orchestration** | Airflow (Astronomer) | Industry standard for data pipelines; managed deployment via Astronomer simplifies ops |
| **Data Lake** | Apache Iceberg + AWS S3 | Schema evolution support crucial for iterating on LLM extraction schemas; ACID transactions for reliable incremental loads |
| **Warehouse** | Snowflake | Handles semi-structured JSON from LLM outputs natively; scales for future expansion to 10K+ documents |
| **Transformation** | dbt | Version-controlled SQL transformations; built-in testing framework for data quality; clear lineage |
| **LLM** | Claude API (Anthropic) | Best-in-class for structured extraction tasks; reliable JSON output; 200K context window handles long policy documents |
| **PDF Processing** | PyMuPDF | Fast, reliable text extraction; handles government PDF formatting quirks better than alternatives tested |
| **Dashboard** | Streamlit | Rapid prototyping; native Python; free cloud hosting; interactive without JavaScript |
| **Language** | Python | Ecosystem support for all components; team familiarity |

**LLM Cost Estimates (Claude Sonnet):**
| Script | API Calls | Est. Cost |
|--------|-----------|-----------|
| Position extraction (30 companies, 112 chunks) | 112 | ~$2.50 |
| Lobbying impact assessment (23 companies) | 23 | ~$1.00 |
| Discrepancy detection (23 companies) | 23 | ~$1.00 |
| China rhetoric analysis (14 companies) | 14 | ~$0.60 |
| Cross-company comparison | 1 | ~$0.15 |
| **Total for sample** | **173** | **~$5.25** |

Full 10K document processing would cost ~$150-200 at current rates.

---

## Project Structure

```
ai-influence-monitor/
├── CLAUDE.md                    # Project context and status
├── docs/
│   ├── DATA_DICTIONARY.md       # Tables, columns, sources
│   ├── ARCHITECTURE.md          # System design, prompts, APIs
│   └── INSIGHTS.md              # Findings and observations
├── include/
│   ├── config.py                # Company lists, LDA filters
│   └── scripts/
│       ├── extraction/          # PDF and LDA data loading
│       ├── agentic/             # 6 LLM-powered analysis scripts
│       └── utils/               # Helpers (progress, export)
├── dashboard/                   # Streamlit dashboard
│   ├── app.py
│   └── data_loader.py
├── dags/                        # 6 Airflow DAGs
├── dbt/ai_influence/            # dbt project (10 staging + 6 marts)
├── data/                        # Downloaded PDFs (gitignored)
└── .env                         # Config (AWS, Snowflake, Anthropic)
```

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/[you]/ai-influence-monitor
cd ai-influence-monitor
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add: AWS credentials, SNOWFLAKE_*, ANTHROPIC_API_KEY

# Download AI submissions (one-time, 600MB)
python include/scripts/extraction/extract_pdf_submissions.py

# Extract LDA lobbying data
python include/scripts/extraction/extract_lda_filings.py

# Run LLM position extraction
python include/scripts/agentic/extract_positions.py

# Run analysis scripts
python include/scripts/agentic/assess_lobbying_impact.py --fresh
python include/scripts/agentic/detect_discrepancies.py --fresh
python include/scripts/agentic/analyze_china_rhetoric.py --fresh

# Export to Snowflake and run dbt
python include/scripts/utils/export_to_snowflake.py
cd dbt/ai_influence && dbt run && dbt test

# Launch dashboard
streamlit run dashboard/app.py
```

---

## Data Sources

| Source | Type | Content |
|--------|------|---------|
| [AI Action Plan Submissions](https://www.nitrd.gov/coordination-areas/ai/90-fr-9088-responses/) | Bulk PDF | 10,068 policy submissions to Trump admin |
| [Senate LDA API](https://lda.senate.gov/api/v1/) | REST API | Lobbying disclosure filings |

**Data Licensing & Attribution:**
- **AI Action Plan RFI:** Public government records from [Federal Register 90 FR 9088](https://www.federalregister.gov/documents/2025/02/06/2025-02305/request-for-information-on-the-development-of-an-artificial-intelligence-action-plan) (Feb 2025). Responses collected by NITRD/OSTP.
- **Senate LDA:** Public lobbying disclosures per the Lobbying Disclosure Act of 1995. Data accessed via the [Senate Office of Public Records API](https://lda.senate.gov/api/).

**Sampling Approach:**
The full dataset contains 10,068 submissions. For this capstone, we prioritized **30 companies** representing AI labs (OpenAI, Anthropic, Google DeepMind), big tech (Microsoft, Amazon, Meta), and trade groups (CCIA, TechNet, US Chamber). This focused sample enables deep analysis while remaining within LLM API cost constraints. The pipeline is designed to scale to all 10K documents.

---

## Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| **Entity matching across datasets** | RFI submissions use "Anthropic-AI", LDA uses "ANTHROPIC, PBC". Built normalization layer with canonical name mappings in `config.py` |
| **LLM output consistency** | Claude sometimes returns varied JSON structures. Added Pydantic validation and retry logic with structured prompts |
| **Taxonomy iteration** | Initial policy_ask codes were too broad. Iterated through 3 versions, expanding from 12 to 30+ codes based on actual document content |
| **Duplicate detection** | Same company files multiple lobbying reports and through subsidiaries. Added ROW_NUMBER() deduplication in staging models |
| **"Quiet lobbying" definition** | Needed to match companies across bill mentions in LDA vs explicit positions in RFI. Built bill-level coalition analysis with fuzzy name matching |
| **Score clustering** | LLM naturally rounds scores to multiples of 25. Updated prompts to explicitly request granular scoring (23, 47, 68 vs 25, 50, 75) |

---

## The China Rhetoric Analysis

A key finding: Companies use "China competition" rhetoric strategically in policy arguments.

| Company | Rhetoric Intensity | Assessment |
|---------|-------------------|------------|
| OpenAI | 85/100 | Most aggressive - uses China in 29% of positions |
| Meta | 75/100 | Heavy reliance |
| Anthropic | 15/100 | Minimal use |
| Google | 2/100 | Barely uses it |

**The insight:** When companies invoke China to oppose specific regulations, we can flag whether their claims are substantive or rhetorical cover. High intensity + low substantiation = potential red flag.

---

## Documentation

| File | Purpose |
|------|---------|
| [CLAUDE.md](CLAUDE.md) | Project overview, current state, session log |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Tables, columns, data sources |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, DAG structure, prompts, scoring methodology |
| [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md) | Data quality checks (35 dbt tests + Python validation) |
| [docs/INSIGHTS.md](docs/INSIGHTS.md) | Findings and observations |

---

## Live Demo

**[AI Influence Tracker Dashboard](https://ai-influence-monitor-kouverk.streamlit.app/)**

---

## Status

**Complete** - DataExpert.io analytics engineering capstone project

- [x] PDF extraction pipeline
- [x] LLM position extraction (878 positions)
- [x] LDA lobbying data integration
- [x] 6 agentic analysis scripts
- [x] Snowflake integration
- [x] dbt models (10 staging + 6 marts)
- [x] Airflow DAGs (6 DAGs)
- [x] Streamlit dashboard
- [x] Deploy dashboard publicly

---

## Future Enhancements

| Enhancement | Value | Effort |
|-------------|-------|--------|
| **Process all 10,000+ submissions** | Complete industry coverage, not just priority companies | Medium - just compute/API cost |
| **Add FEC campaign finance data** | Correlate lobbying positions with political donations | Medium - new data source integration |
| **Temporal analysis** | Track how company positions shift over time as regulations evolve | Low - data already timestamped |
| **Trade group membership mapping** | Explicitly link companies to their trade group advocacy | Medium - requires external data |
| **Automated alerts** | Notify when new lobbying filings contradict stated positions | Medium - add monitoring DAG |
| **Fine-tuned extraction model** | Reduce Claude API costs by training smaller model on extracted positions | High - ML pipeline |

---

## License

MIT
