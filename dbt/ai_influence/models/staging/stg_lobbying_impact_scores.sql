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
        to_timestamp(processed_at) as assessed_at
    from source
)

select * from cleaned
