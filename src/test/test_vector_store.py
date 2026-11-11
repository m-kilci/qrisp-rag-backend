"""Manual Ollama integration check using a temporary embedding store."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.config import get_docs_root
from src.pipeline import build_chunks
from src.vector_store import load_embeddings, save_embeddings


def main() -> None:
    docs_root = get_docs_root()
    chunks = build_chunks(docs_root)[:3]

    # Never replace the populated documentation index with this tiny test set.
    with TemporaryDirectory() as directory:
        with patch("src.vector_store.STORE_PATH", Path(directory) / "embeddings.json"):
            save_embeddings(chunks)
            saved = load_embeddings()

    assert len(saved) == 3
    assert all(len(record["embedding"]) == 768 for record in saved)
    print(f"Saved and loaded {len(saved)} chunks in a temporary store.")
    print(f"First source: {saved[0]['source']}")
    print("Vector-store test passed. The documentation index was not changed.")


if __name__ == "__main__":
    main()
