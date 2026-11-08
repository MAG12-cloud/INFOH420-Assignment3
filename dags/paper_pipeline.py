
import os
import sys
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.pdf_processing import detect_new_pdfs, convert_pdf_to_file
from src.database import initialize_database, save_paper
from src.llm_processing import create_local_llm_client, generate_metadata
from src.discord_notification import notify_discord
from src.html_generator import generate_html

DATABASE_PATH = str(PROJECT_DIR / "data" / "papers.db")
MARKDOWN_DIR = str(PROJECT_DIR / "data" / "markdown")


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
        converted_papers = []

        for pdf_path in pdf_files:
            result = convert_pdf_to_file(
                pdf_path, MARKDOWN_DIR
            )
            converted_papers.append(
                {
                    "filename": Path(pdf_path).name,
                    "markdown_path": result,
                }
            )
            print(f"Converted: {result}")

        return converted_papers

    @task
    def process_papers(converted_papers: list[dict]):
        initialize_database(DATABASE_PATH)
        if not converted_papers:
            print("No new papers to process")
            return []

        client = create_local_llm_client()
        processed_papers = []

        for paper in converted_papers:
            metadata = generate_metadata(
                paper["markdown_path"],
                client=client,
            )
            save_paper(
                DATABASE_PATH,
                paper["filename"],
                metadata,
            )
            processed_papers.append({**paper, **metadata})
            print(
                f"Stored metadata for {paper['filename']}: "
                f"{metadata['title']} ({metadata['category']})"
            )

        return processed_papers

    @task
    def send_notifications(processed_papers: list[dict]):
        for paper in processed_papers:
            notify_discord(
                title=paper["title"],
                category=paper["category"],
                summary=paper["summary"],
            )

            print(f"Discord notification sent: {paper['title']}")

    @task
    def generate_website(processed_papers: list[dict]):
        output_dir_value = os.environ.get("RESEARCH_OUTPUT_DIR")
        if not output_dir_value:
            raise ValueError("RESEARCH_OUTPUT_DIR is not configured")

        output_dir = Path(output_dir_value).expanduser()
        html_path = str(output_dir / "index.html")
        output_dir.mkdir(parents=True, exist_ok=True)

        generate_html(
            DATABASE_PATH,
            html_path,
        )

        print(
            f"Website generated after processing "
            f"{len(processed_papers)} new paper(s): {html_path}"
        )
        return html_path

    converted_papers = convert_papers(find_new_papers())
    processed_papers = process_papers(converted_papers)
    generate_website(processed_papers)
    send_notifications(processed_papers)

paper_pipeline()

