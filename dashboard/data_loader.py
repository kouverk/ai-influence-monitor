"""
Data loading layer for the AI Influence Tracker dashboard.

Loads data from Snowflake tables (via dbt staging/marts) and returns as pandas DataFrames.
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


def get_snowflake_connection():
    """Initialize Snowflake connection."""
    import snowflake.connector

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


def load_table_as_df(table_name: str) -> pd.DataFrame:
    """Load a Snowflake table as a pandas DataFrame."""
    try:
        conn = get_snowflake_connection()
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql(query, conn)
        # Lowercase column names for consistency with existing code
        df.columns = [col.lower() for col in df.columns]
        conn.close()
        return df
    except Exception as e:
        print(f"Warning: Could not load table {table_name}: {e}")
        return pd.DataFrame()


def load_positions() -> pd.DataFrame:
    """Load policy positions from stg_ai_positions."""
    return load_table_as_df("STG_AI_POSITIONS")


def load_impact_scores() -> pd.DataFrame:
    """Load lobbying impact scores from stg_lobbying_impact_scores."""
    return load_table_as_df("STG_LOBBYING_IMPACT_SCORES")


def load_discrepancy_scores() -> pd.DataFrame:
    """Load say-vs-do discrepancy scores from stg_discrepancy_scores."""
    return load_table_as_df("STG_DISCREPANCY_SCORES")


def load_china_rhetoric() -> pd.DataFrame:
    """Load China rhetoric analysis from stg_china_rhetoric."""
    return load_table_as_df("STG_CHINA_RHETORIC")


def load_filings() -> pd.DataFrame:
    """Load LDA filings from stg_lda_filings."""
    return load_table_as_df("STG_LDA_FILINGS")


def load_activities() -> pd.DataFrame:
    """Load LDA activities from stg_lda_activities."""
    return load_table_as_df("STG_LDA_ACTIVITIES")


def load_position_comparisons() -> pd.DataFrame:
    """Load cross-company position comparisons from stg_position_comparisons."""
    return load_table_as_df("STG_POSITION_COMPARISONS")


def load_bill_analysis() -> pd.DataFrame:
    """Load bill-level coalition analysis from stg_bill_position_analysis."""
    return load_table_as_df("STG_BILL_POSITION_ANALYSIS")


def load_company_analysis() -> pd.DataFrame:
    """Load comprehensive company analysis from fct_company_analysis mart."""
    return load_table_as_df("FCT_COMPANY_ANALYSIS")


def load_bill_coalitions() -> pd.DataFrame:
    """Load bill coalition analysis from fct_bill_coalitions mart."""
    return load_table_as_df("FCT_BILL_COALITIONS")


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
    print("Testing data loader (Snowflake)...")

    data = load_all_data()

    for name, df in data.items():
        print(f"\n{name}: {len(df)} rows")
        if not df.empty:
            print(f"  Columns: {list(df.columns)}")
