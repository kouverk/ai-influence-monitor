{{
    config(
        materialized='table'
    )
}}

with positions as (
    select
        submitter_name as company_name,
        count(*) as position_count,
        count(distinct policy_ask) as unique_policy_asks,
        count(distinct primary_argument) as unique_arguments
    from {{ ref('stg_ai_positions') }}
    group by submitter_name
),

impact_scores as (
    select
        company_name,
        company_type,
        concern_score,
        lobbying_agenda_summary,
        top_concerning_policy_asks,
        public_interest_concerns,
        regulatory_capture_signals,
        china_rhetoric_assessment as impact_china_assessment,
        accountability_stance,
        positive_aspects,
        key_flags,
        positions_count as impact_positions_count,
        lobbying_filings_count as impact_lobbying_count,
        assessed_at as impact_assessed_at
    from {{ ref('stg_lobbying_impact_scores') }}
),

discrepancy_scores as (
    select
        company_name,
        discrepancy_score,
        discrepancies,
        consistent_areas,
        lobbying_priorities_vs_rhetoric,
        china_rhetoric_analysis as discrepancy_china_analysis,
        accountability_contradiction,
        key_finding as discrepancy_key_finding,
        assessed_at as discrepancy_assessed_at
    from {{ ref('stg_discrepancy_scores') }}
),

china_rhetoric as (
    select
        company_name,
        rhetoric_intensity,
        claim_categorization,
        rhetoric_patterns,
        policy_asks_supported as china_policy_asks,
        rhetoric_assessment,
        comparison_to_other_arguments,
        notable_quotes as china_notable_quotes,
        key_finding as china_key_finding,
        china_positions_count,
        total_positions_count as china_total_positions,
        assessed_at as china_assessed_at
    from {{ ref('stg_china_rhetoric') }}
),

companies as (
    select * from {{ ref('dim_company') }}
)

select
    c.company_id,
    c.company_name,
    c.company_type,
    -- Sort order: ai_lab first, then big_tech, then trade_group
    case c.company_type
        when 'ai_lab' then 1
        when 'big_tech' then 2
        when 'trade_group' then 3
        else 4
    end as company_type_sort,
    coalesce(p.position_count, 0) as position_count,
    coalesce(p.unique_policy_asks, 0) as unique_policy_asks,
    coalesce(p.unique_arguments, 0) as unique_arguments,

    -- Impact scores
    i.concern_score,
    i.lobbying_agenda_summary,
    i.top_concerning_policy_asks,
    i.public_interest_concerns,
    i.regulatory_capture_signals,
    i.accountability_stance,
    i.positive_aspects,
    i.key_flags,

    -- Discrepancy scores
    d.discrepancy_score,
    d.discrepancies,
    d.consistent_areas,
    d.lobbying_priorities_vs_rhetoric,
    d.accountability_contradiction,
    d.discrepancy_key_finding,

    -- China rhetoric
    r.rhetoric_intensity as china_rhetoric_intensity,
    r.claim_categorization as china_claim_categorization,
    r.rhetoric_patterns as china_rhetoric_patterns,
    r.rhetoric_assessment as china_rhetoric_assessment,
    r.china_key_finding,
    r.china_positions_count,

    -- Timestamps
    greatest(
        coalesce(i.impact_assessed_at, '1900-01-01'),
        coalesce(d.discrepancy_assessed_at, '1900-01-01'),
        coalesce(r.china_assessed_at, '1900-01-01')
    ) as last_assessed_at

from companies c
left join positions p on c.company_name = p.company_name
left join impact_scores i on c.company_name = i.company_name
left join discrepancy_scores d on c.company_name = d.company_name
left join china_rhetoric r on c.company_name = r.company_name
where coalesce(p.position_count, 0) > 0
