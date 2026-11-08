import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import fetch_all_papers, initialize_database, save_paper


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_directory.name) / "data" / "papers.db")
        self.metadata = {
            "title": "A Paper",
            "summary": "A useful summary.",
            "keywords": ["Airflow", "SQLite"],
            "category": "Data Engineering",
        }

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_initialize_database_creates_expected_schema(self):
        initialize_database(self.database_path)

        with sqlite3.connect(self.database_path) as connection:
            columns = connection.execute(
                "PRAGMA table_info(papers)"
            ).fetchall()

        self.assertEqual(
            [column[1] for column in columns],
            ["filename", "title", "summary", "keywords", "category"],
        )
        self.assertEqual(columns[0][5], 1)

    def test_save_and_fetch_paper_round_trip(self):
        save_paper(self.database_path, "paper.pdf", self.metadata)

        self.assertEqual(
            fetch_all_papers(self.database_path),
            [{"filename": "paper.pdf", **self.metadata}],
        )

    def test_saving_same_filename_updates_without_duplicate(self):
        save_paper(self.database_path, "paper.pdf", self.metadata)
        updated = dict(self.metadata, category="Machine Learning")
        save_paper(self.database_path, "paper.pdf", updated)

        papers = fetch_all_papers(self.database_path)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["category"], "Machine Learning")

    def test_fetch_from_missing_database_returns_empty_list(self):
        self.assertEqual(fetch_all_papers(self.database_path), [])


if __name__ == "__main__":
    unittest.main()
