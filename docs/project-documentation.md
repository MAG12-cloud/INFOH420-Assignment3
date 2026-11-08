# INFOH420 Assignment 3 — Project documentation

## 1. Purpose and scope

This project implements an automated research-paper ingestion pipeline with
Apache Airflow. It discovers new PDF files, converts them to Markdown, asks a
locally hosted language model for structured metadata, stores validated data in
SQLite, generates a searchable static website, and sends a Discord
notification.

The default setup keeps all runtime files inside the repository. The PDF input
and HTML output directories can instead point to folders synchronized by
Google Drive. No Google Drive webhook is required for this design: Airflow
polls the synchronized local folder every hour.

## 2. Functional requirements

The implementation provides:

- hourly discovery of previously unprocessed PDFs;
- PDF-to-Markdown conversion with local caching;
- local LLM processing through an OpenAI-compatible endpoint;
- strict validation of `title`, `summary`, `keywords`, and `category`;
- one retry when an LLM response is invalid JSON or violates the contract;
- idempotent SQLite persistence keyed by the PDF filename;
- a static HTML catalogue with text search and category filtering; and
- one Discord embed for every newly processed paper.

## 3. System architecture

```text
PDF input directory
        |
        v
find_new_papers ---- checks filenames in data/papers.db
        |
        v
convert_papers ----- PyMuPDF4LLM -> data/markdown/*.md
        |
        v
process_papers ----- Ollama/LM Studio -> validate -> SQLite
        |
        +---------------------------+
        |                           |
        v                           v
generate_website              send_notifications
RESEARCH_OUTPUT_DIR/index.html      Discord webhook
```

Airflow passes only JSON-serializable paths and dictionaries between tasks via
XCom. Large Markdown documents remain on disk rather than being copied into
Airflow's metadata database.

## 4. Repository layout

| Path | Responsibility |
| --- | --- |
| `dags/paper_pipeline.py` | DAG definition and five task functions |
| `src/pdf_processing.py` | PDF discovery and atomic Markdown conversion |
| `src/llm_processing.py` | Local client, prompt, parsing, validation, retry |
| `src/database.py` | SQLite schema, upsert, and read operations |
| `src/html_generator.py` | Static catalogue generation and browser filtering |
| `src/discord_notification.py` | Discord webhook payload and HTTP request |
| `tests/` | Unit tests for metadata validation and database behavior |
| `data/papers/` | Default PDF input directory, ignored by Git |
| `data/markdown/` | Extracted Markdown cache, ignored by Git |
| `data/output/` | Default generated website directory, ignored by Git |
| `data/papers.db` | Local SQLite database, ignored by Git |

## 5. Airflow orchestration

The DAG ID is `paper_pipeline`. It uses the `Europe/Brussels` timezone, runs
with `schedule="@hourly"`, has `catchup=False`, and permits one active run at a
time. Its logical start date is 1 November 2026.

Task contracts are:

| Task | Input | Output | Important behavior |
| --- | --- | --- | --- |
| `find_new_papers` | `RESEARCH_PAPERS_DIR`, SQLite state | list of PDF paths | Scans only the directory's immediate children and sorts paths |
| `convert_papers` | list of PDF paths | filename/Markdown-path dictionaries | Reuses Markdown if it is newer than the PDF |
| `process_papers` | converted-paper dictionaries | dictionaries containing metadata | Calls the local LLM and saves each successful result |
| `generate_website` | processed-paper dictionaries | generated HTML path | Always rebuilds the page from all database rows |
| `send_notifications` | processed-paper dictionaries | none | Sends one embed for each paper processed in this run |

The website and notification tasks run in parallel after processing succeeds.
If no new PDF is found, processing returns an empty list, the website is still
regenerated, and no notification is sent.

## 6. PDF discovery and conversion

Discovery compares each direct child ending in `.pdf` (case-insensitive) with
the `filename` values already stored in SQLite. Identity is filename-based,
not content-based. Replacing a file while keeping its name therefore does not
cause reprocessing.

PyMuPDF4LLM converts a new PDF to `data/markdown/<stem>.md`. Conversion fails
if the source does not exist or no text can be extracted. The Markdown is
first written to a temporary file and then atomically moved into place, which
avoids leaving a partial file after an interrupted write.

