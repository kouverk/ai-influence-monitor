# Capstone Instructor Feedback

**Date:** February 2025
**Proposal:** AI Industry Intelligence Platform (Combined Market Signals + Policy Signals)

---

## Overall Assessment

This is an excellent, ambitious proposal with a clear problem framing, compelling dual-lens value (market + policy), and a well-thought-out modern data stack. The architecture diagrams, ingestion strategies, dbt layers, and stakeholder value articulation are all strong. It reads like something you can actually build and ship.

---

## What's Strong

- Clear module separation with shared infra (Airflow/dbt/Snowflake/Streamlit) and LLM placement where it adds unique value.
- Thoughtful data modeling: staging → intermediate → marts, sensible fact/dim choices, and explicit tests.
- Concrete success metrics and stakeholder use-cases with example insights.
- Sensible ingestion frequencies and DAG breakdowns; you've thought about freshness and anomaly monitoring.
- Policy module adds real differentiation; "say–do gap" is novel and journalist-friendly.

---

## Key Risks and Gaps to Address

### Source Licensing and Ethics

The LinkedIn Kaggle dataset can be sensitive (ToS/scraping provenance). Confirm license/acceptable use for academic purposes and state caveats in the README and dashboard.

Include citations and licensing notes for OpenSecrets and LDA use; some OpenSecrets bulk data requires attribution and has terms.

### Federal Register Citation Accuracy

Please verify "90 FR 9088" and the description "Trump administration AI policy RFI." Federal Register "FR 90" corresponds to the year-volume that may not match your description. Provide the exact docket IDs, links, and a short note on scope and timeframe to avoid any credibility issues.

### Representativeness and Temporal Coverage

HN "Who Is Hiring" skews to startup/tech-native audiences; LinkedIn snapshot lacks time series. Make these biases explicit in the dashboard. Consider adding at least one time-series-friendly job source (e.g., Indeed, Greenhouse boards, RemoteOK, LevelsFYI postings) for trend validation.

For LinkedIn, you can still extract relative popularity across roles/skills but be careful with trend claims; label these as cross-sectional unless you add additional vintages.

### LLM Extraction Quality, Cost, and Reproducibility

Define a concrete evaluation plan: sample size, annotation rubric, inter-annotator agreement (e.g., 2 reviewers on 200 doc chunks), metrics (precision/recall/F1 by topic and stance). Your "85%+ accuracy" target needs an explicit measurement recipe.

Provide cost estimates: average tokens per chunk, average chunks per doc, total docs processed, total cost for initial pass and weekly deltas. Add batching, rate limiting, idempotency, and retry logic.

OCR coverage: PDF text extraction often fails on image-only scans. Add OCR fallback (e.g., Tesseract or AWS Textract) with quality monitoring (% pages requiring OCR, WER proxy like text density).

Schema stability: version your JSON schema for positions and include a dbt contract to prevent drift.

### Entity Resolution and Say–Do Discrepancy Scoring

Spell out the entity resolution approach: deterministic rules (normalized names, suffix removal), alias seeds, then fuzzy matching (Jaro-Winkler/Levenshtein with thresholds), and an HIL review queue for low-confidence matches.

Provide a first-pass formula for discrepancy scoring:
- Map positions {topic, stance, confidence, timestamp} to lobbying activity {issue_code/topic mapping, spend, activity text, timestamp}.
- Weight by recency and LLM confidence.
- Penalize if lobbying spend/activity contradicts the position within the lookback window.

Pseudocode example (simplified):
```
For each company-topic in the last 12–24 months:
  position_score = max_position_strength × confidence
  lobbying_score = normalized_spend_on_opposing_issue − aligned_spend
  discrepancy = sigmoid(alpha × lobbying_score − beta × position_score)
Rescale to 0–100; show confidence bands and underlying evidence links.
```

Include a human-review override capability and an appeals note in the dashboard to reduce reputational risk.

### Selection Methodology for the 81 GitHub Repos

