with source as (
    select * from {{ source('raw', 'raw_lda_lobbyists') }}
),

cleaned as (
    select
        lobbyist_record_id,
        activity_id,
        filing_uuid,
        lobbyist_id,
        first_name,
        last_name,
        first_name || ' ' || last_name as full_name,
        covered_position as former_government_position,
        is_new as is_new_lobbyist,
        to_timestamp(processed_at) as loaded_at
    from source
)

select * from cleaned
