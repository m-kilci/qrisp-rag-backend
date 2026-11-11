import json
import math
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from src.embeddings import embed_text
from src import embeddings
from src.index_metadata import build_metadata, check_metadata, metadata_path

STORE_PATH = Path("data/embeddings.json")


class EmbeddingStoreError(ValueError):
    """The documentation index cannot be used for retrieval."""


def save_embeddings(
    chunks: list[dict], *, docs_root: Path | None = None,
    chunk_size: int | None = None, overlap: int | None = None,
) -> None:
    """Embed chunks and save their text, metadata, and vectors."""
    if not chunks:
        raise EmbeddingStoreError("Cannot create an empty index. Check the documentation input.")
    records = []

    for index, chunk in enumerate(chunks, start=1):
        vector = embed_text(chunk["text"])

        records.append(
            {
                "text": chunk["text"],
                "source": chunk["source"],
                "chunk_index": chunk["chunk_index"],
                "embedding": vector,
            }
        )

        print(f"Embedded {index}/{len(chunks)} chunks")

    dimensions = len(records[0]["embedding"])
    if any(len(record["embedding"]) != dimensions for record in records):
        raise EmbeddingStoreError("Embedding dimensions changed during indexing; existing index was not replaced.")
    index_bytes = json.dumps(records, ensure_ascii=False).encode("utf-8")
    metadata = build_metadata(
        index_bytes, model=embeddings.EMBEDDING_MODEL, dimensions=dimensions,
        chunk_count=len(records), docs_root=docs_root, chunk_size=chunk_size,
        overlap=overlap,
    )
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Stage both files before replacement. If interrupted between replacements,
    # checksum verification rejects a mismatched pair rather than trusting it.
    with TemporaryDirectory(dir=STORE_PATH.parent) as directory:
        staged_index = Path(directory) / "index.json"
        staged_metadata = Path(directory) / "metadata.json"
        staged_index.write_bytes(index_bytes)
        staged_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        staged_index.replace(STORE_PATH)
        staged_metadata.replace(metadata_path(STORE_PATH))


