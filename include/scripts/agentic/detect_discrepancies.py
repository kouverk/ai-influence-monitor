"""
Detect discrepancies between public policy positions and lobbying activity.

This script systematically compares what companies SAY (from AI Action Plan submissions)
vs what they DO (from Senate LDA lobbying disclosures) to find contradictions.

Unlike assess_lobbying_impact.py which asks "is this concerning?", this script asks
"are they being hypocritical?" - a more specific and actionable question.

Pipeline:
1. Reads structured positions from ai_positions (with taxonomy codes)
2. Reads lobbying from lda_filings + lda_activities
3. Maps policy_ask codes to LDA issue codes
4. Sends paired data to Claude API for discrepancy analysis
5. Writes findings to discrepancy_scores table

Tables:
- Reads from: {schema}.ai_positions
- Reads from: {schema}.lda_filings, {schema}.lda_activities
- Writes to: {schema}.discrepancy_scores

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


# Mapping from policy_ask codes to relevant LDA issue codes
POLICY_TO_LDA_MAPPING = {
    # Regulatory structure
    "federal_preemption": ["CPI", "SCI", "CSP"],  # Computer, Science, Consumer Safety
    "state_autonomy": ["CPI", "SCI", "CSP"],
    "new_federal_agency": ["GOV", "SCI"],  # Government Issues
    "existing_agency_authority": ["GOV", "SCI", "CPI"],
    "self_regulation": ["CPI", "SCI"],
    "international_harmonization": ["TRD", "SCI"],  # Trade

    # Accountability
    "liability_shield": ["CPI", "CSP", "LAW"],  # Law Enforcement/Crime
    "liability_framework": ["CPI", "CSP", "LAW"],
    "mandatory_audits": ["CPI", "SCI", "GOV"],
    "voluntary_commitments": ["CPI", "SCI"],
    "transparency_requirements": ["CPI", "SCI", "CSP"],
    "incident_reporting": ["CPI", "SCI", "HOM"],  # Homeland Security

    # Intellectual property
    "training_data_fair_use": ["CPT", "CPI"],  # Copyright/Patent
    "creator_compensation": ["CPT"],
    "model_weight_protection": ["CPT", "TRD"],
    "open_source_mandate": ["CPI", "SCI"],
    "open_source_protection": ["CPI", "SCI"],

    # National security
    "export_controls_strict": ["DEF", "TRD", "INT"],  # Defense, Trade, Intelligence
    "export_controls_loose": ["DEF", "TRD", "INT"],
    "china_competition_frame": ["DEF", "TRD", "INT", "SCI"],
    "government_ai_adoption": ["GOV", "DEF", "SCI"],
    "defense_ai_investment": ["DEF", "BUD"],  # Budget

    # Resources
    "research_funding": ["SCI", "BUD", "EDU"],  # Education
    "compute_infrastructure": ["SCI", "ENG"],  # Energy
    "energy_infrastructure": ["ENG", "SCI"],
    "immigration_reform": ["IMM", "LBR"],  # Immigration, Labor
    "workforce_training": ["LBR", "EDU"],
}


DISCREPANCY_PROMPT = """
Analyze whether this company's lobbying activity is consistent with their public policy positions.

<company>{company_name} ({company_type})</company>

<what_they_say>
Policy positions from their AI Action Plan submission (grouped by category):

{positions_summary}

Key arguments they use:
{arguments_summary}
</what_they_say>

<what_they_do>
Lobbying activity from Senate LDA filings:
- Total filings: {total_filings}
- Total expenses: ${total_expenses:,.0f}
- Years: {years_active}

By issue area (with sample lobbying descriptions):
{lobbying_summary}
</what_they_do>

<mapping_context>
How their policy positions relate to lobbying issue codes:
{mapping_context}
</mapping_context>

Systematically compare WHAT THEY SAY vs WHAT THEY DO. Look for:

1. SAY BUT DON'T DO: Positions they claim to support but don't lobby for
2. DO BUT DON'T SAY: Heavy lobbying in areas not mentioned in public positions
3. SAY ONE THING, DO ANOTHER: Direct contradictions between stated positions and lobbying
4. RHETORICAL COVER: Using arguments (like "China threat") to justify positions that benefit them

