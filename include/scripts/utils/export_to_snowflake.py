#!/usr/bin/env python3
"""Export Iceberg tables to Snowflake via direct insert.

This script reads data from Iceberg tables (via PyIceberg) and writes
directly to Snowflake tables. This is the bridge between our raw data
layer (Iceberg) and our analytics layer (Snowflake).
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog

load_dotenv()

def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"ERROR: Missing {key}")
        sys.exit(1)
    return value

def get_snowflake_connection():
    import snowflake.connector
    return snowflake.connector.connect(
        account=get_required_env("SNOWFLAKE_ACCOUNT"),
        user=get_required_env("SNOWFLAKE_USER"),
        password=get_required_env("SNOWFLAKE_PASSWORD"),
        warehouse=get_required_env("SNOWFLAKE_WAREHOUSE"),
        database=get_required_env("SNOWFLAKE_DATABASE"),
        schema=get_required_env("SNOWFLAKE_SCHEMA"),
    )

def get_catalog():
    """Initialize and return PyIceberg catalog."""
    aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
    s3_bucket = get_required_env('AWS_S3_BUCKET_TABULAR')
    return load_catalog(
        "glue",
        **{
            "type": "glue",
            "region_name": aws_region,
            "warehouse": f"s3://{s3_bucket}/",
        }
    )

def get_table_names() -> dict:
    """Get all Iceberg table names."""
    schema = get_required_env('SCHEMA')
    return {
        "positions": f"{schema}.ai_positions",
        "metadata": f"{schema}.ai_submissions_metadata",
        "chunks": f"{schema}.ai_submissions_chunks",
        "lda_filings": f"{schema}.lda_filings",
        "lda_activities": f"{schema}.lda_activities",
        "lda_lobbyists": f"{schema}.lda_lobbyists",
        "lobbying_impact_scores": f"{schema}.lobbying_impact_scores",
        "discrepancy_scores": f"{schema}.discrepancy_scores",
        "china_rhetoric_analysis": f"{schema}.china_rhetoric_analysis",
        "position_comparisons": f"{schema}.position_comparisons",
        "bill_position_analysis": f"{schema}.bill_position_analysis",
    }

def iceberg_to_snowflake(table_name: str, iceberg_table_id: str, create_sql: str, dry_run: bool = False):
    """Copy an Iceberg table to Snowflake."""
    print(f"\n=== {table_name} ===")

    # Read from Iceberg
    catalog = get_catalog()
    try:
        iceberg_table = catalog.load_table(iceberg_table_id)
        df = iceberg_table.scan().to_pandas()
        print(f"Read {len(df)} rows from Iceberg")
    except Exception as e:
        print(f"  ERROR reading from Iceberg: {e}")
        return 0

    if len(df) == 0:
        print("  No data to load")
        return 0

    if dry_run:
        print(f"  [DRY RUN] Would load {len(df)} rows")
        return len(df)

    # Write to Snowflake
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        # Create table if not exists
        cursor.execute(create_sql)
        print(f"  Created/verified table: {table_name}")

        # Truncate and reload (full refresh)
        cursor.execute(f"TRUNCATE TABLE IF EXISTS {table_name}")

        # Convert timestamps to strings for Snowflake
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Handle None/NaN values - use appropriate defaults by type
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64', 'int32']:
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna('')

        # Uppercase column names to match Snowflake
        df.columns = [col.upper() for col in df.columns]

        # Insert data using write_pandas
        from snowflake.connector.pandas_tools import write_pandas
        success, nchunks, nrows, _ = write_pandas(
            conn, df, table_name.upper(),
            auto_create_table=False,
            overwrite=False,
            quote_identifiers=False
        )
        print(f"  Loaded {nrows} rows in {nchunks} chunks")
        return nrows

    except Exception as e:
        print(f"  ERROR: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def main():
    dry_run = "--dry-run" in sys.argv
    tables = get_table_names()

    total_rows = 0

    # 1. AI Positions (633 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_AI_POSITIONS",
        tables["positions"],
        """
        CREATE TABLE IF NOT EXISTS RAW_AI_POSITIONS (
            POSITION_ID VARCHAR,
            CHUNK_ID VARCHAR,
            DOCUMENT_ID VARCHAR,
            SUBMITTER_NAME VARCHAR,
            SUBMITTER_TYPE VARCHAR,
            POLICY_ASK VARCHAR,
            ASK_CATEGORY VARCHAR,
            STANCE VARCHAR,
            TARGET VARCHAR,
            PRIMARY_ARGUMENT VARCHAR,
            SECONDARY_ARGUMENT VARCHAR,
            SUPPORTING_QUOTE VARCHAR,
            CONFIDENCE FLOAT,
            MODEL VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 2. AI Submissions Metadata (17 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_AI_SUBMISSIONS_METADATA",
        tables["metadata"],
        """
        CREATE TABLE IF NOT EXISTS RAW_AI_SUBMISSIONS_METADATA (
            DOCUMENT_ID VARCHAR,
            FILENAME VARCHAR,
            SUBMITTER_NAME VARCHAR,
            SUBMITTER_TYPE VARCHAR,
            PAGE_COUNT INTEGER,
            WORD_COUNT INTEGER,
            FILE_SIZE_BYTES INTEGER,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 3. LDA Filings (339 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_LDA_FILINGS",
        tables["lda_filings"],
        """
        CREATE TABLE IF NOT EXISTS RAW_LDA_FILINGS (
            FILING_UUID VARCHAR,
            FILING_TYPE VARCHAR,
            FILING_TYPE_DISPLAY VARCHAR,
            FILING_YEAR INTEGER,
            FILING_PERIOD VARCHAR,
            FILING_PERIOD_DISPLAY VARCHAR,
            EXPENSES FLOAT,
            DT_POSTED VARCHAR,
            TERMINATION_DATE VARCHAR,
            REGISTRANT_ID INTEGER,
            REGISTRANT_NAME VARCHAR,
            CLIENT_ID INTEGER,
            CLIENT_NAME VARCHAR,
            CLIENT_DESCRIPTION VARCHAR,
            CLIENT_STATE VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 4. LDA Activities (869 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_LDA_ACTIVITIES",
        tables["lda_activities"],
        """
        CREATE TABLE IF NOT EXISTS RAW_LDA_ACTIVITIES (
            ACTIVITY_ID VARCHAR,
            FILING_UUID VARCHAR,
            ISSUE_CODE VARCHAR,
            ISSUE_CODE_DISPLAY VARCHAR,
            DESCRIPTION VARCHAR,
            FOREIGN_ENTITY_ISSUES VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 5. LDA Lobbyists (2586 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_LDA_LOBBYISTS",
        tables["lda_lobbyists"],
        """
        CREATE TABLE IF NOT EXISTS RAW_LDA_LOBBYISTS (
            LOBBYIST_RECORD_ID VARCHAR,
            ACTIVITY_ID VARCHAR,
            FILING_UUID VARCHAR,
            LOBBYIST_ID INTEGER,
            FIRST_NAME VARCHAR,
            LAST_NAME VARCHAR,
            COVERED_POSITION VARCHAR,
            IS_NEW BOOLEAN,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 6. Lobbying Impact Scores (10 rows) - v2 schema
    total_rows += iceberg_to_snowflake(
        "RAW_LOBBYING_IMPACT_SCORES",
        tables["lobbying_impact_scores"],
        """
        CREATE OR REPLACE TABLE RAW_LOBBYING_IMPACT_SCORES (
            SCORE_ID VARCHAR,
            COMPANY_NAME VARCHAR,
            COMPANY_TYPE VARCHAR,
            CONCERN_SCORE INTEGER,
            LOBBYING_AGENDA_SUMMARY VARCHAR,
            TOP_CONCERNING_POLICY_ASKS VARCHAR,
            PUBLIC_INTEREST_CONCERNS VARCHAR,
            REGULATORY_CAPTURE_SIGNALS VARCHAR,
            CHINA_RHETORIC_ASSESSMENT VARCHAR,
            ACCOUNTABILITY_STANCE VARCHAR,
            POSITIVE_ASPECTS VARCHAR,
            KEY_FLAGS VARCHAR,
            POSITIONS_COUNT INTEGER,
            LOBBYING_FILINGS_COUNT INTEGER,
            MODEL VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 7. Discrepancy Scores (10 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_DISCREPANCY_SCORES",
        tables["discrepancy_scores"],
        """
        CREATE TABLE IF NOT EXISTS RAW_DISCREPANCY_SCORES (
            SCORE_ID VARCHAR,
            COMPANY_NAME VARCHAR,
            COMPANY_TYPE VARCHAR,
            DISCREPANCY_SCORE INTEGER,
            DISCREPANCIES VARCHAR,
            CONSISTENT_AREAS VARCHAR,
            LOBBYING_PRIORITIES_VS_RHETORIC VARCHAR,
            CHINA_RHETORIC_ANALYSIS VARCHAR,
            ACCOUNTABILITY_CONTRADICTION VARCHAR,
            KEY_FINDING VARCHAR,
            POSITIONS_COUNT INTEGER,
            LOBBYING_FILINGS_COUNT INTEGER,
            MODEL VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 8. China Rhetoric Analysis (11 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_CHINA_RHETORIC_ANALYSIS",
        tables["china_rhetoric_analysis"],
        """
        CREATE TABLE IF NOT EXISTS RAW_CHINA_RHETORIC_ANALYSIS (
            ANALYSIS_ID VARCHAR,
            COMPANY_NAME VARCHAR,
            COMPANY_TYPE VARCHAR,
            RHETORIC_INTENSITY INTEGER,
            CLAIM_CATEGORIZATION VARCHAR,
            RHETORIC_PATTERNS VARCHAR,
            POLICY_ASKS_SUPPORTED VARCHAR,
            RHETORIC_ASSESSMENT VARCHAR,
            COMPARISON_TO_OTHER_ARGUMENTS VARCHAR,
            NOTABLE_QUOTES VARCHAR,
            KEY_FINDING VARCHAR,
            CHINA_POSITIONS_COUNT INTEGER,
            TOTAL_POSITIONS_COUNT INTEGER,
            MODEL VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 9. Position Comparisons (1 row)
    total_rows += iceberg_to_snowflake(
        "RAW_POSITION_COMPARISONS",
        tables["position_comparisons"],
        """
        CREATE TABLE IF NOT EXISTS RAW_POSITION_COMPARISONS (
            COMPARISON_ID VARCHAR,
            COMPANIES_ANALYZED VARCHAR,
            COMPANY_COUNT INTEGER,
            POSITION_COUNT INTEGER,
            CONSENSUS_POSITIONS VARCHAR,
            CONTESTED_POSITIONS VARCHAR,
            COMPANY_TYPE_PATTERNS VARCHAR,
            OUTLIER_POSITIONS VARCHAR,
            COALITION_ANALYSIS VARCHAR,
            ARGUMENT_PATTERNS VARCHAR,
            KEY_FINDINGS VARCHAR,
            MODEL VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    # 10. Bill Position Analysis (21 rows)
    total_rows += iceberg_to_snowflake(
        "RAW_BILL_POSITION_ANALYSIS",
        tables["bill_position_analysis"],
        """
        CREATE TABLE IF NOT EXISTS RAW_BILL_POSITION_ANALYSIS (
            BILL_ID VARCHAR,
            BILL_NAME VARCHAR,
            COMPANIES_SUPPORTING VARCHAR,
            COMPANIES_OPPOSING VARCHAR,
            POSITION_COUNT INTEGER,
            LOBBYING_FILING_COUNT INTEGER,
            LOBBYING_ACTIVITY_COUNT INTEGER,
            LOBBYING_COMPANIES VARCHAR,
            LOBBYING_SPEND_ESTIMATE FLOAT,
            QUIET_LOBBYING VARCHAR,
            ALL_TALK VARCHAR,
            PROCESSED_AT VARCHAR
        )
        """,
        dry_run
    )

    print(f"\n=== Summary ===")
    print(f"Total rows loaded: {total_rows}")

if __name__ == "__main__":
    main()
