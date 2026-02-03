{{
    config(
        materialized='table'
    )
}}

with bill_analysis as (
    select
        bill_id,
        bill_name,
        companies_supporting,
        companies_opposing,
        position_count,
        lobbying_filing_count,
        lobbying_activity_count,
        lobbying_companies,
        lobbying_spend_estimate,
        quiet_lobbying,
        all_talk,
        analyzed_at
    from {{ ref('stg_bill_position_analysis') }}
)

select
    bill_id,
    bill_name,

    -- Position counts
    position_count as public_positions,
    array_size(companies_supporting) as supporting_count,
    array_size(companies_opposing) as opposing_count,

    -- Lobbying metrics
    lobbying_filing_count,
    lobbying_activity_count,
    lobbying_spend_estimate,
    array_size(lobbying_companies) as lobbying_company_count,

    -- Quiet lobbying analysis
    array_size(quiet_lobbying) as quiet_lobbying_count,
    array_size(all_talk) as all_talk_count,

    -- Calculated flags
    case
        when array_size(companies_supporting) > 0 and array_size(companies_opposing) > 0
        then true else false
    end as is_contested,

    case
        when lobbying_filing_count > 0 and position_count = 0
        then true else false
    end as is_pure_quiet_lobbying,

    -- Raw arrays for drill-down
    companies_supporting,
    companies_opposing,
    lobbying_companies,
    quiet_lobbying,
    all_talk,

    analyzed_at

from bill_analysis
