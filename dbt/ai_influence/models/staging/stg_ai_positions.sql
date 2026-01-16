with source as (
    select * from {{ source('raw', 'raw_ai_positions') }}
),

cleaned as (
    select
        position_id,
        chunk_id,
        document_id,
        submitter_name,
        submitter_type,
        policy_ask,
        ask_category,
        stance,
        target as target_regulation,
        primary_argument,
        secondary_argument,
        supporting_quote,
        confidence,
        model as extraction_model,
        to_timestamp(processed_at) as extracted_at
    from source
)

select * from cleaned
