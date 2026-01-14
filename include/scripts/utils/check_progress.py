#!/usr/bin/env python3
"""
Check extraction progress across all Iceberg tables.

Usage:
    ./venv/bin/python include/scripts/utils/check_progress.py
"""

import os
import sys
from datetime import datetime

import boto3
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog


def get_catalog():
    """Initialize PyIceberg catalog."""
    aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
    s3_bucket = os.environ.get('AWS_S3_BUCKET_TABULAR')

    boto3.setup_default_session(region_name=aws_region)

    return load_catalog(
        name="glue_catalog",
        **{
            "type": "glue",
            "region": aws_region,
            "warehouse": f"s3://{s3_bucket}/iceberg-warehouse/",
        }
    )


def check_table(catalog, table_name: str) -> dict:
    """Check if table exists and get row count."""
    try:
        table = catalog.load_table(table_name)
        df = table.scan().to_arrow().to_pandas()
        return {"exists": True, "rows": len(df)}
    except Exception as e:
        return {"exists": False, "rows": 0, "error": str(e)}


def main():
    load_dotenv()

    schema = os.environ.get('SCHEMA')
    if not schema:
        print("Error: SCHEMA environment variable not set")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  AI Influence Tracker - Progress Report")
    print(f"  Schema: {schema}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    catalog = get_catalog()

    # Check all tables
    tables = {
        "AI Submissions": {
            "metadata": f"{schema}.ai_submissions_metadata",
            "text": f"{schema}.ai_submissions_text",
            "chunks": f"{schema}.ai_submissions_chunks",
        },
        "LDA Lobbying": {
            "filings": f"{schema}.lda_filings",
            "activities": f"{schema}.lda_activities",
            "lobbyists": f"{schema}.lda_lobbyists",
        },
        "LLM Extraction": {
            "positions": f"{schema}.ai_positions",
        }
    }

    for section, section_tables in tables.items():
        print(f"📊 {section}")
        print("-" * 40)
        for name, table_name in section_tables.items():
            result = check_table(catalog, table_name)
            if result["exists"]:
                print(f"  ✅ {name}: {result['rows']:,} rows")
            else:
                print(f"  ❌ {name}: not found")
        print()

    # Position extraction progress
    print("🤖 Position Extraction Progress")
    print("-" * 40)

    chunks_result = check_table(catalog, f"{schema}.ai_submissions_chunks")
    positions_result = check_table(catalog, f"{schema}.ai_positions")

    if chunks_result["exists"] and positions_result["exists"]:
        # Get unique chunk_ids from positions
        positions_table = catalog.load_table(f"{schema}.ai_positions")
        positions_df = positions_table.scan().to_arrow().to_pandas()
        chunks_processed = positions_df["chunk_id"].nunique()
        total_chunks = chunks_result["rows"]
        remaining = total_chunks - chunks_processed
        pct = (chunks_processed / total_chunks * 100) if total_chunks > 0 else 0

        print(f"  Chunks processed: {chunks_processed} / {total_chunks} ({pct:.1f}%)")
        print(f"  Chunks remaining: {remaining}")
        print(f"  Positions extracted: {len(positions_df):,}")
        print(f"  Avg positions/chunk: {len(positions_df) / chunks_processed:.1f}" if chunks_processed > 0 else "")

        # Show by submitter
        print(f"\n  By submitter:")
        by_submitter = positions_df.groupby("submitter_name").agg({
            "position_id": "count",
            "chunk_id": "nunique"
        }).rename(columns={"position_id": "positions", "chunk_id": "chunks"})
        by_submitter = by_submitter.sort_values("positions", ascending=False)

        for submitter, row in by_submitter.head(10).iterrows():
            print(f"    {submitter}: {row['positions']} positions ({row['chunks']} chunks)")

    elif chunks_result["exists"]:
        print(f"  Chunks available: {chunks_result['rows']}")
        print(f"  Positions extracted: 0 (not started)")

    print()


if __name__ == "__main__":
    main()
