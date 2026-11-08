# INFOH420 — Assignment 3

An Apache Airflow pipeline that turns research PDFs into a searchable study
library. The pipeline extracts Markdown, generates structured metadata with a
local LLM, stores it in SQLite, builds a static HTML index, and posts a Discord
notification.

## What the pipeline does

```text
find_new_papers
        |
        v
convert_papers
        |
        v
process_papers (Ollama/LM Studio + validation + SQLite)
        |
        +----------------------+
        v                      v
generate_website       send_notifications
```

The DAG runs hourly, does not backfill, and allows one active run. Only PDFs
whose filename is absent from SQLite are processed.

## Quick start: run the complete project

The commands below use project-internal folders:

```text
data/papers/       input PDFs
data/markdown/     extracted Markdown
data/output/       generated index.html
data/papers.db     local metadata database
```

For the final assignment demonstration, the input and output directories can
instead point to Google Drive. The database and Markdown should remain local.

### 1. Open the project

```bash
cd /path/to/INFOH420-Assignment3
```

### 2. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the dependencies using the official Airflow constraints matching the
active Python version:

```bash
AIRFLOW_VERSION=3.0.6
PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

python -m pip install -r requirements.txt --constraint "$CONSTRAINT_URL"
```

The constraints are important. Installing Airflow without them can select an
incompatible PyJWT release and cause `POST /auth/token` to fail with HTTP 500.

### 3. Create the local data directories

```bash
mkdir -p data/papers data/markdown data/output
```

These generated directories, the database, Airflow state, and `.env` are
ignored by Git.

### 4. Install and prepare Ollama

Install Ollama from <https://ollama.com/download>, then download the model:

```bash
ollama pull llama3.2
ollama list
```

The list should contain `llama3.2:latest`. The macOS Ollama application
normally starts the server automatically. Otherwise, start it in a separate
terminal:

```bash
ollama serve
```

If this reports that port `11434` is already in use, Ollama is already
running.

### 5. Create the Discord webhook

In Discord:

1. Open the target server.
2. Open **Server Settings → Integrations → Webhooks**.
3. Select **New Webhook**.
4. Choose the text channel that should receive paper notifications.
5. Copy the webhook URL.

Treat this URL as a password. Never commit or publish it.

### 6. Configure the environment

Create the local configuration:

```bash
cp .env.example .env
```

Open `.env` and replace the Discord placeholder with the copied webhook URL.
The default input and output folders already point inside the project:

```dotenv
RESEARCH_PAPERS_DIR="$PWD/data/papers"
RESEARCH_OUTPUT_DIR="$PWD/data/output"

LOCAL_LLM_BASE_URL="http://localhost:11434/v1"
LOCAL_LLM_API_KEY="ollama"
LOCAL_LLM_MODEL="llama3.2"

DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

Load the configuration from the repository root:

```bash
set -a
source .env
set +a
```

Check the resolved directories:

```bash
printf '%s\n' "$RESEARCH_PAPERS_DIR" "$RESEARCH_OUTPUT_DIR"
```

### 7. Add PDFs

Copy one or more PDFs into the input directory. Filenames must be unique:

```bash
cp "/absolute/path/to/paper.pdf" data/papers/
ls -lh data/papers/
```

The detector scans only PDFs directly inside this directory; it does not scan
subdirectories.

### 8. Start Airflow

Ensure the virtual environment is active and `.env` is loaded, then run:

```bash
airflow standalone
```

Keep this terminal open. The provided configuration runs Airflow on port
`8081` because port `8080` may already be occupied by Adminer.

Open <http://localhost:8081>.

The username is `admin`. Retrieve the generated password with:

```bash
cat "$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated"
```

### 9. Trigger the pipeline

From the Airflow interface:

1. Open **DAGs**.
2. Find `paper_pipeline`.
3. Unpause it if necessary.
4. Open it and select **Trigger DAG**.
5. Monitor the graph until every task is green.

Alternatively, open a second terminal, load the same environment, and trigger
it from the CLI:

```bash
cd /path/to/INFOH420-Assignment3
source .venv/bin/activate
set -a
source .env
set +a
airflow dags trigger paper_pipeline
```

The DAG also runs automatically every hour.

### 10. Verify all outputs

Inspect the database:

```bash
sqlite3 data/papers.db \
  'SELECT filename, title, category FROM papers ORDER BY filename;'
```

Inspect extracted Markdown:

```bash
ls -lh data/markdown/
```

Open the searchable website:

```bash
open data/output/index.html
```

Finally, open the Discord channel selected during webhook creation. Each new
paper appears as an embed titled **New paper processed!**.

## Use Google Drive instead of internal folders

Create this structure in a Google Drive-synchronized location:

```text
ResearchLibrary/
├── papers/
└── output/
```

Set absolute local paths in `.env`:

```dotenv
RESEARCH_PAPERS_DIR="/local/Google Drive/ResearchLibrary/papers"
RESEARCH_OUTPUT_DIR="/local/Google Drive/ResearchLibrary/output"
```

Restart Airflow after changing `.env`. Google Drive then synchronizes the PDFs
and generated HTML, while `data/papers.db` remains local as required.

## Reprocessing and duplicate behavior

- A filename already present in SQLite is skipped on later runs.
- Adding a different PDF with a unique filename processes it normally.
- Replacing a PDF while retaining its filename does not reprocess it.
- A run with no new PDFs still regenerates the HTML page but sends no Discord
  notifications.
- If only `send_notifications` fails, clear and rerun that failed task from
  the same DAG run. Triggering a new DAG run will not rediscover papers already
  stored in SQLite.

To intentionally start with a fresh database, preserve the old database first:

```bash
mv data/papers.db data/papers.backup.db
```

The next DAG run creates a new database.

## Tests

Run the unit suite:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Check installed dependency consistency:

```bash
python -m pip check
```

Check DAG discovery:

```bash
set -a
source .env
set +a
python -c "from airflow.models.dagbag import DagBag; b=DagBag('dags', include_examples=False); print(b.import_errors, sorted(b.dags))"
```

## Common problems

### `POST /auth/token 500`

Cause: Airflow was installed without its constraints and selected an
incompatible PyJWT release.

Fix:

```bash
source .venv/bin/activate
python -m pip install "PyJWT==2.10.1"
```

Restart Airflow after installation.

### Port 8080 opens Adminer

Another Docker application owns port 8080. This project is configured for
<http://localhost:8081>.

### Discord returns HTTP 403

The webhook must be valid, and the request must include a non-default
`User-Agent`. The implementation already sends
`User-Agent: INFOH420-Assignment3/1.0`. Restart Airflow after updating code.

### The HTML file does not exist

Confirm that `RESEARCH_OUTPUT_DIR` is correct, restart Airflow so it receives
the environment, and trigger the DAG. The website task creates the directory
and file.

### No new PDFs are detected

Check that the PDF is directly inside `RESEARCH_PAPERS_DIR` and that its
filename is not already present:

```bash
sqlite3 data/papers.db 'SELECT filename FROM papers ORDER BY filename;'
```

## Complete technical documentation

See [Project documentation](docs/project-documentation.md) for the complete
architecture, task contracts, database design, LLM validation, HTML and Discord
behavior, failure semantics, testing strategy, security considerations, and
operational procedures.

The focused [LLM and database guide](docs/local-llm-and-database.md) remains
available for metadata-processing details.
