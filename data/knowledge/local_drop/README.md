# Local Knowledge Drop Folder

Put psychology source files here for bulk local ingestion.

Supported formats:
- `.txt`
- `.md`
- `.json`
- `.pdf`

Suggested organization:
- `textbooks/`
- `guidelines/`
- `worksheets/`
- `course_notes/`

Run ingestion with:

```bash
uv run psych-support-bot-ingest-knowledge
```

Generated outputs:
- `data/knowledge/local_corpus.json`
- `data/knowledge/local_import_report.json`
- `data/knowledge/learning_notes.json`

Notes:
- Prefer UTF-8 text and clean PDFs when possible.
- File names matter: topic hints are inferred from names like `cbt_anxiety_manual.pdf`.
- JSON files should contain text-rich values; nested content is flattened automatically.
- Each ingestion run now also writes topic-level active learning notes that summarize repeated patterns across the crawled and local corpus.
