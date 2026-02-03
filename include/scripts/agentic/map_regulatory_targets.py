#!/usr/bin/env python3
"""
Regulatory Target Mapper - Bill-level coalition analysis.

Maps company positions on specific legislation to their lobbying activity,
identifying coalition patterns and "quiet opposition" (heavy lobbying without
public position).

Usage:
    ./venv/bin/python include/scripts/agentic/map_regulatory_targets.py
    ./venv/bin/python include/scripts/agentic/map_regulatory_targets.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import boto3
import pyarrow as pa
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# BILL NAME NORMALIZATION
# =============================================================================

# Canonical bill ID -> list of variations found in data
BILL_ALIASES = {
    # Federal legislation
    "chips_act": [
        "CHIPS and Science Act",
        "CHIPS",
    ],
    "create_ai_act": [
        "CREATE AI Act",
        "CREATE AI",
    ],
    "section_230": [
        "Section 230",
    ],
    "nairr": [
        "NAIRR",
        "National AI Research Resource",
        "National AI Research Resource (NAIRR)",
    ],
    "fedramp": [
        "FedRAMP",
        "FedRAMP authorization process",
        "FedRAMP program",
    ],
    "ai_risk_management_act": [
        "Federal Artificial Intelligence Risk Management Act of 2023",
        "Federal Artificial Intelligence Risk Management Act of 2023 (S.3205/H.R. 6936)",
    ],
    "forged_act": [
        "FoRGED Act",
    ],
    "take_it_down_act": [
        "TAKE IT DOWN Act",
    ],

    # Executive Orders
    "eo_14179": [
        "Executive Order 14179",
    ],
    "eo_14158": [
        "Executive Order 14158",
    ],
    "eo_13859": [
        "Executive Order 13859",
        "President Trump's 2019 EO 13859",
    ],

    # Agency/NIST
    "nist_ai_rmf": [
        "NIST AI Risk Management Framework",
    ],
    "ai_diffusion_rule": [
        "AI Diffusion Interim Final Rule",
        "Biden Administration's AI Diffusion Rule",
        "Department of Commerce's January 2025 Interim Final Rule on the Framework for Artificial Intelligence Diffusion",
        "Framework for AI Diffusion and Due Diligence for Advanced Computing Integrated Circuits",
    ],
    "ai_safety_institute": [
        "U.S. AI Safety Institute at NIST",
    ],

    # State legislation
    "ca_sb_1047": [
        "CA SB 1047",
        "SB 1047",
        "California SB 1047",
    ],
    "state_ai_legislation": [
        "state AI legislation",
    ],

    # International
    "eu_ai_act": [
        "EU AI Act",
        "EU AI regulations",
    ],
    "eu_data_governance": [
        "EU Data Governance Act",
    ],
    "g7_hiroshima": [
        "G7 Hiroshima AI Process",
    ],

    # Workforce
    "wioa": [
        "Workforce Innovation and Opportunity Act",
        "Workforce Innovation and Opportunity Act (WIOA)",
    ],

    # AI Action Plan (meta - the RFI itself)
    "ai_action_plan": [
        "AI Action Plan",
        "Trump Administration AI Action Plan",
    ],
}

# Build reverse mapping: variation -> canonical
VARIATION_TO_CANONICAL = {}
for canonical, variations in BILL_ALIASES.items():
    for var in variations:
        VARIATION_TO_CANONICAL[var.lower()] = canonical

# LDA search terms for each bill (for fuzzy matching in activity descriptions)
BILL_LDA_SEARCH = {
    "chips_act": ["CHIPS", "CHIPS and Science"],
    "create_ai_act": ["CREATE AI"],
    "section_230": ["Section 230", "230"],
    "nairr": ["NAIRR", "National AI Research Resource"],
    "fedramp": ["FedRAMP"],
    "ai_diffusion_rule": ["AI Diffusion", "diffusion rule"],
    "ca_sb_1047": ["SB 1047", "1047"],
    "eu_ai_act": ["EU AI Act", "European AI"],
    "ai_risk_management_act": ["AI Risk Management Act"],
}


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


def get_table_names():
    """Get table names from environment."""
    schema = os.environ.get('SCHEMA')
    if not schema:
        raise ValueError("SCHEMA environment variable not set")

    return {
        "positions": f"{schema}.ai_positions",
        "filings": f"{schema}.lda_filings",
        "activities": f"{schema}.lda_activities",
        "bill_analysis": f"{schema}.bill_position_analysis",
    }


def normalize_target(target: str) -> str | None:
    """Normalize a target string to canonical bill ID."""
    if not target:
        return None

    target_lower = target.lower().strip()

    # Direct match
    if target_lower in VARIATION_TO_CANONICAL:
        return VARIATION_TO_CANONICAL[target_lower]

    # Partial match
    for var, canonical in VARIATION_TO_CANONICAL.items():
        if var in target_lower or target_lower in var:
            return canonical

    return None


def load_positions_by_bill(catalog, table_name: str) -> dict:
    """
    Load positions grouped by normalized bill ID.

    Returns:
        dict: {bill_id: {"supporting": [...], "opposing": [...], "positions": [...]}}
    """
    table = catalog.load_table(table_name)
    df = table.scan().to_arrow().to_pandas()

    # Filter to positions with targets
    df_with_target = df[df['target'].notna()].copy()
    logger.info(f"Loaded {len(df_with_target)} positions with targets")

    # Normalize targets
    df_with_target['bill_id'] = df_with_target['target'].apply(normalize_target)
    df_with_target = df_with_target[df_with_target['bill_id'].notna()]
    logger.info(f"Normalized to {df_with_target['bill_id'].nunique()} unique bills")

    # Group by bill
    bills = {}
    for bill_id in df_with_target['bill_id'].unique():
        bill_positions = df_with_target[df_with_target['bill_id'] == bill_id]

        supporting = []
        opposing = []
        all_positions = []

        for _, row in bill_positions.iterrows():
            position_info = {
                "company": row['submitter_name'],
                "stance": row.get('stance', 'unknown'),
                "policy_ask": row.get('policy_ask', ''),
                "argument": row.get('primary_argument', ''),
            }
            all_positions.append(position_info)

            stance = row.get('stance', '').lower()
            if stance in ['support', 'conditional']:
                supporting.append(row['submitter_name'])
            elif stance == 'oppose':
                opposing.append(row['submitter_name'])

        bills[bill_id] = {
            "supporting": list(set(supporting)),
            "opposing": list(set(opposing)),
            "positions": all_positions,
            "position_count": len(all_positions),
        }

    return bills


def load_lobbying_by_bill(catalog, filings_table: str, activities_table: str) -> dict:
    """
    Search LDA activities for bill mentions.

    Returns:
        dict: {bill_id: {"filings": count, "companies": {company: count}}}
    """
    # Load and join tables
    filings = catalog.load_table(filings_table).scan().to_arrow().to_pandas()
    activities = catalog.load_table(activities_table).scan().to_arrow().to_pandas()

    df = activities.merge(
        filings[['filing_uuid', 'client_name', 'expenses']],
        on='filing_uuid',
        how='left'
    )
    logger.info(f"Loaded {len(df)} LDA activities")

    # Search for each bill
    lobbying = {}
    for bill_id, search_terms in BILL_LDA_SEARCH.items():
        # Build regex pattern
        pattern = '|'.join(search_terms)
        matches = df[df['description'].str.contains(pattern, case=False, na=False)]

        if len(matches) > 0:
            # Aggregate by company
            company_counts = matches['client_name'].value_counts().to_dict()

            # Count unique filings
            filing_count = matches['filing_uuid'].nunique()

            # Estimate spend (sum of expenses from matched filings)
            matched_filings = matches['filing_uuid'].unique()
            total_expenses = filings[filings['filing_uuid'].isin(matched_filings)]['expenses'].sum()

            lobbying[bill_id] = {
                "filing_count": filing_count,
                "activity_count": len(matches),
                "companies": company_counts,
                "estimated_spend": float(total_expenses) if total_expenses else 0,
            }
            logger.info(f"  {bill_id}: {filing_count} filings, {len(company_counts)} companies")

    return lobbying


def analyze_bill_coalitions(positions: dict, lobbying: dict) -> list:
    """
    Analyze coalition patterns for each bill.

    Returns:
        list: Analysis records for each bill
    """
    results = []

    # Get all bills from either source
    all_bills = set(positions.keys()) | set(lobbying.keys())

    for bill_id in sorted(all_bills):
        pos_data = positions.get(bill_id, {"supporting": [], "opposing": [], "positions": [], "position_count": 0})
        lob_data = lobbying.get(bill_id, {"filing_count": 0, "companies": {}, "estimated_spend": 0})

        # Get human-readable name
        bill_name = BILL_ALIASES.get(bill_id, [bill_id])[0]

        # Find "quiet opposition" - companies lobbying but no public position
        lobbying_companies = set(lob_data.get("companies", {}).keys())
        position_companies = set(pos_data["supporting"]) | set(pos_data["opposing"])
        quiet_lobbying = lobbying_companies - position_companies

        # Find "all talk" - public position but minimal lobbying
        all_talk = position_companies - lobbying_companies

        analysis = {
            "bill_id": bill_id,
            "bill_name": bill_name,
            "companies_supporting": json.dumps(pos_data["supporting"]),
            "companies_opposing": json.dumps(pos_data["opposing"]),
            "position_count": pos_data["position_count"],
            "lobbying_filing_count": lob_data.get("filing_count", 0),
            "lobbying_activity_count": lob_data.get("activity_count", 0),
            "lobbying_companies": json.dumps(list(lob_data.get("companies", {}).keys())),
            "lobbying_spend_estimate": lob_data.get("estimated_spend", 0),
            "quiet_lobbying": json.dumps(list(quiet_lobbying)),  # Lobbying without public position
            "all_talk": json.dumps(list(all_talk)),  # Public position without lobbying
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

        results.append(analysis)

        # Log interesting patterns
        if quiet_lobbying:
            logger.info(f"  {bill_name}: Quiet lobbying by {list(quiet_lobbying)[:3]}")
        if len(pos_data["supporting"]) > 0 and len(pos_data["opposing"]) > 0:
            logger.info(f"  {bill_name}: Contested! Support: {pos_data['supporting'][:2]}, Oppose: {pos_data['opposing'][:2]}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Map regulatory targets to lobbying activity')
    parser.add_argument('--dry-run', action='store_true', help='Show analysis without writing')
    parser.add_argument('--fresh', action='store_true', help='Drop existing table and recreate')
    args = parser.parse_args()

    load_dotenv()

    tables = get_table_names()
    logger.info(f"Tables: {tables}")

    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Load data
    logger.info("Loading positions by bill...")
    positions = load_positions_by_bill(catalog, tables["positions"])

    logger.info("Loading lobbying by bill...")
    lobbying = load_lobbying_by_bill(catalog, tables["filings"], tables["activities"])

    # Analyze
    logger.info("Analyzing coalitions...")
    results = analyze_bill_coalitions(positions, lobbying)

    if args.dry_run:
        logger.info("=== DRY RUN - Results ===")
        for r in results:
            supporting = json.loads(r["companies_supporting"])
            opposing = json.loads(r["companies_opposing"])
            quiet = json.loads(r["quiet_lobbying"])
            print(f"\n{r['bill_name']}:")
            print(f"  Positions: {r['position_count']}, Lobbying filings: {r['lobbying_filing_count']}")
            if supporting:
                print(f"  Supporting: {supporting}")
            if opposing:
                print(f"  Opposing: {opposing}")
            if quiet:
                print(f"  Quiet lobbying (no public position): {quiet[:5]}")
        return

    # Write to Iceberg
    if args.fresh:
        try:
            catalog.drop_table(tables["bill_analysis"])
            logger.info(f"Dropped existing table {tables['bill_analysis']}")
        except Exception:
            pass

    # Create PyArrow table
    schema = pa.schema([
        pa.field("bill_id", pa.string()),
        pa.field("bill_name", pa.string()),
        pa.field("companies_supporting", pa.string()),
        pa.field("companies_opposing", pa.string()),
        pa.field("position_count", pa.int32()),
        pa.field("lobbying_filing_count", pa.int32()),
        pa.field("lobbying_activity_count", pa.int32()),
        pa.field("lobbying_companies", pa.string()),
        pa.field("lobbying_spend_estimate", pa.float64()),
        pa.field("quiet_lobbying", pa.string()),
        pa.field("all_talk", pa.string()),
        pa.field("processed_at", pa.string()),
    ])

    arrow_table = pa.Table.from_pylist(results, schema=schema)

    # Create or append to table
    try:
        table = catalog.load_table(tables["bill_analysis"])
        table.overwrite(arrow_table)
        logger.info(f"Overwrote {tables['bill_analysis']} with {len(results)} rows")
    except Exception:
        table = catalog.create_table(tables["bill_analysis"], schema=schema)
        table.append(arrow_table)
        logger.info(f"Created {tables['bill_analysis']} with {len(results)} rows")

    # Summary
    print(f"\n=== Bill Position Analysis Complete ===")
    print(f"Bills analyzed: {len(results)}")
    contested = [r for r in results if json.loads(r['companies_supporting']) and json.loads(r['companies_opposing'])]
    print(f"Contested bills (both support and opposition): {len(contested)}")
    for r in contested:
        print(f"  - {r['bill_name']}")


if __name__ == "__main__":
    main()
