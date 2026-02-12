# Insights & Findings

Observations discovered during exploration. Add to this as you find interesting things.

**Related docs:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design, DAG structure, prompts
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) - Tables, columns, data sources

**Last updated:** February 2, 2026

---

## Executive Summary

### The Core Question
**Do AI companies practice what they preach on safety and regulation?**

### Key Findings (February 2026)

| Finding | Evidence |
|---------|----------|
| **Anthropic is most consistent** | Lowest discrepancy (25/100), lowest concern (45/100), minimal China rhetoric (15/100) |
| **Google/Amazon have biggest say-vs-do gap** | Both score 72/100 discrepancy - talk AI policy, lobby on antitrust/procurement |
| **OpenAI most aggressive on China framing** | 85/100 rhetoric intensity, uses China in 29% of positions |
| **Trade groups do the "dirty work"** | More aggressive on deregulation than their member companies |
| **Universal support for government AI adoption** | Every company wants to expand the market via public sector |
| **Section 230 is the silent elephant** | 115 lobbying filings, ZERO public positions - everyone lobbies, no one speaks publicly |

### Data Scale

| Dataset | Count | Description |
|---------|-------|-------------|
| AI Action Plan submissions | 10,068 PDFs | Trump admin RFI responses (Feb 2025) |
| Priority company submissions | 30 | Processed through LLM extraction |
| Policy positions extracted | 878 | Structured with taxonomy |
| LDA lobbying filings | 970 | Senate disclosures (2023+) |
| LDA activities | 3,051 | Specific lobbying issues |
| LDA lobbyists | 11,518 | Individual lobbyist records |
| Bills/regulations analyzed | 21 | Coalition pattern analysis |

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

## Position Extraction Results (February 2026)

**Extraction complete:** 878 positions from 30 priority companies

### Policy Ask Distribution
| Policy Ask | Count | Description |
|------------|-------|-------------|
| `government_ai_adoption` | 95+ | Federal government should use more AI |
| `research_funding` | 60+ | Government R&D money for AI |
| `federal_preemption` | 45+ | Block state AI laws with federal override |
| `workforce_training` | 40+ | Retraining programs |
| `compute_infrastructure` | 35+ | Data center support |
| `liability_shield` | 30+ | Protect developers from lawsuits |
| `self_regulation` | 25+ | Industry-led standards |
| `export_controls_strict` | 20+ | More chip/model restrictions |

### Argument Distribution
| Argument | Count | Description |
|----------|-------|-------------|
| `competitiveness` | 300+ | "Must stay ahead economically" |
| `innovation_harm` | 120+ | "Kills startups/innovation" |
| `china_competition` | 75+ | "China will win if we don't" |
| `job_creation` | 45+ | "Creates jobs" |
| `patchwork_problem` | 40+ | "State-by-state is chaos" |
| `national_security` | 35+ | Defense/security implications |
| `consumer_protection` | 30+ | Protect users/citizens |

### Position Taxonomy Coverage
- 30+ policy_ask codes
- 15+ argument codes
- 5 stance categories: support, oppose, conditional, neutral, mixed

---

## China Rhetoric Analysis (February 2026)

**14 companies analyzed** for China competition rhetoric in their policy positions.

### Key Finding: OpenAI Uses China Framing 6x More Than Anthropic

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
| **Anthropic** | **15/100** | 2 | 41 | mostly_rhetorical |
| CCIA | 15/100 | 1 | 38 | mostly_rhetorical |
| **Google** | **2/100** | 1 | 43 | mostly_rhetorical |

### Notable Patterns

**OpenAI (85/100):** Uses China in 29% of positions (16/56) - most aggressive. Frequently invokes China competition to justify lighter regulation, export control positions, and government AI adoption.

**Google (2/100):** Barely uses China framing at all (1/43 positions). Interesting contrast given Google's actual presence in AI competition. May indicate different lobbying strategy.

**Anthropic (15/100):** Minimal use (2/41 positions = 5%). Consistent with their lower concern score and more consistent say-vs-do profile.

**TechNet is the outlier:** Only company rated "substantive" rather than "mostly_rhetorical" - their China references tend to cite specific data points rather than vague competitive framing.

### What This Means

China rhetoric can be:
1. **Legitimate concern** - Real competitive dynamics and national security implications
2. **Rhetorical strategy** - Invoking fear to avoid regulation

