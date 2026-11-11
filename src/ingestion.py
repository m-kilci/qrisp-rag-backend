from pathlib import Path
import re
from bs4 import BeautifulSoup


def read_rst(path: Path) -> str:
    """Read a reStructuredText documentation file."""
    return path.read_text(encoding="utf-8-sig")


def read_notebook(path: Path) -> str:
    """Extract Markdown and code cells from a Jupyter notebook"""
    import nbformat

    notebook = nbformat.read(path, as_version=4)
    sections = []

    for cell in notebook.cells:
        if cell.cell_type == "markdown":
            sections.append(cell.source)
        elif cell.cell_type == "code":
            sections.append(f"```python\n{cell.source}\n```")

    return "\n\n".join(sections)


def extract_document(path: Path) -> str:
    """Extract text from a supported documentation file."""
    if path.suffix == ".rst":
        return read_rst(path)

    if path.suffix == ".ipynb":
        return read_notebook(path)

    if path.suffix == ".html":
        return read_html(path)

    raise ValueError(f"Unsupported document type: {path.suffix}")


def read_html(path: Path) -> str:
    """Convert generated Sphinx HTML documentation to Markdown."""
    from markdownify import markdownify

    soup = BeautifulSoup(
        path.read_text(encoding="utf-8"),
        "html.parser",
    )

    # Remove navigation and non-documentation elements.
    for element in soup.select(
        "script, style, nav, footer, header, " ".headerlink, .viewcode-link, .sidebar"
    ):
        element.decompose()

    article = soup.select_one("article.bd-article")
    if article is None:
        article = soup.find("main")

    if article is None:
        raise ValueError(f"Could not find main content in {path}")

    # Convert only the main documentation content.
    text = markdownify(
        str(article),
        heading_style="ATX",
        code_language="python",
    )

    # Normalize excessive blank lines without flattening paragraphs.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def discover_documents(docs_root: Path) -> list[Path]:
    """Find source documents and rendered API reference pages."""
    docs_root = docs_root.resolve()
    html_root = docs_root.parent / "build" / "html"

    documents = []

    # Keep source RST and notebooks, except API reference RST files.
    for path in docs_root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix == ".rst":
            relative_path = path.relative_to(docs_root)

            # API reference pages are indexed from rendered HTML instead.
            if relative_path.parts[0] == "reference":
                continue

            documents.append(path)

        elif path.suffix == ".ipynb":
            documents.append(path)

    # Add rendered HTML versions of API reference pages.
    reference_html = html_root / "reference"

    if reference_html.exists():
        documents.extend(
            path for path in reference_html.rglob("*.html") if path.is_file()
        )
    else:
        raise FileNotFoundError(f"Generated reference HTML not found: {reference_html}")

    return sorted(documents)
