# AI Influence Tracker
## Capstone Project Plan

**Subtitle:** What AI Companies Say vs. What They Lobby For

---

## 🎯 Project Overview

Build a document intelligence pipeline that:
1. Processes 10,000+ government policy submissions
2. Extracts structured policy positions using LLMs
3. Joins to federal lobbying disclosure data
4. Surfaces discrepancies between public statements and lobbying activity

**Core Question:** Do AI companies practice what they preach on safety and regulation?

---

## 📊 Data Sources (3 Sources, 1M+ Rows)

### Source 1: AI Action Plan Submissions
| Attribute | Value |
|-----------|-------|
| URL | https://files.nitrd.gov/90-fr-9088/90-fr-9088-combined-responses.zip |
| Format | 600MB zip of PDFs/docs |
| Count | 10,068 documents |
| Key Submitters | OpenAI, Anthropic, Google, Meta, Microsoft, trade groups, academics |
| Fields After Processing | submitter_name, submitter_type, document_text, submission_date |

### Source 2: Senate LDA Lobbying Database
| Attribute | Value |
|-----------|-------|
| URL | https://lda.senate.gov/api/v1/ |
| Format | REST API (JSON) |
| Key Endpoints | /filings/, /clients/, /registrants/, /lobbyists/ |
| Filter | AI-related filings (2020-2025) |
| Fields | filing_id, client_name, registrant_name, amount, lobbying_activities, issues |

### Source 3: OpenSecrets Bulk Data
| Attribute | Value |
|-----------|-------|
| URL | https://www.opensecrets.org/open-data/bulk-data |
| Format | CSV bulk download |
| Content | Lobbying spend by company, by year, by issue |
| Fields | org_name, year, total_lobbying, issues_lobbied |

### Bonus Source 4: Safety Researcher Statements (Optional)
| Attribute | Value |
|-----------|-------|
| Sources | Twitter/X, Substack, news articles |
| People | Jan Leike, Ilya Sutskever, Daniel Kokotajlo, Miles Brundage |
| Method | Manual curation or light scraping |

---

## 🔢 Row Count Estimates

| Table | Estimated Rows |
|-------|----------------|
| stg_submissions_raw | 10,068 |
| stg_submissions_text | 10,068 |
| int_llm_positions | ~50,000 (5 positions per doc avg) |
| stg_lda_filings | ~5,000 (AI-related 2020-2025) |
| stg_opensecrets_lobbying | ~2,000 |
| fct_policy_positions | ~50,000 |
| fct_lobbying_activity | ~5,000 |
| fct_position_lobbying_comparison | ~10,000 |

**Total: ~130,000+ rows (easily expandable to 1M with full LLM extraction)**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXTRACT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  AI Action   │  │  Senate LDA  │  │  OpenSecrets │               │
│  │  Plan Zip    │  │  REST API    │  │  Bulk CSV    │               │
│  │  (600MB)     │  │  (JSON)      │  │              │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                        │
│         ▼                 ▼                 ▼                        │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                    Airflow DAGs                           │       │
│  │  - download_ai_submissions_dag                            │       │
│  │  - extract_lda_filings_dag                                │       │
│  │  - download_opensecrets_dag                               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TRANSFORM LAYER (dbt)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  STAGING                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │ stg_submissions │  │ stg_lda_filings │  │stg_opensecrets  │      │
│  │ - raw text      │  │ - normalized    │  │- lobbying spend │      │
│  │ - metadata      │  │ - client/issue  │  │- by company     │      │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │
│           │                    │                    │               │
│           ▼                    ▼                    ▼               │
│  INTERMEDIATE                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  int_llm_position_extraction                                 │    │
│  │  - Claude API extracts positions from submission text        │    │
│  │  - Output: topic, stance, quote, confidence                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  int_entity_resolution                                       │    │
│  │  - Match "OpenAI" across all sources                         │    │
│  │  - Handle variations: "OpenAI, Inc.", "OpenAI LP", etc.      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│           │                                                          │
│           ▼                                                          │
│  MARTS (Final Tables)                                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐    │
│  │fct_policy_       │  │fct_lobbying_     │  │fct_discrepancy_ │    │
│  │positions         │  │activity          │  │scores           │    │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘    │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐    │
│  │dim_company       │  │dim_topic         │  │dim_person       │    │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LOAD LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      Snowflake                               │    │
│  │  - Raw schema (staging)                                      │    │
│  │  - Analytics schema (marts)                                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VISUALIZATION LAYER                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Dashboard showing:                                                  │
│  - Company "say vs. lobby" discrepancy scores                       │
│  - Timeline: safety departures vs. lobbying spend                   │
│  - Position breakdown by topic (safety, regulation, copyright)      │
│  - Lobbying network graph (who lobbies together)                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Data Models

