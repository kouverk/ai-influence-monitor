-- AI Positions Overview
-- Use these to explore LLM-extracted policy positions in Trino

-- Positions by submitter and topic
SELECT
    submitter_name,
    topic,
    stance,
    COUNT(*) as position_count,
    ROUND(AVG(confidence), 2) as avg_confidence
FROM kouverk.ai_positions
GROUP BY submitter_name, topic, stance
ORDER BY submitter_name, topic, stance;

-- Topic breakdown across all submissions
SELECT
    topic,
    COUNT(*) as total_positions,
    COUNT(DISTINCT submitter_name) as unique_submitters,
    ROUND(AVG(confidence), 2) as avg_confidence
FROM kouverk.ai_positions
GROUP BY topic
ORDER BY total_positions DESC;

-- Stance distribution by submitter type
SELECT
    submitter_type,
    stance,
    COUNT(*) as position_count
FROM kouverk.ai_positions
GROUP BY submitter_type, stance
ORDER BY submitter_type,
    CASE stance
        WHEN 'strong_support' THEN 1
        WHEN 'support' THEN 2
        WHEN 'neutral' THEN 3
        WHEN 'oppose' THEN 4
        WHEN 'strong_oppose' THEN 5
    END;

-- Sample quotes by topic
SELECT
    topic,
    submitter_name,
    stance,
    supporting_quote,
    confidence
FROM kouverk.ai_positions
WHERE confidence > 0.8
ORDER BY topic, confidence DESC;

-- Processing status: chunks processed vs total
SELECT
    (SELECT COUNT(DISTINCT chunk_id) FROM kouverk.ai_positions) as chunks_processed,
    (SELECT COUNT(*) FROM kouverk.ai_submissions_chunks) as total_chunks,
    (SELECT COUNT(*) FROM kouverk.ai_positions) as total_positions;
