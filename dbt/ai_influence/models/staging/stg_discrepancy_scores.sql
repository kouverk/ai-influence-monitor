with source as (
    select * from {{ source('raw', 'raw_discrepancy_scores') }}
),

cleaned as (
    select
        score_id,
        company_name,
        company_type,
        discrepancy_score,
        parse_json(discrepancies) as discrepancies,
        parse_json(consistent_areas) as consistent_areas,
        lobbying_priorities_vs_rhetoric,
        china_rhetoric_analysis,
        accountability_contradiction,
        key_finding,
        positions_count,
        lobbying_filings_count,
        model as assessment_model,
        to_timestamp(processed_at) as assessed_at
    from source
)

select * from cleaned
