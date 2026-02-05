"""
Analyze China competition rhetoric in AI policy positions.

This script does a deep-dive on the 55+ positions using china_competition as an argument.
It examines:
- What types of claims are being made (capability, regulatory, security, vague)
- Which policy asks the China argument supports
- Whether claims are verifiable or unfalsifiable
- How usage differs across company types

Pipeline:
1. Loads positions with china_competition argument from ai_positions
2. Groups by company for context
3. Sends to Claude for detailed rhetoric analysis
4. Writes findings to china_rhetoric_analysis table

Tables:
- Reads from: {schema}.ai_positions
- Writes to: {schema}.china_rhetoric_analysis
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
from config import get_company_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMAnalysisError(Exception):
    """Raised when LLM analysis fails."""
    pass


class IcebergError(Exception):
    """Raised when Iceberg operations fail."""
    pass


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


# Rate limiting
REQUEST_DELAY = 1.0
MAX_RETRIES = 3
RETRY_DELAY = 5.0

# Model configuration
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


CHINA_RHETORIC_PROMPT = """
Analyze how this company uses "China competition" framing in their AI policy arguments.

<company>{company_name} ({company_type})</company>

<positions_using_china_argument>
These are their policy positions that use China competition as an argument:

{china_positions_json}
</positions_using_china_argument>

<all_company_positions>
For context, here are ALL their policy positions (including non-China arguments):
Total positions: {total_positions}
By category: {positions_by_category}
Other arguments used: {other_arguments}
</all_company_positions>

Analyze their China rhetoric and return JSON:

{{
  "rhetoric_intensity": <0-100 - how heavily they lean on China framing. Use the FULL range with precision - scores like 23, 47, 68, 81 are valid. Avoid rounding to multiples of 5 or 25.>,

  "claim_categorization": [
    {{
      "policy_ask": "<the policy they're advocating>",
      "claim_type": "<capability_claim|regulatory_comparison|security_framing|economic_threat|vague_warning>",
      "specific_claim": "<what exactly they claim about China>",
      "verifiable": <true|false - could this claim be fact-checked?>,
      "quote": "<their exact words>"
    }}
  ],

  "rhetoric_patterns": {{
    "uses_specific_evidence": <true|false>,
    "cites_sources": <true|false>,
    "makes_timeline_claims": <true|false - e.g., "China will surpass us by 2025">,
    "invokes_national_security": <true|false>,
    "suggests_existential_stakes": <true|false>
  }},

  "policy_asks_supported_by_china_frame": [
    {{
      "policy_ask": "<code>",
      "how_china_argument_supports": "<how the China frame justifies this policy>"
    }}
  ],

  "rhetoric_assessment": {{
    "substantive_vs_rhetorical": "<substantive|mostly_rhetorical|purely_rhetorical>",
    "reasoning": "<why you assessed it this way>",
    "red_flags": ["<any concerning patterns>"]
  }},

  "comparison_to_other_arguments": {{
    "china_vs_other_ratio": "<X% of their arguments invoke China>",
    "unique_to_china_positions": "<policy asks they ONLY support via China framing>",
    "also_use_other_arguments": "<policy asks where China is one of multiple arguments>"
  }},

  "notable_quotes": [
    {{
      "quote": "<memorable/notable quote>",
      "why_notable": "<why this stands out>"
    }}
  ],

  "key_finding": "<1-2 sentence summary of their China rhetoric strategy>"
}}

ANALYSIS GUIDELINES:
- Claim types:
  - capability_claim: "China is ahead in X technology"
  - regulatory_comparison: "China has less regulation so they move faster"
  - security_framing: "China will use AI against us"
  - economic_threat: "China will dominate the AI market"
  - vague_warning: "We can't fall behind China" without specifics

- Verifiability: A claim is verifiable if it could theoretically be fact-checked
  - Verifiable: "China has more AI researchers" (can check numbers)
  - Unverifiable: "China will win the AI race" (undefined terms)

