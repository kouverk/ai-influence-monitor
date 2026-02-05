"""
Assess lobbying impact on public interest using LLM analysis.

This script analyzes what companies are ACTUALLY lobbying for and flags
concerns for public interest. Unlike a simple "consistency check", this
asks the critical questions:
- What is this company trying to achieve through lobbying?
- Who benefits and who is harmed?
- What should the public/regulators/journalists know?

Pipeline:
1. Reads positions from ai_positions (grouped by company)
2. Reads lobbying from lda_filings + lda_activities (grouped by company)
3. Matches companies using config.py mapping
4. Sends paired data to Claude API for impact assessment
5. Writes assessments to lobbying_impact_scores table

Tables:
- Reads from: {schema}.ai_positions
- Reads from: {schema}.lda_filings, {schema}.lda_activities
- Writes to: {schema}.lobbying_impact_scores

Environment variables required:
- SCHEMA: Target schema/namespace for tables
- ANTHROPIC_API_KEY: Claude API key
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, AWS_S3_BUCKET_TABULAR
"""

import sys
import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    StringType,
    TimestampType,
    NestedField
)
import boto3
from dotenv import load_dotenv

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import get_company_name_mapping, get_company_type


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMScoringError(Exception):
    """Raised when LLM scoring fails."""
    pass


class IcebergError(Exception):
    """Raised when Iceberg operations fail."""
    pass


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


# Rate limiting
REQUEST_DELAY = 1.0  # seconds between API calls
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # seconds between retries

# Model configuration
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


LOBBYING_IMPACT_PROMPT = """
Assess the public interest implications of this company's AI policy lobbying.

<company>{company_name} ({company_type})</company>

<policy_positions_summary>
Aggregated policy asks from their AI Action Plan submission (what they publicly advocate for):

By Category:
{positions_by_category}

Top Arguments Used:
{arguments_summary}

China Competition Framing:
{china_framing_summary}
</policy_positions_summary>

<sample_quotes>
Key quotes from their submission:
{sample_quotes}
</sample_quotes>

<lobbying_activity>
Senate LDA filings (what they're paying lobbyists to push):
- Total filings: {total_filings}
- Total expenses: ${total_expenses:,.0f}
- Years active: {years_active}

By Issue Area:
{lobbying_by_issue}
</lobbying_activity>

Analyze what this company is actually trying to achieve through lobbying and assess the implications.

Return JSON with these fields:

{{
  "lobbying_agenda_summary": "<2-3 sentences: What is this company's overall lobbying agenda? What policy outcomes are they pushing for?>",

  "concern_score": <0-100 integer - how concerning is this lobbying for public interest? Use the FULL range with precision - scores like 23, 47, 68, 81 are valid. Avoid rounding to multiples of 5 or 25.>,

  "top_concerning_policy_asks": [
    {{
      "policy_ask": "<code from their positions>",
      "why_concerning": "<implication for public>",
      "lobbying_alignment": "<how their lobbying supports this>"
    }}
  ],

  "public_interest_concerns": [
    {{
      "concern": "<specific concern>",
      "evidence": "<quote or lobbying activity supporting this>",
      "who_harmed": "<who could be negatively affected>",
      "severity": "<low|medium|high|critical>"
    }}
  ],

  "regulatory_capture_signals": [
    "<any signs they're trying to shape regulations to benefit themselves over competitors or public>"
  ],

  "china_rhetoric_assessment": {{
    "usage_pattern": "<how they use China framing>",
    "serves_which_agenda": "<what policies does the China argument support?>",
    "legitimacy": "<is the China framing substantive or rhetorical cover?>"
  }},

  "accountability_stance": {{
    "wants_oversight": <true|false>,
    "evidence": "<what their positions on audits, liability, transparency reveal>"
  }},

  "positive_aspects": [
    "<any lobbying that genuinely serves public interest>"
  ],

  "key_flags": [
    "<red flags that journalists/regulators/public should know about>"
  ]
}}

Scoring guide for concern_score:
- 0-20: Lobbying appears aligned with public interest (rare)
- 21-40: Minor concerns - mostly standard corporate advocacy
- 41-60: Moderate concerns - some troubling patterns
- 61-80: Significant concerns - lobbying could harm public
- 81-100: Critical concerns - active efforts against public interest

Policy ask codes reference:
- federal_preemption: Block state AI laws with federal override
- liability_shield: Protect from lawsuits for AI harms
- self_regulation: Industry-led standards, no mandates
- export_controls_loose: Fewer chip/model restrictions
- training_data_fair_use: Use copyrighted data without payment

IMPORTANT analysis guidelines:
- Don't just report what they said - analyze the IMPLICATIONS
- "Opposing state regulation" isn't neutral - it means less oversight
- "Preemption" means blocking states from protecting their citizens
- "Self-regulation" means no external accountability
- Export control opposition may benefit adversaries
- Liability shield requests mean victims can't seek recourse
- Look for gaps between stated "safety" positions and actual lobbying
- Consider: If they get what they want, who benefits and who is harmed?

Return ONLY valid JSON, no other text.
"""


