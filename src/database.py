"""SQLite persistence for processed research-paper metadata."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping

from src.llm_processing import validate_metadata


CREATE_PAPERS_TABLE = """
CREATE TABLE IF NOT EXISTS papers (
    filename TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    keywords TEXT NOT NULL,
    category TEXT NOT NULL
)
"""


def _database_file(database_path: str) -> Path:
    database = Path(database_path).expanduser()
    database.parent.mkdir(parents=True, exist_ok=True)
    return database


def initialize_database(database_path: str) -> None:
    """Create the local database and papers table when they do not exist."""
    database = _database_file(database_path)
    with sqlite3.connect(str(database)) as connection:
        connection.execute(CREATE_PAPERS_TABLE)


def save_paper(
    database_path: str,
    filename: str,
    metadata: Mapping[str, Any],
) -> None:
    """Insert or update one paper atomically.

    Upserting makes the operation safe when Airflow retries a task after a
    previous attempt committed successfully.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string")

    clean_metadata = validate_metadata(metadata)
    database = _database_file(database_path)

    with sqlite3.connect(str(database)) as connection:
        connection.execute(CREATE_PAPERS_TABLE)
        connection.execute(
            """
            INSERT INTO papers (filename, title, summary, keywords, category)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                keywords = excluded.keywords,
                category = excluded.category
            """,
            (
                filename.strip(),
                clean_metadata["title"],
                clean_metadata["summary"],
                json.dumps(clean_metadata["keywords"], ensure_ascii=False),
                clean_metadata["category"],
            ),
        )


def fetch_all_papers(database_path: str) -> List[Dict[str, Any]]:
    """Return all stored papers as dictionaries for HTML generation."""
    database = Path(database_path).expanduser()
    if not database.is_file():
        return []

    with sqlite3.connect(str(database)) as connection:
        connection.row_factory = sqlite3.Row
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'papers'"
        ).fetchone()
        if not table_exists:
            return []

        rows = connection.execute(
            """
            SELECT filename, title, summary, keywords, category
            FROM papers
            ORDER BY title COLLATE NOCASE, filename COLLATE NOCASE
            """
        ).fetchall()

    papers = []
    for row in rows:
        paper = dict(row)
        paper["keywords"] = json.loads(paper["keywords"])
        papers.append(paper)
    return papers
