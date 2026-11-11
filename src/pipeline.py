from pathlib import Path

from src.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_text
from src.ingestion import discover_documents, extract_document


def build_chunks(
    docs_root: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Discover documentation files and create chunks with metadata."""
    docs_root = docs_root.resolve()
    html_root = docs_root.parent / "build" / "html"

    all_chunks = []

    for path in discover_documents(docs_root):
        text = extract_document(path)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        # Keep source paths relative to their respective documentation roots.
        if path.is_relative_to(docs_root):
            source = path.relative_to(docs_root)
        elif path.is_relative_to(html_root):
            source = path.relative_to(html_root)
        else:
            source = path

        for index, chunk in enumerate(chunks):
            all_chunks.append(
                {
                    "text": chunk,
                    "source": str(source),
                    "chunk_index": index,
                }
            )

    return all_chunks
