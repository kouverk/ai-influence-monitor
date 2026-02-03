# Extraction Schema Proposal

> **Status: ✅ IMPLEMENTED** (January 2025)
>
> This proposal has been fully implemented. The enhanced schema is now in production with 878 positions extracted. See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for current table schemas.

---

## The Problem

Current extraction gives us:
```
topic: "federal_regulation"
stance: "support"
```

But "federal_regulation + support" could mean VERY different things:
- "We want a new federal AI agency" (more oversight)
- "We want federal preemption of states" (less oversight)
- "We want federal funding for AI" (money)

These get lumped together, making analysis meaningless.

---

## Analytics We Want to Enable

### Questions we want to answer:

1. **Who wants what?**
   - "Which companies want liability shields?"
   - "Who opposes California SB 1047?"
   - "Who's asking for federal preemption?"

2. **Patterns across company types**
   - "Do AI labs differ from Big Tech on safety?"
   - "Do trade groups take more extreme positions than their members?"

3. **Rhetorical analysis**
   - "Who uses China framing to oppose regulation?"
   - "What arguments are used to justify less oversight?"

4. **Follow the money**
   - "Do stated positions match lobbying spend allocation?"
   - "Who's spending most on preemption lobbying?"

---

## Proposed Schema: Policy Asks

Instead of broad topics, extract **specific policy asks**:

```python
{
    # WHAT do they want?
    "policy_ask": "federal_preemption",  # Specific, actionable

    # Taxonomy of asks (enumerated list)
    "ask_category": "regulatory_structure",  # High-level grouping

    # WHAT is their position?
    "stance": "support",  # support/oppose/neutral

    # WHO or WHAT are they responding to?
    "target": "California SB 1047",  # Specific regulation, or null

    # HOW are they arguing for it?
    "primary_argument": "innovation_harm",  # Why they say it matters
    "secondary_argument": "china_competition",  # Optional second argument

    # Evidence
    "supporting_quote": "...",
    "confidence": 0.9
}
```

### Policy Ask Taxonomy

```
REGULATORY STRUCTURE
├── federal_preemption          # Federal law overrides state
├── state_autonomy              # States should regulate
├── new_federal_agency          # Create AI oversight body
├── existing_agency_authority   # Use FTC/FDA/etc
├── self_regulation             # Industry-led standards
├── international_harmonization # Align with EU/others

ACCOUNTABILITY
├── liability_shield            # Protect developers from lawsuits
├── liability_framework         # Define who's responsible
├── mandatory_audits            # Third-party testing required
├── voluntary_commitments       # Industry self-commitments
├── transparency_requirements   # Disclosure mandates
├── incident_reporting          # Mandatory breach reporting

INTELLECTUAL PROPERTY
├── training_data_fair_use      # Allow copyrighted data for training
├── creator_compensation        # Pay content creators
├── model_weight_protection     # Treat weights as trade secrets
├── open_source_mandate         # Require open models
├── open_source_allowed         # Don't restrict open models

NATIONAL SECURITY
├── export_controls_strict      # More chip/model restrictions
├── export_controls_loose       # Fewer restrictions
├── china_competition_frame     # Frame as beating China
├── government_ai_adoption      # More federal AI use
├── defense_ai_investment       # Military AI funding

RESOURCES
├── research_funding            # Government R&D money
├── compute_infrastructure      # Data center support
├── energy_infrastructure       # Power grid for AI
├── immigration_reform          # AI talent visas
├── workforce_training          # Retraining programs
```

### Argument Types (HOW they argue)

```
ECONOMIC
├── innovation_harm        # "Kills startups"
├── competitiveness        # "Must stay ahead"
├── job_creation           # "Creates jobs"
├── cost_burden            # "Too expensive to comply"

SECURITY
├── china_competition      # "China will win"
├── national_security      # "Defense requires this"
├── adversary_benefit      # "Helps bad actors"

PRACTICAL
├── technical_infeasibility # "Can't be done"
├── patchwork_problem      # "State-by-state is chaos"
├── duplicative            # "Already regulated"
├── premature              # "Too early to regulate"

RIGHTS/FAIRNESS
├── free_speech            # First Amendment
├── consumer_protection    # Protect users
├── creator_rights         # Protect artists
├── civil_liberties        # Privacy, bias concerns
```

