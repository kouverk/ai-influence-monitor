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

**Extraction complete:** 633 positions from 112 chunks (17 priority companies)

### Policy Ask Distribution
| Policy Ask | Count | Description |
|------------|-------|-------------|
| `government_ai_adoption` | 70 | Federal government should use more AI |
| `research_funding` | 43 | Government R&D money for AI |
| `federal_preemption` | 31 | Block state AI laws with federal override |
| `workforce_training` | 28 | Retraining programs |
| `compute_infrastructure` | 25 | Data center support |

### Argument Distribution
| Argument | Count | Description |
|----------|-------|-------------|
| `competitiveness` | 223 | "Must stay ahead economically" |
| `innovation_harm` | 87 | "Kills startups/innovation" |
| `china_competition` | 55 | "China will win if we don't" |
| `job_creation` | 32 | "Creates jobs" |
| `patchwork_problem` | 28 | "State-by-state is chaos" |

---

## China Rhetoric Analysis

### Key Finding: OpenAI Uses China Framing 6x More Than Anthropic

**55 positions** across 11 companies use `china_competition` as their primary argument.

### China Rhetoric Intensity Scores (0=minimal, 100=heavy reliance)

| Company | Intensity | China Positions | Total Positions | Assessment |
|---------|-----------|-----------------|-----------------|------------|
| **OpenAI** | **85/100** | 16 | 56 | mostly_rhetorical |
| Meta | 75/100 | 10 | 50 | mostly_rhetorical |
| Palantir | 25/100 | 6 | 28 | mostly_rhetorical |
| TechNet | 25/100 | 5 | 47 | substantive |
| IBM | 25/100 | 4 | 30 | mostly_rhetorical |
| Microsoft | 25/100 | 4 | 49 | mostly_rhetorical |
| Cohere | 25/100 | 2 | 35 | mostly_rhetorical |
| DomelabsAI | 15/100 | 4 | 85 | mostly_rhetorical |
| **Anthropic** | **15/100** | 2 | 41 | mostly_rhetorical |
| CCIA | 15/100 | 1 | 38 | mostly_rhetorical |
| **Google** | **2/100** | 1 | 43 | mostly_rhetorical |

**Notable patterns:**
- OpenAI uses China 29% of the time (16/56 positions) - most aggressive
- Anthropic uses China 5% of the time (2/41 positions) - minimal use
- Google barely uses China framing at all (1/43 positions = 2%)
- TechNet is the only company rated "substantive" rather than "mostly_rhetorical"

### Rhetoric Analysis vs Fact-Checking: The Distinction

This project takes two complementary but distinct approaches to China-related claims:

| Approach | What It Does | Scope | Data Needed |
|----------|--------------|-------|-------------|
| **Rhetoric Analysis** (PRIMARY) | Categorizes *how* companies use China framing | All 55 positions | Already have it |
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

### OpenSecrets Data (Evaluated, Not Implemented)

**What it is:** OpenSecrets aggregates lobbying data from the same source we use (Senate LDA) but enriches it with:
- Standardized industry codes (CRP_Categories)
- Cross-linked company IDs across datasets
- 30+ years of historical data
- Campaign contribution data (PACs, individual donations)

