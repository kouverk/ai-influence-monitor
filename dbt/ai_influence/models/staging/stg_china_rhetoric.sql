with source as (
    select * from {{ source('raw', 'raw_china_rhetoric_analysis') }}
),

cleaned as (
    select
        analysis_id,
        company_name,
        company_type,
        rhetoric_intensity,
        parse_json(claim_categorization) as claim_categorization,
        parse_json(rhetoric_patterns) as rhetoric_patterns,
        parse_json(policy_asks_supported) as policy_asks_supported,
        rhetoric_assessment,
        comparison_to_other_arguments,
        parse_json(notable_quotes) as notable_quotes,
        key_finding,
        china_positions_count,
        total_positions_count,
        model as assessment_model,
        to_timestamp(processed_at) as assessed_at
    from source
)

select * from cleaned
