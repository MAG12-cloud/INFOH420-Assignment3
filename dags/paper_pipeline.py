
import os
import sys
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.pdf_processing import detect_new_pdfs, convert_pdf_to_file
from src.discord_notification import notify_discord
from src.html_generator import generate_html

PAPERS_DIR = os.environ.get("RESEARCH_PAPERS_DIR")
DATABASE_PATH = str(PROJECT_DIR / "data" / "papers.db")
MARKDOWN_DIR = str(PROJECT_DIR / "data" / "markdown")

OUTPUT_DIR = Path(os.environ.get("RESEARCH_OUTPUT_DIR", ""))
HTML_PATH = str(OUTPUT_DIR / "index.html")


@dag(
    dag_id="paper_pipeline",
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Brussels"),
    catchup=False,
    max_active_runs=1,
    tags=["INFOH420", "research-library"],
)
def paper_pipeline():

    @task
    def find_new_papers():
        papers_dir = os.environ.get("RESEARCH_PAPERS_DIR")
        if not papers_dir:
            raise ValueError(
                "RESEARCH_PAPERS_DIR is not configured"
            )

        files = detect_new_pdfs(papers_dir, DATABASE_PATH)
        print(f"Found {len(files)} unprocessed PDF(s)")
        return files

    @task
    def convert_papers(pdf_files: list[str]):
        markdown_files = []

        for pdf_path in pdf_files:
            result = convert_pdf_to_file(
                pdf_path, MARKDOWN_DIR
            )
            markdown_files.append(result)
            print(f"Converted: {result}")

        return markdown_files

    @task
    def send_notifications(processed_papers: list[dict]):
        for paper in processed_papers:
            notify_discord(
                title=paper["title"],
                category=paper["category"],
                summary=paper["summary"]
            )

            print(f"Discord notification sent: {paper['title']}")

    @task
    def generate_website():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        generate_html(
            DATABASE_PATH,
            HTML_PATH
        )

        print(f"Website generated: {HTML_PATH}")

    
    convert_papers(find_new_papers())

    generate_website()
    send_notifications("processed papeeeeeeeeeeeeer")  # need sqlite part

paper_pipeline()