**What it would add:**
- Better entity matching (they've done the deduplication work)
- Historical trends (did lobbying spike after ChatGPT?)
- **Campaign contributions** - follow money beyond just lobbying (e.g., "OpenAI lobbies for X AND donates to congresspeople on relevant committees")

**Why we're not using it (for now):**
- Their API was discontinued April 2025
- Bulk data requires registration/approval for "legitimate research purposes"
- It's essentially enriched LDA data - we already have the raw source
- Core analytics questions are answerable with what we have

**Future value:** If we want to add campaign contribution analysis or historical lobbying trends, OpenSecrets bulk data is the path. Not blocking for MVP.

**Sources:**
- [OpenSecrets Bulk Data](https://www.opensecrets.org/bulk-data)
- [Bulk Data Documentation](https://www.opensecrets.org/open-data/bulk-data-documentation)

---

## Position Patterns

### Common Themes Across Companies
- **Government AI adoption** - universal support (70 positions)
- **Research funding** - all want more government R&D money (43 positions)
- **Federal preemption** - most support blocking state AI laws (31 positions)
- **Self-regulation** - industry-led standards preferred over mandates

### AI Labs vs Big Tech

| Pattern | AI Labs | Big Tech |
|---------|---------|----------|
| Safety oversight | Support more | Prefer self-regulation |
| China framing | Heavy use (OpenAI 85%, Meta 75%) | Minimal use (Google 2%) |
| Liability shields | Mixed | Strong support |
| Transparency | Generally support | Oppose (competitive info) |

### Trade Group Positions vs Their Members

Trade groups take more aggressive stances than individual companies:
- **Federal preemption**: Trade groups push harder for state law override
- **Existing agency authority**: Prefer current regulators over new AI agency
- **Self-regulation**: More explicit about opposing mandates

**Why?** Trade groups provide political cover - companies can benefit from aggressive advocacy without being directly associated with the positions.

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

## Discrepancy Analysis Results (January 2025)

### Say-vs-Do Discrepancy Scores (0=consistent, 100=hypocrite)

| Company | Discrepancy Score | Key Finding |
|---------|-------------------|-------------|
| **Anthropic** | **25/100** | Most consistent - lobbying aligns with stated positions |
| OpenAI | 35/100 | Moderate - uses national security framing in rhetoric but generic tech lobbying |
| Adobe | 35/100 | Moderate consistency |
| IBM | 35/100 | Defense contracting focus matches rhetoric |
| CCIA | 35/100 | Core IP advocacy aligns with positions |
| TechNet | 35/100 | Research/government adoption lobbying matches |
| **Google** | **75/100** | Big gap - talks government AI adoption, lobbies exclusively on antitrust |
| **Amazon** | **75/100** | Major discrepancy - 100% of lobbying on cloud/procurement, not AI policy |

### Notable Discrepancy Patterns

**Google (75/100):** "Talks extensively about government AI adoption and national competitiveness but lobbies exclusively on antitrust defense and competition issues"

**Amazon (75/100):** "Major discrepancy between AI policy rhetoric and lobbying reality - 100% of their lobbying focuses on cloud procurement and market access"

**Anthropic (25/100):** "Strong consistency between stated positions and lobbying activity - major focus on AI safety and responsible deployment actually shows in lobbying priorities"

---

## Public Interest Concern Scores (January 2025)

### Concern Scores (0=aligned with public interest, 100=concerning)

| Company | Concern Score | Company Type |
|---------|---------------|--------------|
| **Anthropic** | **45/100** | ai_lab |
| IBM | 68/100 | big_tech |
| Amazon | 68/100 | big_tech |
| US Chamber | 72/100 | trade_group |
| Palantir | 72/100 | big_tech |
| CCIA | 72/100 | trade_group |
| Adobe | 72/100 | big_tech |
| OpenAI | 72/100 | ai_lab |
| Google | 72/100 | ai_lab |
| TechNet | 72/100 | trade_group |

**Key finding:** Anthropic is the only company scoring below 60/100. All trade groups scored 72/100 (highest tier).

---

## Cross-Company Position Comparison (January 2025)

### Key Insights from 17 Companies, 633 Positions

**1. "Incumbent Protection" Pattern**
Market leaders (Google, Microsoft, Amazon) consistently support policies that raise compliance costs - which they can absorb but smaller competitors cannot. They oppose transparency requirements that might help competitors.

**2. Safety Positions Correlate with Marketing**
Companies marketing themselves as "responsible AI" (Anthropic, OpenAI) support more oversight, while pure-play commercial companies prefer self-regulation. Safety positions appear strategic, not purely altruistic.

**3. Trade Groups Do the "Dirty Work"**
Trade groups (CCIA, TechNet, US Chamber) advocate for aggressive deregulatory positions (federal preemption, existing agency authority) that individual companies might be reluctant to champion publicly. This provides political cover for member companies.

**4. Universal Government AI Adoption Support**
Every company supports government AI adoption - this reveals the industry's primary growth strategy: expanding the market through public sector adoption rather than just competing for existing private sector demand.

**5. Internal Conflicts at Diversified Tech Giants**
Diversified tech giants face internal policy conflicts. Example: Amazon opposes training data fair use because of their content businesses (Prime Video, Music, Audible), even though it might benefit their AI efforts.

### Coalition Patterns Identified

**Natural Allies:**
- AI Labs (OpenAI, Anthropic) align on safety-focused oversight
- Big Tech (Google, Microsoft, Amazon) align on incumbent-protective compliance
- Trade Groups align on aggressive deregulation

**Surprising Alignments:**
- OpenAI and Anthropic (competitors) both support mandatory audits
- Trade groups more aggressive than their member companies would be publicly
