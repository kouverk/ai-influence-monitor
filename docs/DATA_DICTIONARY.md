# Data Dictionary

Reference for all tables, columns, and data sources in this project.

**Related docs:**
- [CLAUDE.md](../CLAUDE.md) - Project overview, current state, next steps
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design, DAG structure, prompts
- [INSIGHTS.md](INSIGHTS.md) - Findings and observations

---

## Data Sources

### Source 1: AI Action Plan RFI Submissions (PRIMARY)
- **What:** Public responses to Trump administration's Request for Information on AI policy
- **Citation:** 90 FR 9088 (Volume 90, Federal Register, page 9088)
- **Format:** 600MB zip of PDFs/docs
- **Volume:** 10,068 documents
- **Where:** `data/90-fr-9088-combined-responses/`
- **URL:** https://files.nitrd.gov/90-fr-9088/90-fr-9088-combined-responses.zip
- **Key submitters:** OpenAI, Anthropic, Google, Meta, Microsoft, Amazon, trade groups, academics
- **LLM Task:** Extract policy positions, classify pro-safety vs pro-speed
- **Status:** ✅ Loaded (30 priority companies → 10,068 documents in Iceberg)

### Source 2: Senate LDA Lobbying Database (PRIMARY)
- **What:** Every lobbying disclosure filing - who lobbied, for whom, on what issues, how much spent
- **Format:** REST API (JSON) - paginated, no auth required
- **URL:** https://lda.senate.gov/api/v1/
- **Docs:** https://lda.senate.gov/api/
- **LLM Task:** Match lobbying activity to stated positions, detect discrepancies
- **Status:** ✅ Loaded (970 filings, 3,051 activities, 11,518 lobbyists for priority companies)

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

### Source 6: FARA Foreign Agents Database (FUTURE - CHINA RHETORIC)
- **What:** DOJ database of foreign lobbying activity in the US
- **Why:** Check if China actually lobbies on AI policy (vs companies just claiming "China threat")
- **Format:** REST API (JSON) + bulk CSV download
- **URL:** https://efile.fara.gov/
- **API Docs:** https://efile.fara.gov/api/
- **Bulk Data:** https://efile.fara.gov/bulk-data
- **Key fields:** Foreign principal, registrant, activities, expenditures
- **Use case:** Ground-truth data point for China rhetoric analysis
- **Limitation:** Shows foreign lobbying in US, not China's domestic AI activity
- **Status:** Not yet implemented

### Source 7: Georgetown CSET China AI Data (FUTURE - CHINA RHETORIC)
- **What:** Academic datasets on China's AI ecosystem from Georgetown's Center for Security and Emerging Technology
- **Why:** Provides verifiable data on China AI capabilities to compare against company claims
- **Format:** CSV/JSON datasets on GitHub
- **URL:** https://github.com/georgetown-cset
- **Key datasets:**
  - Chinese AI company profiles
  - AI talent flows (US↔China)
  - Patent and publication analysis
  - Government AI initiatives
- **Use case:** Fact-check specific verifiable claims in submissions
- **Limitation:** Academic research data, not real-time
- **Status:** Not yet implemented

**Note on China data sources:** Our primary analysis focuses on *how companies use China rhetoric* rather than proving/disproving China's capabilities. These sources provide optional ground-truth data for fact-checking specific verifiable claims. See [INSIGHTS.md](INSIGHTS.md) for the analysis approach.

### Source 8: Safety Researcher Statements (STRETCH)
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

**Current data (Feb 2026):** 970 filings, 3,051 activities, 11,518 lobbyists (all priority companies)

