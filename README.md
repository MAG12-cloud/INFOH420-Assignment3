# INFOH420 — Assignment 3

This project turns research PDFs into a searchable study library. Apache
Airflow detects new PDFs, converts them to Markdown, asks a locally served LLM
for structured metadata, stores the result in SQLite, regenerates a static HTML
index, and sends a Discord webhook notification.

## Pipeline

```text
find_new_papers
        |
        v
convert_papers
        |
        v
process_papers (local LLM validation + SQLite)
        |
        +--------------------+
        v                    v
generate_website     send_notifications
```

The DAG runs hourly, does not backfill, and permits only one active run. A PDF
is considered processed only after its validated metadata is committed to
SQLite. Database writes are idempotent, so an Airflow retry cannot create a
duplicate filename.

## Project structure

```text
INFOH420-Assignment3/
├── dags/paper_pipeline.py
├── src/
│   ├── pdf_processing.py
│   ├── llm_processing.py
│   ├── database.py
│   ├── html_generator.py
│   └── discord_notification.py
├── tests/
├── docs/local-llm-and-database.md
├── data/                  # local generated state; database is ignored
├── .env.example
└── requirements.txt
```

## Prerequisites

- Python 3.9 or newer
- Ollama or LM Studio exposing an OpenAI-compatible local endpoint
- Google Drive for Desktop, with input and output folders
- A Discord webhook for real notifications

The SQLite database and extracted Markdown stay local. Only the source PDFs and
generated `index.html` need to be in Google Drive.

## Installation

Create and activate the repository-local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The dependency ranges deliberately keep Airflow on 3.0 and PyMuPDF4LLM below
the unrelated empty `2.0` package release.

## Local LLM

Install Ollama from <https://ollama.com/download>, then start it and download a
model:

```bash
ollama serve
ollama pull llama3.2
```

`ollama serve` may be unnecessary when the macOS application is already
running. LM Studio can be used instead by changing the endpoint and model in
the environment configuration.

## Environment configuration

Copy the template and edit all machine-specific values:

```bash
cp .env.example .env
```

Load it into the shell that will start Airflow:

```bash
set -a
source .env
set +a
```

Required runtime values are:

| Variable | Purpose |
| --- | --- |
| `RESEARCH_PAPERS_DIR` | Google Drive-synced input PDF directory |
| `RESEARCH_OUTPUT_DIR` | Google Drive-synced directory for `index.html` |
| `LOCAL_LLM_MODEL` | Model exposed by Ollama or LM Studio |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook URL |

Optional LLM values and their defaults are documented in
[the implementation guide](docs/local-llm-and-database.md).

Configure Airflow from the repository root:

```bash
export AIRFLOW_HOME="$PWD/.airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
```

## Running the pipeline

With the virtual environment active and all variables loaded:

```bash
airflow standalone
```

Open <http://localhost:8080>, locate `paper_pipeline`, enable it, and trigger a
run. It also runs automatically every hour.

Expected generated files are:

```text
data/papers.db
data/markdown/<paper-name>.md
$RESEARCH_OUTPUT_DIR/index.html
```

Inspect stored metadata with:

```bash
sqlite3 data/papers.db \
  'SELECT filename, title, keywords, category FROM papers;'
```

## Testing

Run the unit suite inside `.venv`:

```bash
python -m unittest discover -s tests -v
```

Validate DAG discovery and task dependencies:

```bash
python -c "from airflow.models.dagbag import DagBag; b=DagBag('dags', include_examples=False); print(b.import_errors, sorted(b.dags))"
```

For an end-to-end test, place a PDF with a filename that is not already in the
database, start the local model server, configure the webhook, and trigger the
DAG. The run should create one database row, update `index.html`, and send one
notification. Re-running with no new PDF should produce no duplicate row or
notification.

## Metadata contract

The model must return a JSON object shaped like this:

```json
{
  "title": "Paper title",
  "summary": "A concise summary of the paper",
  "keywords": ["keyword one", "keyword two"],
  "category": "Data Engineering"
}
```

All fields are validated. Malformed or structurally invalid output is requested
again once, after which the Airflow task fails with a clear error.

## Documentation

See [Local LLM and SQLite implementation](docs/local-llm-and-database.md) for
the detailed configuration, validation rules, retry behavior, schema, task data
contracts, and verification procedure.
