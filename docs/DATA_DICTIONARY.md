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

**Current data (Jan 2025):** 110 filings, 236 activities, 624 lobbyists (OpenAI, Anthropic, Nvidia)

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
**Status:** ✅ Complete - 633 positions extracted from 112 chunks (17 priority companies)

**Extraction stats (Jan 2025):**
- Total positions: 633
- Avg positions/chunk: 5.9
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
| `public_interest_concerns` | STRING (JSON) | Array of specific concerns with evidence, who_harmed, severity |
| `regulatory_capture_signals` | STRING (JSON) | Signs they're shaping regulations for self-benefit |
| `safety_vs_profit_tensions` | STRING (JSON) | Areas where lobbying prioritizes profit over safety |
| `positive_aspects` | STRING (JSON) | Any lobbying genuinely serving public interest |
| `key_flags` | STRING (JSON) | Red flags for journalists/regulators/public |
| `positions_count` | INT | Number of policy positions analyzed |
| `lobbying_filings_count` | INT | Number of LDA filings analyzed |
| `model` | STRING | Model used (e.g., `claude-sonnet-4-20250514`) |
| `processed_at` | TIMESTAMP | When assessment ran |

**Assessment script:** `include/scripts/agentic/assess_lobbying_impact.py`
**Status:** ✅ Complete - 10 companies assessed

**Results (Jan 2025):**
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
