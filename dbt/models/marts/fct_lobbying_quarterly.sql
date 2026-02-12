{{
    config(
        materialized='table'
    )
}}

-- Fact table for lobbying activity
-- Aggregated at company + quarter level

with filings as (
    select * from {{ ref('stg_lda_filings') }}
),

activities as (
    select * from {{ ref('stg_lda_activities') }}
),

companies as (
    select * from {{ ref('dim_company') }}
),

-- Get activity counts and issue codes per filing
filing_activities as (
    select
        f.filing_uuid,
        f.client_name,
        f.registrant_name,
        f.filing_year,
        f.filing_period,
        f.lobbying_expenses,
        count(distinct a.activity_id) as activity_count,
        listagg(distinct a.issue_code, ', ') as issue_codes,
        listagg(distinct a.issue_code_display, '; ') as issue_code_descriptions
    from filings f
    left join activities a on f.filing_uuid = a.filing_uuid
    group by f.filing_uuid, f.client_name, f.registrant_name, f.filing_year, f.filing_period, f.lobbying_expenses
),

final as (
    select
        fa.filing_uuid,
        c.company_id,
        fa.client_name as company_name,
        fa.registrant_name as lobbying_firm,
        fa.filing_year,
        fa.filing_period,
        fa.lobbying_expenses,
        fa.activity_count,
        fa.issue_codes,
        fa.issue_code_descriptions
    from filing_activities fa
    left join companies c on fa.client_name = c.company_name
)

select * from final
