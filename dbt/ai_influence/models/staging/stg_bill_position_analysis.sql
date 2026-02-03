with source as (
    select * from {{ source('raw', 'raw_bill_position_analysis') }}
),

cleaned as (
    select
        bill_id,
        bill_name,
        parse_json(companies_supporting) as companies_supporting,
        parse_json(companies_opposing) as companies_opposing,
        position_count,
        lobbying_filing_count,
        lobbying_activity_count,
        parse_json(lobbying_companies) as lobbying_companies,
        lobbying_spend_estimate,
        parse_json(quiet_lobbying) as quiet_lobbying,
        parse_json(all_talk) as all_talk,
        to_timestamp(processed_at) as analyzed_at
    from source
)

select * from cleaned