def get_required_env(var_name: str) -> str:
    """Get required environment variable or raise ConfigurationError."""
    value = os.environ.get(var_name)
    if not value:
        raise ConfigurationError(f"Required environment variable {var_name} is not set")
    return value


def get_catalog():
    """Initialize and return PyIceberg catalog."""
    aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
    s3_bucket = get_required_env('AWS_S3_BUCKET_TABULAR')

    get_required_env('AWS_ACCESS_KEY_ID')
    get_required_env('AWS_SECRET_ACCESS_KEY')

    boto3.setup_default_session(region_name=aws_region)

    return load_catalog(
        name="glue_catalog",
        **{
            "type": "glue",
            "region": aws_region,
            "warehouse": f"s3://{s3_bucket}/iceberg-warehouse/",
        }
    )


def get_table_names() -> dict:
    """Get table names from SCHEMA environment variable."""
    schema = get_required_env('SCHEMA')
    return {
        "positions": f"{schema}.ai_positions",
        "filings": f"{schema}.lda_filings",
        "activities": f"{schema}.lda_activities",
        "scores": f"{schema}.lobbying_impact_scores",
    }


def get_processed_companies(catalog, scores_table_name: str) -> set:
    """Get set of companies that have already been scored."""
    try:
        table = catalog.load_table(scores_table_name)
        scan = table.scan(selected_fields=("company_name",))
        df = scan.to_arrow().to_pandas()
        return set(df["company_name"].unique())
    except Exception as e:
        logger.info(f"No existing scores found (this is fine for first run): {e}")
        return set()


def get_positions_by_company(catalog, positions_table_name: str) -> dict[str, dict]:
    """
    Load positions and group by submitter_name with structured taxonomy aggregation.

    Returns:
        dict: {company_name: {
            "positions": [list of position dicts],
            "by_category": {category: [{policy_ask, stance, count}]},
            "arguments": {argument: count},
            "china_framing": {policy_ask: count},
            "sample_quotes": [top quotes by confidence]
        }}
    """
    try:
        table = catalog.load_table(positions_table_name)
        df = table.scan().to_arrow().to_pandas()

        positions_by_company = {}
        for company in df["submitter_name"].unique():
            company_df = df[df["submitter_name"] == company]

            # Raw positions list
            positions = []
            for _, row in company_df.iterrows():
                positions.append({
                    "policy_ask": row["policy_ask"],
                    "ask_category": row["ask_category"],
                    "stance": row["stance"],
                    "primary_argument": row["primary_argument"],
                    "secondary_argument": row.get("secondary_argument"),
                    "supporting_quote": row["supporting_quote"],
                    "confidence": row["confidence"]
                })

            # Aggregate by category
            by_category = {}
            category_groups = company_df.groupby(["ask_category", "policy_ask", "stance"]).size().reset_index(name="count")
            for _, row in category_groups.iterrows():
                cat = row["ask_category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append({
                    "policy_ask": row["policy_ask"],
                    "stance": row["stance"],
                    "count": int(row["count"])
                })

            # Aggregate arguments
            arguments = company_df["primary_argument"].value_counts().to_dict()

            # China-specific framing
            china_positions = company_df[company_df["primary_argument"] == "china_competition"]
            china_framing = china_positions["policy_ask"].value_counts().to_dict() if len(china_positions) > 0 else {}

            # Top quotes by confidence
            top_quotes = company_df.nlargest(5, "confidence")[["policy_ask", "supporting_quote", "confidence"]].to_dict("records")

            positions_by_company[company] = {
                "positions": positions,
                "by_category": by_category,
                "arguments": {k: int(v) for k, v in arguments.items()},
                "china_framing": {k: int(v) for k, v in china_framing.items()},
                "sample_quotes": top_quotes
            }

        logger.info(f"Loaded positions for {len(positions_by_company)} companies")
        return positions_by_company

    except Exception as e:
        raise IcebergError(f"Failed to load positions: {e}")