Document curation criteria (e.g., inclusion thresholds by stars/issues, coverage by category, independent/open-source focus). Publish the list as a seed with category and rationale to mitigate selection bias.

### Snowflake Cost/Perf and Data Volume Realism

30M+ rows is plausible if you explode mention-level facts; provide a quick row-count forecast per fact table and expected warehouse size.

Add a cost plan: Snowflake warehouse size per task, auto-suspend, query caching, dbt materialization (incremental where possible).

For iteration, consider DuckDB/MotherDuck locally for prototyping to reduce warehouse spend.

### Observability and Ops

Add:
- Lineage and documentation (dbt docs + exposures).
- Alerts on DAG/task failures, Snowflake query failures, and LLM error rates.
- Token/cost dashboards for LLM calls.
- SLA/SLO definitions per source.

### UX and Communication

Streamlit performance: cache query results, parameterize date ranges/companies/topics, and pre-aggregate marts for sub-second interactions.

Prominent caveats: sampling bias, time coverage, LLM confidence, and methods used. Provide "How this score is calculated" modal with citations.

---

## Concrete Requests and Clarifications

1. Share exact policy topic taxonomy (labels, definitions, and mapping to LDA issue codes). Include it as a dbt seed with IDs and synonyms.

2. Provide 3–5 sample records for:
   - `int_llm_positions` (final JSON shape and typical values).
   - `fct_discrepancy_scores` (showing inputs/weights).
   - `dim_company` (aliases and canonical IDs).

3. Add one page of discrepancy scoring math/pseudocode including how you handle:
   - Multiple positions per topic
   - Mixed stances (e.g., support with conditions)
   - Missing lobbying data
   - Time window/recency weighting

4. Provide LLM prompt(s) and few-shot examples you'll use for position extraction; include guardrails (JSON schema, function calling, refusal handling).

5. Provide the repo list seed with categories and rationale.

6. Provide your back-of-the-envelope cost estimates for the initial run and a typical weekly refresh.

7. Confirm the licensing/terms for the LinkedIn dataset and how you'll disclose limitations publicly.

8. Verify and correct the Federal Register citation(s) with links and date ranges.

---

## Nice-to-Have Enhancements (Optional)

- Add a small vector store for policy doc semantic search and "document Q&A" with retrieval-augmented generation; log citations/snippets for transparency.
- Calibrate LLM confidence via a small Platt scaling or isotonic regression on the labeled set; use that for thresholding flags.
- Use dbt snapshots (SCD2) for company metadata and alias history.
- Use ETag/If-None-Match for GitHub API and handle secondary rate limits gracefully.
- Consider a unified dbt project with packages/subdirs and exposures per dashboard page.

---

## Suggested Immediate Next Steps (2–3 weeks)

1. Finalize taxonomies (technologies, roles, policy topics) and publish seeds with IDs and synonyms.
2. Implement entity resolution v1 with a review queue for low-confidence matches.
3. Build and validate the discrepancy score v1 on 3–5 companies end-to-end with transparent evidence tables.
4. Label a 200-chunk evaluation set; report extraction precision/recall and calibration; adjust prompts and thresholds.
5. Publish the curated GitHub repo list and run the daily pipeline with caching.
6. Add OCR fallback and report extraction coverage/quality metrics.

---

## Items to Send

- Exact FR/Regulations.gov docket IDs and links you plan to use.
- Sample dbt models (one per layer), plus a screenshot of dbt docs lineage.
- One Airflow DAG file per module and a run screenshot/log snippet.
- Example Streamlit screenshots or a short Loom showing the intended interactions.
- Seeds: technology/role/database taxonomies; company aliases; policy topics.
- LLM prompt templates and 3 example inputs → outputs.
- A short cost plan (Snowflake and LLM).

---

## Verdict

**This is capstone-ready with a few important clarifications** (citations, licensing, scoring math, LLM evaluation). Addressing the items above will make it both rigorous and defensible, especially for the Policy Signals module where the reputational stakes are higher.