- Be skeptical: Companies may use China framing as rhetorical cover for self-interested policies
"""


def get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.environ.get(key)
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {key}")
    return value


def get_table_names() -> dict:
    """Get table names using SCHEMA env var."""
    schema = get_required_env('SCHEMA')
    return {
        "positions": f"{schema}.ai_positions",
        "analysis": f"{schema}.china_rhetoric_analysis"
    }


def get_catalog():
    """Initialize PyIceberg catalog."""
    aws_region = get_required_env('AWS_DEFAULT_REGION')
    s3_bucket = get_required_env('AWS_S3_BUCKET_TABULAR')

    return load_catalog(
        "glue",
        **{
            "type": "glue",
            "glue.region": aws_region,
            "s3.region": aws_region,
            "warehouse": f"s3://{s3_bucket}/warehouse"
        }
    )


def get_processed_companies(catalog, table_name: str) -> set:
    """Get companies already analyzed."""
    try:
        table = catalog.load_table(table_name)
        scan = table.scan(selected_fields=("company_name",))
        df = scan.to_arrow().to_pandas()
        return set(df["company_name"].unique())
    except Exception as e:
        logger.info(f"No existing analysis found: {e}")
        return set()


def get_china_positions_by_company(catalog, positions_table: str) -> dict:
    """
    Load positions and group by company, focusing on china_competition argument.

    Returns:
        dict: {company_name: {
            "china_positions": [positions using china_competition],
            "all_positions": [all positions],
            "total_positions": int,
            "by_category": {category: count},
            "other_arguments": {arg: count}
        }}
    """
    try:
        table = catalog.load_table(positions_table)
        df = table.scan().to_arrow().to_pandas()

        positions_by_company = {}

        for company in df["submitter_name"].unique():
            company_df = df[df["submitter_name"] == company]

            # Get China-specific positions
            china_df = company_df[company_df["primary_argument"] == "china_competition"]

            # Skip companies with no China rhetoric
            if len(china_df) == 0:
                continue

            china_positions = []
            for _, row in china_df.iterrows():
                china_positions.append({
                    "policy_ask": row["policy_ask"],
                    "ask_category": row["ask_category"],
                    "stance": row["stance"],
                    "target": row.get("target"),
                    "secondary_argument": row.get("secondary_argument"),
                    "supporting_quote": row["supporting_quote"],
                    "confidence": row["confidence"]
                })

            # Aggregate all positions by category
            by_category = company_df.groupby("ask_category").size().to_dict()

            # Other arguments (excluding china_competition)
            other_args = company_df[company_df["primary_argument"] != "china_competition"]["primary_argument"].value_counts().to_dict()

            positions_by_company[company] = {
                "china_positions": china_positions,
                "total_positions": len(company_df),
                "china_count": len(china_df),
                "by_category": by_category,
                "other_arguments": other_args
            }

        logger.info(f"Found {len(positions_by_company)} companies with China rhetoric")
        total_china = sum(d["china_count"] for d in positions_by_company.values())
        logger.info(f"Total China-framed positions: {total_china}")

        return positions_by_company

    except Exception as e:
        raise IcebergError(f"Failed to load positions: {e}")


def format_positions_by_category(by_category: dict) -> str:
    """Format category breakdown."""
    return ", ".join(f"{cat}: {count}" for cat, count in sorted(by_category.items()))


def format_other_arguments(other_args: dict) -> str:
    """Format other argument counts."""
    if not other_args:
        return "None"
    return ", ".join(f"{arg}: {count}" for arg, count in sorted(other_args.items(), key=lambda x: -x[1])[:5])


def call_china_rhetoric_api(client: anthropic.Anthropic, company_name: str,
                            company_type: str, company_data: dict) -> dict:
    """Call Claude API to analyze China rhetoric."""

    prompt = CHINA_RHETORIC_PROMPT.format(
        company_name=company_name,
        company_type=company_type,
        china_positions_json=json.dumps(company_data["china_positions"], indent=2),
        total_positions=company_data["total_positions"],
        positions_by_category=format_positions_by_category(company_data["by_category"]),
        other_arguments=format_other_arguments(company_data["other_arguments"])
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
                if brace_pos != -1:
                    response_text = response_text[brace_pos:]

            result = json.loads(response_text)
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMAnalysisError(f"Failed to parse JSON after {MAX_RETRIES} attempts")
        except anthropic.APIError as e:
            logger.warning(f"API error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMAnalysisError(f"API failed after {MAX_RETRIES} attempts: {e}")


def analyze_china_rhetoric(
    limit: Optional[int] = None,
    dry_run: bool = False,
    fresh: bool = False
) -> dict:
    """
    Analyze China rhetoric for all companies that use it.
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
            catalog.drop_table(tables["analysis"])
            logger.info(f"Fresh mode: dropped {tables['analysis']}")
        except Exception:
            logger.info("Fresh mode: no existing table to drop")
        processed_companies = set()
    else:
        processed_companies = get_processed_companies(catalog, tables["analysis"])
        logger.info(f"Already processed: {len(processed_companies)} companies")

    # Load China positions
    china_data = get_china_positions_by_company(catalog, tables["positions"])

    # Filter to unprocessed
    unprocessed = {k: v for k, v in china_data.items() if k not in processed_companies}
    logger.info(f"Found {len(unprocessed)} unprocessed companies with China rhetoric")

    if not unprocessed:
        return {"companies_processed": 0, "errors": []}

    # Sort by China count (most aggressive first)
    companies_to_process = sorted(unprocessed.items(), key=lambda x: -x[1]["china_count"])

    if limit:
        companies_to_process = companies_to_process[:limit]
        logger.info(f"Limited to {len(companies_to_process)} companies")

    if dry_run:
        logger.info(f"DRY RUN: Would analyze {len(companies_to_process)} companies:")
        for name, data in companies_to_process:
            company_type = get_company_type(name) or "unknown"
            logger.info(f"  - {name} ({company_type}): {data['china_count']} China positions out of {data['total_positions']}")
        return {"dry_run": True, "would_process": [c[0] for c in companies_to_process]}

    # Process
    records = []
    errors = []
    processed_at = datetime.now()

    for i, (company_name, company_data) in enumerate(companies_to_process):
        company_type = get_company_type(company_name) or "unknown"
        logger.info(f"Analyzing {i + 1}/{len(companies_to_process)}: {company_name} ({company_data['china_count']} China positions)")

        try:
            result = call_china_rhetoric_api(client, company_name, company_type, company_data)

            analysis_id = f"{company_name}_{processed_at.strftime('%Y%m%d%H%M%S')}"

            records.append({
                "analysis_id": analysis_id,
                "company_name": company_name,
                "company_type": company_type,
                "rhetoric_intensity": int(result.get("rhetoric_intensity", 0)),
                "claim_categorization": json.dumps(result.get("claim_categorization", [])),
                "rhetoric_patterns": json.dumps(result.get("rhetoric_patterns", {})),
                "policy_asks_supported": json.dumps(result.get("policy_asks_supported_by_china_frame", [])),
                "rhetoric_assessment": json.dumps(result.get("rhetoric_assessment", {})),
                "comparison_to_other_arguments": json.dumps(result.get("comparison_to_other_arguments", {})),
                "notable_quotes": json.dumps(result.get("notable_quotes", [])),
                "key_finding": result.get("key_finding", ""),
                "china_positions_count": company_data["china_count"],
                "total_positions_count": company_data["total_positions"],
                "model": MODEL,
                "processed_at": processed_at
            })

            logger.info(f"  Rhetoric Intensity: {result.get('rhetoric_intensity')}/100")
            logger.info(f"  Assessment: {result.get('rhetoric_assessment', {}).get('substantive_vs_rhetorical', 'unknown')}")

            time.sleep(REQUEST_DELAY)

        except (LLMAnalysisError, Exception) as e:
            logger.error(f"Error analyzing {company_name}: {e}")
            errors.append({"company": company_name, "error": str(e)})
            continue

    logger.info(f"Analyzed {len(records)} companies")

    if not records:
        logger.warning("No analysis results - nothing to write")
        return {"companies_processed": len(companies_to_process), "analyses_written": 0, "errors": errors}

    # Define schema
    analysis_schema = Schema(
        NestedField(1, "analysis_id", StringType(), required=True),
        NestedField(2, "company_name", StringType(), required=False),
        NestedField(3, "company_type", StringType(), required=False),
        NestedField(4, "rhetoric_intensity", IntegerType(), required=False),
        NestedField(5, "claim_categorization", StringType(), required=False),
        NestedField(6, "rhetoric_patterns", StringType(), required=False),
        NestedField(7, "policy_asks_supported", StringType(), required=False),
        NestedField(8, "rhetoric_assessment", StringType(), required=False),
        NestedField(9, "comparison_to_other_arguments", StringType(), required=False),
        NestedField(10, "notable_quotes", StringType(), required=False),
        NestedField(11, "key_finding", StringType(), required=False),
        NestedField(12, "china_positions_count", IntegerType(), required=False),
        NestedField(13, "total_positions_count", IntegerType(), required=False),
        NestedField(14, "model", StringType(), required=False),
        NestedField(15, "processed_at", TimestampType(), required=False)
    )

    pa_schema = pa.schema([
        pa.field("analysis_id", pa.string(), nullable=False),
        pa.field("company_name", pa.string(), nullable=True),
        pa.field("company_type", pa.string(), nullable=True),
        pa.field("rhetoric_intensity", pa.int32(), nullable=True),
        pa.field("claim_categorization", pa.string(), nullable=True),
        pa.field("rhetoric_patterns", pa.string(), nullable=True),
        pa.field("policy_asks_supported", pa.string(), nullable=True),
        pa.field("rhetoric_assessment", pa.string(), nullable=True),
        pa.field("comparison_to_other_arguments", pa.string(), nullable=True),
        pa.field("notable_quotes", pa.string(), nullable=True),
        pa.field("key_finding", pa.string(), nullable=True),
        pa.field("china_positions_count", pa.int32(), nullable=True),
        pa.field("total_positions_count", pa.int32(), nullable=True),
        pa.field("model", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    pa_table = pa.Table.from_pylist(records, schema=pa_schema)

    try:
        try:
            iceberg_table = catalog.load_table(tables["analysis"])
            logger.info(f"Table {tables['analysis']} exists - appending")
        except Exception:
            iceberg_table = catalog.create_table(
                identifier=tables["analysis"],
                schema=analysis_schema
            )
            logger.info(f"Created table {tables['analysis']}")

        iceberg_table.append(pa_table)
        logger.info(f"Appended {len(records)} analyses to {tables['analysis']}")

    except Exception as e:
        raise IcebergError(f"Failed to write analysis: {e}")

    return {
        "companies_processed": len(companies_to_process),
        "analyses_written": len(records),
        "errors": errors,
        "table": tables["analysis"]
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
        result = analyze_china_rhetoric(limit=limit, dry_run=dry_run, fresh=fresh)
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
