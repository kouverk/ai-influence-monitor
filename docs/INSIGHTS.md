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

## Position Extraction Results (January 2025)

**Extraction complete:** 607 positions from 112 chunks (17 priority companies)

### Topic Distribution
| Topic | Count | Description |
|-------|-------|-------------|
| `china_competition` | 94 | National security, competitiveness framing |
| `federal_regulation` | ~X | Federal AI oversight |
| `ai_safety` | ~X | Risk concerns, alignment |
| `state_regulation` | ~X | State-level laws (SB 1047, etc.) |
| *...more topics...* | | |

*Note: Run `queries/06_positions_overview.sql` for exact counts*

---

## China Rhetoric Analysis

### Rhetoric Analysis vs Fact-Checking: The Distinction

This project takes two complementary but distinct approaches to China-related claims:

| Approach | What It Does | Scope | Data Needed |
|----------|--------------|-------|-------------|
| **Rhetoric Analysis** (PRIMARY) | Categorizes *how* companies use China framing | All 94 positions | Already have it |
| **Fact-Checking** (OPTIONAL) | Verifies *whether* specific claims are true | Only verifiable claims | Requires FARA, CSET |

**Why rhetoric analysis comes first:**
- We already have the data (94 extracted positions)
- Every claim can be categorized, but only some can be fact-checked
- The pattern of *how* companies use China framing is itself a finding
- Doesn't require us to become China policy experts

**When fact-checking adds value:**
- For claims that make specific, verifiable assertions
- Example: "China doesn't regulate AI" → We can research Chinese AI laws
- Example: "China published more AI papers" → CSET has publication data
- NOT for: "China will dominate if we regulate" → Unfalsifiable prediction

**The key insight:** A company can use China rhetoric strategically even if their underlying claims are true. The rhetoric analysis reveals the *pattern of usage*; fact-checking reveals *accuracy*. Both are valid, but rhetoric analysis is tractable for all claims while fact-checking only applies to a subset.

---

### The Angle

AI companies frequently invoke "China competition" when arguing against regulation. But is this genuine concern or rhetorical strategy?

**Key insight:** We can analyze the *rhetoric* without needing to prove/disprove whether China is actually a threat. The question becomes: "How do companies use China framing in their policy arguments?"

### What We Found

**94 positions** classified as `china_competition` across 17 companies.

### Research Questions

1. **What types of claims are companies making?**
   - Capability claims: "China will overtake us"
   - Regulatory comparisons: "China doesn't regulate"
   - Security framing: "National security requires X"
   - Vague competitiveness: "We need to compete"

2. **Are the claims verifiable or unfalsifiable rhetoric?**
   - Verifiable: "China published X papers last year" (can check)
   - Unfalsifiable: "China will dominate if we regulate" (how would you prove this?)

3. **When do companies invoke China?**
   - To argue against specific regulations?
   - To request government funding?
   - To justify less oversight?

4. **Is there a pattern by company type?**
   - Do AI labs use China framing more than Big Tech?
   - Do trade groups differ from their members?

### Analysis Approach

Rather than trying to answer "Is China a threat?" (a massive geopolitical question), we focus on:

1. **Categorize the rhetoric** - What kinds of China claims appear in submissions?
2. **Flag verifiability** - Which claims can be fact-checked vs. which are unfalsifiable?
3. **Map to policy positions** - When China is invoked, what regulation is being opposed?
4. **Compare across companies** - Who uses this framing most heavily?

This keeps us in the "document intelligence" lane rather than becoming China policy experts.

### Potential Data Sources for Fact-Checking (Documented, Not Implemented)

| Source | What It Provides | Limitation |
|--------|------------------|------------|
| **FARA** (efile.fara.gov) | Foreign lobbying in US - is China lobbying on AI? | Doesn't show China's domestic AI activity |
| **Georgetown CSET** (github.com/georgetown-cset) | Academic data on China AI ecosystem | Research data, not real-time |
| **USCC Annual Reports** | Congressional commission reports on China | Analysis, not raw data |

---

## Position Patterns

### Common themes across companies
- [ ] TBD - analyze after reviewing positions

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