### `ai_positions`
LLM-extracted **policy asks** - specific things companies want the government to do (or not do).

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | STRING (PK) | `{chunk_id}_{position_index}` |
| `chunk_id` | STRING | FK to ai_submissions_chunks |
| `document_id` | STRING | FK to ai_submissions_metadata |
| `submitter_name` | STRING | Company/org name |
| `submitter_type` | STRING | `ai_lab`, `big_tech`, `trade_group`, etc. |
| `policy_ask` | STRING | Specific policy action requested (see Policy Ask Taxonomy below) |
| `ask_category` | STRING | High-level grouping: `regulatory_structure`, `accountability`, `intellectual_property`, `national_security`, `resources`, `other` |
| `stance` | STRING | `support`, `oppose`, `neutral` |
| `target` | STRING | Specific regulation/bill being referenced (e.g., "California SB 1047", "EU AI Act"), or null |
| `primary_argument` | STRING | Main argument for position (see Argument Types below) |
| `secondary_argument` | STRING | Optional second argument, or null |
| `supporting_quote` | STRING | Direct quote from document (≤50 words) |
| `confidence` | DOUBLE | LLM confidence score (0.0-1.0) |
| `model` | STRING | Model used for extraction (e.g., `claude-sonnet-4-20250514`) |
| `processed_at` | TIMESTAMP | When extraction ran |

**Extraction script:** `include/scripts/agentic/extract_positions.py`
**Status:** ✅ Complete - 878 positions extracted (30 priority companies)

**Extraction stats (Feb 2026):**
- Total positions: 878
- Model: claude-sonnet-4-20250514

**Top policy asks:**
| Policy Ask | Count |
|------------|-------|
| government_ai_adoption | 70 |
| research_funding | 43 |
| international_harmonization | 40 |
| federal_preemption | 31 |
| existing_agency_authority | 30 |
| workforce_training | 30 |
| training_data_fair_use | 27 |
| self_regulation | 26 |

**Top arguments used:**
| Argument | Count |
|----------|-------|
| competitiveness | 223 |
| national_security | 87 |
| innovation_harm | 87 |
| china_competition | 55 |
| patchwork_problem | 39 |

### `lobbying_impact_scores`
LLM-assessed public interest implications of corporate lobbying - THE KEY ANALYSIS TABLE.

| Column | Type | Description |
|--------|------|-------------|
| `score_id` | STRING (PK) | `{company_name}_{timestamp}` |
| `company_name` | STRING | Canonical company name |
| `company_type` | STRING | `ai_lab`, `big_tech`, `trade_group` |
| `concern_score` | INT | 0-100 (0=public interest aligned, 100=critical concern) |
| `lobbying_agenda_summary` | STRING | 2-3 sentence summary of what they're lobbying for |
| `top_concerning_policy_asks` | STRING (JSON) | Most concerning policy asks with evidence |
| `public_interest_concerns` | STRING (JSON) | Array of specific concerns with evidence, who_harmed, severity |
| `regulatory_capture_signals` | STRING (JSON) | Signs they're shaping regulations for self-benefit |
| `china_rhetoric_assessment` | STRING | Assessment of China competition framing |
| `accountability_stance` | STRING | Assessment of position on liability/oversight |
| `positive_aspects` | STRING (JSON) | Any lobbying genuinely serving public interest |
| `key_flags` | STRING (JSON) | Red flags for journalists/regulators/public |
| `positions_count` | INT | Number of policy positions analyzed |
| `lobbying_filings_count` | INT | Number of LDA filings analyzed |
| `model` | STRING | Model used (e.g., `claude-sonnet-4-20250514`) |
| `processed_at` | TIMESTAMP | When assessment ran |

**Assessment script:** `include/scripts/agentic/assess_lobbying_impact.py`
**Status:** ✅ Complete - 23 companies assessed

**Results (Feb 2026):**
| Company | Type | Concern Score |
|---------|------|---------------|
| Google | ai_lab | 75/100 |
| OpenAI | ai_lab | 72/100 |
| Amazon | big_tech | 72/100 |
| Palantir | big_tech | 72/100 |
| TechNet | trade_group | 72/100 |
| CCIA | trade_group | 72/100 |
| US-Chamber | trade_group | 72/100 |
| IBM | big_tech | 68/100 |
| Adobe | big_tech | 68/100 |
| Anthropic | ai_lab | 45/100 |

**Key findings:** Most companies score 68-75/100 (significant concerns). Common patterns:
- Federal preemption to block state protections
- Liability shields to avoid accountability
- Self-regulation instead of external oversight
- China competition rhetoric to justify reduced oversight

### `discrepancy_scores`
LLM-assessed say-vs-do discrepancy scores comparing public positions to lobbying activity.