**High intensity + low substantiation = red flag.** Most companies use China as rhetorical flourish rather than substantiated argument. The companies that score high on rhetoric intensity tend to:
- Use vague "China will win" framing
- Apply China argument across unrelated policy areas
- Lack specific citations or data

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
- **Government AI adoption** - universal support (95+ positions) - everyone wants the government to buy AI
- **Research funding** - all want more government R&D money (60+ positions)
- **Federal preemption** - most support blocking state AI laws (45+ positions)
- **Self-regulation** - industry-led standards preferred over mandates
- **Liability shields** - widespread support, especially from Big Tech

### AI Labs vs Big Tech

| Pattern | AI Labs | Big Tech |
|---------|---------|----------|
| Safety oversight | Support more (Anthropic, OpenAI) | Prefer self-regulation |
| China framing | Heavy use (OpenAI 85%, Meta 75%) | Minimal use (Google 2%) |
| Liability shields | Mixed | Strong support |
| Transparency | Generally support | Oppose (competitive info) |
| Discrepancy | Lower (OpenAI 45, Anthropic 25) | Higher (Google 72, Amazon 72) |

### Trade Group Positions vs Their Members

Trade groups take more aggressive stances than individual companies:
- **Federal preemption**: Trade groups push harder for state law override
- **Existing agency authority**: Prefer current regulators over new AI agency
- **Self-regulation**: More explicit about opposing mandates
- **Concern scores**: All trade groups scored 72/100 (highest tier)

**Why?** Trade groups provide political cover - companies can benefit from aggressive advocacy without being directly associated with the positions.

### Company Type Patterns

| Type | # Companies | Avg Concern | Avg Discrepancy | China Intensity |
|------|-------------|-------------|-----------------|-----------------|
| AI Labs | 6 | 58 | 42 | High (OpenAI 85) |
| Big Tech | 16 | 56 | 52 | Low-Medium |
| Trade Groups | 4 | 72 | 50 | Low-Medium |
| AI-Focused | 1 | 45 | 35 | Low |

---

## Lobbying Data Insights

### Senate LDA Data (February 2026)

**Total extracted:**
| Table | Records | Description |
|-------|---------|-------------|
| LDA Filings | 970 | Quarterly disclosure filings (2023+) |
| LDA Activities | 3,051 | Specific issues lobbied on |
| LDA Lobbyists | 11,518 | Individual lobbyist records |

**Filters applied:**
- Year: 2023 and later
- Issue codes: AI-relevant (CPI, SCI, CPT, CSP, DEF, HOM)
- Companies: 27 priority companies from config

### Selected Company Lobbying Summary

| Company | Filings | Est. Spend | Key Issues |
|---------|---------|------------|------------|
| OpenAI | 40+ | $2M+ | AI policy, IP, national security |
| Anthropic | 38+ | $720K+ | AI safety, responsible deployment |
| Palantir | 55 | varies | Defense, government contracts |
| Adobe | 13 | varies | IP, copyright, creative industries |
| Intel | 92 | varies | Semiconductors, CHIPS Act, AI hardware |
| Google | 100+ | varies | Antitrust, competition, AI policy |
| Microsoft | 150+ | varies | Competition, cloud, AI policy |
| Amazon | 200+ | varies | Cloud procurement, competition |

**Key observation:** OpenAI and Anthropic are relatively new to lobbying (2023+), but spending heavily. Palantir, Intel, and big tech have deeper lobbying histories.

### Issue Code Distribution

| Code | Description | % of Activities |
|------|-------------|-----------------|
| CPI | Computer Industry | ~35% |
| SCI | Science/Technology | ~25% |
| CPT | Copyright/Patent/Trademark | ~15% |
| DEF | Defense | ~10% |
| CSP | Consumer Safety/Products | ~10% |
| HOM | Homeland Security | ~5% |

**Data quality notes:**
- API uses fuzzy matching - extraction uses exact match filtering
- Some filings show $0 expenses (registrations, no-activity reports)
- Expenses are per-filing, aggregated by company for totals
- Rate limiting: 2s between requests, 5s between companies

---

## Discrepancy Analysis Results (February 2026)

**23 companies analyzed** comparing public policy positions against lobbying activity.

### Say-vs-Do Discrepancy Scores (0=consistent, 100=hypocrite)

