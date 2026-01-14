# Data Dictionary

Reference for all tables, columns, and data sources in this project.

**Related docs:**
- [CLAUDE.md](../CLAUDE.md) - Project overview, current state, next steps
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design, DAG structure, prompts
- [INSIGHTS.md](INSIGHTS.md) - Findings and observations

---

## Data Sources

### Source 1: AI Action Plan RFI Submissions (PRIMARY)
- **What:** Public responses to Trump administration's Request for Information on AI policy (90 FR 9088)
- **Format:** 600MB zip of PDFs/docs
- **Volume:** 10,068 documents
- **Where:** `data/90-fr-9088-combined-responses/`
- **URL:** https://files.nitrd.gov/90-fr-9088/90-fr-9088-combined-responses.zip
- **Key submitters:** OpenAI, Anthropic, Google, Meta, Microsoft, Amazon, trade groups, academics
- **LLM Task:** Extract policy positions, classify pro-safety vs pro-speed
- **Status:** ✅ Loaded (17 priority companies → 112 chunks in Iceberg)

### Source 2: Senate LDA Lobbying Database (PRIMARY)
- **What:** Every lobbying disclosure filing - who lobbied, for whom, on what issues, how much spent
- **Format:** REST API (JSON) - paginated, no auth required
- **URL:** https://lda.senate.gov/api/v1/
- **Docs:** https://lda.senate.gov/api/
- **LLM Task:** Match lobbying activity to stated positions, detect discrepancies
- **Status:** ✅ Loaded (110 filings for OpenAI, Anthropic, Nvidia)

**API Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `/filings/?client_name=X` | Search filings by client name (fuzzy match) |
| `/filings/{uuid}/` | Get specific filing details |
| `/registrants/` | Lobbying firms |
| `/clients/` | Companies being represented |
| `/lobbyists/` | Individual lobbyists |

**Key Fields per Filing:**
| Field | Description |
|-------|-------------|
| `filing_uuid` | Unique identifier |
| `filing_type_display` | Registration, Quarterly Report, Amendment |
| `filing_year` / `filing_period` | e.g., 2024, 4th Quarter |
| `expenses` | Dollar amount spent on lobbying |
| `registrant` | The lobbying firm (or self if in-house) |
| `client` | The company being represented |
| `lobbying_activities[]` | Issue codes + description + lobbyists list |

**Volume (from exploration Jan 2025):**
| Company | Filings | Expenses (pg1) | Years |
|---------|---------|----------------|-------|
| OpenAI | 40 | $1,970,000 | 2023-2024 |
| Anthropic | 38 | $720,000 | 2023-2025 |
| Nvidia | 44 | varies | 2015-2024 |

**Note:** API does fuzzy matching on `client_name`. "Google" returns 1,500+ filings including unrelated companies. For big tech, need to filter results by exact client name match.

### Source 3: OpenSecrets Bulk Data
- **What:** Aggregated lobbying spend by company, year, issue
- **Format:** CSV bulk download (API discontinued April 2025)
- **URL:** https://www.opensecrets.org/open-data/bulk-data
- **LLM Task:** Trend analysis, anomaly detection
- **Status:** Not yet implemented

### Source 4: Federal Register API (FUTURE)
- **What:** Official government notices, RFIs, proposed rules
- **Format:** REST API (JSON)
- **URL:** https://www.federalregister.gov/api/v1/
- **Docs:** https://www.federalregister.gov/developers/documentation/api/v1
- **Use case:** Monitor for new AI policy documents
- **Status:** Not yet implemented

### Source 5: Regulations.gov API (FUTURE)
- **What:** Public comments on regulatory dockets
- **Format:** REST API (JSON)
- **URL:** https://api.regulations.gov/v4/
- **Docs:** https://open.gsa.gov/api/regulationsgov/
- **Requires:** API key registration
- **Use case:** Track ongoing comment periods on AI regulations
- **Status:** Not yet implemented

### Source 6: Safety Researcher Statements (STRETCH)
- **What:** Public statements from AI safety researchers who left labs
- **Format:** Scrape from Twitter/X, Substack, news articles
- **Key people:** Jan Leike, Ilya Sutskever, Daniel Kokotajlo
- **LLM Task:** Sentiment analysis, extract specific safety concerns
- **Status:** Not yet implemented (stretch goal)

---

## Iceberg Tables (Staging Layer)