| Column | Type | Description |
|--------|------|-------------|
| `score_id` | STRING (PK) | `{company_name}_{timestamp}` |
| `company_name` | STRING | Canonical company name |
| `company_type` | STRING | `ai_lab`, `big_tech`, `trade_group` |
| `discrepancy_score` | INT | 0-100 (0=consistent, 100=hypocrite) |
| `discrepancies` | STRING (JSON) | Array of identified inconsistencies |
| `consistent_areas` | STRING (JSON) | Areas where positions match lobbying |
| `lobbying_priorities_vs_rhetoric` | STRING | Comparison of stated vs actual priorities |
| `china_rhetoric_analysis` | STRING | Analysis of China framing in context |
| `accountability_contradiction` | STRING | Gaps in accountability positions |
| `key_finding` | STRING | Primary takeaway |
| `positions_count` | INT | Number of policy positions analyzed |
| `lobbying_filings_count` | INT | Number of LDA filings analyzed |
| `model` | STRING | Model used |
| `processed_at` | TIMESTAMP | When assessment ran |

**Assessment script:** `include/scripts/agentic/detect_discrepancies.py`
**Status:** ✅ Complete - 23 companies assessed

**Results (Feb 2026):**
| Company | Type | Discrepancy Score |
|---------|------|-------------------|
| Anthropic | ai_lab | 25/100 (most consistent) |
| OpenAI | ai_lab | 35/100 |
| IBM | big_tech | 35/100 |
| Google | ai_lab | 72/100 (biggest gap) |
| Amazon | big_tech | 72/100 |

### `china_rhetoric_analysis`
LLM deep-dive on China competition rhetoric intensity and patterns.

| Column | Type | Description |
|--------|------|-------------|
| `analysis_id` | STRING (PK) | `{company_name}_{timestamp}` |
| `company_name` | STRING | Canonical company name |
| `company_type` | STRING | `ai_lab`, `big_tech`, `trade_group` |
| `rhetoric_intensity` | INT | 0-100 (0=minimal, 100=heavy reliance on China framing) |
| `claim_categorization` | STRING (JSON) | Types of China claims made |
| `rhetoric_patterns` | STRING (JSON) | Patterns in how China is invoked |
| `policy_asks_supported` | STRING (JSON) | Which policy asks use China rhetoric |
| `rhetoric_assessment` | STRING | Overall assessment of rhetoric |
| `comparison_to_other_arguments` | STRING | How China compares to other arguments used |
| `notable_quotes` | STRING (JSON) | Key quotes using China framing |
| `key_finding` | STRING | Primary takeaway |
| `china_positions_count` | INT | Positions using China argument |
| `total_positions_count` | INT | Total positions analyzed |
| `model` | STRING | Model used |
| `processed_at` | TIMESTAMP | When assessment ran |

**Assessment script:** `include/scripts/agentic/analyze_china_rhetoric.py`
**Status:** ✅ Complete - 14 companies with China rhetoric analyzed

**Results (Feb 2026):**
| Company | Rhetoric Intensity |
|---------|-------------------|
| OpenAI | 85/100 (most aggressive) |
| Meta | 75/100 |
| Palantir | 25/100 |
| Anthropic | 15/100 |
| Google | 2/100 (barely uses it) |

### `position_comparisons`
LLM cross-company position comparison analysis (one row per analysis run).

| Column | Type | Description |
|--------|------|-------------|
| `comparison_id` | STRING (PK) | Unique identifier |
| `companies_analyzed` | STRING (JSON) | Array of company names |
| `company_count` | INT | Number of companies |
| `position_count` | INT | Total positions analyzed |
| `consensus_positions` | STRING (JSON) | Positions all/most companies agree on |
| `contested_positions` | STRING (JSON) | Positions with significant disagreement |
| `company_type_patterns` | STRING (JSON) | Patterns by company type |
| `outlier_positions` | STRING (JSON) | Unusual positions |
| `coalition_analysis` | STRING (JSON) | Identified coalitions/alliances |
| `argument_patterns` | STRING (JSON) | Common argument patterns |
| `key_findings` | STRING (JSON) | Top insights |
| `model` | STRING | Model used |
| `processed_at` | TIMESTAMP | When assessment ran |

