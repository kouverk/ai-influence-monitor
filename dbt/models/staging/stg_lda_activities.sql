with source as (
    select * from {{ source('raw', 'raw_lda_activities') }}
),

cleaned as (
    select
        activity_id,
        filing_uuid,
        issue_code,
        issue_code_display,
        description as activity_description,
        foreign_entity_issues,
        to_timestamp(processed_at) as loaded_at
    from source
)

select * from cleaned