| Company | Score | Assessment |
|---------|-------|------------|
| **Anthropic** | **25/100** | Most consistent - lobbying aligns with stated positions |
| Adobe | 35/100 | Moderate consistency |
| IBM | 35/100 | Defense contracting focus matches rhetoric |
| Intel | 35/100 | Hardware focus aligns |
| Workday | 35/100 | Enterprise software consistency |
| OpenAI | 45/100 | Moderate gap - national security rhetoric vs generic tech lobbying |
| CCIA | 45/100 | Core IP advocacy mostly aligns |
| TechNet | 45/100 | Research/government adoption lobbying matches |
| Cisco | 52/100 | Network infrastructure focus with some gaps |
| Twilio | 52/100 | Communications platform alignment |
| Snowflake | 55/100 | Data platform messaging gaps |
| Microsoft | 65/100 | Large gap - talks safety, lobbies on competition |
| **Google** | **72/100** | Major gap - talks AI adoption, lobbies on antitrust |
| **Amazon** | **72/100** | Major discrepancy - rhetoric vs cloud/procurement reality |
| US-Chamber-of-Commerce | 72/100 | Trade group aggressive positioning |
| Palantir | 72/100 | Defense rhetoric vs broader lobbying |
| Meta | 72/100 | Open source rhetoric vs defensive lobbying |
| Cohere | 72/100 | Canada-based, limited US lobbying history |

### Notable Discrepancy Patterns

**Google (72/100):** "Talks extensively about government AI adoption and national competitiveness but lobbies almost exclusively on antitrust defense and competition issues. Their AI policy submissions don't match their lobbying priorities."

**Amazon (72/100):** "Major discrepancy between AI policy rhetoric and lobbying reality - bulk of their lobbying focuses on cloud procurement, AWS market access, and competition issues rather than AI safety or governance."

**Anthropic (25/100):** "Strong consistency between stated positions and lobbying activity. Their major focus on AI safety and responsible deployment actually shows in lobbying priorities. Walks the talk."

**OpenAI (45/100):** "Uses aggressive national security and China competition framing in public positions, but lobbying is more generic tech advocacy. The rhetoric doesn't fully match the spend."

---

## Public Interest Concern Scores (February 2026)

**23 companies analyzed** for public interest implications of their lobbying agenda.

### Concern Scores (0=aligned with public interest, 100=concerning)

| Score Range | Companies |
|-------------|-----------|
| **35-45** (Lower concern) | Intel (35), Workday (35), Anthropic (45), ServiceNow (45), Adobe (45), Qualcomm (45), Snowflake (55) |
| **52-55** (Moderate) | Cisco (52), Twilio (52), Meta (55) |
| **65** (Elevated) | IBM (65), Microsoft (65) |
| **72** (High concern) | US-Chamber (72), Palantir (72), CCIA (72), OpenAI (72), Google (72), TechNet (72), Meta (72), Amazon (72), Cohere (72) |

### Key Findings

**Anthropic (45/100):** Only major AI lab scoring in the "lower concern" tier. Their lobbying agenda focuses more on responsible AI deployment than regulatory avoidance.

**Trade groups cluster at 72/100:** US Chamber, CCIA, and TechNet all scored maximum concern. Trade groups consistently advocate for weaker oversight than their member companies would publicly support.

**OpenAI paradox:** Despite safety-focused public messaging, OpenAI's lobbying agenda scores 72/100 - same as trade groups. Heavy reliance on China competition framing to justify deregulation.

**Big Tech split:**
- Lower concern: Intel, Workday, ServiceNow, Adobe (hardware/enterprise focus)
- Higher concern: Google, Amazon, Microsoft, Meta (platform/AI focus)

---

## Cross-Company Position Comparison (February 2026)

### Key Insights from 30 Companies, 878 Positions

**1. Market Expansion Consensus**
Market expansion policies (government AI adoption, research funding) achieve **unanimous support** because they benefit all players regardless of business model or competitive position. This is the one area where the entire industry aligns.

**2. "Grow the Pie" vs. Competitive Protection Divide**
The AI industry shows a clear divide between:
- **Consensus policies** (grow the pie): Government adoption, research funding, infrastructure
- **Contested policies** (competitive protection): Regulations split based on whether they help or hurt specific market positions

