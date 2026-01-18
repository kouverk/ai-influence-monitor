"""
Compare policy positions across companies to find agreement and disagreement.

This script analyzes:
- Where do companies agree/disagree on specific policy asks
- How do AI labs differ from Big Tech?
- What's the "industry consensus" vs outlier positions?
- Coalition dynamics and fracture lines

Pipeline:
1. Loads all positions from ai_positions
2. Groups by policy_ask to find agreement/disagreement
3. Sends comparisons to Claude for cross-company analysis
4. Writes findings to position_comparisons table

Tables:
- Reads from: {schema}.ai_positions
- Writes to: {schema}.position_comparisons
"""

import sys
import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

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
    pass


class IcebergError(Exception):
    pass


class ConfigurationError(Exception):
    pass


# Rate limiting
REQUEST_DELAY = 1.0
MAX_RETRIES = 3
RETRY_DELAY = 5.0

# Model configuration
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


COMPARISON_PROMPT = """
Analyze the policy positions of these AI/tech companies to identify agreement, disagreement, and coalition patterns.

<companies_analyzed>
{companies_list}
</companies_analyzed>

<positions_by_policy_ask>
Positions grouped by the policy being advocated:

{positions_by_ask}
</positions_by_policy_ask>

<positions_by_company_type>
Aggregated by company type:

AI LABS (startups building frontier AI):
{ai_labs_summary}

BIG TECH (large tech companies):
{big_tech_summary}

TRADE GROUPS (industry associations):
{trade_groups_summary}
</positions_by_company_type>

Analyze cross-company patterns and return JSON:

{{
  "consensus_positions": [
    {{
      "policy_ask": "<code>",
      "direction": "<support|oppose>",
      "companies_aligned": ["<company names>"],
      "strength": "<unanimous|near_unanimous|majority>",
      "significance": "<why this consensus matters>"
    }}
  ],

  "contested_positions": [
    {{
      "policy_ask": "<code>",
      "supporters": ["<companies supporting>"],
      "opponents": ["<companies opposing>"],
      "key_disagreement": "<what they disagree about>",
      "likely_reason": "<why they disagree - business model, values, etc.>"
    }}
  ],

  "company_type_patterns": {{
    "ai_labs_vs_big_tech": {{
      "agree_on": ["<policy asks where they align>"],
      "disagree_on": ["<policy asks where they differ>"],
      "analysis": "<why these patterns exist>"
    }},
    "trade_groups_vs_individual_companies": {{
      "more_aggressive_positions": ["<where trade groups go further>"],
      "more_moderate_positions": ["<where trade groups are softer>"],
      "analysis": "<why trade groups differ>"
    }}
  }},

  "outlier_positions": [
    {{
      "company": "<name>",
      "position": "<policy_ask: stance>",
      "why_outlier": "<how this differs from others>",
      "possible_explanation": "<business or strategic reason>"
    }}
  ],

  "coalition_analysis": {{
    "natural_allies": [
      {{
        "companies": ["<list>"],
        "aligned_on": ["<policy asks>"],
        "coalition_type": "<safety_focused|deregulation|etc.>"
      }}
    ],
    "surprising_alignments": [
      {{
        "companies": ["<unlikely pair>"],
        "aligned_on": "<policy ask>",
        "why_surprising": "<explanation>"
      }}
    ]
  }},

  "argument_patterns": {{
    "most_used_arguments": [
      {{
        "argument": "<code>",
        "used_by": ["<companies>"],
        "supports_policies": ["<policy asks this argument supports>"]
      }}
    ],
    "unique_arguments": [
      {{
        "company": "<name>",
        "argument": "<code>",
        "why_unique": "<only this company uses it>"
      }}
    ]
  }},

  "key_findings": [
    "<major insight 1>",
    "<major insight 2>",
    "<major insight 3>"
  ]
}}

ANALYSIS GUIDELINES:
- Look for business model explanations (cloud providers vs pure AI labs, etc.)
- Consider who benefits from each policy (incumbents vs challengers)
- Trade groups often take more aggressive positions than individual companies would publicly
- "Safety" positions may be genuine or strategic (safety requirements benefit leaders)
"""


def get_required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {key}")
    return value


def get_table_names() -> dict:
    schema = get_required_env('SCHEMA')
    return {
        "positions": f"{schema}.ai_positions",
        "comparisons": f"{schema}.position_comparisons"
    }


def get_catalog():
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


