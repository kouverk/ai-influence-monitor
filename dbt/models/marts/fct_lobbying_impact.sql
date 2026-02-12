{{
    config(
        materialized='table'
    )
}}

-- Fact table for lobbying impact assessments
-- LLM-generated public interest concern scores

with scores as (
    select * from {{ ref('stg_lobbying_impact_scores') }}
),

companies as (
    select * from {{ ref('dim_company') }}
),

final as (
    select
        s.score_id,
        c.company_id,
        s.company_name,
        s.company_type,

        -- Core score
        s.concern_score,
        case
            when s.concern_score between 0 and 20 then 'aligned'
            when s.concern_score between 21 and 40 then 'minor_concerns'
            when s.concern_score between 41 and 60 then 'moderate_concerns'
            when s.concern_score between 61 and 80 then 'significant_concerns'
            when s.concern_score between 81 and 100 then 'critical_concerns'
        end as concern_level,

        -- Summary
        s.lobbying_agenda_summary,

        -- Detailed analysis (JSON arrays)
        s.top_concerning_policy_asks,
        s.public_interest_concerns,
        s.regulatory_capture_signals,
        s.china_rhetoric_assessment,
        s.accountability_stance,
        s.positive_aspects,
        s.key_flags,

        -- Counts
        s.positions_count,
        s.lobbying_filings_count,

        -- Metadata
        s.assessment_model,
        s.assessed_at

    from scores s
    left join companies c on s.company_name = c.company_name
)

select * from final
