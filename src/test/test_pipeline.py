from collections import Counter

from src.config import get_docs_root
from src.pipeline import build_chunks

DOCS_ROOT = get_docs_root()

chunks = build_chunks(DOCS_ROOT)

by_top_level = Counter(chunk["source"].split("/")[0] for chunk in chunks)

print("\nChunks by top-level directory:")
for directory, count in by_top_level.most_common():
    print(f"  {directory}: {count}")

code_chunks = sum("```python" in chunk["text"] for chunk in chunks)
print(f"\nChunks containing Python code fences: {code_chunks}")


print(f"Documents processed: {len({chunk['source'] for chunk in chunks})}")
print(f"Total chunks: {len(chunks)}")

for chunk in chunks[:3]:
    print(f"\nSource: {chunk['source']}")
    print(f"Chunk index: {chunk['chunk_index']}")
    print(chunk["text"][:250])
