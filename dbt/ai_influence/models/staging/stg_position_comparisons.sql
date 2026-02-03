with source as (
    select * from {{ source('raw', 'raw_position_comparisons') }}
),

cleaned as (
    select
        comparison_id,
        parse_json(companies_analyzed) as companies_analyzed,
        company_count,
        position_count,
        parse_json(consensus_positions) as consensus_positions,
        parse_json(contested_positions) as contested_positions,
        parse_json(company_type_patterns) as company_type_patterns,
        parse_json(outlier_positions) as outlier_positions,
        parse_json(coalition_analysis) as coalition_analysis,
        parse_json(argument_patterns) as argument_patterns,
        parse_json(key_findings) as key_findings,
        model as assessment_model,
        to_timestamp(processed_at) as assessed_at
    from source
)

select * from cleaned
