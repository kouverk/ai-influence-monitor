-- Total row count across all Iceberg tables
-- Quick check for capstone requirements (1M+ rows target)

SELECT SUM(cnt) AS total_records
FROM (
    SELECT COUNT(*) AS cnt FROM kouverk.ai_positions
    UNION ALL
    SELECT COUNT(*) FROM kouverk.ai_submissions_chunks
    UNION ALL
    SELECT COUNT(*) FROM kouverk.ai_submissions_metadata
    UNION ALL
    SELECT COUNT(*) FROM kouverk.ai_submissions_text
    UNION ALL
    SELECT COUNT(*) FROM kouverk.lda_activities
    UNION ALL
    SELECT COUNT(*) FROM kouverk.lda_filings
    UNION ALL
    SELECT COUNT(*) FROM kouverk.lda_lobbyists
)
