{{
    config(
        materialized='table'
    )
}}

-- Fact table for policy positions
-- Each row = one policy ask extracted from a submission

with positions as (
    select * from {{ ref('stg_ai_positions') }}
),

companies as (
    select * from {{ ref('dim_company') }}
),

final as (
    select
        p.position_id,
        c.company_id,
        p.submitter_name as company_name,
        p.submitter_type as company_type,
        p.document_id,
        p.chunk_id,

        -- Policy ask details
        p.policy_ask,
        p.ask_category,
        p.stance,
        p.target_regulation,

        -- Arguments used
        p.primary_argument,
        p.secondary_argument,

        -- Evidence
        p.supporting_quote,
        p.confidence,

        -- Metadata
        p.extraction_model,
        p.extracted_at

    from positions p
    left join companies c on p.submitter_name = c.company_name
)

select * from final
