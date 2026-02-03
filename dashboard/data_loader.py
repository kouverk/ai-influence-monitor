"""
Data loading layer for the AI Influence Tracker dashboard.

Loads data from Iceberg tables via PyIceberg and returns as pandas DataFrames.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add parent to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent / "include"))
from config import get_company_name_mapping, PRIORITY_COMPANIES


def get_catalog():
    """Initialize PyIceberg catalog."""
    from pyiceberg.catalog import load_catalog

    return load_catalog(
        "glue",
        **{
            "type": "glue",
            "region_name": os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
            "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID"),
            "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "s3.region": os.getenv("AWS_DEFAULT_REGION", "us-west-2"),
        }
    )


def get_schema() -> str:
    """Get schema name from environment."""
    return os.getenv("SCHEMA", "kouverk")


def load_table_as_df(table_name: str) -> pd.DataFrame:
    """Load an Iceberg table as a pandas DataFrame."""
    try:
        catalog = get_catalog()
        schema = get_schema()
        full_name = f"{schema}.{table_name}"

        table = catalog.load_table(full_name)
        df = table.scan().to_pandas()
        return df
    except Exception as e:
        print(f"Warning: Could not load table {table_name}: {e}")
        return pd.DataFrame()


def load_positions() -> pd.DataFrame:
    """Load policy positions from ai_positions table."""
    return load_table_as_df("ai_positions")


def load_impact_scores() -> pd.DataFrame:
    """Load lobbying impact scores."""
    return load_table_as_df("lobbying_impact_scores")


def load_discrepancy_scores() -> pd.DataFrame:
    """Load say-vs-do discrepancy scores."""
    return load_table_as_df("discrepancy_scores")


def load_china_rhetoric() -> pd.DataFrame:
    """Load China rhetoric analysis."""
    return load_table_as_df("china_rhetoric_analysis")


def load_filings() -> pd.DataFrame:
    """Load LDA filings."""
    return load_table_as_df("lda_filings")


def load_activities() -> pd.DataFrame:
    """Load LDA activities."""
    return load_table_as_df("lda_activities")


def load_position_comparisons() -> pd.DataFrame:
    """Load cross-company position comparisons."""
    return load_table_as_df("position_comparisons")


def load_bill_analysis() -> pd.DataFrame:
    """Load bill-level coalition analysis."""
    return load_table_as_df("bill_position_analysis")


def get_lda_name(submitter_name: str) -> str | None:
    """Get LDA client name for a submitter name."""
    mapping = get_company_name_mapping()

    # Strip common suffixes from submitter name
    clean_name = submitter_name
    for suffix in ["-AI", "-ai", "_AI", "_ai"]:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)]
            break

    # Also handle names like "Ryan-Hagemann-IBM-AI" -> try to find "IBM"
    name_parts = clean_name.replace("-", " ").replace("_", " ").split()

    # Direct match
    if clean_name in mapping:
        return mapping[clean_name]["lda_name"]

    # Case-insensitive match
    for name, info in mapping.items():
        if name.lower() == clean_name.lower():
            return info["lda_name"]

    # Partial match - check if any config name is in the submitter name
    for name, info in mapping.items():
        if name.lower() in clean_name.lower():
            return info["lda_name"]

    # Check if any part of the name matches a config name
    for part in name_parts:
        for name, info in mapping.items():
            if name.lower() == part.lower():
                return info["lda_name"]

    return None


# LDA client name aliases - map canonical name to all variants that should be summed
LDA_NAME_ALIASES = {
    "OPENAI": ["OPENAI", "OPENAI OPCO, LLC", "OPENAI, INC."],
    "ANTHROPIC": ["ANTHROPIC", "ANTHROPIC, PBC", "AQUIA GROUP ON BEHALF OF ANTHROPIC, PBC"],
    "TECHNET": ["TECHNET", "TECHNOLOGY NETWORK (AKA TECHNET)", "TECHNOLOGY NETWORK AKA TECHNET"],
    "GOOGLE LLC": ["GOOGLE LLC", "GOOGLE CLIENT SERVICES LLC (FKA GOOGLE LLC)"],
    "PALANTIR TECHNOLOGIES INC.": ["PALANTIR TECHNOLOGIES INC.", "J.A. GREEN AND COMPANY (FOR PALANTIR TECHNOLOGIES INC.)"],
    "U.S. CHAMBER OF COMMERCE": [
        "U.S. CHAMBER OF COMMERCE",
        "U.S. CHAMBER OF COMMERCE CENTER FOR CAPITAL MARKETS COMPETITIVENESS",
        "U.S. CHAMBER OF COMMERCE GLOBAL INNOVATION POLICY CENTER",
        "U.S. CHAMBER OF COMMERCE INSTITUTE FOR LEGAL REFORM",
        "U.S. CHAMBER OF COMMERCE, GLOBAL INTELLECTUAL PROPERTY CENTER",
    ],
}


def get_lda_aliases(lda_name: str) -> list[str]:
    """Get all LDA client name variants for a canonical name."""
    if lda_name in LDA_NAME_ALIASES:
        return LDA_NAME_ALIASES[lda_name]
    # Also check if the lda_name is an alias itself
    for canonical, aliases in LDA_NAME_ALIASES.items():
        if lda_name.upper() in [a.upper() for a in aliases]:
            return aliases
    return [lda_name]


def load_all_data() -> dict:
    """Load all data needed for the dashboard.

    Returns:
        dict with keys:
        - positions: policy positions DataFrame
        - impact_scores: lobbying impact scores DataFrame
        - discrepancy_scores: say-vs-do discrepancy scores DataFrame
        - china_rhetoric: China rhetoric analysis DataFrame
        - filings: LDA filings DataFrame
        - activities: LDA activities DataFrame
        - comparisons: position comparisons DataFrame
        - bill_analysis: bill-level coalition analysis DataFrame
    """
    return {
        "positions": load_positions(),
        "impact_scores": load_impact_scores(),
        "discrepancy_scores": load_discrepancy_scores(),
        "china_rhetoric": load_china_rhetoric(),
        "filings": load_filings(),
        "activities": load_activities(),
        "comparisons": load_position_comparisons(),
        "bill_analysis": load_bill_analysis(),
    }


# For testing
if __name__ == "__main__":
    print("Testing data loader...")

    data = load_all_data()

    for name, df in data.items():
        print(f"\n{name}: {len(df)} rows")
        if not df.empty:
            print(f"  Columns: {list(df.columns)}")
