-- Overview of text chunks
-- Use this to understand chunking distribution

-- Chunks per document
SELECT
    m.submitter_name,
    m.submitter_type,
    m.word_count as doc_words,
    c.total_chunks,
    ROUND(m.word_count * 1.0 / c.total_chunks, 0) as avg_words_per_chunk
FROM kouverk.ai_submissions_metadata m
JOIN (
    SELECT document_id, MAX(total_chunks) as total_chunks
    FROM kouverk.ai_submissions_chunks
    GROUP BY document_id
) c ON m.document_id = c.document_id
ORDER BY c.total_chunks DESC;

-- Total chunk stats
SELECT
    COUNT(*) as total_chunks,
    COUNT(DISTINCT document_id) as total_docs,
    ROUND(AVG(word_count), 0) as avg_chunk_words,
    MIN(word_count) as min_chunk_words,
    MAX(word_count) as max_chunk_words
FROM kouverk.ai_submissions_chunks;

-- Sample chunk from a specific document (e.g., OpenAI)
SELECT
    chunk_id,
    chunk_index,
    total_chunks,
    word_count,
    SUBSTRING(chunk_text, 1, 500) as chunk_preview
FROM kouverk.ai_submissions_chunks
WHERE document_id = 'OpenAI-RFI-2025'
ORDER BY chunk_index;
