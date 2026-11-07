# INFOH420 — Assignment 3

## Research PDF Processing Pipeline with Apache Airflow

This project was developed for **INFO-H420 — Process Modeling, Data Pipelines, and Responsible AI** at the Université Libre de Bruxelles (ULB).

### 1. Project Overview

The objective is to build an automated pipeline that transforms research papers in PDF format into a searchable study library.

The pipeline uses Apache Airflow to coordinate the following operations:

1. Detect new research PDFs in a Google Drive-synchronized folder.
2. Convert PDFs into Markdown using PyMuPDF4LLM.
3. Generate structured metadata using a locally hosted Large Language Model (LLM).
4. Validate the generated JSON metadata.
5. Store paper information in a local SQLite database.
6. Generate a searchable HTML page.
7. Send notifications through a Discord webhook when new papers are processed.

The PDF detection and conversion stages have been tested successfully. The remaining components are developed separately and must be integrated and tested as part of the complete workflow.

### 2. Technologies

| Technology | Purpose |
|---|---|
| Python 3.12 | Programming language |
| Apache Airflow | Workflow orchestration and scheduling |
| Google Drive for Desktop | Synchronization of research PDFs and HTML output |
| PyMuPDF4LLM | PDF-to-Markdown conversion |
| Ollama or LM Studio | Local LLM inference |
| OpenAI Python package | Communication with an OpenAI-compatible local endpoint |
| SQLite | Metadata storage |
| HTML, CSS, JavaScript | Searchable research library |
| Discord webhook | Processing notifications |

### 3. Project Structure

```text
INFOH420-Assignment3/
├── dags/
│   └── paper_pipeline.py
├── src/
│   ├── pdf_processing.py
│   ├── llm_processing.py
│   ├── database.py
│   ├── html_generator.py
│   └── discord_notification.py
├── data/
│   └── .gitkeep
├── requirements.txt
├── .gitignore
└── README.md
```

**Note:** The SQLite database, local Markdown files, virtual environment, Airflow configuration and credentials are excluded from version control.

### 4. Prerequisites

Before running the project, ensure that you have:

- Python 3.12
- Git
- Google Drive for Desktop
- Apache Airflow
- A compatible locally served LLM, once the LLM component is integrated
- A Discord webhook URL, once notifications are integrated

### 5. Installation

#### Step 1 — Clone the repository

```bash
git clone https://github.com/MAG12-cloud/INFOH420-Assignment3.git
cd INFOH420-Assignment3
```

Repository access is required because the project is currently private.

#### Step 2 — Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

On Windows, the activation command is different. The configuration below was tested on macOS.

#### Step 3 — Install Apache Airflow

Install Airflow with version-specific constraints:

```bash
AIRFLOW_VERSION=3.3.2
PYTHON_VERSION=3.12

python -m pip install "apache-airflow==${AIRFLOW_VERSION}" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
```

Install the remaining dependencies:

```bash
python -m pip install pymupdf4llm openai
```

### 6. Google Drive Configuration

Create the following directory structure in your Google Drive:

```text
My Drive/
└── ResearchLibrary/
    ├── papers/
    │   └── example.pdf
    └── output/
        └── index.html
```

The `papers/` directory contains input research PDFs.

The `output/` directory is intended for the generated HTML library.

The SQLite database must remain outside the Google Drive-synchronized directory.

### 7. Environment Configuration

The pipeline reads the Google Drive PDF directory through an environment variable.

For macOS, configure:

```bash
export RESEARCH_PAPERS_DIR="/path/to/GoogleDrive/My Drive/ResearchLibrary/papers"
```

Replace the example with the actual local directory.

Configure the Airflow home and DAG directory:

```bash
export AIRFLOW_HOME="$PWD/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
```

These commands should be executed from the project root.

For the complete pipeline, the LLM endpoint and Discord webhook must also be configured according to the implementations in their corresponding modules. Do not commit passwords, API credentials, or webhook URLs to GitHub.

### 8. Running Apache Airflow

Start Airflow:

```bash
airflow standalone
```

Open the web interface:

http://localhost:8080

Log in using your local Airflow credentials.

Navigate to **DAGs** and find:

`paper_pipeline`

The DAG is configured to run every hour.

To execute it manually:

1. Open `paper_pipeline`.
2. Enable the DAG if necessary.
3. Click **Trigger**.
4. Select **Single Run**.
5. Monitor the task execution results.

### 9. PDF Detection and Conversion

The implemented processing stages are:

**Task 1: `find_new_papers`**

Scans the synchronized `papers/` directory and identifies PDF filenames that are not recorded in the local `papers` SQLite table.

If the database or table has not yet been created, all PDFs in the folder are considered eligible for processing.

**Task 2: `convert_papers`**

Converts the detected PDF files into Markdown using PyMuPDF4LLM.

The generated Markdown files are saved in:

```text
data/markdown/
```

The task returns Markdown file paths for downstream processing.

Previously generated Markdown files may be reused when the corresponding PDF has not changed.

### 10. Local LLM and Metadata

The LLM component is intended to process the extracted Markdown and generate JSON containing:

```json
{
  "title": "Paper title",
  "summary": "A short summary of the paper.",
  "keywords": ["keyword one", "keyword two"],
  "category": "Data Engineering"
}
```

The response must be parsed, validated and retried once if JSON parsing fails.

The exact local LLM setup and execution instructions should be added after the team's LLM component is integrated and tested.

### 11. SQLite, HTML and Discord

The remaining components are intended to:

- Store one metadata record per paper in SQLite.
- Generate a static HTML index with search or category filtering.
- Write the HTML output to the synchronized Google Drive directory.
- Send a Discord webhook notification after successful processing of a new paper.

The final end-to-end execution should be verified after these components are connected to the Airflow DAG.

### 12. Testing and Verification

The Airflow and PDF-processing components have been tested locally with a research PDF.

The tested workflow successfully:

- Detected a PDF in the Google Drive-synchronized folder.
- Converted its contents into Markdown.
- Saved the Markdown file locally.
- Completed both Airflow tasks successfully.

To inspect generated Markdown files:

```bash
ls -lh data/markdown/
```

To inspect the beginning of a converted paper:

```bash
head -20 data/markdown/example.md
```

Replace `example.md` with the actual generated filename.

After integration, the complete pipeline should additionally be tested for database insertion, HTML generation, Discord notifications and prevention of duplicate processing.

### 13. Stopping Airflow

To stop the local Airflow services, return to the Terminal running Airflow and press:

`Ctrl + C`

The application can be restarted later using `airflow standalone` with the same environment configuration.

### 14. Group Collaboration

The project is developed collaboratively through GitHub. Each component is maintained in its corresponding Python module, while `dags/paper_pipeline.py` coordinates the workflow.

Before making changes, synchronize with the remote repository:

```bash
git pull --ff-only origin main
```

After testing changes, commit and push the relevant files. Coordinate modifications to the shared DAG to avoid merge conflicts.# INFOH420-Assignment3
Assignment 3 — Research PDF processing pipeline using Apache Airflow, a local LLM, SQLite, HTML, and Discord notifications.
