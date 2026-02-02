"""
Extract policy positions from document chunks using Claude API.

This script:
1. Reads unprocessed chunks from ai_submissions_chunks
2. Sends each to Claude API with position extraction prompt
3. Parses JSON response and writes to ai_positions table
4. Tracks processed chunks to enable incremental/idempotent runs

Tables:
- Reads from: {schema}.ai_submissions_chunks
- Reads from: {schema}.ai_submissions_metadata (for submitter info)
- Writes to: {schema}.ai_positions

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
from typing import Optional

import anthropic
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog

# Add project root to path for config import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from include.config import get_pdf_filter_names
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    StringType,
    TimestampType,
    DoubleType,
    NestedField
)
from pyiceberg.expressions import EqualTo
import boto3
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMExtractionError(Exception):
    """Raised when LLM extraction fails."""
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


POSITION_EXTRACTION_PROMPT = """
You are analyzing a policy submission to the US government regarding AI regulation.

<document>
{document_text}
</document>

<submitter>
{submitter_name} ({submitter_type})
</submitter>

Extract all **specific policy asks** from this document. A policy ask is a concrete thing the submitter wants the government to do (or not do).

For each policy ask found, return:

1. policy_ask: The specific policy action requested. Use ONE of these codes:

   REGULATORY STRUCTURE:
   - federal_preemption: Federal law should override state laws
   - state_autonomy: States should be able to regulate
   - new_federal_agency: Create new AI oversight body
   - existing_agency_authority: Use existing agencies (FTC/FDA/etc)
   - self_regulation: Industry-led standards without mandates
   - international_harmonization: Align with EU/international standards

   ACCOUNTABILITY:
   - liability_shield: Protect developers from lawsuits
   - liability_framework: Define who's responsible for AI harms
   - mandatory_audits: Require third-party testing
   - voluntary_commitments: Support industry self-commitments
   - transparency_requirements: Mandate disclosures
   - incident_reporting: Require breach/incident reporting

   INTELLECTUAL PROPERTY:
   - training_data_fair_use: Allow copyrighted data for training
   - creator_compensation: Pay content creators
   - model_weight_protection: Treat weights as trade secrets
   - open_source_mandate: Require open models
   - open_source_protection: Don't restrict open source

   NATIONAL SECURITY:
   - export_controls_strict: More chip/model restrictions
   - export_controls_loose: Fewer restrictions
   - china_competition_frame: Frame as beating China
   - government_ai_adoption: More federal AI use
   - defense_ai_investment: Military AI funding

   RESOURCES:
   - research_funding: Government R&D money
   - compute_infrastructure: Data center support
   - energy_infrastructure: Power grid for AI
   - immigration_reform: AI talent visas
   - workforce_training: Retraining programs

   - other: Doesn't fit above (specify in notes)

2. ask_category: High-level grouping:
   - regulatory_structure
   - accountability
   - intellectual_property
   - national_security
   - resources
   - other

3. stance: Their position on this policy ask:
   - support: They want this
   - oppose: They don't want this
   - neutral: Mentioned without clear position

4. target: Specific regulation or bill they're responding to (e.g., "California SB 1047", "EU AI Act"), or null if general

5. primary_argument: WHY they support/oppose this. Use ONE code:

   ECONOMIC:
   - innovation_harm: "Kills startups/innovation"
   - competitiveness: "Must stay ahead economically"
   - job_creation: "Creates jobs"
   - cost_burden: "Too expensive to comply"

   SECURITY:
   - china_competition: "China will win if we don't"
   - national_security: "Defense/security requires this"
   - adversary_benefit: "Helps bad actors"

   PRACTICAL:
   - technical_infeasibility: "Can't be done technically"
   - patchwork_problem: "State-by-state is chaos"
   - duplicative: "Already regulated elsewhere"
   - premature: "Too early to regulate"

   RIGHTS/VALUES:
   - free_speech: First Amendment concerns
   - consumer_protection: Protect users
   - creator_rights: Protect artists/creators
   - civil_liberties: Privacy, bias, fairness
   - safety_concern: AI safety/alignment risks

   - none: No clear argument given