def get_lobbying_by_company(catalog, filings_table_name: str,
                            activities_table_name: str) -> dict[str, dict]:
    """
    Load lobbying data and group by client_name.

    Returns:
        dict: {client_name: {
            "total_filings": int,
            "total_expenses": float,
            "activities": [{issue_code, description, count}],
            "years": [list of years]
        }}
    """
    try:
        # Load filings
        filings_table = catalog.load_table(filings_table_name)
        filings_df = filings_table.scan().to_arrow().to_pandas()

        # Load activities
        activities_table = catalog.load_table(activities_table_name)
        activities_df = activities_table.scan().to_arrow().to_pandas()

        # Join activities to filings
        merged = activities_df.merge(
            filings_df[["filing_uuid", "client_name", "expenses", "filing_year"]],
            on="filing_uuid",
            how="left"
        )

        lobbying_by_company = {}

        for client_name in merged["client_name"].unique():
            client_data = merged[merged["client_name"] == client_name]
            client_filings = filings_df[filings_df["client_name"] == client_name]

            # Aggregate activities by issue code
            activity_counts = client_data.groupby(
                ["issue_code", "issue_code_display"]
            ).agg({
                "description": lambda x: list(x.dropna().unique())[:3],  # Sample descriptions
                "filing_uuid": "count"
            }).reset_index()

            activities = []
            for _, row in activity_counts.iterrows():
                activities.append({
                    "issue_code": row["issue_code"],
                    "issue_name": row["issue_code_display"],
                    "times_lobbied": int(row["filing_uuid"]),
                    "sample_descriptions": row["description"]
                })

            lobbying_by_company[client_name] = {
                "total_filings": len(client_filings),
                "total_expenses": float(client_filings["expenses"].sum()),
                "years": sorted(client_filings["filing_year"].unique().tolist()),
                "activities": sorted(activities, key=lambda x: x["times_lobbied"], reverse=True)
            }

        logger.info(f"Loaded lobbying data for {len(lobbying_by_company)} companies")
        return lobbying_by_company

    except Exception as e:
        raise IcebergError(f"Failed to load lobbying data: {e}")


def normalize_submitter_name(name: str) -> str:
    """Normalize submitter name by removing common suffixes."""
    # Remove common suffixes from PDF filenames
    normalized = name.replace("-AI", "").replace("-ai", "")
    normalized = normalized.replace("AI-", "").replace("ai-", "")
    return normalized


def match_companies(positions: dict, lobbying: dict,
                    name_mapping: dict) -> list[dict]:
    """
    Match companies across positions and lobbying datasets.

    Args:
        positions: {submitter_name: [positions]}
        lobbying: {client_name: {lobbying_data}}
        name_mapping: {submitter_name: {"lda_name": ..., "type": ...}}

    Returns:
        list of matched company dicts with positions and lobbying data
    """
    matched = []

    for submitter_name, company_positions in positions.items():
        # Try direct match first, then normalized match
        normalized_name = normalize_submitter_name(submitter_name)

        mapping = None
        canonical_name = None

        # Check for direct match
        if submitter_name in name_mapping:
            mapping = name_mapping[submitter_name]
            canonical_name = submitter_name
        # Check for normalized match
        elif normalized_name in name_mapping:
            mapping = name_mapping[normalized_name]
            canonical_name = normalized_name
        else:
            # Try fuzzy match - check if any mapping key is contained in submitter_name
            for map_name, map_info in name_mapping.items():
                if map_name.lower() in submitter_name.lower():
                    mapping = map_info
                    canonical_name = map_name
                    break

        if mapping is None:
            logger.debug(f"No mapping for {submitter_name}")
            continue

        lda_name = mapping["lda_name"]

        # Find matching lobbying data - aggregate all matching client names
        lda_name_upper = lda_name.upper()
        matching_lobbying = None
        matched_client_names = []

        for client_name, lobbying_data in lobbying.items():
            client_upper = client_name.upper()
            # Match if LDA name is contained in client name OR exact match
            if lda_name_upper in client_upper or client_upper == lda_name_upper:
                matched_client_names.append(client_name)
                if matching_lobbying is None:
                    matching_lobbying = lobbying_data.copy()
                    matching_lobbying["matched_clients"] = [client_name]
                else:
                    # Aggregate multiple matching clients
                    matching_lobbying["total_filings"] += lobbying_data["total_filings"]
                    matching_lobbying["total_expenses"] += lobbying_data["total_expenses"]
                    matching_lobbying["years"] = sorted(set(matching_lobbying["years"]) | set(lobbying_data["years"]))
                    matching_lobbying["activities"].extend(lobbying_data["activities"])
                    matching_lobbying["matched_clients"].append(client_name)

        if matching_lobbying is None:
            logger.warning(f"No lobbying data found for {submitter_name} (LDA: {lda_name})")
            continue

        if len(matched_client_names) > 1:
            logger.info(f"  Aggregated {len(matched_client_names)} LDA clients for {canonical_name}")

        matched.append({
            "company_name": canonical_name,  # Use canonical name from config
            "company_type": mapping["type"],
            "positions": company_positions,
            "lobbying": matching_lobbying
        })

    logger.info(f"Matched {len(matched)} companies with both positions and lobbying data")
    return matched


