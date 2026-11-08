# Local LLM and SQLite implementation

This document describes the metadata-processing portion of the research-paper
pipeline. It covers configuration, runtime behavior, failure handling, data
contracts, and verification.

## Responsibilities

After a PDF has been converted to Markdown, the implementation:

1. reads the Markdown without modifying the source file;
2. sends it to an OpenAI-compatible local LLM;
3. parses and validates the JSON response;
4. retries once if the JSON is malformed or fails validation;
5. stores the validated result in the local SQLite database; and
6. returns the metadata through Airflow for the later HTML and Discord tasks.

The main implementation files are:

- `src/llm_processing.py`: client creation, prompting, JSON parsing, retry, and
  validation;
- `src/database.py`: schema creation, idempotent writes, and reads; and
- `dags/paper_pipeline.py`: task orchestration and hand-off to later tasks.

## Configuration

The implementation does not contain machine-specific paths, model names, or
credentials. It uses these environment variables:

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `LOCAL_LLM_MODEL` | Yes | none | Model name exposed by the local server |
| `LOCAL_LLM_BASE_URL` | No | `http://localhost:11434/v1` | OpenAI-compatible API root |
| `LOCAL_LLM_API_KEY` | No | `ollama` | API key; local servers usually ignore it |
| `LOCAL_LLM_JSON_MODE` | No | `true` | Send OpenAI JSON response mode |
| `LOCAL_LLM_MAX_DOCUMENT_CHARS` | No | `60000` | Maximum Markdown characters sent |
| `RESEARCH_PAPERS_DIR` | Yes | none | Local or Google Drive-synced PDF directory |

Set `LOCAL_LLM_JSON_MODE=false` if a selected server or model does not accept
`response_format={"type": "json_object"}`. The prompt still explicitly asks
for JSON, and the same parsing and validation rules apply.

The document-size limit prevents unexpectedly large papers from exceeding a
local model's context window. The beginning is retained because it normally
contains the title, abstract, and introduction. Increase the value only when
the chosen model has sufficient context capacity.

## LLM response contract

The LLM must return one JSON object:

```json
{
  "title": "Paper title",
  "summary": "A concise summary of the paper",
  "keywords": ["keyword one", "keyword two"],
  "category": "Data Engineering"
}
```

Validation requires all four fields. `title`, `summary`, and `category` must be
non-empty strings. `keywords` must be a non-empty list containing only
non-empty strings. Values are trimmed, duplicate keywords are removed without
changing their order, and unrecognized fields are not persisted.

Invalid JSON and invalid field structures cause one new LLM request. After two
invalid responses, `MetadataGenerationError` fails the task. Transport errors
are allowed to propagate so Airflow records the real server error. After
restoring the local service, rerun the failed task or trigger a new DAG run.

## Database contract

The database is local at `data/papers.db`, outside the Google Drive-synced
folder. Its schema is:

```sql
CREATE TABLE papers (
    filename TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    keywords TEXT NOT NULL,
    category TEXT NOT NULL
);
```

`keywords` is stored as a JSON string and decoded by `fetch_all_papers()`.
Writes use `ON CONFLICT(filename) DO UPDATE`, making them idempotent during an
Airflow retry. The filename is only inserted after successful LLM validation;
therefore a failed paper remains discoverable on the next DAG run.

## Airflow data flow

The tasks exchange JSON-serializable values through XCom:

```text
find_new_papers: ["/drive/papers/example.pdf"]
        |
        v
convert_papers: [{"filename": "example.pdf", "markdown_path": ".../example.md"}]
        |
        v
process_papers: [{"filename": ..., "markdown_path": ..., "title": ...,
                  "summary": ..., "keywords": [...], "category": ...}]
```

Keeping `filename` in the conversion result is important: the database uses the
original PDF name as its unique identifier, while the LLM reads the generated
Markdown path.

## Verification

Run the dependency-independent unit suite inside the virtual environment:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

For an integration test, start the local server, export the environment
variables, place one PDF in `RESEARCH_PAPERS_DIR`, and trigger the DAG. Verify
the stored result with:

```bash
sqlite3 data/papers.db \
  'SELECT filename, title, keywords, category FROM papers;'
```

Useful report evidence includes the Airflow graph, successful task logs, the
SQLite query output, the generated HTML page, and the Discord notification.