**Assessment script:** `include/scripts/agentic/compare_positions.py`
**Status:** ✅ Complete - 30 companies, 878 positions analyzed

### `bill_position_analysis`
Bill-level coalition analysis - compares public positions on specific legislation to lobbying activity.

| Column | Type | Description |
|--------|------|-------------|
| `bill_id` | STRING (PK) | Normalized bill identifier (e.g., `chips_act`, `section_230`) |
| `bill_name` | STRING | Human-readable name (e.g., "CHIPS and Science Act") |
| `companies_supporting` | STRING (JSON) | Array of companies with public support positions |
| `companies_opposing` | STRING (JSON) | Array of companies with public opposition positions |
| `position_count` | INT | Total public positions on this bill |
| `lobbying_filing_count` | INT | LDA filings mentioning this bill |
| `lobbying_activity_count` | INT | LDA activities mentioning this bill |
| `lobbying_companies` | STRING (JSON) | Companies lobbying on this bill |
| `lobbying_spend_estimate` | DOUBLE | Estimated $ lobbying spend on this bill |
| `quiet_lobbying` | STRING (JSON) | Companies lobbying WITHOUT public position (see Glossary) |
| `all_talk` | STRING (JSON) | Companies with positions but NO lobbying activity |
| `processed_at` | TIMESTAMP | When analysis ran |

**Analysis script:** `include/scripts/agentic/map_regulatory_targets.py`
**Status:** ✅ Complete - 21 bills analyzed

**Key findings (Feb 2026):**
| Bill | Lobbying Filings | Public Positions | Pattern |
|------|------------------|------------------|---------|
| Section 230 | 115 | 0 | Pure quiet lobbying |
| CHIPS Act | 78 | 2 | Mostly quiet |
| CREATE AI Act | 29 | 1 | Quiet lobbying |
| EU AI Act | 4 | 4 | Only contested bill |

---

## Snowflake Tables (Analytics Layer)

All dbt models in database `DATAEXPERT_STUDENT`.

### Staging Views (10 views in schema `KOUVERK_AI_INFLUENCE_STAGING`)

| View | Source | Rows | Description |
|------|--------|------|-------------|
| `STG_AI_POSITIONS` | RAW_AI_POSITIONS | 878 | Staged policy positions |
| `STG_AI_SUBMISSIONS` | RAW_AI_SUBMISSIONS_METADATA | 10,068 | Staged submission metadata |
| `STG_LDA_FILINGS` | RAW_LDA_FILINGS | 970 | Staged LDA filings |
| `STG_LDA_ACTIVITIES` | RAW_LDA_ACTIVITIES | 3,051 | Staged LDA activities |
| `STG_LDA_LOBBYISTS` | RAW_LDA_LOBBYISTS | 11,518 | Staged lobbyists |
| `STG_LOBBYING_IMPACT_SCORES` | RAW_LOBBYING_IMPACT_SCORES | 23 | Staged concern scores |
| `STG_DISCREPANCY_SCORES` | RAW_DISCREPANCY_SCORES | 23 | Staged discrepancy scores |
| `STG_CHINA_RHETORIC` | RAW_CHINA_RHETORIC_ANALYSIS | 14 | Staged China rhetoric |
| `STG_POSITION_COMPARISONS` | RAW_POSITION_COMPARISONS | 1 | Staged cross-company analysis |
| `STG_BILL_POSITION_ANALYSIS` | RAW_BILL_POSITION_ANALYSIS | 21 | Staged bill coalitions |

### Mart Tables (6 tables in schema `KOUVERK_AI_INFLUENCE_MARTS`)

#### `DIM_COMPANY`
Company dimension combining all sources.

| Column | Type | Description |
|--------|------|-------------|
| `company_id` | INT | Surrogate key |
| `company_name` | STRING | Canonical name |
| `company_type` | STRING | `ai_lab`, `big_tech`, `trade_group`, `unknown` |
| `source_count` | INT | Number of sources this company appears in |
| `has_multiple_sources` | BOOLEAN | Appears in more than one source |