6. secondary_argument: Optional second argument code (or null)

7. supporting_quote: Direct quote (≤50 words) that best supports this extraction

8. confidence: Your confidence in this extraction (0.0-1.0)

Return as JSON array. If no clear policy asks exist, return [].

Example output:
[
  {{
    "policy_ask": "federal_preemption",
    "ask_category": "regulatory_structure",
    "stance": "support",
    "target": "California SB 1047",
    "primary_argument": "patchwork_problem",
    "secondary_argument": "innovation_harm",
    "supporting_quote": "A patchwork of state regulations risks fragmenting the market and stifling American AI leadership.",
    "confidence": 0.92
  }},
  {{
    "policy_ask": "liability_shield",
    "ask_category": "accountability",
    "stance": "support",
    "target": null,
    "primary_argument": "innovation_harm",
    "secondary_argument": null,
    "supporting_quote": "Excessive liability exposure will drive AI development overseas.",
    "confidence": 0.85
  }}
]
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
        "chunks": f"{schema}.ai_submissions_chunks",
        "metadata": f"{schema}.ai_submissions_metadata",
        "positions": f"{schema}.ai_positions",
    }


def get_processed_chunk_ids(catalog, positions_table_name: str) -> set:
    """
    Get set of chunk_ids that have already been processed.
    This enables idempotent incremental runs.
    """
    try:
        table = catalog.load_table(positions_table_name)
        # Read just the chunk_id column
        scan = table.scan(selected_fields=("chunk_id",))
        df = scan.to_arrow().to_pandas()
        return set(df["chunk_id"].unique())
    except Exception as e:
        # Table doesn't exist yet or is empty
        logger.info(f"No existing positions found (this is fine for first run): {e}")
        return set()


def get_unprocessed_chunks(catalog, chunks_table_name: str, metadata_table_name: str,
                           processed_ids: set, limit: Optional[int] = None) -> list[dict]:
    """
    Get chunks that haven't been processed yet, joined with metadata.
    """
    try:
        chunks_table = catalog.load_table(chunks_table_name)
        metadata_table = catalog.load_table(metadata_table_name)

        # Load chunks
        chunks_df = chunks_table.scan().to_arrow().to_pandas()

        # Load metadata for submitter info
        metadata_df = metadata_table.scan(
            selected_fields=("document_id", "submitter_name", "submitter_type")
        ).to_arrow().to_pandas()

        # Join
        merged = chunks_df.merge(metadata_df, on="document_id", how="left")

        # Filter to only priority companies
        priority_names = get_pdf_filter_names()
        # Match submitter names that contain priority company names (case-insensitive)
        priority_mask = merged["submitter_name"].apply(
            lambda x: any(pn.lower() in str(x).lower() for pn in priority_names) if pd.notna(x) else False
        )
        merged = merged[priority_mask]
        logger.info(f"Filtered to {len(merged)} chunks from priority companies")

        # Filter out already processed
        unprocessed = merged[~merged["chunk_id"].isin(processed_ids)]

        logger.info(f"Found {len(unprocessed)} unprocessed chunks")

        if limit:
            unprocessed = unprocessed.head(limit)
            logger.info(f"Limited to {len(unprocessed)} chunks")

        return unprocessed.to_dict("records")

    except Exception as e:
        raise IcebergError(f"Failed to read chunks: {e}")


