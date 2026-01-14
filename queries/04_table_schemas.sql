-- Table schemas and row counts
-- Run these to verify tables exist and check structure

-- Check all tables in your schema
SHOW TABLES IN kouverk;

-- Describe each table
DESCRIBE kouverk.ai_submissions_metadata;
DESCRIBE kouverk.ai_submissions_text;
DESCRIBE kouverk.ai_submissions_chunks;

-- Row counts
SELECT 'metadata' as table_name, COUNT(*) as row_count FROM kouverk.ai_submissions_metadata
UNION ALL
SELECT 'text' as table_name, COUNT(*) as row_count FROM kouverk.ai_submissions_text
UNION ALL
SELECT 'chunks' as table_name, COUNT(*) as row_count FROM kouverk.ai_submissions_chunks;
