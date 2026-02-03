"""
Extract lobbying filings from Senate LDA API and write to Iceberg tables.

This script:
1. Queries the Senate LDA API for specified companies
2. Paginates through all results
3. Writes to three separate Iceberg tables (normalized structure)

Tables created:
- {schema}.lda_filings: Core filing data (one row per filing)
- {schema}.lda_activities: Lobbying activities per filing (one row per issue code)
- {schema}.lda_lobbyists: Lobbyists per activity (one row per lobbyist)

Environment variables required:
- SCHEMA: Target schema/namespace for tables
- AWS_ACCESS_KEY_ID: AWS access key
- AWS_SECRET_ACCESS_KEY: AWS secret key
- AWS_DEFAULT_REGION: AWS region (default: us-west-2)
- AWS_S3_BUCKET_TABULAR: S3 bucket for Iceberg warehouse
"""

import sys
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    LongType,
    StringType,
    TimestampType,
    DoubleType,
    BooleanType,
    NestedField
)
import boto3
from dotenv import load_dotenv

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import get_lda_client_names, LDA_MIN_YEAR, LDA_AI_ISSUE_CODES


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LDAAPIError(Exception):
    """Raised when LDA API request fails."""
    pass


class IcebergWriteError(Exception):
    """Raised when writing to Iceberg fails."""
    pass


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


# API Configuration
LDA_BASE_URL = "https://lda.senate.gov/api/v1"
REQUEST_DELAY = 2.0  # seconds between requests (be nice to the API)
COMPANY_DELAY = 5.0  # seconds between companies
MAX_RETRIES = 3  # retry on 429
RETRY_BACKOFF = 30.0  # base backoff seconds on 429


def get_required_env(var_name: str) -> str:
    """Get required environment variable or raise ConfigurationError."""
    value = os.environ.get(var_name)
    if not value:
        raise ConfigurationError(f"Required environment variable {var_name} is not set")
    return value


def get_table_names() -> tuple[str, str, str]:
    """Get table names from SCHEMA environment variable."""
    schema = get_required_env('SCHEMA')
    return (
        f"{schema}.lda_filings",
        f"{schema}.lda_activities",
        f"{schema}.lda_lobbyists"
    )


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