Return JSON:

{{
  "discrepancy_score": <0-100, where 0=fully consistent, 100=complete hypocrite. Use the FULL range with precision - scores like 23, 47, 68, 81 are valid. Avoid rounding to multiples of 5 or 25.>,

  "discrepancies": [
    {{
      "type": "<say_but_dont_do|do_but_dont_say|say_one_thing_do_another|rhetorical_cover>",
      "policy_ask": "<the policy position code>",
      "stated_position": "<what they said>",
      "lobbying_reality": "<what their lobbying shows>",
      "interpretation": "<why this is a discrepancy>",
      "severity": "<minor|moderate|significant|major>"
    }}
  ],

  "consistent_areas": [
    {{
      "policy_ask": "<policy position code>",
      "evidence": "<how lobbying supports their stated position>"
    }}
  ],

  "lobbying_priorities_vs_rhetoric": {{
    "top_lobbying_areas": ["<issue codes they lobby most on>"],
    "top_stated_priorities": ["<policy asks they emphasize most>"],
    "alignment_assessment": "<are their lobbying dollars going where their mouth is?>"
  }},

  "china_rhetoric_analysis": {{
    "times_invoked": <count>,
    "used_to_justify": ["<policy asks where China is used as argument>"],
    "appears_genuine": <true|false>,
    "explanation": "<is the China framing substantive or rhetorical cover?>"
  }},

  "accountability_contradiction": {{
    "claims_to_want_oversight": <true|false>,
    "lobbying_supports_oversight": <true|false>,
    "explanation": "<do they actually lobby for accountability measures?>"
  }},

  "key_finding": "<1-2 sentence summary of the most important discrepancy or consistency>"
}}

Scoring guide:
- 0-20: Highly consistent - lobbying aligns with stated positions
- 21-40: Mostly consistent with minor gaps
- 41-60: Mixed - some contradictions but also consistency
- 61-80: Significant discrepancies - lobbying often contradicts rhetoric
- 81-100: Major hypocrisy - says one thing, lobbies for opposite

Be specific. Quote their positions and lobbying activities when identifying discrepancies.

Return ONLY valid JSON.
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
        "discrepancies": f"{schema}.discrepancy_scores",
    }


def get_processed_companies(catalog, table_name: str) -> set:
    """Get set of companies that have already been scored."""
    try:
        table = catalog.load_table(table_name)
        scan = table.scan(selected_fields=("company_name",))
        df = scan.to_arrow().to_pandas()
        return set(df["company_name"].unique())
    except Exception as e:
        logger.info(f"No existing scores found (this is fine for first run): {e}")
        return set()


def get_positions_by_company(catalog, positions_table_name: str) -> dict[str, dict]:
    """Load positions grouped by company with structured aggregation."""
    try:
        table = catalog.load_table(positions_table_name)
        df = table.scan().to_arrow().to_pandas()

        positions_by_company = {}
        for company in df["submitter_name"].unique():
            company_df = df[df["submitter_name"] == company]

            # Aggregate by category and policy_ask
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

            # China framing
            china_positions = company_df[company_df["primary_argument"] == "china_competition"]
            china_framing = china_positions["policy_ask"].value_counts().to_dict() if len(china_positions) > 0 else {}

            # Sample quotes
            quotes = company_df.nlargest(5, "confidence")[["policy_ask", "supporting_quote"]].to_dict("records")

            positions_by_company[company] = {
                "by_category": by_category,
                "arguments": {k: int(v) for k, v in arguments.items()},
                "china_framing": {k: int(v) for k, v in china_framing.items()},
                "quotes": quotes,
                "total_positions": len(company_df)
            }

        logger.info(f"Loaded positions for {len(positions_by_company)} companies")
        return positions_by_company

    except Exception as e:
        raise IcebergError(f"Failed to load positions: {e}")


