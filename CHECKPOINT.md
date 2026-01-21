# Project Checkpoint - January 17, 2025

## What's Complete ✅

### Data Pipeline
- **PDF Extraction**: 17 priority company submissions → 112 chunks
- **Position Extraction**: 633 policy positions with structured taxonomy
- **Senate LDA Data**: 339 filings, 869 activities, 2,586 lobbyists (2023+)
- **Snowflake Export**: All Iceberg tables exported to `DATAEXPERT_STUDENT.KOUVERK_AI_INFLUENCE`
- **dbt Models**: 6 staging views + 4 mart tables, 23 tests passing
- **Airflow DAGs**: 6 DAGs ready for Astronomer deployment

### LLM Analysis Scripts (All Run Successfully)
| Script | Output Table | Records | Key Finding |
|--------|--------------|---------|-------------|
| `extract_positions.py` | `ai_positions` | 633 | 30+ policy codes, 15+ argument codes |
| `assess_lobbying_impact.py` | `lobbying_impact_scores` | 10 | Anthropic 45/100 (lowest concern) |
| `detect_discrepancies.py` | `discrepancy_scores` | 10 | Google/Amazon 75/100 (highest gap) |
| `analyze_china_rhetoric.py` | `china_rhetoric_analysis` | 11 | OpenAI 85/100 (most aggressive) |
| `compare_positions.py` | `position_comparisons` | 1 | Trade groups do "dirty work" |

### Key Findings Summary
1. **Anthropic stands out**: Lowest concern score (45/100), most consistent say-vs-do (25/100)
2. **OpenAI aggressive on China**: Uses China framing 29% of time (85/100 intensity)
3. **Google/Amazon biggest gap**: Talk AI policy, lobby on antitrust/procurement (75/100 discrepancy)
4. **Trade groups provide cover**: Advocate aggressive positions companies won't say publicly
5. **Universal market strategy**: Every company supports government AI adoption

---

## What's NOT Done

### Required for Capstone
- [ ] Dashboard/visualization layer (Streamlit, Tableau, or similar)
- [ ] Run Astronomer locally (`astro dev start` - requires Docker)
- [ ] Process more documents (only 17 of 10,000+ available)

### Nice to Have
- [ ] Trade Group Aggregator script (`analyze_trade_groups.py`)
- [ ] Regulatory Target Mapper script (`map_regulatory_targets.py`)
- [ ] Re-export to Snowflake after agentic script runs

---

## Quick Start Commands

```bash
# Activate environment
source venv/bin/activate

# Run any agentic script with fresh data
./venv/bin/python include/scripts/agentic/assess_lobbying_impact.py --fresh
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --fresh
./venv/bin/python include/scripts/agentic/analyze_china_rhetoric.py --fresh
./venv/bin/python include/scripts/agentic/compare_positions.py --fresh

# Dry run (no API calls)
./venv/bin/python include/scripts/agentic/detect_discrepancies.py --dry-run

# Export to Snowflake
./venv/bin/python include/scripts/utils/export_to_snowflake.py

# Start Astronomer (requires Docker)
cd /Users/kouverbingham/development/data-expert-analytics/ai-influence-monitor
astro dev start
```

---

## File Locations

| Purpose | Path |
|---------|------|
| Project docs | `CLAUDE.md`, `docs/*.md` |
| Extraction scripts | `include/scripts/extraction/` |
| Agentic scripts | `include/scripts/agentic/` |
| Config (company lists) | `include/config.py` |
| Airflow DAGs | `dags/` |
| dbt project | `dbt/ai_influence/` |
| Credentials | `.env` |

---

## Data Locations

| Data | Location |
|------|----------|
| PDFs (source) | `data/ai-action-plan/` |
| Iceberg tables | S3 via AWS Glue (`kouverk.*`) |
| Snowflake | `DATAEXPERT_STUDENT.KOUVERK_AI_INFLUENCE` |

---

## Session History

- **Session 6** (Jan 17): Ran all 4 agentic scripts, documented findings
- **Session 5** (Jan 17): Astronomer setup, v2 prompts, discrepancy detection
- **Session 4** (Jan 14): Shared config, LDA filters
- **Session 3** (Jan 14): Position extraction complete, LDA loaded
- **Session 2** (Jan 14): PDF extraction pipeline
- **Session 1** (Jan 2025): Project setup, PDF download

---

*Next session: Build dashboard or process more documents*
