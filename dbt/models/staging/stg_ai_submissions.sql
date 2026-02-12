with source as (
    select * from {{ source('raw', 'raw_ai_submissions_metadata') }}
),

cleaned as (
    select
        document_id,
        filename,
        submitter_name,
        submitter_type,
        page_count,
        word_count,
        file_size_bytes,
        to_timestamp(processed_at) as extracted_at
    from source
)

select * from cleaned
