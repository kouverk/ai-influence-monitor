-- Overview of submissions metadata
-- Quick stats without touching text data

-- Count by submitter type
SELECT
    submitter_type,
    COUNT(*) as doc_count,
    SUM(page_count) as total_pages,
    SUM(word_count) as total_words,
    ROUND(AVG(page_count), 1) as avg_pages,
    ROUND(AVG(word_count), 0) as avg_words
FROM kouverk.ai_submissions_metadata
GROUP BY submitter_type
ORDER BY doc_count DESC;

-- All documents sorted by size
SELECT
    document_id,
    submitter_name,
    submitter_type,
    page_count,
    word_count,
    ROUND(file_size_bytes / 1024.0, 1) as size_kb
FROM kouverk.ai_submissions_metadata
ORDER BY word_count DESC;

-- Just the priority companies
SELECT
    document_id,
    submitter_name,
    submitter_type,
    page_count,
    word_count
FROM kouverk.ai_submissions_metadata
WHERE submitter_type IN ('ai_lab', 'big_tech', 'trade_group')
ORDER BY submitter_type, submitter_name;