def load_positions(catalog, positions_table: str) -> dict:
    """
    Load all positions and organize for comparison.

    Returns:
        dict: {
            "by_policy_ask": {ask: [{company, stance, argument, quote}]},
            "by_company": {company: [positions]},
            "by_company_type": {type: {ask: [{company, stance}]}},
            "companies": [{name, type, position_count}]
        }
    """
    try:
        table = catalog.load_table(positions_table)
        df = table.scan().to_arrow().to_pandas()

        # By policy ask
        by_policy_ask = defaultdict(list)
        for _, row in df.iterrows():
            company = row["submitter_name"]
            company_type = get_company_type(company) or "unknown"
            by_policy_ask[row["policy_ask"]].append({
                "company": company,
                "company_type": company_type,
                "stance": row["stance"],
                "argument": row["primary_argument"],
                "quote": row["supporting_quote"][:100] + "..." if len(row["supporting_quote"]) > 100 else row["supporting_quote"]
            })

        # By company
        by_company = defaultdict(list)
        for _, row in df.iterrows():
            by_company[row["submitter_name"]].append({
                "policy_ask": row["policy_ask"],
                "stance": row["stance"],
                "argument": row["primary_argument"]
            })

        # By company type
        by_company_type = {"ai_lab": defaultdict(list), "big_tech": defaultdict(list), "trade_group": defaultdict(list)}
        for _, row in df.iterrows():
            company = row["submitter_name"]
            company_type = get_company_type(company) or "unknown"
            if company_type in by_company_type:
                by_company_type[company_type][row["policy_ask"]].append({
                    "company": company,
                    "stance": row["stance"]
                })

        # Company list
        companies = []
        for company in df["submitter_name"].unique():
            company_type = get_company_type(company) or "unknown"
            count = len(df[df["submitter_name"] == company])
            companies.append({"name": company, "type": company_type, "position_count": count})

        logger.info(f"Loaded positions for {len(companies)} companies")
        logger.info(f"Unique policy asks: {len(by_policy_ask)}")

        return {
            "by_policy_ask": dict(by_policy_ask),
            "by_company": dict(by_company),
            "by_company_type": {k: dict(v) for k, v in by_company_type.items()},
            "companies": companies
        }

    except Exception as e:
        raise IcebergError(f"Failed to load positions: {e}")


def format_positions_by_ask(by_policy_ask: dict) -> str:
    """Format positions grouped by policy ask for the prompt."""
    lines = []
    # Sort by most positions first (most discussed topics)
    for ask, positions in sorted(by_policy_ask.items(), key=lambda x: -len(x[1])):
        if len(positions) < 2:  # Skip asks with only 1 company
            continue
        lines.append(f"\n{ask.upper()} ({len(positions)} positions):")

        # Group by stance
        supporters = [p for p in positions if p["stance"] == "support"]
        opponents = [p for p in positions if p["stance"] == "oppose"]
        neutral = [p for p in positions if p["stance"] == "neutral"]

        if supporters:
            companies = ", ".join(set(p["company"] for p in supporters))
            lines.append(f"  SUPPORT: {companies}")
        if opponents:
            companies = ", ".join(set(p["company"] for p in opponents))
            lines.append(f"  OPPOSE: {companies}")
        if neutral:
            companies = ", ".join(set(p["company"] for p in neutral))
            lines.append(f"  NEUTRAL: {companies}")

    return "\n".join(lines)


def format_company_type_summary(by_type: dict, type_name: str) -> str:
    """Format summary for a company type."""
    if not by_type:
        return "No positions"

    # Aggregate stances
    support_count = defaultdict(int)
    oppose_count = defaultdict(int)

    for ask, positions in by_type.items():
        for p in positions:
            if p["stance"] == "support":
                support_count[ask] += 1
            elif p["stance"] == "oppose":
                oppose_count[ask] += 1

    lines = []
    top_support = sorted(support_count.items(), key=lambda x: -x[1])[:5]
    top_oppose = sorted(oppose_count.items(), key=lambda x: -x[1])[:3]

    if top_support:
        lines.append("  Most supported: " + ", ".join(f"{a} ({c})" for a, c in top_support))
    if top_oppose:
        lines.append("  Most opposed: " + ", ".join(f"{a} ({c})" for a, c in top_oppose))

    return "\n".join(lines) if lines else "Limited data"