def load_embeddings() -> list[dict]:
    """Load and validate the saved chunks before retrieval contacts Ollama."""
    try:
        index_bytes = STORE_PATH.read_bytes()
        text = index_bytes.decode("utf-8")
    except FileNotFoundError as exc:
        raise EmbeddingStoreError(
            f"Documentation index is missing at {STORE_PATH}. "
            "Run python -m src.index_docs to create it."
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise EmbeddingStoreError(
            f"Documentation index at {STORE_PATH} could not be read. "
            "Check the file location, permissions, and UTF-8 encoding."
        ) from exc

    try:
        records = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EmbeddingStoreError(
            "Documentation index contains invalid JSON. "
            "Restore a valid index or rebuild it with python -m src.index_docs."
        ) from exc

    if not isinstance(records, list):
        raise EmbeddingStoreError(
            "Documentation index must contain a JSON list of chunk records. "
            "Restore a compatible index or rebuild it with python -m src.index_docs."
        )
    if not records:
        raise EmbeddingStoreError(
            "Documentation index is empty. Check the documentation input, "
            "then run python -m src.index_docs."
        )

    dimensions = None
    for position, record in enumerate(records):
        problem = None
        if not isinstance(record, dict):
            problem = "expected a chunk object"
        elif any(
            not isinstance(record.get(field), str) or not record[field].strip()
            for field in ("text", "source")
        ):
            problem = "text and source must be nonempty strings"
        elif type(record.get("chunk_index")) is not int or record["chunk_index"] < 0:
            problem = "chunk_index must be a nonnegative integer"
        else:
            vector = record.get("embedding")
            if not isinstance(vector, list) or not vector:
                problem = "embedding must be a nonempty numeric list"
            else:
                try:
                    finite = all(type(value) in (int, float) and math.isfinite(value)
                                 for value in vector)
                except OverflowError:
                    finite = False
                if not finite:
                    problem = "embedding must contain only finite numbers"
                elif not any(vector):
                    problem = "embedding must not be a zero vector"
                elif dimensions is not None and len(vector) != dimensions:
                    problem = "stored embeddings have inconsistent dimensions"
                else:
                    dimensions = len(vector)
        if problem:
            raise EmbeddingStoreError(
                f"Documentation index record {position} is invalid: {problem}. "
                "Restore a valid index or rebuild it with python -m src.index_docs."
            )

    try:
        check_metadata(
            STORE_PATH, index_bytes, model=embeddings.EMBEDDING_MODEL,
            dimensions=dimensions, chunk_count=len(records),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise EmbeddingStoreError(
            f"Documentation index metadata is unusable: {exc}. "
            "Check the model configuration, restore the matching index/metadata "
            "pair, or rebuild with python -m src.index_docs."
        ) from exc
    return records


def tokenize(text: str) -> list[str]:
    """Split technical identifiers into searchable words."""
    # Split camelCase: QuantumVariable -> Quantum Variable
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)

    # Split on punctuation and underscores:
    # get_measurement -> get, measurement
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def prepare_retrieval_query(query: str) -> str:
    """Separate a trailing example-format request from the search topic."""
    match = re.search(
        r"(?<=[?.!])\s+(?:please\s+)?(?:show|give|provide)\s+"
        r"(?:(?:me|us)\s+)?(?:a|an)\s+"
        r"(?:(?:short|simple|brief|small)\s+)?(?:python\s+)?"
        r"(?:code\s+)?example[.!]?\s*$",
        query,
        flags=re.IGNORECASE,
    )
    return query[:match.start()].strip() if match else query.strip()


def expand_query_tokens(query: str) -> list[str]:
    """Add common technical variants of query terms."""
    tokens = [token for token in tokenize(query) if token not in ENGLISH_STOP_WORDS]
    expanded = list(tokens)

    synonyms = {
        "measure": ["measurement", "get_measurement"],
        "measuring": ["measurement", "get_measurement"],
        "measured": ["measurement", "get_measurement"],
    }

    for token in tokens:
        expanded.extend(synonyms.get(token, []))

    return expanded


def search_embeddings(query: str, top_k: int = 3) -> list[dict]:
    """Combine semantic search and BM25 using reciprocal rank fusion."""
    from rank_bm25 import BM25Okapi

    records = load_embeddings()
    retrieval_query = prepare_retrieval_query(query)
    query_embedding = embed_text(retrieval_query)
    if len(query_embedding) != len(records[0]["embedding"]):
        raise EmbeddingStoreError(
            f"Query embedding has {len(query_embedding)} dimensions, but the "
            f"documentation index has {len(records[0]['embedding'])}. "
            "Use the embedding model that produced the index, or rebuild it "
            "with python -m src.index_docs."
        )

    # 1. Rank documents by semantic similarity.
    document_embeddings = [record["embedding"] for record in records]
    semantic_scores = cosine_similarity(
        [query_embedding],
        document_embeddings,
    )[0]

    semantic_order = sorted(
        range(len(records)),
        key=lambda i: semantic_scores[i],
        reverse=True,
    )

    # 2. Rank documents by keyword relevance using BM25.
    tokenized_documents = [
        tokenize(record["source"]) + tokenize(record["text"]) for record in records
    ]
    bm25 = BM25Okapi(tokenized_documents)
    bm25_scores = bm25.get_scores(expand_query_tokens(retrieval_query))

    bm25_order = sorted(
        range(len(records)),
        key=lambda i: bm25_scores[i],
        reverse=True,
    )

    # 3. Combine both rankings using reciprocal rank fusion.
    rrf_scores = [0.0] * len(records)
    rrf_constant = 60

    for rank, index in enumerate(semantic_order, start=1):
        rrf_scores[index] += 1 / (rrf_constant + rank)

    for rank, index in enumerate(bm25_order, start=1):
        rrf_scores[index] += 1 / (rrf_constant + rank)

    # 4. Return the highest-ranked chunks with diagnostic scores.
    results = []

    for index, record in enumerate(records):
        results.append(
            {
                "text": record["text"],
                "source": record["source"],
                "chunk_index": record["chunk_index"],
                "score": rrf_scores[index],
                "semantic_score": float(semantic_scores[index]),
                "bm25_score": float(bm25_scores[index]),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: max(0, top_k)]


def select_context_chunks(
    query: str, ranked_chunks: list[dict], top_k: int = 10,
) -> list[dict]:
    """Choose up to three pages, keeping definitions and examples together.

    ranked_chunks must contain all indexed chunks in retrieval order so that
    a selected page's introduction and examples are available for expansion.
    Each example window contains at most three consecutive chunks; top_k
    still limits the total context, including these continuation chunks.
    """
    if top_k <= 0:
        return []

    # Match complete API-name components, not incidental links in body text.
    # Ordinary words are considered only when explicitly written as calls or
    # in backticks; class names and dotted/underscored names are recognizable.
    identifiers = set()
    for match in re.finditer(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", query):
        name = match.group()
        if (
            re.search(r"[a-z0-9][A-Z]|[_.]", name)
            or re.match(r"\s*\(", query[match.end():])
            or (match.start() > 0 and query[match.start() - 1] == "`")
        ):
            identifiers.add(name.lower())

    def matches_identifier(source: str) -> bool:
        stem = Path(source).stem.lower()
        return any(stem == name or stem.endswith("." + name)
                   or name in stem.split(".") for name in identifiers)

    scoped = [r for r in ranked_chunks if matches_identifier(r["source"])]
    if not scoped:
        # Recognize complete spaced class names using indexed filenames:
        # "quantum circuit" can refer to QuantumCircuit. Do not let an
        # inferred phrase override an explicitly matched API identifier.
        query_words = " " + " ".join(tokenize(prepare_retrieval_query(query))) + " "
        for source in dict.fromkeys(r["source"] for r in ranked_chunks):
            name = Path(source).stem
            words = tokenize(name)
            if (
                "." not in name
                and re.search(r"[a-z0-9][A-Z]", name)
                and len(words) > 1
                and " " + " ".join(words) + " " in query_words
            ):
                identifiers.add(name.lower())
        scoped = [r for r in ranked_chunks if matches_identifier(r["source"])]
    candidates = scoped or ranked_chunks
    pages = {}
    for record in ranked_chunks:
        pages.setdefault(record["source"], []).append(record)
    for page in pages.values():
        page.sort(key=lambda r: r["chunk_index"])

    sources = []
    for record in candidates:
        source = record["source"]
        if source in sources:
            continue
        sources.append(source)
        # Generated method pages can contain only a signature. Their parent
        # class page provides construction and usage context, when indexed.
        path = Path(source)
        parts = path.stem.split(".")
        has_example = any(re.search(r"```(?:python|py)\b", r["text"])
                          for r in pages[source])
        if path.parent.name == "generated" and len(parts) >= 3 and not has_example:
            parent_source = str(path.parent.parent / f"{parts[-2]}.html")
            if parent_source in pages and parent_source not in sources:
                sources.append(parent_source)
        if len(sources) >= 3:
            break
    sources = sources[:3]
    selected = []
    seen = set()

    for source in sources:
        page = pages[source]
        best = next(r for r in ranked_chunks if r["source"] == source)
        example_start = next(
            (i for i, r in enumerate(page) if re.search(
                r"^\s*(?:#+\s*)?Examples\s*$", r["text"], re.MULTILINE,
            )),
            None,
        )
        # A heading can occur at the end of a chunk. Keep its following
        # passages too, since the code and explanation may start there.
        example_chunks = (
            page[example_start:example_start + 3]
            if example_start is not None else []
        )
        for record in [page[0], best] + example_chunks:
            key = (record["source"], record["chunk_index"])
            if key not in seen:
                seen.add(key)
                selected.append(record)
                if len(selected) == top_k:
                    return selected

    return selected


def search_context(query: str, top_k: int = 10) -> list[dict]:
    """Retrieve ranked chunks, then assemble bounded, page-aware context."""
    count = len(load_embeddings())
    if top_k <= 0:
        return []
    return select_context_chunks(
        query, search_embeddings(query, top_k=count), top_k=top_k,
    )
