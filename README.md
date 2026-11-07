# INFOH420-Assignment3
Assignment 3 — Research PDF processing pipeline using Apache Airflow, a local LLM, SQLite, HTML, and Discord notifications.

## Local setup

The project uses a local virtual environment. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start an OpenAI-compatible local model server before running the pipeline.

For Ollama, for example:

```bash
ollama pull llama3.2
export LOCAL_LLM_BASE_URL="http://localhost:11434/v1"
export LOCAL_LLM_API_KEY="ollama"
export LOCAL_LLM_MODEL="llama3.2"
```

For LM Studio, start its local server and use its displayed model identifier:

```bash
export LOCAL_LLM_BASE_URL="http://localhost:1234/v1"
export LOCAL_LLM_API_KEY="lm-studio"
export LOCAL_LLM_MODEL="<model-identifier>"
```

Configure the PDF directory and run Airflow from the same shell so the
scheduler receives the variables:

```bash
export RESEARCH_PAPERS_DIR="/absolute/path/to/Google Drive/ResearchLibrary/papers"
export AIRFLOW_HOME="$PWD/.airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
airflow standalone
```

The DAG runs hourly and stores its local database at `data/papers.db`.
The same settings are collected in `.env.example`; copy it to the ignored
`.env`, edit the values, and load it before starting Airflow if preferred.

## Tests

Run the unit tests inside the virtual environment:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

The tests cover JSON validation, the required one-time retry, model
configuration, SQLite schema creation, JSON keyword storage, and idempotent
database updates.

## Implementation documentation

See [Local LLM and SQLite implementation](docs/local-llm-and-database.md) for
the configuration reference, validation and retry behavior, database schema,
Airflow task contracts, and integration-test procedure.


## Workload split

### Part 1 – Airflow and PDF Processing

Set up Apache Airflow locally.

Create the scheduled Airflow DAG.

Detect new PDFs in the Google Drive-synced folder.

Convert the PDFs into Markdown using PyMuPDF4LLM.

### Part 2 – Local LLM and Database (me)

Set up Ollama or LM Studio to run the LLM locally.

Generate the title, summary, keywords, and category in JSON format.

Validate the JSON output.

Store the metadata in SQLite.

### Part 3 – HTML, Discord and Documentation

Generate the searchable HTML page with category filtering.

Set up Discord webhook notifications.

Prepare the README and help with the final report.