def format_positions_by_category(by_category: dict) -> str:
    """Format positions by category for prompt."""
    lines = []
    for category, asks in sorted(by_category.items()):
        lines.append(f"\n{category.upper()}:")
        for ask in sorted(asks, key=lambda x: x["count"], reverse=True):
            lines.append(f"  - {ask['policy_ask']}: {ask['stance']} (x{ask['count']})")
    return "\n".join(lines) if lines else "No positions found"


def format_arguments_summary(arguments: dict) -> str:
    """Format argument counts for prompt."""
    lines = []
    for arg, count in sorted(arguments.items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"  - {arg}: {count}")
    return "\n".join(lines) if lines else "No arguments found"


def format_china_framing(china_framing: dict) -> str:
    """Format China competition framing for prompt."""
    if not china_framing:
        return "Not used"
    total = sum(china_framing.values())
    lines = [f"Used {total} times to support:"]
    for ask, count in sorted(china_framing.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  - {ask}: {count}")
    return "\n".join(lines)


def format_sample_quotes(quotes: list) -> str:
    """Format sample quotes for prompt."""
    lines = []
    for q in quotes[:5]:
        quote_text = q["supporting_quote"][:150] + "..." if len(q["supporting_quote"]) > 150 else q["supporting_quote"]
        lines.append(f"  [{q['policy_ask']}] \"{quote_text}\"")
    return "\n".join(lines) if lines else "No quotes available"


def format_lobbying_by_issue(activities: list) -> str:
    """Format lobbying activities by issue code for prompt."""
    lines = []
    for act in sorted(activities, key=lambda x: x["times_lobbied"], reverse=True)[:10]:
        lines.append(f"  - {act['issue_name']} ({act['issue_code']}): {act['times_lobbied']} filings")
        if act.get("sample_descriptions"):
            for desc in act["sample_descriptions"][:2]:
                if desc:
                    desc_short = desc[:100] + "..." if len(desc) > 100 else desc
                    lines.append(f"      \"{desc_short}\"")
    return "\n".join(lines) if lines else "No lobbying activity found"


def call_lobbying_impact_api(client: anthropic.Anthropic, company_name: str,
                              company_type: str, positions_data: dict, lobbying: dict) -> dict:
    """
    Call Claude API to assess lobbying impact on public interest.

    Args:
        positions_data: Structured positions dict with by_category, arguments, china_framing, sample_quotes
        lobbying: Lobbying data with total_filings, total_expenses, years, activities

    Returns:
        dict with concern_score, lobbying_agenda_summary, public_interest_concerns, etc.
    """
    # Format structured data for prompt
    positions_by_category = format_positions_by_category(positions_data.get("by_category", {}))
    arguments_summary = format_arguments_summary(positions_data.get("arguments", {}))
    china_framing_summary = format_china_framing(positions_data.get("china_framing", {}))
    sample_quotes = format_sample_quotes(positions_data.get("sample_quotes", []))
    lobbying_by_issue = format_lobbying_by_issue(lobbying.get("activities", []))

    prompt = LOBBYING_IMPACT_PROMPT.format(
        company_name=company_name,
        company_type=company_type,
        positions_by_category=positions_by_category,
        arguments_summary=arguments_summary,
        china_framing_summary=china_framing_summary,
        sample_quotes=sample_quotes,
        total_filings=lobbying.get("total_filings", 0),
        total_expenses=lobbying.get("total_expenses", 0),
        years_active=", ".join(str(y) for y in lobbying.get("years", [])),
        lobbying_by_issue=lobbying_by_issue
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON - handle various response formats
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                if "\n" in response_text[start:start+20]:
                    start = response_text.find("\n", start) + 1
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()

            # If response starts with text before JSON object, find the object
            if not response_text.startswith("{"):
                brace_pos = response_text.find("{")
                if brace_pos > 0:
                    response_text = response_text[brace_pos:]

            result = json.loads(response_text)

            # Validate required fields
            if "concern_score" not in result:
                raise LLMScoringError("Missing concern_score in response")

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
            logger.warning(f"Response was: {response_text[:500]}...")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMScoringError(f"Failed to parse JSON after {MAX_RETRIES} attempts")

        except anthropic.APIError as e:
            logger.warning(f"API error on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMScoringError(f"API failed after {MAX_RETRIES} attempts: {e}")


def score_discrepancies(
    limit: Optional[int] = None,
    dry_run: bool = False,
    fresh: bool = False
) -> dict:
    """
    Score discrepancies for all matched companies.

    Args:
        limit: Max number of companies to process (None = all)
        dry_run: If True, don't call API or write to Iceberg
        fresh: If True, reprocess all companies (ignore existing scores)

    Returns:
        dict with keys: companies_processed, errors
    """
    # Get API key
    api_key = get_required_env('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    # Get table names
    tables = get_table_names()
    logger.info(f"Tables: {tables}")

    # Initialize catalog
    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Get already processed companies (for idempotency) - skip if fresh
    if fresh:
        # Drop existing table for clean reprocessing
        try:
            catalog.drop_table(tables["scores"])
            logger.info(f"Fresh mode: dropped existing table {tables['scores']}")
        except Exception:
            logger.info("Fresh mode: no existing table to drop")
        processed_companies = set()
    else:
        processed_companies = get_processed_companies(catalog, tables["scores"])
        logger.info(f"Already processed: {len(processed_companies)} companies")

    # Load data
    positions = get_positions_by_company(catalog, tables["positions"])
    lobbying = get_lobbying_by_company(catalog, tables["filings"], tables["activities"])

    # Get company name mapping
    name_mapping = get_company_name_mapping()

    # Match companies
    matched = match_companies(positions, lobbying, name_mapping)

    # Filter out already processed
    unprocessed = [m for m in matched if m["company_name"] not in processed_companies]
    logger.info(f"Found {len(unprocessed)} unprocessed companies out of {len(matched)} matched")

    if not unprocessed:
        logger.info("No unprocessed companies found - nothing to do")
        return {"companies_processed": 0, "errors": []}

    # Apply limit
    if limit:
        unprocessed = unprocessed[:limit]
        logger.info(f"Limited to {len(unprocessed)} companies")

    if dry_run:
        logger.info(f"DRY RUN: Would process {len(unprocessed)} companies:")
        for m in unprocessed:
            pos_data = m['positions']
            pos_count = len(pos_data.get('positions', []))
            china_count = sum(pos_data.get('china_framing', {}).values())
            logger.info(f"  - {m['company_name']} ({m['company_type']}): "
                       f"{pos_count} positions, {china_count} china-framed, "
                       f"{m['lobbying']['total_filings']} filings")
        return {"companies_processed": 0, "errors": [], "dry_run": True,
                "would_process": [m["company_name"] for m in unprocessed]}

    # Process companies
    score_records = []
    errors = []
    processed_at = datetime.now()

    for i, company_data in enumerate(unprocessed):
        company_name = company_data["company_name"]
        logger.info(f"Scoring {i + 1}/{len(unprocessed)}: {company_name}")

        try:
            result = call_lobbying_impact_api(
                client,
                company_name,
                company_data["company_type"],
                company_data["positions"],
                company_data["lobbying"]
            )

            score_id = f"{company_name}_{processed_at.strftime('%Y%m%d%H%M%S')}"
            pos_data = company_data["positions"]

            score_records.append({
                "score_id": score_id,
                "company_name": company_name,
                "company_type": company_data["company_type"],
                "concern_score": int(result.get("concern_score", 0)),
                "lobbying_agenda_summary": result.get("lobbying_agenda_summary", ""),
                "top_concerning_policy_asks": json.dumps(result.get("top_concerning_policy_asks", [])),
                "public_interest_concerns": json.dumps(result.get("public_interest_concerns", [])),
                "regulatory_capture_signals": json.dumps(result.get("regulatory_capture_signals", [])),
                "china_rhetoric_assessment": json.dumps(result.get("china_rhetoric_assessment", {})),
                "accountability_stance": json.dumps(result.get("accountability_stance", {})),
                "positive_aspects": json.dumps(result.get("positive_aspects", [])),
                "key_flags": json.dumps(result.get("key_flags", [])),
                "positions_count": len(pos_data.get("positions", [])),
                "lobbying_filings_count": company_data["lobbying"]["total_filings"],
                "model": MODEL,
                "processed_at": processed_at
            })

            logger.info(f"  Concern Score: {result.get('concern_score')}/100")

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        except LLMScoringError as e:
            error_msg = f"Failed to score {company_name}: {e}"
            logger.error(error_msg)
            errors.append({"company": company_name, "error": str(e)})
            continue

    logger.info(f"Scored {len(score_records)} companies")

    if not score_records:
        logger.warning("No scores generated - nothing to write")
        return {"companies_processed": len(unprocessed), "scores_written": 0, "errors": errors}

    # Define schema - lobbying impact assessment (v2 with taxonomy)
    scores_schema = Schema(
        NestedField(1, "score_id", StringType(), required=True),
        NestedField(2, "company_name", StringType(), required=False),
        NestedField(3, "company_type", StringType(), required=False),
        NestedField(4, "concern_score", IntegerType(), required=False),
        NestedField(5, "lobbying_agenda_summary", StringType(), required=False),
        NestedField(6, "top_concerning_policy_asks", StringType(), required=False),
        NestedField(7, "public_interest_concerns", StringType(), required=False),
        NestedField(8, "regulatory_capture_signals", StringType(), required=False),
        NestedField(9, "china_rhetoric_assessment", StringType(), required=False),
        NestedField(10, "accountability_stance", StringType(), required=False),
        NestedField(11, "positive_aspects", StringType(), required=False),
        NestedField(12, "key_flags", StringType(), required=False),
        NestedField(13, "positions_count", IntegerType(), required=False),
        NestedField(14, "lobbying_filings_count", IntegerType(), required=False),
        NestedField(15, "model", StringType(), required=False),
        NestedField(16, "processed_at", TimestampType(), required=False)
    )

    pa_schema = pa.schema([
        pa.field("score_id", pa.string(), nullable=False),
        pa.field("company_name", pa.string(), nullable=True),
        pa.field("company_type", pa.string(), nullable=True),
        pa.field("concern_score", pa.int32(), nullable=True),
        pa.field("lobbying_agenda_summary", pa.string(), nullable=True),
        pa.field("top_concerning_policy_asks", pa.string(), nullable=True),
        pa.field("public_interest_concerns", pa.string(), nullable=True),
        pa.field("regulatory_capture_signals", pa.string(), nullable=True),
        pa.field("china_rhetoric_assessment", pa.string(), nullable=True),
        pa.field("accountability_stance", pa.string(), nullable=True),
        pa.field("positive_aspects", pa.string(), nullable=True),
        pa.field("key_flags", pa.string(), nullable=True),
        pa.field("positions_count", pa.int32(), nullable=True),
        pa.field("lobbying_filings_count", pa.int32(), nullable=True),
        pa.field("model", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    # Convert to PyArrow
    pa_table = pa.Table.from_pylist(score_records, schema=pa_schema)

    # Write to Iceberg (APPEND for incremental)
    try:
        try:
            iceberg_table = catalog.load_table(tables["scores"])
            logger.info(f"Table {tables['scores']} exists - appending")
        except Exception:
            iceberg_table = catalog.create_table(
                identifier=tables["scores"],
                schema=scores_schema
            )
            logger.info(f"Created table {tables['scores']}")

        iceberg_table.append(pa_table)
        logger.info(f"Appended {len(score_records)} scores to {tables['scores']}")

    except Exception as e:
        raise IcebergError(f"Failed to write scores: {e}")

    return {
        "companies_processed": len(unprocessed),
        "scores_written": len(score_records),
        "errors": errors,
        "table": tables["scores"]
    }


if __name__ == "__main__":
    load_dotenv()

    # Parse args
    limit = None
    dry_run = False
    fresh = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--fresh":
            fresh = True
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.isdigit():
            limit = int(arg)

    try:
        result = score_discrepancies(limit=limit, dry_run=dry_run, fresh=fresh)
        logger.info(f"Scoring complete: {result}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except IcebergError as e:
        logger.error(f"Iceberg error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