def fetch_filings_for_client(
    client_name: str,
    exact_match: bool = True,
    min_year: Optional[int] = None,
    issue_codes: Optional[list[str]] = None
) -> list[dict]:
    """
    Fetch all filings for a client from LDA API.

    Args:
        client_name: Company name to search for
        exact_match: If True, filter results to exact client name match
        min_year: Only include filings from this year onward (default: from config)
        issue_codes: Only include filings with these issue codes (default: from config)

    Returns:
        List of filing dictionaries
    """
    # Use config defaults if not specified
    if min_year is None:
        min_year = LDA_MIN_YEAR
    if issue_codes is None:
        issue_codes = LDA_AI_ISSUE_CODES

    all_filings = []
    url = f"{LDA_BASE_URL}/filings/"
    params = {"client_name": client_name}

    # Add year filter to API query if supported
    if min_year:
        params["filing_year__gte"] = min_year

    page = 1
    while url:
        # Retry logic for rate limiting
        for retry in range(MAX_RETRIES + 1):
            try:
                logger.info(f"Fetching page {page} for {client_name} (year >= {min_year})...")
                resp = requests.get(url, params=params if page == 1 else None, timeout=30)

                if resp.status_code == 429:
                    if retry < MAX_RETRIES:
                        wait_time = RETRY_BACKOFF * (2 ** retry)  # exponential backoff
                        logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {retry + 1}/{MAX_RETRIES}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise LDAAPIError(f"Rate limited after {MAX_RETRIES} retries for {client_name}")

                resp.raise_for_status()
                break  # Success, exit retry loop
            except requests.exceptions.RequestException as e:
                if retry < MAX_RETRIES and "429" in str(e):
                    wait_time = RETRY_BACKOFF * (2 ** retry)
                    logger.warning(f"Request error, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                raise LDAAPIError(f"Failed to fetch filings for {client_name}: {e}")

        data = resp.json()

        results = data.get("results", [])

        # Filter to exact match if requested
        if exact_match:
            results = [
                f for f in results
                if f.get("client", {}).get("name", "").upper() == client_name.upper()
                or client_name.upper() in f.get("client", {}).get("name", "").upper()
            ]

        # Filter by year (in case API doesn't support year filter)
        if min_year:
            results = [
                f for f in results
                if f.get("filing_year", 0) >= min_year
            ]

        # Filter by issue codes - keep filing if ANY activity has a matching code
        if issue_codes:
            filtered_results = []
            for filing in results:
                activities = filing.get("lobbying_activities", [])
                has_ai_issue = any(
                    act.get("general_issue_code") in issue_codes
                    for act in activities
                )
                if has_ai_issue or not activities:  # Keep filings with no activities too
                    filtered_results.append(filing)
            results = filtered_results

        all_filings.extend(results)

        # Get next page URL
        url = data.get("next")
        params = None  # Next URL includes params
        page += 1

        time.sleep(REQUEST_DELAY)

    logger.info(f"Fetched {len(all_filings)} filings for {client_name} (year >= {min_year}, AI-relevant)")
    return all_filings


def normalize_filings(filings: list[dict], processed_at: datetime) -> tuple[list, list, list]:
    """
    Normalize nested filing data into three flat record lists.

    Args:
        filings: Raw filings from API
        processed_at: Timestamp for processing

    Returns:
        tuple: (filing_records, activity_records, lobbyist_records)
    """
    filing_records = []
    activity_records = []
    lobbyist_records = []

    for filing in filings:
        filing_uuid = filing.get("filing_uuid")

        # Parse expenses safely
        expenses = None
        if filing.get("expenses"):
            try:
                expenses = float(filing["expenses"])
            except (ValueError, TypeError):
                pass

        # Filing record
        filing_records.append({
            "filing_uuid": filing_uuid,
            "filing_type": filing.get("filing_type"),
            "filing_type_display": filing.get("filing_type_display"),
            "filing_year": filing.get("filing_year"),
            "filing_period": filing.get("filing_period"),
            "filing_period_display": filing.get("filing_period_display"),
            "expenses": expenses,
            "dt_posted": filing.get("dt_posted"),
            "termination_date": filing.get("termination_date"),
            # Registrant (lobbying firm)
            "registrant_id": filing.get("registrant", {}).get("id"),
            "registrant_name": filing.get("registrant", {}).get("name"),
            # Client (company being represented)
            "client_id": filing.get("client", {}).get("id"),
            "client_name": filing.get("client", {}).get("name"),
            "client_description": filing.get("client", {}).get("general_description"),
            "client_state": filing.get("client", {}).get("state"),
            # Metadata
            "processed_at": processed_at
        })

        # Activity records (one per issue code)
        for act_idx, activity in enumerate(filing.get("lobbying_activities", [])):
            activity_id = f"{filing_uuid}_{act_idx}"

            activity_records.append({
                "activity_id": activity_id,
                "filing_uuid": filing_uuid,
                "issue_code": activity.get("general_issue_code"),
                "issue_code_display": activity.get("general_issue_code_display"),
                "description": activity.get("description"),
                "foreign_entity_issues": activity.get("foreign_entity_issues"),
                "processed_at": processed_at
            })

            # Lobbyist records (one per lobbyist per activity)
            for lob_idx, lobbyist_entry in enumerate(activity.get("lobbyists", [])):
                lobbyist = lobbyist_entry.get("lobbyist", {})
                lobbyist_id = f"{activity_id}_{lob_idx}"

                lobbyist_records.append({
                    "lobbyist_record_id": lobbyist_id,
                    "activity_id": activity_id,
                    "filing_uuid": filing_uuid,
                    "lobbyist_id": lobbyist.get("id"),
                    "first_name": lobbyist.get("first_name"),
                    "last_name": lobbyist.get("last_name"),
                    "covered_position": lobbyist_entry.get("covered_position"),
                    "is_new": lobbyist_entry.get("new"),
                    "processed_at": processed_at
                })

    return filing_records, activity_records, lobbyist_records


def extract_lda_filings(
    companies: Optional[list[str]] = None,
    exact_match: bool = True
) -> dict:
    """
    Extract LDA filings for specified companies and write to Iceberg.

    Args:
        companies: List of company names to query (default: AI labs)
        exact_match: Filter to exact client name matches

    Returns:
        dict with keys: filings, activities, lobbyists, errors, tables
    """
    # Default to all priority companies from shared config
    if companies is None:
        companies = get_lda_client_names()

    # Get table names
    table_filings, table_activities, table_lobbyists = get_table_names()
    logger.info(f"Target tables: {table_filings}, {table_activities}, {table_lobbyists}")

    # Initialize catalog
    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Fetch filings for all companies
    all_filings = []
    errors = []

    for i, company in enumerate(companies):
        try:
            filings = fetch_filings_for_client(company, exact_match=exact_match)
            all_filings.extend(filings)
        except LDAAPIError as e:
            error_msg = str(e)
            logger.warning(error_msg)
            errors.append({"company": company, "error": error_msg})

        # Pause between companies to avoid rate limiting
        if i < len(companies) - 1:
            logger.info(f"Waiting {COMPANY_DELAY}s before next company...")
            time.sleep(COMPANY_DELAY)

    if not all_filings:
        raise LDAAPIError("No filings were successfully fetched")

    # Deduplicate by filing_uuid (in case same filing matched multiple queries)
    seen_uuids = set()
    unique_filings = []
    for f in all_filings:
        uuid = f.get("filing_uuid")
        if uuid and uuid not in seen_uuids:
            seen_uuids.add(uuid)
            unique_filings.append(f)

    logger.info(f"Total unique filings: {len(unique_filings)}")

    # Normalize into flat tables
    processed_at = datetime.now()
    filing_records, activity_records, lobbyist_records = normalize_filings(
        unique_filings, processed_at
    )

    logger.info(f"Normalized: {len(filing_records)} filings, {len(activity_records)} activities, {len(lobbyist_records)} lobbyists")

    # Define Iceberg schemas
    filings_schema = Schema(
        NestedField(1, "filing_uuid", StringType(), required=True),
        NestedField(2, "filing_type", StringType(), required=False),
        NestedField(3, "filing_type_display", StringType(), required=False),
        NestedField(4, "filing_year", IntegerType(), required=False),
        NestedField(5, "filing_period", StringType(), required=False),
        NestedField(6, "filing_period_display", StringType(), required=False),
        NestedField(7, "expenses", DoubleType(), required=False),
        NestedField(8, "dt_posted", StringType(), required=False),
        NestedField(9, "termination_date", StringType(), required=False),
        NestedField(10, "registrant_id", LongType(), required=False),
        NestedField(11, "registrant_name", StringType(), required=False),
        NestedField(12, "client_id", LongType(), required=False),
        NestedField(13, "client_name", StringType(), required=False),
        NestedField(14, "client_description", StringType(), required=False),
        NestedField(15, "client_state", StringType(), required=False),
        NestedField(16, "processed_at", TimestampType(), required=False)
    )

    activities_schema = Schema(
        NestedField(1, "activity_id", StringType(), required=True),
        NestedField(2, "filing_uuid", StringType(), required=False),
        NestedField(3, "issue_code", StringType(), required=False),
        NestedField(4, "issue_code_display", StringType(), required=False),
        NestedField(5, "description", StringType(), required=False),
        NestedField(6, "foreign_entity_issues", StringType(), required=False),
        NestedField(7, "processed_at", TimestampType(), required=False)
    )

    lobbyists_schema = Schema(
        NestedField(1, "lobbyist_record_id", StringType(), required=True),
        NestedField(2, "activity_id", StringType(), required=False),
        NestedField(3, "filing_uuid", StringType(), required=False),
        NestedField(4, "lobbyist_id", LongType(), required=False),
        NestedField(5, "first_name", StringType(), required=False),
        NestedField(6, "last_name", StringType(), required=False),
        NestedField(7, "covered_position", StringType(), required=False),
        NestedField(8, "is_new", BooleanType(), required=False),
        NestedField(9, "processed_at", TimestampType(), required=False)
    )

    # PyArrow schemas
    pa_filings_schema = pa.schema([
        pa.field("filing_uuid", pa.string(), nullable=False),
        pa.field("filing_type", pa.string(), nullable=True),
        pa.field("filing_type_display", pa.string(), nullable=True),
        pa.field("filing_year", pa.int32(), nullable=True),
        pa.field("filing_period", pa.string(), nullable=True),
        pa.field("filing_period_display", pa.string(), nullable=True),
        pa.field("expenses", pa.float64(), nullable=True),
        pa.field("dt_posted", pa.string(), nullable=True),
        pa.field("termination_date", pa.string(), nullable=True),
        pa.field("registrant_id", pa.int64(), nullable=True),
        pa.field("registrant_name", pa.string(), nullable=True),
        pa.field("client_id", pa.int64(), nullable=True),
        pa.field("client_name", pa.string(), nullable=True),
        pa.field("client_description", pa.string(), nullable=True),
        pa.field("client_state", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    pa_activities_schema = pa.schema([
        pa.field("activity_id", pa.string(), nullable=False),
        pa.field("filing_uuid", pa.string(), nullable=True),
        pa.field("issue_code", pa.string(), nullable=True),
        pa.field("issue_code_display", pa.string(), nullable=True),
        pa.field("description", pa.string(), nullable=True),
        pa.field("foreign_entity_issues", pa.string(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    pa_lobbyists_schema = pa.schema([
        pa.field("lobbyist_record_id", pa.string(), nullable=False),
        pa.field("activity_id", pa.string(), nullable=True),
        pa.field("filing_uuid", pa.string(), nullable=True),
        pa.field("lobbyist_id", pa.int64(), nullable=True),
        pa.field("first_name", pa.string(), nullable=True),
        pa.field("last_name", pa.string(), nullable=True),
        pa.field("covered_position", pa.string(), nullable=True),
        pa.field("is_new", pa.bool_(), nullable=True),
        pa.field("processed_at", pa.timestamp("us"), nullable=True)
    ])

    # Convert to PyArrow tables
    pa_filings_table = pa.Table.from_pylist(filing_records, schema=pa_filings_schema)
    pa_activities_table = pa.Table.from_pylist(activity_records, schema=pa_activities_schema)
    pa_lobbyists_table = pa.Table.from_pylist(lobbyist_records, schema=pa_lobbyists_schema)

    # Write to Iceberg
    try:
        def get_or_create_table(table_name, schema):
            try:
                table = catalog.load_table(table_name)
                logger.info(f"Table {table_name} already exists")
                return table
            except Exception:
                table = catalog.create_table(identifier=table_name, schema=schema)
                logger.info(f"Created table {table_name}")
                return table

        iceberg_filings = get_or_create_table(table_filings, filings_schema)
        iceberg_activities = get_or_create_table(table_activities, activities_schema)
        iceberg_lobbyists = get_or_create_table(table_lobbyists, lobbyists_schema)

        iceberg_filings.overwrite(pa_filings_table)
        iceberg_activities.overwrite(pa_activities_table)
        iceberg_lobbyists.overwrite(pa_lobbyists_table)

        logger.info(f"Wrote {len(filing_records)} filings to {table_filings}")
        logger.info(f"Wrote {len(activity_records)} activities to {table_activities}")
        logger.info(f"Wrote {len(lobbyist_records)} lobbyists to {table_lobbyists}")

    except Exception as e:
        raise IcebergWriteError(f"Failed to write to Iceberg: {e}")

    return {
        "filings": len(filing_records),
        "activities": len(activity_records),
        "lobbyists": len(lobbyist_records),
        "errors": errors,
        "tables": {
            "filings": table_filings,
            "activities": table_activities,
            "lobbyists": table_lobbyists
        }
    }


if __name__ == "__main__":
    load_dotenv()

    # Default companies or pass via command line
    companies = sys.argv[1:] if len(sys.argv) > 1 else None

    try:
        result = extract_lda_filings(companies=companies)
        logger.info(f"Extraction complete: {result}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except LDAAPIError as e:
        logger.error(f"LDA API error: {e}")
        sys.exit(1)
    except IcebergWriteError as e:
        logger.error(f"Iceberg write error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