All tables in schema `{SCHEMA}` (configured via `.env`).

### `ai_submissions_metadata`
Document metadata - fast queries without scanning text.

| Column | Type | Description |
|--------|------|-------------|
| `document_id` | STRING (PK) | Filename without extension (e.g., `OpenAI-RFI-2025`) |
| `filename` | STRING | Original PDF filename |
| `submitter_name` | STRING | Parsed from filename (e.g., `OpenAI`) |
| `submitter_type` | STRING | `ai_lab`, `big_tech`, `trade_group`, `anonymous`, `other` |
| `page_count` | INT | Number of pages in PDF |
| `word_count` | INT | Total words extracted |
| `file_size_bytes` | LONG | File size in bytes |
| `processed_at` | TIMESTAMP | When extraction ran |

### `ai_submissions_text`
Full document text - join to metadata when you need content.

| Column | Type | Description |
|--------|------|-------------|
| `document_id` | STRING (PK) | FK to metadata |
| `full_text` | STRING | Complete extracted text from PDF |
| `processed_at` | TIMESTAMP | When extraction ran |

### `ai_submissions_chunks`
Chunked text for LLM processing - multiple rows per document.

| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | STRING (PK) | `{document_id}_{chunk_index}` |
| `document_id` | STRING | FK to metadata |
| `chunk_index` | INT | 0-indexed position in document |
| `total_chunks` | INT | Total chunks for this document |
| `chunk_text` | STRING | ~800 words of text |
| `word_count` | INT | Words in this chunk |
| `processed_at` | TIMESTAMP | When extraction ran |

**Chunking parameters:** 800 words per chunk, 100 word overlap

### `lda_filings`
Core lobbying filing data - one row per quarterly disclosure.

| Column | Type | Description |
|--------|------|-------------|
| `filing_uuid` | STRING (PK) | LDA filing unique identifier |
| `filing_type` | STRING | Filing type code (RR, Q1, Q2, etc.) |
| `filing_type_display` | STRING | Human-readable type (Registration, 1st Quarter, etc.) |
| `filing_year` | INT | Year of filing |
| `filing_period` | STRING | Quarter code (first_quarter, etc.) |
| `filing_period_display` | STRING | Human-readable period |
| `expenses` | DOUBLE | Lobbying spend for this filing ($) |
| `dt_posted` | STRING | When filing was posted |
| `termination_date` | STRING | If lobbying relationship ended |
| `registrant_id` | LONG | FK to lobbying firm |
| `registrant_name` | STRING | Lobbying firm name |
| `client_id` | LONG | FK to client company |
| `client_name` | STRING | Company being represented |
| `client_description` | STRING | Company description |
| `client_state` | STRING | Company state |
| `processed_at` | TIMESTAMP | When extraction ran |

### `lda_activities`
Lobbying activities per filing - one row per issue code lobbied on.

| Column | Type | Description |
|--------|------|-------------|
| `activity_id` | STRING (PK) | `{filing_uuid}_{index}` |
| `filing_uuid` | STRING | FK to lda_filings |
| `issue_code` | STRING | LDA issue code (CPI, CPT, etc.) |
| `issue_code_display` | STRING | Human-readable issue (Computer Industry, etc.) |
| `description` | STRING | Description of lobbying activity |
| `foreign_entity_issues` | STRING | Foreign entity involvement |
| `processed_at` | TIMESTAMP | When extraction ran |

### `lda_lobbyists`
Individual lobbyists per activity - one row per person.

| Column | Type | Description |
|--------|------|-------------|
| `lobbyist_record_id` | STRING (PK) | `{activity_id}_{index}` |
| `activity_id` | STRING | FK to lda_activities |
| `filing_uuid` | STRING | FK to lda_filings |
| `lobbyist_id` | LONG | LDA lobbyist ID |
| `first_name` | STRING | Lobbyist first name |
| `last_name` | STRING | Lobbyist last name |
| `covered_position` | STRING | Former government positions held |
| `is_new` | BOOLEAN | New to this filing |
| `processed_at` | TIMESTAMP | When extraction ran |

**Current data (Jan 2025):** 110 filings, 236 activities, 624 lobbyists (OpenAI, Anthropic, Nvidia)