def call_comparison_api(client: anthropic.Anthropic, data: dict) -> dict:
    """Call Claude API to analyze cross-company patterns."""

    prompt = COMPARISON_PROMPT.format(
        companies_list=", ".join(f"{c['name']} ({c['type']})" for c in data["companies"]),
        positions_by_ask=format_positions_by_ask(data["by_policy_ask"]),
        ai_labs_summary=format_company_type_summary(data["by_company_type"]["ai_lab"], "AI Labs"),
        big_tech_summary=format_company_type_summary(data["by_company_type"]["big_tech"], "Big Tech"),
        trade_groups_summary=format_company_type_summary(data["by_company_type"]["trade_group"], "Trade Groups")
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


def compare_positions(
    dry_run: bool = False,
    fresh: bool = False
) -> dict:
    """
    Compare positions across all companies.

    This is a single-shot analysis (not per-company) so it runs once.
    """
    api_key = get_required_env('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    tables = get_table_names()
    logger.info(f"Tables: {tables}")

    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Check if already run (unless fresh)
    if not fresh:
        try:
            existing = catalog.load_table(tables["comparisons"])
            count = len(existing.scan().to_arrow())
            if count > 0:
                logger.info(f"Comparison already exists ({count} records). Use --fresh to rerun.")
                return {"already_exists": True, "records": count}
        except Exception:
            pass

    # Fresh mode - drop table
    if fresh:
        try:
            catalog.drop_table(tables["comparisons"])
            logger.info(f"Fresh mode: dropped {tables['comparisons']}")
        except Exception:
            logger.info("Fresh mode: no existing table to drop")

    # Load all positions
    data = load_positions(catalog, tables["positions"])

    if dry_run:
        logger.info(f"DRY RUN: Would analyze {len(data['companies'])} companies")
        logger.info(f"  Policy asks with multiple companies: {sum(1 for v in data['by_policy_ask'].values() if len(v) >= 2)}")
        for c in data["companies"]:
            logger.info(f"  - {c['name']} ({c['type']}): {c['position_count']} positions")
        return {"dry_run": True, "companies": [c["name"] for c in data["companies"]]}

    # Run comparison
    logger.info("Running cross-company comparison...")
    result = call_comparison_api(client, data)

    processed_at = datetime.now()
    comparison_id = f"comparison_{processed_at.strftime('%Y%m%d%H%M%S')}"

    record = {
        "comparison_id": comparison_id,
        "companies_analyzed": json.dumps([c["name"] for c in data["companies"]]),
        "company_count": len(data["companies"]),
        "position_count": sum(c["position_count"] for c in data["companies"]),
        "consensus_positions": json.dumps(result.get("consensus_positions", [])),
        "contested_positions": json.dumps(result.get("contested_positions", [])),
        "company_type_patterns": json.dumps(result.get("company_type_patterns", {})),
        "outlier_positions": json.dumps(result.get("outlier_positions", [])),
        "coalition_analysis": json.dumps(result.get("coalition_analysis", {})),
        "argument_patterns": json.dumps(result.get("argument_patterns", {})),
        "key_findings": json.dumps(result.get("key_findings", [])),
        "model": MODEL,
        "processed_at": processed_at
    }

    logger.info(f"Key findings: {result.get('key_findings', [])}")

    # Write to Iceberg
    comparison_schema = Schema(
        NestedField(1, "comparison_id", StringType(), required=True),
        NestedField(2, "companies_analyzed", StringType(), required=False),
        NestedField(3, "company_count", IntegerType(), required=False),
        NestedField(4, "position_count", IntegerType(), required=False),
        NestedField(5, "consensus_positions", StringType(), required=False),
        NestedField(6, "contested_positions", StringType(), required=False),
        NestedField(7, "company_type_patterns", StringType(), required=False),
        NestedField(8, "outlier_positions", StringType(), required=False),
        NestedField(9, "coalition_analysis", StringType(), required=False),
        NestedField(10, "argument_patterns", StringType(), required=False),
        NestedField(11, "key_findings", StringType(), required=False),
        NestedField(12, "model", StringType(), required=False),
        NestedField(13, "processed_at", TimestampType(), required=False)
    )

    pa_schema = pa.schema([
        pa.field("comparison_id", pa.string(), nullable=False),
        pa.field("companies_analyzed", pa.string(), nullable=True),
        pa.field("company_count", pa.int32(), nullable=True),
        pa.field("position_count", pa.int32(), nullable=True),
        pa.field("consensus_positions", pa.string(), nullable=True),
        pa.field("contested_positions", pa.string(), nullable=True),
        pa.field("company_type_patterns", pa.string(), nullable=True),
        pa.field("outlier_positions", pa.string(), nullable=True),
        pa.field("coalition_analysis", pa.string(), nullable=True),
        pa.field("argument_patterns", pa.string(), nullable=True),
        pa.field("key_findings", pa.string(), nullable=True),
        pa.field("model", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    pa_table = pa.Table.from_pylist([record], schema=pa_schema)

    try:
        try:
            iceberg_table = catalog.load_table(tables["comparisons"])
            logger.info(f"Table {tables['comparisons']} exists - appending")
        except Exception:
            iceberg_table = catalog.create_table(
                identifier=tables["comparisons"],
                schema=comparison_schema
            )
            logger.info(f"Created table {tables['comparisons']}")

        iceberg_table.append(pa_table)
        logger.info(f"Wrote comparison to {tables['comparisons']}")

    except Exception as e:
        raise IcebergError(f"Failed to write comparison: {e}")

    return {
        "companies_analyzed": len(data["companies"]),
        "positions_analyzed": sum(c["position_count"] for c in data["companies"]),
        "key_findings": result.get("key_findings", []),
        "table": tables["comparisons"]
    }


if __name__ == "__main__":
    load_dotenv()

    dry_run = False
    fresh = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--fresh":
            fresh = True

    try:
        result = compare_positions(dry_run=dry_run, fresh=fresh)
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
