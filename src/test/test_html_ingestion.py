from src.config import get_docs_root
from src.ingestion import read_html

path = (
    get_docs_root().parent / "build" / "html"
    / "general/tutorial/tutorial.html"
)

text = read_html(path)

print(f"Extracted characters: {len(text)}")
print(text[:5000])