## 7. Local LLM processing

The client uses the OpenAI Python SDK against an OpenAI-compatible local
endpoint. The defaults target Ollama at `http://localhost:11434/v1`; LM Studio
can be used by changing the base URL and model identifier.

The prompt requests exactly this structure:

```json
{
  "title": "Paper title",
  "summary": "A concise summary",
  "keywords": ["keyword one", "keyword two"],
  "category": "Academic category"
}
```

All fields are required. `title`, `summary`, and `category` must be non-empty
strings. `keywords` must be a non-empty list of non-empty strings. Whitespace
is trimmed and case-insensitive duplicate keywords are removed while retaining
their original order.

The request uses temperature zero and, by default, JSON response mode. Invalid
JSON or invalid field structure causes exactly one additional LLM request.
After a second invalid response, the task fails. Network and server errors are
not masked, so their original exception appears in the Airflow log.

Only the first `LOCAL_LLM_MAX_DOCUMENT_CHARS` characters are sent (60,000 by
default). This usually preserves the title and abstract while limiting local
model context use.

## 8. Database design and idempotency

The database is always local at `data/papers.db`:

```sql
CREATE TABLE IF NOT EXISTS papers (
    filename TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    keywords TEXT NOT NULL,
    category TEXT NOT NULL
);
```

Keywords are encoded as a JSON string. Writes use `ON CONFLICT(filename) DO
UPDATE`, so retrying a completed database write does not create a duplicate.
Metadata is validated again before persistence. A filename is stored only
after successful LLM processing; a failed paper remains discoverable later.

Useful inspection commands are:

```bash
sqlite3 data/papers.db '.schema papers'
sqlite3 data/papers.db \
  'SELECT filename, title, category FROM papers ORDER BY filename;'
```

## 9. Generated website

`generate_html()` reads all database rows and writes a self-contained
`index.html`. It includes responsive CSS, a title/summary/keyword text search,
a category selector, a visible result count, and cards containing the source
filename. Database values are HTML-escaped before insertion.

The page has no backend and can be opened directly:

```bash
open data/output/index.html
```

When `RESEARCH_OUTPUT_DIR` points to a synchronized Drive folder, the same
static file becomes available to collaborators through Google Drive.

## 10. Discord notification behavior

Each new paper produces an embed with the fixed heading **New paper
processed!**, the summary as its description, and title/category fields.
Discord limits are respected by truncating the description to 2,000 characters
and the title field to 1,024 characters. Requests use a 15-second timeout and
the explicit `INFOH420-Assignment3/1.0` user agent.

The webhook selects the destination channel. To see a notification, open that
channel in the server where the webhook was created. A successful Discord
webhook normally returns HTTP 204.

If notification delivery alone fails, fix the webhook or connectivity and
clear only `send_notifications` in the same Airflow DAG run. Starting a new
run will not rediscover filenames that processing already committed.

## 11. Configuration reference

| Variable | Required | Default/example | Purpose |
| --- | --- | --- | --- |
| `RESEARCH_PAPERS_DIR` | Yes | `$PWD/data/papers` | PDF input directory |
| `RESEARCH_OUTPUT_DIR` | Yes | `$PWD/data/output` | Parent of generated `index.html` |
| `LOCAL_LLM_MODEL` | Yes | `llama3.2` | Model identifier exposed by the server |
| `LOCAL_LLM_BASE_URL` | No | `http://localhost:11434/v1` | OpenAI-compatible API root |
| `LOCAL_LLM_API_KEY` | No | `ollama` | Local API key placeholder |
| `LOCAL_LLM_JSON_MODE` | No | `true` | Enables JSON response format |
| `LOCAL_LLM_MAX_DOCUMENT_CHARS` | No | `60000` | Maximum Markdown characters sent |
| `DISCORD_WEBHOOK_URL` | Yes for notification | no safe default | Discord channel webhook secret |
| `AIRFLOW_HOME` | Recommended | `$PWD/.airflow` | Local Airflow configuration and state |
| `AIRFLOW__CORE__DAGS_FOLDER` | Recommended | `$PWD/dags` | DAG discovery directory |
| `AIRFLOW__API__PORT` | Recommended | `8081` | Avoids the Adminer port at 8080 |

