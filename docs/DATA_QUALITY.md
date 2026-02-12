# Data Quality Checks

This document outlines all data quality checks implemented in the AI Influence Tracker pipeline.

---

## Summary

| Layer | Check Type | Count | Status |
|-------|------------|-------|--------|
| **dbt Tests** | Staging models | 20 | ✅ All passing |
| **dbt Tests** | Mart models | 15 | ✅ All passing |
| **Python** | Extraction validation | 6 | ✅ Implemented |
| **Total** | | **41** | |

**Last test run:** 35/35 dbt tests passing

---

## dbt Tests

### Staging Layer (20 tests)

Each staging model has `unique` and `not_null` tests on primary keys:

| Model | Column | Tests |
|-------|--------|-------|
| `stg_ai_positions` | position_id | unique, not_null |
| `stg_ai_submissions` | document_id | unique, not_null |
| `stg_lda_filings` | filing_uuid | unique, not_null |
| `stg_lda_activities` | activity_id | unique, not_null |
| `stg_lda_lobbyists` | lobbyist_record_id | unique, not_null |
| `stg_lobbying_impact_scores` | score_id | unique, not_null |
| `stg_discrepancy_scores` | score_id | unique, not_null |
| `stg_china_rhetoric` | analysis_id | unique, not_null |
| `stg_position_comparisons` | comparison_id | unique, not_null |
| `stg_bill_position_analysis` | bill_id | unique, not_null |

### Mart Layer (15 tests)

| Model | Column | Tests |
|-------|--------|-------|
| `dim_company` | company_id | unique, not_null |
| `dim_company` | company_name | unique, not_null |
| `fct_policy_positions` | position_id | unique, not_null |
| `fct_policy_positions` | stance | accepted_values: support, oppose, neutral |
| `fct_lobbying_quarterly` | filing_uuid | unique, not_null |
| `fct_lobbying_impact` | score_id | unique, not_null |
| `fct_company_analysis` | company_id | unique, not_null |
| `fct_bill_coalitions` | bill_id | unique, not_null |

---

## Staging Model Deduplication

Raw data may contain duplicates from multiple pipeline runs. Each staging model implements `ROW_NUMBER()` deduplication:

```sql
-- Example from stg_lobbying_impact_scores
with source as (
    select * from {{ source('raw', 'raw_lobbying_impact_scores') }}
),

cleaned as (
    select
        *,
        row_number() over (
            partition by company_name
            order by processed_at desc
        ) as rn
    from source
),

deduplicated as (
    select * from cleaned where rn = 1
)

select * from deduplicated
```

**Deduplication strategy by table:**

| Table | Partition By | Order By |
|-------|--------------|----------|
| `stg_lobbying_impact_scores` | company_name | processed_at DESC |
| `stg_discrepancy_scores` | company_name | processed_at DESC |
| `stg_china_rhetoric` | company_name | analyzed_at DESC |
| `stg_position_comparisons` | comparison_id | compared_at DESC |
| `stg_ai_positions` | position_id | (none - unique) |

---

## Python Extraction Validation

### 1. LLM Response Parsing

All agentic scripts validate Claude API responses:

```python
# JSON extraction with validation
def parse_llm_response(response_text: str) -> dict:
    """Extract and validate JSON from LLM response."""
    # Handle markdown code blocks
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0]
    else:
        json_str = response_text

    return json.loads(json_str.strip())
```

### 2. Retry Logic

API calls include exponential backoff:

```python
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

for attempt in range(MAX_RETRIES):
    try:
        response = client.messages.create(...)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
        else:
            raise
```

### 3. Rate Limiting

1-second delay between API calls to respect rate limits:

```python
time.sleep(1)  # Rate limiting between chunks
```

### 4. Idempotency Tracking

Scripts track processed items to prevent duplicate processing:

```python
# Check already processed
existing_df = table.scan().to_pandas()
processed_companies = set(existing_df['company_name'].unique())

# Skip already processed
for company in companies:
    if company['name'] in processed_companies:
        continue
```

### 5. Entity Resolution Validation

Company name matching uses explicit mappings in `config.py`:

```python
PRIORITY_COMPANIES = [
    {"name": "OpenAI", "lda_name": "OPENAI", "type": "ai_lab"},
    {"name": "Anthropic", "lda_name": "ANTHROPIC", "type": "ai_lab"},
    # ... explicit mappings prevent fuzzy matching errors
]
```

### 6. Score Range Validation

LLM prompts explicitly request 0-100 scores:

```python
# Prompt includes:
"Scoring: 0-20=aligned, 21-40=minor concerns, 41-60=moderate, 61-80=significant, 81-100=critical"
```

---

## Data Quality by Source

### AI Action Plan Submissions (PDFs)

| Check | Implementation | Status |
|-------|----------------|--------|
| Text extraction success | PyMuPDF with error handling | ✅ |
| Chunking consistency | 800 words, 100 overlap | ✅ |
| Submitter identification | Filename parsing + manual review | ✅ |

### Senate LDA API

| Check | Implementation | Status |
|-------|----------------|--------|
| API response validation | JSON schema validation | ✅ |
| Date range filtering | 2023+ filings only | ✅ |
| Issue code filtering | AI-relevant codes (CPI, SCI, CPT, CSP, DEF, HOM) | ✅ |
| Pagination handling | Auto-pagination with next URL | ✅ |

### LLM Outputs

| Check | Implementation | Status |
|-------|----------------|--------|
| JSON parsing | Markdown stripping + json.loads | ✅ |
| Required fields | Prompt specifies all fields | ✅ |
| Score bounds | 0-100 specified in prompts | ✅ |
| Confidence thresholds | 0.0-1.0 for position extraction | ✅ |

---

## Running Data Quality Checks

### dbt Tests

```bash
# Set environment variables
export SNOWFLAKE_ACCOUNT=...
export SNOWFLAKE_USER=...
export SNOWFLAKE_PASSWORD=...
export SNOWFLAKE_WAREHOUSE=...
export SNOWFLAKE_DATABASE=...
export SNOWFLAKE_SCHEMA=...

# Run all tests
cd dbt
dbt test --profiles-dir .

# Run specific test
dbt test --select stg_ai_positions
```

### Progress Check

```bash
# Check row counts and processing status
./venv/bin/python include/scripts/utils/check_progress.py
```

**Example output:**
```
=== Iceberg Table Row Counts ===
ai_submissions_metadata: 30
ai_submissions_chunks: 112
ai_positions: 878
lda_filings: 970
lda_activities: 3,051
lobbying_impact_scores: 23
discrepancy_scores: 23
china_rhetoric_analysis: 14
```

---

## Known Data Quality Issues

### 1. PDF Text Extraction

Some PDFs have image-only pages that PyMuPDF cannot extract. These are logged but not blocking:

```
Warning: Empty text extracted from page 3 of submission_xyz.pdf
```

**Mitigation:** Manual review of low-text documents; future enhancement to add OCR fallback.

### 2. LDA Name Variations

Companies appear with different names in LDA filings (e.g., "MICROSOFT CORPORATION" vs "MICROSOFT").

**Mitigation:** Explicit mappings in `config.py`; fuzzy matching avoided to prevent false matches.

### 3. Position Confidence Scores

LLM-assigned confidence scores tend to cluster around 0.85-0.95.

**Mitigation:** Scores are captured but not used for filtering; all positions included for transparency.

---

## Future Enhancements

- [ ] Add freshness tests (alert if data >N days old)
- [ ] Add row count anomaly detection
- [ ] Add LLM token/cost monitoring
- [ ] Add OCR fallback for image-only PDFs
- [ ] Add automated data profiling reports
