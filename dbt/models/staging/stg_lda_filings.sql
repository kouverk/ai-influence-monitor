with source as (
    select * from {{ source('raw', 'raw_lda_filings') }}
),

cleaned as (
    select
        filing_uuid,
        filing_type,
        filing_type_display,
        filing_year,
        filing_period,
        filing_period_display,
        expenses as lobbying_expenses,
        dt_posted as posted_date,
        termination_date,
        registrant_id,
        registrant_name,
        client_id,
        client_name,
        client_description,
        client_state,
        to_timestamp(processed_at) as loaded_at
    from source
)

select * from cleaned