**Row count:** 84 companies

#### `FCT_POLICY_POSITIONS`
Policy positions with company dimension join.

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | STRING | Unique position identifier |
| `company_id` | INT | FK to dim_company |
| `company_name` | STRING | Company name |
| `policy_ask` | STRING | Specific policy action requested |
| `ask_category` | STRING | High-level category |
| `stance` | STRING | `support`, `oppose`, `neutral` |
| `primary_argument` | STRING | Main argument |
| `supporting_quote` | STRING | Direct quote |
| `confidence` | FLOAT | LLM confidence (0-1) |

**Row count:** 878 positions

#### `FCT_LOBBYING_QUARTERLY`
Quarterly lobbying filings with company dimension join.

| Column | Type | Description |
|--------|------|-------------|
| `filing_uuid` | STRING | LDA filing UUID |
| `company_id` | INT | FK to dim_company |
| `client_name` | STRING | Company name |
| `filing_year` | INT | Year |
| `filing_period` | STRING | Quarter |
| `expenses` | DECIMAL | Lobbying spend |

**Row count:** 970 filings

#### `FCT_LOBBYING_IMPACT`
LLM-assessed concern scores with company dimension join.

| Column | Type | Description |
|--------|------|-------------|
| `score_id` | STRING | Unique identifier |
| `company_id` | INT | FK to dim_company |
| `company_name` | STRING | Company name |
| `concern_score` | INT | 0-100 concern level |
| `concern_level` | STRING | Bucketed level (aligned/minor/moderate/significant/critical) |
| `lobbying_agenda_summary` | STRING | Summary |
| `top_concerning_policy_asks` | VARIANT (JSON) | JSON array of concerns |
| `public_interest_concerns` | VARIANT (JSON) | JSON array |
| `regulatory_capture_signals` | VARIANT (JSON) | JSON array |

**Row count:** 23 companies

#### `FCT_COMPANY_ANALYSIS`
Comprehensive company analysis combining ALL LLM scores.

| Column | Type | Description |
|--------|------|-------------|
| `company_id` | INT | FK to dim_company |
| `company_name` | STRING | Company name |
| `company_type` | STRING | Company type |
| `position_count` | INT | Number of policy positions |
| `unique_policy_asks` | INT | Distinct policy asks |
| `unique_arguments` | INT | Distinct arguments used |
| `concern_score` | INT | Lobbying impact score (0-100) |
| `discrepancy_score` | INT | Say-vs-do score (0-100) |
| `china_rhetoric_intensity` | INT | China rhetoric score (0-100) |
| `last_assessed_at` | TIMESTAMP | Most recent assessment |

**Row count:** 30 companies with positions

#### `FCT_BILL_COALITIONS`
Bill-level coalition analysis with computed flags.

| Column | Type | Description |
|--------|------|-------------|
| `bill_id` | STRING | Canonical bill ID |
| `bill_name` | STRING | Human-readable name |
| `public_positions` | INT | Count of public positions |
| `supporting_count` | INT | Companies supporting |
| `opposing_count` | INT | Companies opposing |
| `lobbying_filing_count` | INT | LDA filings on this bill |
| `quiet_lobbying_count` | INT | Companies lobbying without public position |
| `is_contested` | BOOLEAN | Has both supporters and opponents |
| `is_pure_quiet_lobbying` | BOOLEAN | Lobbying but no public positions |
| `quiet_lobbying` | VARIANT (JSON) | Array of quiet lobbyist names |

**Row count:** 21 bills

---

## Submitter Type Classification

### Entity Type Definitions

