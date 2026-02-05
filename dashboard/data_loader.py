"""
Data loading layer for the AI Influence Tracker dashboard.

Loads data from Snowflake tables (via dbt staging/marts) and returns as pandas DataFrames.
Supports both local .env files and Streamlit Cloud secrets.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Load environment variables (for local development)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def get_secret(key: str, default: str = None) -> str:
    """Get a secret from Streamlit secrets or environment variables.

    Streamlit Cloud uses st.secrets, local dev uses .env files.
    """
    # Try Streamlit secrets first (for cloud deployment)
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Fall back to environment variables (for local development)
    return os.getenv(key, default)


# Add parent to path for config import (only works locally)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "include"))
    from config import get_company_name_mapping, PRIORITY_COMPANIES
except ImportError:
    # Fallback for Streamlit Cloud where include/ may not be accessible
    # Inline the company mapping so dashboard works standalone
    PRIORITY_COMPANIES = [
        {"name": "OpenAI", "lda_name": "OPENAI", "type": "ai_lab"},
        {"name": "Anthropic", "lda_name": "ANTHROPIC", "type": "ai_lab"},
        {"name": "Google", "lda_name": "GOOGLE LLC", "type": "ai_lab"},
        {"name": "Meta", "lda_name": "META PLATFORMS, INC.", "type": "ai_lab"},
        {"name": "Microsoft", "lda_name": "MICROSOFT CORPORATION", "type": "big_tech"},
        {"name": "Amazon", "lda_name": "AMAZON.COM SERVICES LLC", "type": "big_tech"},
        {"name": "Apple", "lda_name": "APPLE INC.", "type": "big_tech"},
        {"name": "IBM", "lda_name": "IBM CORPORATION", "type": "big_tech"},
        {"name": "Palantir", "lda_name": "PALANTIR TECHNOLOGIES INC.", "type": "big_tech"},
        {"name": "Salesforce", "lda_name": "SALESFORCE, INC.", "type": "big_tech"},
        {"name": "Adobe", "lda_name": "ADOBE INC.", "type": "big_tech"},
        {"name": "Oracle", "lda_name": "ORACLE CORPORATION", "type": "big_tech"},
        {"name": "NVIDIA", "lda_name": "NVIDIA CORPORATION", "type": "big_tech"},
        {"name": "Cohere", "lda_name": "COHERE INC.", "type": "ai_lab"},
        {"name": "Inflection AI", "lda_name": "INFLECTION AI, INC.", "type": "ai_lab"},
        {"name": "TechNet", "lda_name": "TECHNET", "type": "trade_group"},
        {"name": "CCIA", "lda_name": "COMPUTER & COMMUNICATIONS INDUSTRY ASSOCIATION", "type": "trade_group"},
        {"name": "BSA", "lda_name": "BSA | THE SOFTWARE ALLIANCE", "type": "trade_group"},
        {"name": "ITI", "lda_name": "INFORMATION TECHNOLOGY INDUSTRY COUNCIL (ITI)", "type": "trade_group"},
        {"name": "U.S. Chamber of Commerce", "lda_name": "U.S. CHAMBER OF COMMERCE", "type": "trade_group"},
    ]

    def get_company_name_mapping():
        return {c["name"]: c for c in PRIORITY_COMPANIES}


def get_snowflake_connection():
    """Initialize Snowflake connection."""
    import snowflake.connector

    return snowflake.connector.connect(
        account=get_secret("SNOWFLAKE_ACCOUNT"),
        user=get_secret("SNOWFLAKE_USER"),
        password=get_secret("SNOWFLAKE_PASSWORD"),
        warehouse=get_secret("SNOWFLAKE_WAREHOUSE"),
        database=get_secret("SNOWFLAKE_DATABASE"),
        # Don't set default schema - we use fully-qualified names for dbt tables
    )


# dbt schema configuration
# These must match dbt_project.yml schema settings
SNOWFLAKE_DATABASE = get_secret("SNOWFLAKE_DATABASE", "DATAEXPERT_STUDENT")
DBT_BASE_SCHEMA = get_secret("SNOWFLAKE_SCHEMA", "KOUVERK_AI_INFLUENCE")
DBT_STAGING_SCHEMA = f"{DBT_BASE_SCHEMA}_STAGING"
DBT_MARTS_SCHEMA = f"{DBT_BASE_SCHEMA}_MARTS"


def load_table_as_df(table_name: str, schema: str = None) -> pd.DataFrame:
    """Load a Snowflake table as a pandas DataFrame.

    Args:
        table_name: Name of the table (without schema prefix)
        schema: Full schema name. If None, uses DBT_STAGING_SCHEMA for STG_ tables,
                DBT_MARTS_SCHEMA for FCT_/DIM_ tables.
    """
    # Auto-detect schema from table name prefix if not specified
    if schema is None:
        if table_name.upper().startswith("STG_"):
            schema = DBT_STAGING_SCHEMA
        elif table_name.upper().startswith(("FCT_", "DIM_")):
            schema = DBT_MARTS_SCHEMA
        else:
            schema = DBT_BASE_SCHEMA

    fully_qualified_name = f"{SNOWFLAKE_DATABASE}.{schema}.{table_name}"

    try:
        conn = get_snowflake_connection()
        query = f"SELECT * FROM {fully_qualified_name}"
        df = pd.read_sql(query, conn)
        # Lowercase column names for consistency with existing code
        df.columns = [col.lower() for col in df.columns]
        conn.close()
        return df
    except Exception as e:
        print(f"Warning: Could not load table {fully_qualified_name}: {e}")
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


def get_canonical_name(submitter_name: str) -> str:
    """Get canonical company name for a submitter name.

    Handles variations like 'Anthropic-AI' -> 'Anthropic'.
    Returns original name if no match found.
    """
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
        return clean_name

    # Case-insensitive match
    for name in mapping.keys():
        if name.lower() == clean_name.lower():
            return name

    # Partial match - check if any config name is in the submitter name
    for name in mapping.keys():
        if name.lower() in clean_name.lower():
            return name

    # Check if any part of the name matches a config name
    for part in name_parts:
        for name in mapping.keys():
            if name.lower() == part.lower():
                return name

    # No match - return original
    return submitter_name


def get_lda_name(submitter_name: str) -> str | None:
    """Get LDA client name for a submitter name."""
    mapping = get_company_name_mapping()
    canonical = get_canonical_name(submitter_name)

    if canonical in mapping:
        return mapping[canonical]["lda_name"]

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
