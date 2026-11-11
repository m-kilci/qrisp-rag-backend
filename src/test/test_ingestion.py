from src.config import get_docs_root
from src.ingestion import discover_documents, extract_document

DOCS_ROOT = get_docs_root()

documents = discover_documents(DOCS_ROOT)

print(f"Discovered {len(documents)} documents.")

for extension in (".rst", ".ipynb", ".html"):
    count = sum(path.suffix == extension for path in documents)
    print(f"  {extension}: {count}")

failed = []
total_characters = 0

for path in documents:
    try:
        text = extract_document(path)
        total_characters += len(text)

        if not text.strip():
            failed.append((path, "Empty extracted text"))

    except Exception as exc:
        failed.append((path, str(exc)))

print(f"\nTotal extracted characters: {total_characters:,}")
print(f"Files with problems: {len(failed)}")

for path, error in failed[:20]:
    print(f"  {path.relative_to(DOCS_ROOT.parent)}: {error}")

if len(failed) > 20:
    print(f"  ... and {len(failed) - 20} more")