**3. Trade Groups as Political Cover**
Trade groups are more aggressive than individual companies on deregulation. This creates political cover - companies benefit from advocacy they wouldn't do publicly. Safety-focused AI labs create unexpected coalitions with defense contractors on security and transparency issues.

**4. "Incumbent Protection" Pattern**
Market leaders (Google, Microsoft, Amazon) consistently support policies that raise compliance costs they can absorb but smaller competitors cannot. They oppose transparency requirements that might help competitors.

**5. Safety Positions Correlate with Marketing**
Companies marketing themselves as "responsible AI" (Anthropic, OpenAI) support more oversight, while pure-play commercial companies prefer self-regulation. Safety positions appear strategic, not purely altruistic.

**6. Internal Conflicts at Diversified Tech Giants**
Diversified tech giants face internal policy conflicts. Example: Amazon opposes training data fair use because of their content businesses (Prime Video, Music, Audible), even though it might benefit their AI efforts.

### Coalition Patterns Identified

**Natural Allies:**
- AI Labs (OpenAI, Anthropic) align on safety-focused oversight
- Big Tech (Google, Microsoft, Amazon) align on incumbent-protective compliance
- Trade Groups align on aggressive deregulation
- Defense contractors (Palantir) and safety labs on security issues

**Surprising Alignments:**
- OpenAI and Anthropic (competitors) both support mandatory audits
- Trade groups more aggressive than their member companies
- Hardware companies (Intel, Qualcomm, Nvidia) form infrastructure coalition

---

## Bill-Level Coalition Analysis (February 2026)

**21 bills/regulations analyzed** - comparing public positions on specific legislation to actual lobbying activity.

### Key Finding: "Quiet Lobbying" Pattern

Many companies heavily lobby on specific legislation without taking public positions. This "quiet lobbying" pattern reveals priorities companies don't want publicly associated with their brand. *(See [DATA_DICTIONARY.md](DATA_DICTIONARY.md#quiet-lobbying) for full definition)*

### Most Lobbied Bills Without Public Positions

| Bill | Lobbying Filings | Companies Publicly Positioned | Companies Lobbying Without Position |
|------|------------------|-------------------------------|-------------------------------------|
| **Section 230** | 115 | 0 | Meta, Microsoft, CCIA, TechNet |
| **CHIPS Act** | 78 | 2 | Intel, Nvidia, TechNet, Qualcomm |
| **CREATE AI Act** | 29 | 1 | OpenAI, Anthropic, Cohere, Microsoft, TechNet |
| **FedRAMP** | 24 | 0 | Workday |
| **NAIRR** | 10 | 0 | TechNet |

### Contested Legislation

**EU AI Act** - The only bill with both supporters AND opponents:
- **Support:** TechNet, CCIA
- **Oppose:** Google, Meta
- **Quiet lobbying:** TechNet

This split reveals a real policy divide - trade groups favor EU AI Act compliance standardization, while Big Tech opposes international AI regulation complexity.

### "Quiet Lobbying" Analysis

| Company | Bills Lobbying Without Public Position |
|---------|----------------------------------------|
| TechNet | 6 bills (CHIPS, CREATE AI, EU AI Act, NAIRR, Section 230, AI Diffusion) |
| Microsoft | 2 bills (CREATE AI, Section 230) |
| Intel | 1 bill (CHIPS Act) |
| Nvidia | 1 bill (CHIPS Act) |
| Anthropic | 1 bill (AI Diffusion Rule) |
| Workday | 1 bill (FedRAMP) |

### "All Talk" Pattern

Some companies take public positions but don't lobby on those bills:
- Multiple companies position on CA SB 1047, state AI legislation, and international frameworks without corresponding LDA filings
- This may indicate strategic public positioning on "safe" topics without financial commitment

### What This Means

1. **Section 230 is the silent elephant** - Massive lobbying (115 filings), zero public positions. Everyone lobbies on it, no one wants to publicly state their position.

2. **Semiconductor legislation gets quiet treatment** - CHIPS Act has heavy lobbying but minimal public positioning. Companies want the benefits without the advocacy spotlight.

3. **AI-specific legislation gets public support** - Bills like CREATE AI get public positions because supporting AI R&D is politically safe.

4. **TechNet is the ultimate quiet lobbyist** - Lobbies on 6 bills without taking public positions on any of them. True "political cover" operation.
