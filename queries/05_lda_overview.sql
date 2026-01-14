-- LDA Lobbying Data Overview
-- Use these to explore lobbying filings in Trino

-- Filings summary by company
SELECT
    client_name,
    COUNT(*) as filing_count,
    SUM(expenses) as total_expenses,
    MIN(filing_year) as first_year,
    MAX(filing_year) as last_year
FROM kouverk.lda_filings
GROUP BY client_name
ORDER BY total_expenses DESC;

-- Filings by year and quarter
SELECT
    client_name,
    filing_year,
    filing_period_display,
    filing_type_display,
    expenses
FROM kouverk.lda_filings
ORDER BY client_name, filing_year DESC, filing_period;

-- Issue codes lobbied on
SELECT
    f.client_name,
    a.issue_code_display,
    COUNT(*) as times_lobbied,
    a.description
FROM kouverk.lda_filings f
JOIN kouverk.lda_activities a ON f.filing_uuid = a.filing_uuid
GROUP BY f.client_name, a.issue_code_display, a.description
ORDER BY f.client_name, times_lobbied DESC;

-- Top lobbyists by company
SELECT
    f.client_name,
    l.first_name,
    l.last_name,
    l.covered_position,
    COUNT(DISTINCT f.filing_uuid) as filings_worked
FROM kouverk.lda_filings f
JOIN kouverk.lda_lobbyists l ON f.filing_uuid = l.filing_uuid
GROUP BY f.client_name, l.first_name, l.last_name, l.covered_position
ORDER BY f.client_name, filings_worked DESC;

-- Lobbyists with government experience (revolving door)
SELECT DISTINCT
    f.client_name,
    l.first_name || ' ' || l.last_name as lobbyist_name,
    l.covered_position
FROM kouverk.lda_filings f
JOIN kouverk.lda_lobbyists l ON f.filing_uuid = l.filing_uuid
WHERE l.covered_position IS NOT NULL
  AND l.covered_position != ''
ORDER BY f.client_name, lobbyist_name;
