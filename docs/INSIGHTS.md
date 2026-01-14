# Insights & Findings

Observations discovered during exploration. Add to this as you find interesting things.

**Related docs:**
- [CLAUDE.md](../CLAUDE.md) - Project overview, current state, next steps
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design, DAG structure, prompts
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) - Tables, columns, data sources

---

## Data Exploration Insights

### AI Action Plan Submissions (January 2025)

**Volume breakdown:**
- 10,068 total submissions
- ~1,687 named (organization/person in filename)
- ~8,381 anonymous (AI-RFI-2025-XXXX format)

**File sizes tell a story:**
- Key companies (OpenAI, Anthropic, Google): 150-350KB, 10-20 pages of detailed policy positions
- Anonymous submissions: Often 10-50KB, 1-2 pages, many are form letters or brief comments
- Largest files (1-6MB): Usually contain images, charts, or are scanned documents

**Who submitted:**
- All major AI labs represented: OpenAI, Anthropic, Google, Meta, Microsoft, Amazon, Mistral, Cohere
- Big tech: Palantir, IBM, Adobe, Nvidia
- Trade groups: CCIA, TechNet, US Chamber of Commerce, BSA
- Lots of academics, nonprofits, and individuals

---

## Position Patterns (to be filled in after LLM extraction)

*Add observations here as you run LLM extraction...*

### Common themes across companies
- [ ] TBD

### Differences between AI labs vs Big Tech
- [ ] TBD

### Trade group positions vs their members
- [ ] TBD

---

## Lobbying Data Insights

### Senate LDA API Exploration (January 2025)

**Summary of priority companies:**
| Company | Filings | Expenses (pg1) | Years Active |
|---------|---------|----------------|--------------|
| OpenAI | 40 | $1,970,000 | 2023-2024 |
| Anthropic | 38 | $720,000 | 2023-2025 |
| Nvidia | 44 | varies | 2015-2024 |
| Google | 1,549* | varies | 2003+ |
| Microsoft | 2,214* | $2,040,000 | 1999+ |
| Amazon | 1,272* | $10,804,000 | 2000+ |

*Note: High counts for big tech are due to fuzzy matching - "Google" matches any client containing "Google". Need exact name filtering.*

**Issue codes AI companies lobby on:**
- Computer Industry (CPI)
- Copyright/Patent/Trademark (CPT)
- Science/Technology
- Consumer Issues/Safety/Products
- Energy/Nuclear (data center power)

**Key observation:** OpenAI and Anthropic are relatively new to lobbying (2023+), but spending heavily. OpenAI: ~$2M in 2 years. Anthropic: $720K+ and growing.

**Lobbyists working for OpenAI (17 identified):**
Mix of in-house and external firms. Notable covered positions include former Senate Judiciary Committee counsel, former Assistant US Attorneys - indicates serious investment in DC influence.

**Data quality notes:**
- API uses fuzzy matching on `client_name` - need to filter results by exact match
- Some filings show $0 expenses (registrations, no-activity reports)
- Expenses are per-filing, need to aggregate by quarter/year for totals
- 25 results per page, must paginate for complete data

---

## Discrepancy Observations (to be filled in)

*Add examples of "say one thing, lobby another" as you find them...*

### Notable discrepancies
- [ ] TBD

### Companies with highest consistency
- [ ] TBD

### Companies with lowest consistency
- [ ] TBD
