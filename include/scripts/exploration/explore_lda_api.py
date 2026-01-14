#!/usr/bin/env python3
"""
Quick exploration of Senate LDA API for priority companies.
Outputs summary stats without loading full data into memory.
"""

import requests
import time

BASE_URL = "https://lda.senate.gov/api/v1/filings/"

# Priority companies to check
COMPANIES = [
    # AI Labs
    "OpenAI",
    "Anthropic",
    "Google",
    "Meta",
    "Microsoft",
    "Amazon",
    "Mistral",
    "Cohere",
    # Big Tech
    "Nvidia",
    "IBM",
    "Apple",
    "Palantir",
    "Salesforce",
    "Oracle",
    "Adobe",
    # Trade Groups
    "BSA",
    "TechNet",
    "Chamber of Commerce",
]


def get_filing_count(client_name: str) -> dict:
    """Get filing count and summary for a client."""
    try:
        resp = requests.get(
            BASE_URL,
            params={"client_name": client_name},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        count = data.get("count", 0)
        results = data.get("results", [])

        # Quick stats from first page
        years = set()
        total_expenses = 0.0
        issue_codes = set()

        for filing in results:
            years.add(filing.get("filing_year"))
            if filing.get("expenses"):
                try:
                    total_expenses += float(filing["expenses"])
                except (ValueError, TypeError):
                    pass
            for act in filing.get("lobbying_activities", []):
                if act.get("general_issue_code_display"):
                    issue_codes.add(act["general_issue_code_display"])

        return {
            "client_name": client_name,
            "total_filings": count,
            "first_page_count": len(results),
            "years": sorted(years) if years else [],
            "expenses_first_page": total_expenses,
            "issue_codes": sorted(issue_codes) if issue_codes else [],
        }

    except requests.exceptions.RequestException as e:
        return {
            "client_name": client_name,
            "error": str(e),
        }


def main():
    print("=" * 70)
    print("Senate LDA API - Priority Companies Summary")
    print("=" * 70)
    print()

    all_results = []

    for company in COMPANIES:
        print(f"Querying: {company}...", end=" ", flush=True)
        result = get_filing_count(company)
        all_results.append(result)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        elif result["total_filings"] == 0:
            print("No filings found")
        else:
            print(f"{result['total_filings']} filings, ${result['expenses_first_page']:,.0f} (page 1)")

        time.sleep(0.5)  # Be nice to the API

    print()
    print("=" * 70)
    print("Summary Table")
    print("=" * 70)
    print()
    print(f"{'Company':<25} {'Filings':>8} {'Expenses (pg1)':>15} {'Years':>15}")
    print("-" * 70)

    total_filings = 0
    total_expenses = 0.0

    for r in sorted(all_results, key=lambda x: x.get("total_filings", 0), reverse=True):
        if "error" in r:
            print(f"{r['client_name']:<25} {'ERROR':>8}")
        else:
            filings = r["total_filings"]
            expenses = r["expenses_first_page"]
            years = r["years"]
            year_range = f"{min(years)}-{max(years)}" if years else "N/A"

            print(f"{r['client_name']:<25} {filings:>8} ${expenses:>13,.0f} {year_range:>15}")
            total_filings += filings
            total_expenses += expenses

    print("-" * 70)
    print(f"{'TOTAL':<25} {total_filings:>8} ${total_expenses:>13,.0f}")
    print()

    # Show unique issue codes across all companies
    all_issues = set()
    for r in all_results:
        all_issues.update(r.get("issue_codes", []))

    if all_issues:
        print("=" * 70)
        print(f"Unique Issue Codes Across All Companies ({len(all_issues)}):")
        print("=" * 70)
        for issue in sorted(all_issues):
            print(f"  - {issue}")


if __name__ == "__main__":
    main()