---

## Example Extractions

**Current (vague):**
```json
{"topic": "state_regulation", "stance": "strong_oppose"}
```

**Proposed (specific):**
```json
{
    "policy_ask": "federal_preemption",
    "ask_category": "regulatory_structure",
    "stance": "support",
    "target": "California SB 1047",
    "primary_argument": "patchwork_problem",
    "secondary_argument": "innovation_harm",
    "supporting_quote": "A patchwork of state regulations risks...",
    "confidence": 0.92
}
```

**Another example:**
```json
{
    "policy_ask": "training_data_fair_use",
    "ask_category": "intellectual_property",
    "stance": "support",
    "target": null,
    "primary_argument": "innovation_harm",
    "secondary_argument": null,
    "supporting_quote": "AI training on publicly available data should be...",
    "confidence": 0.88
}
```

---

## Analytics This Enables

### Query 1: Who wants liability shields?
```sql
SELECT company_name, COUNT(*) as mentions
FROM policy_asks
WHERE policy_ask = 'liability_shield' AND stance = 'support'
GROUP BY company_name
ORDER BY mentions DESC
```

### Query 2: What arguments are used against SB 1047?
```sql
SELECT primary_argument, COUNT(*) as usage
FROM policy_asks
WHERE target LIKE '%SB 1047%' AND stance IN ('oppose', 'strong_oppose')
GROUP BY primary_argument
ORDER BY usage DESC
```

### Query 3: Who uses China framing most?
```sql
SELECT company_name, company_type, COUNT(*) as china_mentions
FROM policy_asks
WHERE primary_argument = 'china_competition'
   OR secondary_argument = 'china_competition'
GROUP BY company_name, company_type
ORDER BY china_mentions DESC
```

### Query 4: AI Labs vs Big Tech on safety
```sql
SELECT
    company_type,
    policy_ask,
    SUM(CASE WHEN stance = 'support' THEN 1 ELSE 0 END) as supports,
    SUM(CASE WHEN stance = 'oppose' THEN 1 ELSE 0 END) as opposes
FROM policy_asks
WHERE ask_category = 'accountability'
GROUP BY company_type, policy_ask
```

---

## Implementation Options

### Option A: Re-extract all positions ✅ CHOSEN
- Delete existing `ai_positions` table
- Run new extraction with enhanced prompt
- Cost: ~$5-10 in API calls for 112 chunks
- Pro: Clean data, consistent schema
- Con: Loses existing data

### Option B: Enrich existing positions
- Create new `ai_policy_asks` table
- Run enrichment on existing 607 positions
- Pro: Keeps original data, additive
- Con: Two tables to manage

### Option C: Start fresh on new documents
- Keep existing data as-is
- Use new schema only for future extractions
- Pro: No rework
- Con: Inconsistent data

**Recommendation:** Option A (re-extract) since we only have 17 documents and the cost is low.

**Result:** Option A implemented. 878 positions extracted with enhanced schema.

---

## Row Count Impact

~~Current: 607 positions~~
**Actual result: 878 positions** (30 priority companies)

Each row is now analytically useful with structured fields enabling queries like:
- "Who uses China competition arguments?" → 55 positions
- "Who wants liability shields?" → Direct query on `policy_ask`
- "What arguments are used against SB 1047?" → Filter by `target`

---

## Next Steps

1. [x] Review this proposal
2. [x] Finalize the taxonomy (add/remove categories)
3. [x] Update `extract_positions.py` with new prompt
4. [x] Re-run extraction on 112 chunks → **878 positions extracted**
5. [x] Update `assess_lobbying_impact.py` to use new schema
6. [x] Build dbt models for analysis → **10 staging views + 6 mart tables**

---

*Created: January 14, 2025*
*Implemented: January 17, 2025*
