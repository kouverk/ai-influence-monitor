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
        to_timestamp(processed_at) as assessed_at,
        row_number() over (partition by company_name order by processed_at desc) as rn
    from source
),

-- Keep only the latest assessment per company
deduplicated as (
    select * from cleaned where rn = 1
)

select
    analysis_id,
    company_name,
    company_type,
    rhetoric_intensity,
    claim_categorization,
    rhetoric_patterns,
    policy_asks_supported,
    rhetoric_assessment,
    comparison_to_other_arguments,
    notable_quotes,
    key_finding,
    china_positions_count,
    total_positions_count,
    assessment_model,
    assessed_at
from deduplicated