def get_lobbying_by_company(catalog, filings_table_name: str,
                            activities_table_name: str) -> dict[str, dict]:
    """Load lobbying data grouped by client_name."""
    try:
        filings_table = catalog.load_table(filings_table_name)
        filings_df = filings_table.scan().to_arrow().to_pandas()

        activities_table = catalog.load_table(activities_table_name)
        activities_df = activities_table.scan().to_arrow().to_pandas()

        merged = activities_df.merge(
            filings_df[["filing_uuid", "client_name", "expenses", "filing_year"]],
            on="filing_uuid",
            how="left"
        )

        lobbying_by_company = {}

        for client_name in merged["client_name"].unique():
            client_data = merged[merged["client_name"] == client_name]
            client_filings = filings_df[filings_df["client_name"] == client_name]

            # Aggregate by issue code
            activity_counts = client_data.groupby(
                ["issue_code", "issue_code_display"]
            ).agg({
                "description": lambda x: list(x.dropna().unique())[:3],
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


def match_companies(positions: dict, lobbying: dict, name_mapping: dict) -> list[dict]:
    """Match companies across datasets using config mapping."""
    matched = []

    for submitter_name, pos_data in positions.items():
        # Normalize name
        normalized = submitter_name.replace("-AI", "").replace("-ai", "")

        mapping = None
        canonical_name = None

        if submitter_name in name_mapping:
            mapping = name_mapping[submitter_name]
            canonical_name = submitter_name
        elif normalized in name_mapping:
            mapping = name_mapping[normalized]
            canonical_name = normalized
        else:
            for map_name, map_info in name_mapping.items():
                if map_name.lower() in submitter_name.lower():
                    mapping = map_info
                    canonical_name = map_name
                    break

        if mapping is None:
            continue

        lda_name = mapping["lda_name"].upper()
        matching_lobbying = None

        for client_name, lobbying_data in lobbying.items():
            if lda_name in client_name.upper():
                if matching_lobbying is None:
                    matching_lobbying = lobbying_data.copy()
                else:
                    matching_lobbying["total_filings"] += lobbying_data["total_filings"]
                    matching_lobbying["total_expenses"] += lobbying_data["total_expenses"]
                    matching_lobbying["activities"].extend(lobbying_data["activities"])

        if matching_lobbying is None:
            continue

        matched.append({
            "company_name": canonical_name,
            "company_type": mapping["type"],
            "positions": pos_data,
            "lobbying": matching_lobbying
        })

    logger.info(f"Matched {len(matched)} companies")
    return matched


def format_positions_summary(by_category: dict) -> str:
    """Format positions by category."""
    lines = []
    for category, asks in sorted(by_category.items()):
        lines.append(f"\n{category.upper()}:")
        for ask in sorted(asks, key=lambda x: x["count"], reverse=True):
            lines.append(f"  - {ask['policy_ask']}: {ask['stance']} (x{ask['count']})")
    return "\n".join(lines) if lines else "No positions found"


def format_arguments_summary(arguments: dict) -> str:
    """Format argument usage."""
    lines = []
    for arg, count in sorted(arguments.items(), key=lambda x: x[1], reverse=True)[:8]:
        lines.append(f"  - {arg}: {count} times")
    return "\n".join(lines) if lines else "No arguments"


def format_lobbying_summary(activities: list) -> str:
    """Format lobbying activities."""
    lines = []
    for act in sorted(activities, key=lambda x: x["times_lobbied"], reverse=True)[:10]:
        lines.append(f"\n{act['issue_name']} ({act['issue_code']}): {act['times_lobbied']} filings")
        for desc in act.get("sample_descriptions", [])[:2]:
            if desc:
                lines.append(f"    \"{desc[:120]}...\"" if len(desc) > 120 else f"    \"{desc}\"")
    return "\n".join(lines) if lines else "No lobbying activity"


def format_mapping_context(by_category: dict, activities: list) -> str:
    """Create context about how policy positions map to lobbying codes."""
    lines = []
    lda_codes = {a["issue_code"] for a in activities}

    for category, asks in by_category.items():
        for ask in asks:
            policy_ask = ask["policy_ask"]
            if policy_ask in POLICY_TO_LDA_MAPPING:
                relevant_codes = POLICY_TO_LDA_MAPPING[policy_ask]
                matched = [c for c in relevant_codes if c in lda_codes]
                if matched:
                    lines.append(f"  {policy_ask} → lobbied on: {', '.join(matched)}")
                else:
                    lines.append(f"  {policy_ask} → NO matching lobbying found (expected: {', '.join(relevant_codes)})")

    return "\n".join(lines) if lines else "No mapping context"


def call_discrepancy_api(client: anthropic.Anthropic, company_name: str,
                          company_type: str, positions: dict, lobbying: dict) -> dict:
    """Call Claude API to detect discrepancies."""

    positions_summary = format_positions_summary(positions.get("by_category", {}))
    arguments_summary = format_arguments_summary(positions.get("arguments", {}))
    lobbying_summary = format_lobbying_summary(lobbying.get("activities", []))
    mapping_context = format_mapping_context(
        positions.get("by_category", {}),
        lobbying.get("activities", [])
    )

    prompt = DISCREPANCY_PROMPT.format(
        company_name=company_name,
        company_type=company_type,
        positions_summary=positions_summary,
        arguments_summary=arguments_summary,
        total_filings=lobbying.get("total_filings", 0),
        total_expenses=lobbying.get("total_expenses", 0),
        years_active=", ".join(str(y) for y in lobbying.get("years", [])),
        lobbying_summary=lobbying_summary,
        mapping_context=mapping_context
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON
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

            if not response_text.startswith("{"):
                brace_pos = response_text.find("{")
                if brace_pos > 0:
                    response_text = response_text[brace_pos:]

            result = json.loads(response_text)

            if "discrepancy_score" not in result:
                raise LLMScoringError("Missing discrepancy_score in response")

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
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


def detect_discrepancies(
    limit: Optional[int] = None,
    dry_run: bool = False,
    fresh: bool = False
) -> dict:
    """
    Detect discrepancies for all matched companies.

    Args:
        limit: Max companies to process
        dry_run: If True, don't call API or write
        fresh: If True, drop existing table and reprocess all
    """
    api_key = get_required_env('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    tables = get_table_names()
    logger.info(f"Tables: {tables}")

    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Handle fresh mode
    if fresh:
        try:
            catalog.drop_table(tables["discrepancies"])
            logger.info(f"Dropped table {tables['discrepancies']}")
        except Exception:
            pass
        processed_companies = set()
    else:
        processed_companies = get_processed_companies(catalog, tables["discrepancies"])
    logger.info(f"Already processed: {len(processed_companies)} companies")

    # Load data
    positions = get_positions_by_company(catalog, tables["positions"])
    lobbying = get_lobbying_by_company(catalog, tables["filings"], tables["activities"])

    # Match
    name_mapping = get_company_name_mapping()
    matched = match_companies(positions, lobbying, name_mapping)

    # Filter
    unprocessed = [m for m in matched if m["company_name"] not in processed_companies]
    logger.info(f"Found {len(unprocessed)} unprocessed companies")

    if not unprocessed:
        return {"companies_processed": 0, "errors": []}

    if limit:
        unprocessed = unprocessed[:limit]

    if dry_run:
        logger.info(f"DRY RUN: Would process {len(unprocessed)} companies:")
        for m in unprocessed:
            china_count = sum(m['positions'].get('china_framing', {}).values())
            logger.info(f"  - {m['company_name']}: {m['positions']['total_positions']} positions, "
                       f"{china_count} china-framed, {m['lobbying']['total_filings']} filings")
        return {"dry_run": True, "would_process": [m["company_name"] for m in unprocessed]}

    # Process
    records = []
    errors = []
    processed_at = datetime.now()

    for i, company_data in enumerate(unprocessed):
        company_name = company_data["company_name"]
        logger.info(f"Analyzing {i + 1}/{len(unprocessed)}: {company_name}")

        try:
            result = call_discrepancy_api(
                client,
                company_name,
                company_data["company_type"],
                company_data["positions"],
                company_data["lobbying"]
            )

            score_id = f"{company_name}_{processed_at.strftime('%Y%m%d%H%M%S')}"

            records.append({
                "score_id": score_id,
                "company_name": company_name,
                "company_type": company_data["company_type"],
                "discrepancy_score": int(result.get("discrepancy_score", 0)),
                "discrepancies": json.dumps(result.get("discrepancies", [])),
                "consistent_areas": json.dumps(result.get("consistent_areas", [])),
                "lobbying_priorities_vs_rhetoric": json.dumps(result.get("lobbying_priorities_vs_rhetoric", {})),
                "china_rhetoric_analysis": json.dumps(result.get("china_rhetoric_analysis", {})),
                "accountability_contradiction": json.dumps(result.get("accountability_contradiction", {})),
                "key_finding": result.get("key_finding", ""),
                "positions_count": company_data["positions"]["total_positions"],
                "lobbying_filings_count": company_data["lobbying"]["total_filings"],
                "model": MODEL,
                "processed_at": processed_at
            })

            logger.info(f"  Discrepancy Score: {result.get('discrepancy_score')}/100")
            logger.info(f"  Key Finding: {result.get('key_finding', '')[:100]}...")

            time.sleep(REQUEST_DELAY)

        except LLMScoringError as e:
            logger.error(f"Failed to analyze {company_name}: {e}")
            errors.append({"company": company_name, "error": str(e)})

    if not records:
        return {"companies_processed": len(unprocessed), "scores_written": 0, "errors": errors}

    # Define schema
    schema = Schema(
        NestedField(1, "score_id", StringType(), required=True),
        NestedField(2, "company_name", StringType(), required=False),
        NestedField(3, "company_type", StringType(), required=False),
        NestedField(4, "discrepancy_score", IntegerType(), required=False),
        NestedField(5, "discrepancies", StringType(), required=False),
        NestedField(6, "consistent_areas", StringType(), required=False),
        NestedField(7, "lobbying_priorities_vs_rhetoric", StringType(), required=False),
        NestedField(8, "china_rhetoric_analysis", StringType(), required=False),
        NestedField(9, "accountability_contradiction", StringType(), required=False),
        NestedField(10, "key_finding", StringType(), required=False),
        NestedField(11, "positions_count", IntegerType(), required=False),
        NestedField(12, "lobbying_filings_count", IntegerType(), required=False),
        NestedField(13, "model", StringType(), required=False),
        NestedField(14, "processed_at", TimestampType(), required=False)
    )

    pa_schema = pa.schema([
        pa.field("score_id", pa.string(), nullable=False),
        pa.field("company_name", pa.string(), nullable=True),
        pa.field("company_type", pa.string(), nullable=True),
        pa.field("discrepancy_score", pa.int32(), nullable=True),
        pa.field("discrepancies", pa.string(), nullable=True),
        pa.field("consistent_areas", pa.string(), nullable=True),
        pa.field("lobbying_priorities_vs_rhetoric", pa.string(), nullable=True),
        pa.field("china_rhetoric_analysis", pa.string(), nullable=True),
        pa.field("accountability_contradiction", pa.string(), nullable=True),
        pa.field("key_finding", pa.string(), nullable=True),
        pa.field("positions_count", pa.int32(), nullable=True),
        pa.field("lobbying_filings_count", pa.int32(), nullable=True),
        pa.field("model", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    pa_table = pa.Table.from_pylist(records, schema=pa_schema)

    try:
        try:
            iceberg_table = catalog.load_table(tables["discrepancies"])
            logger.info(f"Table exists - appending")
        except Exception:
            iceberg_table = catalog.create_table(
                identifier=tables["discrepancies"],
                schema=schema
            )
            logger.info(f"Created table {tables['discrepancies']}")

        iceberg_table.append(pa_table)
        logger.info(f"Wrote {len(records)} discrepancy scores")

    except Exception as e:
        raise IcebergError(f"Failed to write: {e}")

    return {
        "companies_processed": len(unprocessed),
        "scores_written": len(records),
        "errors": errors
    }


if __name__ == "__main__":
    load_dotenv()

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
        result = detect_discrepancies(limit=limit, dry_run=dry_run, fresh=fresh)
        logger.info(f"Complete: {result}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except IcebergError as e:
        logger.error(f"Iceberg error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
