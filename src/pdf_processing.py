
from pathlib import Path
import os
import sqlite3
import pymupdf4llm


def detect_new_pdfs(papers_folder: str, database_path: str) -> list[str]:
    """Find PDFs not yet recorded in the SQLite database."""
    folder = Path(papers_folder).expanduser()
    database = Path(database_path).expanduser()

    if not folder.is_dir():
        raise FileNotFoundError(f"PDF folder not found: {folder}")

    processed = set()

    if database.is_file():
        with sqlite3.connect(database) as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'papers'"
            ).fetchone()

            if table_exists:
                processed = {
                    row[0]
                    for row in conn.execute(
                        "SELECT filename FROM papers"
                    )
                }

    return [
        str(pdf)
        for pdf in sorted(folder.iterdir())
        if pdf.is_file()
        and pdf.suffix.lower() == ".pdf"
        and pdf.name not in processed
    ]


def convert_pdf_to_file(pdf_path: str, markdown_folder: str) -> str:
    """Convert a PDF to a local Markdown file."""
    pdf = Path(pdf_path)
    output_folder = Path(markdown_folder).expanduser()

    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    output_folder.mkdir(parents=True, exist_ok=True)
    output_file = output_folder / f"{pdf.stem}.md"

    # Reuse the conversion when the PDF has not changed.
    if (
        output_file.exists()
        and output_file.stat().st_mtime >= pdf.stat().st_mtime
    ):
        return str(output_file)

    markdown = pymupdf4llm.to_markdown(str(pdf))

    if not markdown.strip():
        raise ValueError(f"No text extracted from {pdf.name}")

    temporary_file = output_file.with_suffix(".md.tmp")
    temporary_file.write_text(markdown, encoding="utf-8")
    os.replace(temporary_file, output_file)

    return str(output_file)


