# SQL Queries

Copy-paste these into Trino browser interface.

## Files

| File | Purpose |
|------|---------|
| `01_metadata_overview.sql` | Quick stats on submissions (no text data) |
| `02_chunks_overview.sql` | Chunk distribution and samples |
| `03_text_samples.sql` | Preview actual document text |
| `04_table_schemas.sql` | Verify tables exist, check structure |
| `05_lda_overview.sql` | Lobbying filings, activities, lobbyists |

## Tables

### AI Submissions (Source 1)
| Table | Description |
|-------|-------------|
| `kouverk.ai_submissions_metadata` | File info: submitter, pages, words, size |
| `kouverk.ai_submissions_text` | Full document text (join when needed) |
| `kouverk.ai_submissions_chunks` | Text chunks for LLM processing |

### LDA Lobbying (Source 2)
| Table | Description |
|-------|-------------|
| `kouverk.lda_filings` | Core filing data: client, expenses, dates |
| `kouverk.lda_activities` | Issue codes and descriptions per filing |
| `kouverk.lda_lobbyists` | Individual lobbyists per activity |

## Tips

- Start with `01_metadata_overview.sql` - fast queries, no text scanning
- Only join to `_text` table when you need actual content
- Use `SUBSTRING(full_text, 1, 500)` to preview text without pulling huge strings