### Fact Tables

#### fct_policy_positions
```sql
company_id          INT         -- FK to dim_company
document_id         VARCHAR     -- Source document ID
position_text       TEXT        -- Extracted position (LLM output)
topic               VARCHAR     -- safety, regulation, copyright, competition, etc.
stance              VARCHAR     -- support, oppose, neutral, qualified
confidence_score    FLOAT       -- LLM confidence (0-1)
quote               TEXT        -- Supporting quote from document
extracted_at        TIMESTAMP
```

#### fct_lobbying_activity
```sql
company_id          INT         -- FK to dim_company
filing_id           VARCHAR     -- LDA filing ID
quarter             DATE        
amount              DECIMAL     -- Lobbying spend
issues_lobbied      ARRAY       -- List of issue codes
bills_lobbied       ARRAY       -- Specific bills mentioned
lobbyists_count     INT
filing_type         VARCHAR     -- LD-1, LD-2, etc.
```

#### fct_discrepancy_scores
```sql
company_id          INT
topic               VARCHAR
public_stance       VARCHAR     -- From submissions
lobbying_stance     VARCHAR     -- Inferred from activity
discrepancy_score   FLOAT       -- 0 (consistent) to 100 (hypocritical)
evidence_summary    TEXT        -- LLM-generated explanation
calculated_at       TIMESTAMP
```

### Dimension Tables

#### dim_company
```sql
company_id          INT
company_name        VARCHAR     -- Canonical name
aliases             ARRAY       -- ["OpenAI", "OpenAI, Inc.", "OpenAI LP"]
company_type        VARCHAR     -- ai_lab, big_tech, trade_group, academic, etc.
headquarters        VARCHAR
founded_year        INT
```

#### dim_topic
```sql
topic_id            INT
topic_name          VARCHAR     -- e.g., "ai_safety", "state_regulation"
topic_category      VARCHAR     -- safety, regulation, competition, etc.
description         TEXT
keywords            ARRAY       -- For LLM classification
```

#### dim_person
```sql
person_id           INT
person_name         VARCHAR
role                VARCHAR     -- lobbyist, researcher, executive
company_id          INT
linkedin_url        VARCHAR
```

---

## 🤖 Agentic LLM Component

### Position Extraction Prompt

```python
EXTRACTION_PROMPT = """
You are analyzing a policy submission to the US government's AI Action Plan.

Document:
{document_text}

Extract all policy positions from this document. For each position, provide:
1. topic: One of [ai_safety, state_regulation, federal_regulation, copyright, 
   open_source, china_competition, export_controls, liability, workforce, 
   research_funding, energy_infrastructure, other]
2. stance: One of [strong_support, support, neutral, oppose, strong_oppose]
3. quote: A direct quote (under 50 words) supporting this classification
4. confidence: Your confidence in this classification (0.0-1.0)

Return as JSON array:
[
  {
    "topic": "state_regulation",
    "stance": "strong_oppose",
    "quote": "patchwork of regulations risks bogging down innovation",
    "confidence": 0.95
  },
  ...
]

If the document contains no clear policy positions, return an empty array.
"""
```

### Discrepancy Scoring Prompt

```python
DISCREPANCY_PROMPT = """
Analyze the consistency between a company's public statements and lobbying activity.

Company: {company_name}

PUBLIC STATEMENTS (from AI Action Plan submission):
{positions_summary}

LOBBYING ACTIVITY (from Senate disclosures):
{lobbying_summary}

Rate the consistency on a scale of 0-100:
- 0 = Perfectly consistent (lobbying matches stated positions)
- 50 = Some inconsistencies
- 100 = Completely inconsistent (lobbying contradicts stated positions)

Provide:
1. discrepancy_score: Integer 0-100
2. reasoning: Brief explanation (2-3 sentences)
3. key_inconsistencies: List of specific contradictions found

Return as JSON.
"""
```