Copy `.env.example` to `.env`, replace the webhook placeholder, and load it
from the repository root with `set -a; source .env; set +a`. Restart Airflow
after changing environment variables because running services retain their
old environment.

## 12. Installation and complete operation

The authoritative start-to-finish procedure is in the repository
[`README.md`](../README.md). In summary:

1. create and activate `.venv`;
2. install `requirements.txt` with the official Airflow 3.0.6 constraints;
3. create `data/papers`, `data/markdown`, and `data/output`;
4. install Ollama and pull `llama3.2`;
5. create a Discord webhook;
6. copy and load `.env`;
7. add PDFs to the configured input directory;
8. run `airflow standalone` and open `http://localhost:8081`;
9. trigger `paper_pipeline`; and
10. inspect SQLite, Markdown, HTML, and the Discord channel.

Airflow's simple-auth username is `admin`. Its generated password is stored in
`$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated`.

## 13. Failure semantics and recovery

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| `/auth/token` returns 500 | Incompatible PyJWT installed without Airflow constraints | Install `PyJWT==2.10.1`, then restart Airflow |
| Port 8080 shows Adminer | Another stack already owns the default port | Use the configured Airflow URL on port 8081 |
| No PDF is detected | Wrong directory, nested file, or filename already in SQLite | Check the resolved environment path and query stored filenames |
| PDF conversion fails | Missing/corrupt/scanned PDF or no extractable text | Inspect the conversion task log and use a text-bearing PDF/OCR |
| LLM connection fails | Ollama is stopped, URL is wrong, or model is absent | Run `ollama list`, start Ollama, and verify `.env` |
| LLM fails after two replies | Both responses violate the metadata contract | Inspect the raw model behavior and try a capable model |
| Discord returns 403 | Invalid/revoked webhook or unsuitable request headers | Replace the webhook; current code already supplies a user agent |
| `index.html` is missing | Website task did not run or output path is wrong | Inspect that task and `RESEARCH_OUTPUT_DIR` |

Airflow logs are the primary diagnostic source. In the UI, open the failed task
instance and select its log. Because papers are persisted one at a time, a
failure partway through a multi-paper batch can leave earlier papers committed;
the next fresh DAG run skips those names and processes the remainder.

## 14. Verification and testing

Run the unit tests from the repository root:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m pip check
```

Validate DAG discovery without starting the scheduler:

```bash
set -a
source .env
set +a
python -c "from airflow.models.dagbag import DagBag; b=DagBag('dags', include_examples=False); assert not b.import_errors; print(sorted(b.dags))"
```

The automated tests cover database initialization, round-trip persistence,
idempotent filename updates, missing-database reads, metadata normalization,
schema rejection, JSON mode, the single invalid-response retry, and missing
model configuration. A full integration test additionally requires a running
local model, a real PDF, Airflow, and a valid Discord webhook.

## 15. Security and privacy

- `.env`, Airflow state, databases, source PDFs, extracted Markdown, and output
  are ignored by Git.
- The Discord webhook is a secret with permission to post to its channel; rotate
  it immediately if exposed.
- Paper contents are sent only to the configured LLM endpoint. The Ollama
  default is local, but changing the URL can send document text elsewhere.
- SQLite and Markdown may contain copyrighted or sensitive document content;
  protect backups and synchronized folders appropriately.
- Generated HTML escapes stored values to prevent paper metadata from injecting
  markup into the catalogue.

## 16. Known limitations

- PDF identity is based only on filename, not a content hash.
- Subdirectories are not scanned.
- Image-only PDFs need OCR before this pipeline can extract text.
- Long documents are truncated rather than summarized in chunks.
- SQLite is suitable for this single-machine assignment, not concurrent
  distributed workers.
- The generated site is static; access control and sharing are delegated to the
  filesystem or Google Drive.
- Discord delivery has no independent outbox, so recovery uses the failed
  Airflow task instance.

## 17. Suggested demonstration evidence

For the assignment report or presentation, capture the Airflow graph with all
five tasks successful, logs showing PDF discovery and metadata persistence, an
SQLite query of the stored record, the extracted Markdown file, the searchable
HTML catalogue, and the resulting Discord embed. This demonstrates both the
orchestration and every externally visible output.
