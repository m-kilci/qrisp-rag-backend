from src.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from src.config import get_docs_root
from src.pipeline import build_chunks
from src.vector_store import save_embeddings


def main() -> None:
    docs_root = get_docs_root()
    print(f"Documentation source: {docs_root}")
    print("Discovering and chunking Qrisp documentation...")
    chunks = build_chunks(
        docs_root, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP,
    )

    print(f"Created {len(chunks)} chunks.")
    print("Generating embeddings and saving them...")

    save_embeddings(
        chunks, docs_root=docs_root,
        chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP,
    )

    print("Documentation indexing complete.")


if __name__ == "__main__":
    main()