| Type | Definition |
|------|------------|
| `ai_lab` | **Pure-play AI companies** whose core business is developing AI models and systems. These companies have the most direct stake in AI regulation since it affects their primary product. |
| `big_tech` | **Diversified technology giants** where AI is one of many business lines. These companies may have conflicting internal interests (e.g., Amazon's cloud AI vs. content businesses on copyright). |
| `trade_group` | **Industry associations** that represent multiple member companies collectively. Trade groups are not companies themselves—they advocate on behalf of their members' shared interests. |
| `anonymous` | Individual submissions without identifiable company affiliation. |
| `other` | Submissions from entities that don't fit the above categories (universities, NGOs, individuals, etc.). |

### Why This Distinction Matters

**Trade groups deserve special attention** in lobbying analysis because:

1. **Collective voice**: Organizations like the U.S. Chamber of Commerce, TechNet, and CCIA represent hundreds of member companies speaking with one voice
2. **Deniable advocacy**: Trade groups often advocate more aggressive positions than individual member companies would state publicly, allowing members to benefit without direct attribution
3. **Lowest common denominator**: Trade group positions typically represent what all members can agree on, which often skews toward deregulation

**Example**: A tech company might publicly support "responsible AI regulation" while their trade group lobbies against specific accountability measures. This project's discrepancy analysis attempts to surface these gaps.

### Detection Rules

How `submitter_type` is assigned in the extraction script:

| Type | Examples | Detection |
|------|----------|-----------|
| `ai_lab` | OpenAI, Anthropic, Google, Meta, Mistral, Cohere, xAI | Keyword match in filename |
| `big_tech` | Microsoft, Amazon, Apple, Nvidia, IBM, Palantir, Adobe | Keyword match in filename |
| `trade_group` | CCIA, TechNet, BSA, ITI, Chamber of Commerce | Keyword match in filename |
| `anonymous` | AI-RFI-2025-0829, AI-RFI-2025-1234 | Filename starts with `AI-RFI-2025-` |
| `other` | Everything else | Default |

---

## Policy Ask Taxonomy (for LLM extraction)

### Ask Categories

| Category | Description |
|----------|-------------|
| `regulatory_structure` | How AI should be governed (federal vs state, new vs existing agencies) |
| `accountability` | Liability, audits, transparency, incident reporting |
| `intellectual_property` | Training data, copyright, open source |
| `national_security` | Export controls, China competition, defense AI |
| `resources` | Funding, infrastructure, immigration, workforce |
| `other` | Doesn't fit above |

### Policy Asks by Category

**REGULATORY STRUCTURE:**
| Policy Ask | Description |
|------------|-------------|
| `federal_preemption` | Federal law should override state laws |
| `state_autonomy` | States should be able to regulate |
| `new_federal_agency` | Create new AI oversight body |
| `existing_agency_authority` | Use existing agencies (FTC/FDA/etc) |
| `self_regulation` | Industry-led standards without mandates |
| `international_harmonization` | Align with EU/international standards |

**ACCOUNTABILITY:**
| Policy Ask | Description |
|------------|-------------|
| `liability_shield` | Protect developers from lawsuits |
| `liability_framework` | Define who's responsible for AI harms |
| `mandatory_audits` | Require third-party testing |
| `voluntary_commitments` | Support industry self-commitments |
| `transparency_requirements` | Mandate disclosures |
| `incident_reporting` | Require breach/incident reporting |

**INTELLECTUAL PROPERTY:**
| Policy Ask | Description |
|------------|-------------|
| `training_data_fair_use` | Allow copyrighted data for training |
| `creator_compensation` | Pay content creators |
| `model_weight_protection` | Treat weights as trade secrets |
| `open_source_mandate` | Require open models |
| `open_source_protection` | Don't restrict open source |

**NATIONAL SECURITY:**
| Policy Ask | Description |
|------------|-------------|
| `export_controls_strict` | More chip/model restrictions |
| `export_controls_loose` | Fewer restrictions |
| `china_competition_frame` | Frame policy as beating China |
| `government_ai_adoption` | More federal AI use |
| `defense_ai_investment` | Military AI funding |

**RESOURCES:**
| Policy Ask | Description |
|------------|-------------|
| `research_funding` | Government R&D money |
| `compute_infrastructure` | Data center support |
| `energy_infrastructure` | Power grid for AI |
| `immigration_reform` | AI talent visas |
| `workforce_training` | Retraining programs |

---

## Argument Types (HOW companies justify their asks)

**ECONOMIC:**
| Argument | Description |
|----------|-------------|
| `innovation_harm` | "Kills startups/innovation" |
| `competitiveness` | "Must stay ahead economically" |
| `job_creation` | "Creates jobs" |
| `cost_burden` | "Too expensive to comply" |

**SECURITY:**
| Argument | Description |
|----------|-------------|
| `china_competition` | "China will win if we don't" |
| `national_security` | "Defense/security requires this" |
| `adversary_benefit` | "Helps bad actors" |

**PRACTICAL:**
| Argument | Description |
|----------|-------------|
| `technical_infeasibility` | "Can't be done technically" |
| `patchwork_problem` | "State-by-state is chaos" |
| `duplicative` | "Already regulated elsewhere" |
| `premature` | "Too early to regulate" |

**RIGHTS/VALUES:**
| Argument | Description |
|----------|-------------|
| `free_speech` | First Amendment concerns |
| `consumer_protection` | Protect users |
| `creator_rights` | Protect artists/creators |
| `civil_liberties` | Privacy, bias, fairness |
| `safety_concern` | AI safety/alignment risks |

---

## Glossary

Key terms and concepts used in this project's analysis.

### Quiet Lobbying

**Definition:** When a company files lobbying disclosures (LDA filings) on specific legislation but takes NO public position on that legislation.

**Why it matters:** Companies are spending money to influence policy on issues they don't want publicly associated with their brand. This reveals hidden priorities and potential concerns about public perception.

**Example:** Section 230 has 115 lobbying filings from Meta, Microsoft, CCIA, and TechNet, but ZERO of these companies took a public position on Section 230 in their AI Action Plan submissions. They clearly care about it (they're paying lobbyists), but they don't want to publicly state their position.

**How we detect it:** Compare `lobbying_companies` (from LDA filings) to `companies_supporting + companies_opposing` (from public positions). Companies appearing in lobbying but not in positions are "quiet lobbying."

**Stored in:** `bill_position_analysis.quiet_lobbying` (JSON array)

### All Talk

**Definition:** When a company takes a public position on legislation but files NO lobbying disclosures on that specific bill.

**Why it matters:** This may indicate:
- Virtue signaling (saying the "right" thing without backing it up financially)
- Strategic positioning on politically safe topics
- Genuine positions they just don't prioritize in their lobbying budget

**Example:** Multiple companies publicly position on CA SB 1047 and state AI legislation, but have no corresponding LDA filings mentioning those bills.

**How we detect it:** Compare `companies_supporting + companies_opposing` (from public positions) to `lobbying_companies` (from LDA filings). Companies appearing in positions but not in lobbying are "all talk."

**Stored in:** `bill_position_analysis.all_talk` (JSON array)

### Discrepancy Score

**Definition:** A 0-100 score measuring how much a company's public statements differ from their lobbying activity.
- **0** = Perfectly consistent (says what they lobby for)
- **100** = Maximum hypocrisy (says one thing, lobbies for opposite)

**Example:** Anthropic scores 25/100 (most consistent). Google and Amazon score 72/100 (biggest gap between public AI policy rhetoric and actual lobbying priorities which focus on antitrust and procurement).

**Stored in:** `discrepancy_scores.discrepancy_score`

### Concern Score

**Definition:** A 0-100 score measuring how much a company's lobbying agenda raises public interest concerns.
- **0** = Lobbying agenda aligned with public interest
- **100** = Lobbying agenda raises critical concerns

**Factors:** Federal preemption of state protections, liability shields, self-regulation over external oversight, regulatory capture signals.

**Example:** Trade groups (TechNet, CCIA, US Chamber) cluster at 72/100. Anthropic scores 45/100 (lower concern).

**Stored in:** `lobbying_impact_scores.concern_score`

### China Rhetoric Intensity

**Definition:** A 0-100 score measuring how heavily a company relies on China competition framing in their policy arguments.
- **0** = Minimal or no China framing
- **100** = Heavy reliance on China rhetoric across many positions

**Why it matters:** "China will win" can be:
1. Legitimate national security concern
2. Rhetorical strategy to avoid regulation

High intensity + low substantiation = potential red flag.

**Example:** OpenAI scores 85/100 (uses China in 29% of positions). Google scores 2/100 (barely uses it). Anthropic scores 15/100 (minimal use).

**Stored in:** `china_rhetoric_analysis.rhetoric_intensity`
