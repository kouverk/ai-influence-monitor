-- Sample full text from documents
-- Only run these when you need to see actual content

-- Preview first 1000 chars of a specific document
SELECT
    document_id,
    SUBSTRING(full_text, 1, 1000) as text_preview
FROM kouverk.ai_submissions_text
WHERE document_id = 'OpenAI-RFI-2025';

-- Preview first 1000 chars of all priority companies
SELECT
    t.document_id,
    m.submitter_name,
    m.submitter_type,
    SUBSTRING(t.full_text, 1, 500) as text_preview
FROM kouverk.ai_submissions_text t
JOIN kouverk.ai_submissions_metadata m ON t.document_id = m.document_id
WHERE m.submitter_type IN ('ai_lab', 'big_tech', 'trade_group')
ORDER BY m.submitter_type, m.submitter_name;

-- Join metadata + text for a single company
SELECT
    m.document_id,
    m.submitter_name,
    m.page_count,
    m.word_count,
    t.full_text
FROM kouverk.ai_submissions_metadata m
JOIN kouverk.ai_submissions_text t ON m.document_id = t.document_id
WHERE m.submitter_name LIKE '%Anthropic%';
