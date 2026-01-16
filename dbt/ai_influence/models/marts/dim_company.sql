{{
    config(
        materialized='table'
    )
}}

-- Build company dimension from multiple sources
-- Combines: submitters from AI positions + clients from LDA filings + impact scores

with position_companies as (
    select distinct
        submitter_name as company_name,
        submitter_type as company_type,
        'ai_submission' as source
    from {{ ref('stg_ai_positions') }}
),

lda_companies as (
    select distinct
        client_name as company_name,
        null as company_type,
        'lda_filing' as source
    from {{ ref('stg_lda_filings') }}
),

scored_companies as (
    select distinct
        company_name,
        company_type,
        'impact_score' as source
    from {{ ref('stg_lobbying_impact_scores') }}
),

all_companies as (
    select * from position_companies
    union
    select * from lda_companies
    union
    select * from scored_companies
),

-- Deduplicate and pick best company_type
deduped as (
    select
        company_name,
        max(company_type) as company_type,  -- Pick non-null if available
        count(distinct source) as source_count
    from all_companies
    group by company_name
),

-- Add row number for surrogate key
final as (
    select
        row_number() over (order by company_name) as company_id,
        company_name,
        coalesce(company_type, 'unknown') as company_type,
        source_count,
        source_count > 1 as has_multiple_sources
    from deduped
)

select * from final