---

## 📅 4-Week Timeline

### Week 1: Data Acquisition & Exploration
| Day | Task |
|-----|------|
| Mon | Download AI Action Plan zip, explore structure |
| Tue | Set up Senate LDA API access, test endpoints |
| Wed | Download OpenSecrets bulk data, identify AI companies |
| Thu | Set up Snowflake, create raw schemas |
| Fri | Set up Airflow project structure, initial DAGs |

**Deliverable:** All data accessible, raw tables in Snowflake

### Week 2: PDF Processing & Staging
| Day | Task |
|-----|------|
| Mon | Set up Reducto.ai (or PyMuPDF fallback) for PDF extraction |
| Tue | Process ~100 key submissions (OpenAI, Anthropic, Google, etc.) |
| Wed | Build staging models in dbt (stg_submissions, stg_lda) |
| Thu | Entity resolution: match companies across sources |
| Fri | Data quality checks on staging tables |

**Deliverable:** Staging tables populated, entity resolution complete

### Week 3: LLM Enrichment & Modeling
| Day | Task |
|-----|------|
| Mon | Build LLM position extraction pipeline |
| Tue | Run extraction on 100 key documents |
| Wed | Build intermediate models (int_llm_positions) |
| Thu | Build discrepancy scoring logic |
| Fri | Build mart tables (fct_*, dim_*) |

**Deliverable:** Fact tables with LLM-extracted positions

### Week 4: Visualization & Polish
| Day | Task |
|-----|------|
| Mon | Build dashboard (company scorecards) |
| Tue | Build timeline visualization (safety departures) |
| Wed | Deploy to Astronomer, test end-to-end |
| Thu | Documentation, README, data dictionary |
| Fri | Final polish, demo prep |

**Deliverable:** Working pipeline, deployed, documented

---

## ✅ Bootcamp Requirements Checklist

| Requirement | How This Project Meets It |
|-------------|---------------------------|
| 2+ data sources | AI submissions + LDA API + OpenSecrets |
| 1M+ rows | 10K docs × ~5 positions = 50K+ (expandable) |
| ETL pipeline | Airflow orchestrates extract, dbt transforms |
| Data quality checks | LLM confidence scores, entity matching validation |
| Astronomer deployment | Yes |
| Agentic action | LLM extracts structured positions from unstructured PDFs |

---

## 🎤 Pitch Framing

### For Bootcamp Demo:
> "I built an NLP pipeline that processes 10,000+ government policy filings, 
> extracts structured positions using LLMs, and joins them to lobbying data 
> to surface discrepancies between what companies say and what they lobby for."

### For Job Interviews:
> "I built a document intelligence pipeline demonstrating PDF extraction, 
> LLM-powered semantic classification, and multi-source entity resolution. 
> The same architecture applies to legal document review, regulatory compliance, 
> or any domain requiring large-scale document processing."

### For Tech/AI Audience:
> "I built a tool that answers: 'Do AI companies practice what they preach?' 
> by systematically comparing their AI Action Plan submissions to their 
> federal lobbying disclosures."

---

## 🚀 Expansion Opportunities (Post-Capstone)

1. **Scale to all 10,068 documents** (not just 100 key ones)
2. **Add state lobbying data** (California SB 1047 opposition)
3. **Add safety researcher tracker** (departures, statements)
4. **Real-time monitoring** (new lobbying filings)
5. **Expand to other policy areas** (tech, pharma, energy)
6. **Open source the pipeline** (document intelligence toolkit)

---

## 📚 Resources

- AI Action Plan Submissions: https://www.nitrd.gov/coordination-areas/ai/90-fr-9088-responses/
- Senate LDA API: https://lda.senate.gov/api/
- OpenSecrets Bulk Data: https://www.opensecrets.org/open-data/bulk-data
- Reducto.ai: https://reducto.ai/
- dbt: https://docs.getdbt.com/
- Astronomer: https://www.astronomer.io/

---

*Last updated: January 2025*
