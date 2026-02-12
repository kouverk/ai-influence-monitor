with source as (
    select * from {{ source('raw', 'raw_lobbying_impact_scores') }}
),

cleaned as (
    select
        score_id,
        company_name,
        company_type,
        concern_score,
        lobbying_agenda_summary,
        parse_json(top_concerning_policy_asks) as top_concerning_policy_asks,
        parse_json(public_interest_concerns) as public_interest_concerns,
        parse_json(regulatory_capture_signals) as regulatory_capture_signals,
        china_rhetoric_assessment,
        accountability_stance,
        parse_json(positive_aspects) as positive_aspects,
        parse_json(key_flags) as key_flags,
        positions_count,
        lobbying_filings_count,
        model as assessment_model,
        to_timestamp(processed_at) as assessed_at,
        row_number() over (partition by company_name order by processed_at desc) as rn
    from source
),

-- Keep only the latest assessment per company
deduplicated as (
    select * from cleaned where rn = 1
)

select
    score_id,
    company_name,
    company_type,
    concern_score,
    lobbying_agenda_summary,
    top_concerning_policy_asks,
    public_interest_concerns,
    regulatory_capture_signals,
    china_rhetoric_assessment,
    accountability_stance,
    positive_aspects,
    key_flags,
    positions_count,
    lobbying_filings_count,
    assessment_model,
    assessed_at
from deduplicated
