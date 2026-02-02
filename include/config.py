"""
Shared configuration for AI Influence Tracker extraction scripts.

This file centralizes company lists, filters, and other settings
used across multiple extraction scripts.
"""

# =============================================================================
# COMPANY CONFIGURATION
# =============================================================================

# Priority companies to process - used by both PDF and LDA extraction
# These are companies that:
# 1. Submitted to the AI Action Plan RFI
# 2. Have lobbying records we want to compare against
PRIORITY_COMPANIES = {
    # AI Labs
    "ai_labs": [
        {"name": "OpenAI", "lda_name": "OPENAI", "type": "ai_lab"},
        {"name": "Anthropic", "lda_name": "ANTHROPIC", "type": "ai_lab"},
        {"name": "Google", "lda_name": "GOOGLE LLC", "type": "ai_lab"},
        {"name": "Meta", "lda_name": "META PLATFORMS, INC.", "type": "ai_lab"},
        {"name": "MistralAI", "lda_name": "MISTRAL AI", "type": "ai_lab"},
        {"name": "Cohere", "lda_name": "COHERE", "type": "ai_lab"},
    ],
    # Big Tech
    "big_tech": [
        {"name": "Microsoft", "lda_name": "MICROSOFT CORPORATION", "type": "big_tech"},
        {"name": "Amazon", "lda_name": "AMAZON.COM, INC.", "type": "big_tech"},
        {"name": "Nvidia", "lda_name": "NVIDIA CORPORATION", "type": "big_tech"},
        {"name": "IBM", "lda_name": "IBM CORPORATION", "type": "big_tech"},
        {"name": "Palantir", "lda_name": "PALANTIR TECHNOLOGIES INC.", "type": "big_tech"},
        {"name": "Adobe", "lda_name": "ADOBE INC.", "type": "big_tech"},
        {"name": "Intel", "lda_name": "INTEL CORPORATION", "type": "big_tech"},
        {"name": "Cisco", "lda_name": "CISCO SYSTEMS, INC.", "type": "big_tech"},
        {"name": "Qualcomm", "lda_name": "QUALCOMM INCORPORATED", "type": "big_tech"},
        {"name": "Dell-Technologies", "lda_name": "DELL TECHNOLOGIES INC.", "type": "big_tech"},
        {"name": "Atlassian", "lda_name": "ATLASSIAN CORPORATION", "type": "big_tech"},
        {"name": "Cloudflare", "lda_name": "CLOUDFLARE, INC.", "type": "big_tech"},
        {"name": "ServiceNow", "lda_name": "SERVICENOW, INC.", "type": "big_tech"},
        {"name": "Snowflake", "lda_name": "SNOWFLAKE INC.", "type": "big_tech"},
        {"name": "Workday", "lda_name": "WORKDAY, INC.", "type": "big_tech"},
        {"name": "Twilio", "lda_name": "TWILIO INC.", "type": "big_tech"},
    ],
    # AI-focused companies
    "ai_focused": [
        {"name": "Snorkel", "lda_name": "SNORKEL AI, INC.", "type": "ai_focused"},
    ],
    # Trade Groups
    "trade_groups": [
        {"name": "CCIA", "lda_name": "COMPUTER & COMMUNICATIONS INDUSTRY ASSOCIATION", "type": "trade_group"},
        {"name": "TechNet", "lda_name": "TECHNET", "type": "trade_group"},
        {"name": "BSA", "lda_name": "BSA | THE SOFTWARE ALLIANCE", "type": "trade_group"},
        {"name": "US-Chamber-of-Commerce", "lda_name": "U.S. CHAMBER OF COMMERCE", "type": "trade_group"},
    ],
}


def get_all_companies() -> list[dict]:
    """Get flat list of all priority companies."""
    all_companies = []
    for category in PRIORITY_COMPANIES.values():
        all_companies.extend(category)
    return all_companies


def get_pdf_filter_names() -> list[str]:
    """Get company names for PDF filename filtering."""
    return [c["name"] for c in get_all_companies()]


def get_lda_client_names() -> list[str]:
    """Get company names for LDA API queries."""
    return [c["lda_name"] for c in get_all_companies()]


def get_company_name_mapping() -> dict[str, dict]:
    """Get mapping from PDF submitter name to LDA client name and metadata.

    Returns:
        dict: {submitter_name: {"lda_name": ..., "type": ...}}
    """
    return {
        c["name"]: {"lda_name": c["lda_name"], "type": c["type"]}
        for c in get_all_companies()
    }


def get_company_type(name: str) -> str:
    """Look up company type by name (case-insensitive)."""
    name_lower = name.lower()
    for company in get_all_companies():
        if company["name"].lower() in name_lower or name_lower in company["name"].lower():
            return company["type"]
    return "other"


# =============================================================================
# LDA FILTERING CONFIGURATION
# =============================================================================

# Only fetch filings from this year forward
LDA_MIN_YEAR = 2023

# AI-relevant LDA issue codes
# See: https://lda.senate.gov/api/v1/constants/filing/lobbyingactivityissuecodes/
LDA_AI_ISSUE_CODES = [
    "CPI",  # Computer Industry
    "SCI",  # Science/Technology
    "CPT",  # Copyright/Patent/Trademark (relevant for AI training data)
    "CSP",  # Consumer Issues/Safety/Products
    "DEF",  # Defense (AI in military)
    "HOM",  # Homeland Security
]

# Issue codes to include descriptions containing these keywords
# (for filtering activity descriptions, not issue codes)
LDA_AI_KEYWORDS = [
    "artificial intelligence",
    "AI",
    "machine learning",
    "large language model",
    "LLM",
    "generative AI",
    "foundation model",
    "neural network",
    "deep learning",
    "algorithm",
]


# =============================================================================
# SUBMITTER TYPE CLASSIFICATION
# =============================================================================

# Keywords for classifying submitter type from PDF filename
SUBMITTER_TYPE_KEYWORDS = {
    "ai_lab": ["openai", "anthropic", "google", "meta", "mistralai", "cohere", "xai"],
    "big_tech": ["microsoft", "amazon", "apple", "nvidia", "ibm", "oracle", "salesforce", "palantir", "adobe",
                 "intel", "cisco", "qualcomm", "dell", "atlassian", "cloudflare", "servicenow", "snowflake",
                 "workday", "twilio"],
    "ai_focused": ["snorkel", "scale.ai", "labelbox", "weights", "wandb", "huggingface"],
    "trade_group": ["ccia", "technet", "bsa", "iti", "chamber", "acc"],
}


def classify_submitter_type(name: str) -> str:
    """Classify submitter type based on name."""
    name_lower = name.lower().replace("-", "")

    for submitter_type, keywords in SUBMITTER_TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return submitter_type

    # Check if anonymous
    if name.startswith("AI-RFI-2025-") or name.startswith("AI-"):
        return "anonymous"

    return "other"