def call_claude_api(client: anthropic.Anthropic, chunk_text: str,
                    submitter_name: str, submitter_type: str) -> list[dict]:
    """
    Call Claude API to extract positions from a chunk.
    Returns list of position dicts.
    """
    prompt = POSITION_EXTRACTION_PROMPT.format(
        document_text=chunk_text,
        submitter_name=submitter_name,
        submitter_type=submitter_type
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract text from response
            response_text = response.content[0].text.strip()

            # Parse JSON - handle various response formats
            # 1. Handle markdown code blocks anywhere in response
            if "```json" in response_text:
                # Extract content between ```json and ```
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                # Generic code block
                start = response_text.find("```") + 3
                # Skip language identifier if present
                if response_text[start:start+1] == "\n":
                    start += 1
                elif "\n" in response_text[start:start+20]:
                    start = response_text.find("\n", start) + 1
                end = response_text.find("```", start)
                if end > start:
                    response_text = response_text[start:end].strip()

            # 2. If response starts with text before JSON array, find the array
            if not response_text.startswith("["):
                bracket_pos = response_text.find("[")
                if bracket_pos > 0:
                    response_text = response_text[bracket_pos:]

            positions = json.loads(response_text)

            if not isinstance(positions, list):
                raise LLMExtractionError(f"Expected list, got {type(positions)}")

            return positions

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
            logger.warning(f"Response was: {response_text[:500]}...")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMExtractionError(f"Failed to parse JSON after {MAX_RETRIES} attempts")

        except anthropic.APIError as e:
            logger.warning(f"API error on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise LLMExtractionError(f"API failed after {MAX_RETRIES} attempts: {e}")


def extract_positions(
    limit: Optional[int] = None,
    dry_run: bool = False,
    fresh: bool = False
) -> dict:
    """
    Extract positions from unprocessed chunks using Claude API.

    Args:
        limit: Max number of chunks to process (None = all unprocessed)
        dry_run: If True, don't call API or write to Iceberg
        fresh: If True, drop existing table and re-extract all chunks

    Returns:
        dict with keys: chunks_processed, positions_extracted, errors
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

    # Handle fresh extraction - drop existing table
    if fresh:
        logger.info("FRESH mode: Dropping existing positions table if it exists")
        try:
            catalog.drop_table(tables["positions"])
            logger.info(f"Dropped table {tables['positions']}")
        except Exception as e:
            logger.info(f"Table didn't exist or couldn't be dropped (this is fine): {e}")
        processed_ids = set()  # Start fresh
    else:
        # Get already processed chunk IDs (for idempotency)
        processed_ids = get_processed_chunk_ids(catalog, tables["positions"])
    logger.info(f"Already processed: {len(processed_ids)} chunks")

    # Get unprocessed chunks
    chunks = get_unprocessed_chunks(
        catalog, tables["chunks"], tables["metadata"],
        processed_ids, limit=limit
    )

    if not chunks:
        logger.info("No unprocessed chunks found - nothing to do")
        return {"chunks_processed": 0, "positions_extracted": 0, "errors": []}

    if dry_run:
        logger.info(f"DRY RUN: Would process {len(chunks)} chunks")
        return {"chunks_processed": 0, "positions_extracted": 0, "errors": [], "dry_run": True}

    # Process chunks
    position_records = []
    errors = []
    processed_at = datetime.now()

    for i, chunk in enumerate(chunks):
        chunk_id = chunk["chunk_id"]
        document_id = chunk["document_id"]
        submitter_name = chunk.get("submitter_name", "Unknown")
        submitter_type = chunk.get("submitter_type", "other")
        chunk_text = chunk["chunk_text"]

        logger.info(f"Processing chunk {i + 1}/{len(chunks)}: {chunk_id}")

        try:
            positions = call_claude_api(
                client, chunk_text, submitter_name, submitter_type
            )

            for pos_idx, pos in enumerate(positions):
                position_id = f"{chunk_id}_{pos_idx}"
                position_records.append({
                    "position_id": position_id,
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "submitter_name": submitter_name,
                    "submitter_type": submitter_type,
                    "policy_ask": pos.get("policy_ask", "other"),
                    "ask_category": pos.get("ask_category", "other"),
                    "stance": pos.get("stance", "neutral"),
                    "target": pos.get("target"),  # Can be null
                    "primary_argument": pos.get("primary_argument", "none"),
                    "secondary_argument": pos.get("secondary_argument"),  # Can be null
                    "supporting_quote": pos.get("supporting_quote", ""),
                    "confidence": float(pos.get("confidence", 0.0)),
                    "model": MODEL,
                    "processed_at": processed_at
                })

            logger.info(f"  Extracted {len(positions)} positions")

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        except LLMExtractionError as e:
            error_msg = f"Failed to extract from {chunk_id}: {e}"
            logger.error(error_msg)
            errors.append({"chunk_id": chunk_id, "error": str(e)})
            continue

    logger.info(f"Extracted {len(position_records)} positions from {len(chunks)} chunks")

    if not position_records:
        logger.warning("No positions extracted - nothing to write")
        return {
            "chunks_processed": len(chunks),
            "positions_extracted": 0,
            "errors": errors
        }

    # Define schema for enhanced policy asks extraction
    positions_schema = Schema(
        NestedField(1, "position_id", StringType(), required=True),
        NestedField(2, "chunk_id", StringType(), required=False),
        NestedField(3, "document_id", StringType(), required=False),
        NestedField(4, "submitter_name", StringType(), required=False),
        NestedField(5, "submitter_type", StringType(), required=False),
        NestedField(6, "policy_ask", StringType(), required=False),
        NestedField(7, "ask_category", StringType(), required=False),
        NestedField(8, "stance", StringType(), required=False),
        NestedField(9, "target", StringType(), required=False),
        NestedField(10, "primary_argument", StringType(), required=False),
        NestedField(11, "secondary_argument", StringType(), required=False),
        NestedField(12, "supporting_quote", StringType(), required=False),
        NestedField(13, "confidence", DoubleType(), required=False),
        NestedField(14, "model", StringType(), required=False),
        NestedField(15, "processed_at", TimestampType(), required=False)
    )

    pa_schema = pa.schema([
        pa.field("position_id", pa.string(), nullable=False),
        pa.field("chunk_id", pa.string(), nullable=True),
        pa.field("document_id", pa.string(), nullable=True),
        pa.field("submitter_name", pa.string(), nullable=True),
        pa.field("submitter_type", pa.string(), nullable=True),
        pa.field("policy_ask", pa.string(), nullable=True),
        pa.field("ask_category", pa.string(), nullable=True),
        pa.field("stance", pa.string(), nullable=True),
        pa.field("target", pa.string(), nullable=True),
        pa.field("primary_argument", pa.string(), nullable=True),
        pa.field("secondary_argument", pa.string(), nullable=True),
        pa.field("supporting_quote", pa.string(), nullable=True),
        pa.field("confidence", pa.float64(), nullable=True),
        pa.field("model", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    # Convert to PyArrow
    pa_table = pa.Table.from_pylist(position_records, schema=pa_schema)

    # Write to Iceberg (APPEND, not overwrite - for incremental)
    try:
        try:
            iceberg_table = catalog.load_table(tables["positions"])
            logger.info(f"Table {tables['positions']} exists - appending")
        except Exception:
            iceberg_table = catalog.create_table(
                identifier=tables["positions"],
                schema=positions_schema
            )
            logger.info(f"Created table {tables['positions']}")

        # APPEND new positions (not overwrite!)
        iceberg_table.append(pa_table)
        logger.info(f"Appended {len(position_records)} positions to {tables['positions']}")

    except Exception as e:
        raise IcebergError(f"Failed to write positions: {e}")

    return {
        "chunks_processed": len(chunks),
        "positions_extracted": len(position_records),
        "errors": errors,
        "table": tables["positions"]
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
        result = extract_positions(limit=limit, dry_run=dry_run, fresh=fresh)
        logger.info(f"Extraction complete: {result}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except IcebergError as e:
        logger.error(f"Iceberg error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
