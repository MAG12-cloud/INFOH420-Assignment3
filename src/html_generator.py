import sqlite3
import html
import json
from pathlib import Path


def generate_html(database_path: str, output_path: str):

    # Connect to SQLite
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row

    papers = conn.execute("""
        SELECT filename, title, summary, keywords, category
        FROM papers
        ORDER BY rowid DESC
    """).fetchall()

    conn.close()

    # Extract categories
    categories = sorted({
        paper["category"] or "Uncategorized"
        for paper in papers
    })

    # Generate category
    category_options = ""

    for category in categories:
        safe_category = html.escape(category, quote=True)

        category_options += (
            f'<option value="{safe_category}">'
            f'{safe_category}</option>'
        )

    # Generate paper cards
    cards = ""

    for paper in papers:

        filename = paper["filename"] or ""
        title = paper["title"] or "Untitled"
        summary = paper["summary"] or ""
        category = paper["category"] or "Uncategorized"

        # Decode JSON keywords
        try:
            keywords = json.loads(paper["keywords"] or "[]")
            if isinstance(keywords, list):
                keywords = ", ".join(str(k) for k in keywords)
            else:
                keywords = str(keywords)
        except (json.JSONDecodeError, TypeError):
            keywords = paper["keywords"] or ""

        # Escape HTML content
        safe_filename = html.escape(filename)
        safe_title = html.escape(title)
        safe_summary = html.escape(summary)
        safe_category = html.escape(category, quote=True)
        safe_keywords = html.escape(keywords)

        search_content = html.escape(
            f"{title} {summary} {keywords}".lower(),
            quote=True
        )

        cards += f"""
        <article class="paper"
            data-category="{safe_category}"
            data-search="{search_content}">

            <span class="category">{safe_category}</span>

            <h2>{safe_title}</h2>

            <p>{safe_summary}</p>

            <p class="keywords">
                <strong>Keywords:</strong> {safe_keywords}
            </p>

            <p class="filename">
                <strong>File:</strong> {safe_filename}
            </p>

        </article>
        """

    # Generate HTML page
    page = f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>Research Library</title>

        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1000px;
                margin: 40px auto;
                padding: 0 20px;
                background: #f5f5f5;
                color: #222;
            }}

            h1 {{
                margin-bottom: 5px;
            }}

            .controls {{
                display: flex;
                gap: 10px;
                margin: 25px 0;
            }}

            input, select {{
                padding: 12px;
                font-size: 15px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }}

            input {{
                flex: 1;
            }}

            .paper {{
                background: white;
                padding: 20px;
                margin-bottom: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 5px #ddd;
            }}

            .category {{
                background: #dceeff;
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 13px;
            }}

            .keywords, .filename {{
                color: #666;
                font-size: 14px;
            }}

            #count {{
                color: #666;
                margin-bottom: 20px;
            }}

            @media (max-width: 600px) {{
                .controls {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>

    <body>

        <h1>Research Library</h1>

        <p id="count">{len(papers)} papers indexed</p>

        <div class="controls">

            <input
                type="text"
                id="search"
                placeholder="Search by title, summary or keywords..."
            >

            <select id="category">
                <option value="">All categories</option>
                {category_options}
            </select>

        </div>

        <div id="papers">
            {cards if cards else "<p>No papers indexed yet.</p>"}
        </div>

        <script>
            const searchInput = document.getElementById("search");
            const categorySelect = document.getElementById("category");
            const count = document.getElementById("count");

            function filterPapers() {{

                const search = searchInput.value.toLowerCase();
                const category = categorySelect.value;

                let visible = 0;

                document.querySelectorAll(".paper").forEach(paper => {{

                    const matchesSearch =
                        paper.dataset.search.includes(search);

                    const matchesCategory =
                        !category ||
                        paper.dataset.category === category;

                    const show = matchesSearch && matchesCategory;

                    paper.style.display = show ? "" : "none";

                    if (show) visible++;
                }});

                count.textContent =
                    visible + " papers displayed";
            }}

            searchInput.addEventListener("input", filterPapers);
            categorySelect.addEventListener("change", filterPapers);
        </script>

    </body>
    </html>
    """

    # Save HTML
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(page, encoding="utf-8")

    print(f"Website generated: {output}")
    print(f"Total papers: {len(papers)}")