### `ai_positions`
LLM-extracted policy positions - multiple rows per chunk.

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | STRING (PK) | `{chunk_id}_{position_index}` |
| `chunk_id` | STRING | FK to ai_submissions_chunks |
| `document_id` | STRING | FK to ai_submissions_metadata |
| `submitter_name` | STRING | Company/org name |
| `submitter_type` | STRING | `ai_lab`, `big_tech`, `trade_group`, etc. |
| `topic` | STRING | Policy topic category (see Topic Categories below) |
| `stance` | STRING | `strong_support`, `support`, `neutral`, `oppose`, `strong_oppose` |
| `supporting_quote` | STRING | Direct quote from document (≤50 words) |
| `confidence` | DOUBLE | LLM confidence score (0.0-1.0) |
| `model` | STRING | Model used for extraction (e.g., `claude-sonnet-4-20250514`) |
| `processed_at` | TIMESTAMP | When extraction ran |

**Extraction script:** `include/scripts/agentic/extract_positions.py`
**Status:** ✅ Table created, extraction in progress

---

## Snowflake Tables (Analytics Layer)

*Not yet implemented - will be created by dbt*

### `fct_policy_positions`
LLM-extracted positions from documents.

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | STRING | `{document_id}_{position_index}` |
| `company_id` | INT | FK to dim_company |
| `document_id` | STRING | Source document |
| `topic` | STRING | `ai_safety`, `state_regulation`, `federal_regulation`, etc. |
| `stance` | STRING | `strong_support`, `support`, `neutral`, `oppose`, `strong_oppose` |
| `supporting_quote` | STRING | Direct quote from document |
| `confidence_score` | FLOAT | LLM confidence (0-1) |
| `extracted_at` | TIMESTAMP | When LLM extraction ran |

### `fct_lobbying_activity`
Lobbying filings from Senate LDA.

| Column | Type | Description |
|--------|------|-------------|
| `filing_id` | STRING | LDA filing UUID |
| `company_id` | INT | FK to dim_company |
| `quarter_start` | DATE | Filing period start |
| `quarter_end` | DATE | Filing period end |
| `amount` | DECIMAL | Lobbying spend |
| `issues` | ARRAY | Issue codes lobbied on |
| `bills` | ARRAY | Specific bills mentioned |

### `fct_discrepancy_scores`
Computed scores comparing stated positions to lobbying activity.

| Column | Type | Description |
|--------|------|-------------|
| `company_id` | INT | FK to dim_company |
| `topic` | STRING | Policy topic |
| `public_stance` | STRING | Aggregated from submissions |
| `lobbying_stance` | STRING | Inferred from activity |
| `discrepancy_score` | INT | 0 (consistent) to 100 (hypocrite) |
| `evidence_summary` | STRING | LLM-generated explanation |

### `dim_company`
Company dimension with alias resolution.

| Column | Type | Description |
|--------|------|-------------|
| `company_id` | INT | Surrogate key |
| `company_name` | STRING | Canonical name |
| `aliases` | ARRAY | All known variations |
| `company_type` | STRING | `ai_lab`, `big_tech`, `trade_group`, etc. |

---

## Submitter Type Classification

How `submitter_type` is assigned in extraction script:

| Type | Examples | Detection |
|------|----------|-----------|
| `ai_lab` | OpenAI, Anthropic, Google, Meta, Mistral, Cohere, xAI | Keyword match in filename |
| `big_tech` | Microsoft, Amazon, Apple, Nvidia, IBM, Palantir, Adobe | Keyword match in filename |
| `trade_group` | CCIA, TechNet, BSA, ITI, Chamber of Commerce | Keyword match in filename |
| `anonymous` | AI-RFI-2025-0829, AI-RFI-2025-1234 | Filename starts with `AI-RFI-2025-` |
| `other` | Everything else | Default |

---

## Topic Categories (for LLM extraction)

| Topic Code | Description |
|------------|-------------|
| `ai_safety` | AI risks, alignment, testing requirements |
| `state_regulation` | Position on state-level AI laws (e.g., CA SB 1047) |
| `federal_regulation` | Federal AI oversight/agencies |
| `preemption` | Federal law preempting state laws |
| `copyright` | Training data, fair use, IP |
| `open_source` | Open vs closed model development |
| `china_competition` | National security, competitiveness framing |
| `export_controls` | Chip restrictions, model weight controls |
| `liability` | Responsibility when AI causes harm |
| `workforce` | Job displacement, retraining |
| `research_funding` | Government R&D investment |
| `energy_infrastructure` | Data centers, power grid |
| `other` | Doesn't fit above |
