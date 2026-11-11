import os
import math

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "nomic-embed-text",
)


class EmbeddingResponseError(RuntimeError):
    """Ollama returned a response that cannot be used as a query/document vector."""


def embed_text(text: str) -> list[float]:
    """Convert text into an embedding vector using Ollama."""
    if not OLLAMA_BASE_URL:
        raise RuntimeError("OLLAMA_BASE_URL is not configured.")

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={
            "model": EMBEDDING_MODEL,
            "input": text,
        },
        timeout=60.0,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:
        raise EmbeddingResponseError(
            "Ollama returned invalid JSON for the embedding response."
        ) from exc

    vectors = data.get("embeddings") if isinstance(data, dict) else None
    if not isinstance(vectors, list) or len(vectors) != 1:
        raise EmbeddingResponseError(
            "Ollama returned an invalid embedding response: expected one embedding vector."
        )
    vector = vectors[0]
    if not isinstance(vector, list) or not vector or any(
        type(value) not in (int, float) for value in vector
    ):
        raise EmbeddingResponseError(
            "Ollama returned an invalid embedding response: expected a nonempty numeric vector."
        )
    try:
        finite = all(math.isfinite(value) for value in vector)
    except OverflowError:
        finite = False
    if not finite or not any(vector):
        raise EmbeddingResponseError(
            "Ollama returned an invalid embedding response: vector must be finite and nonzero."
        )
    return [float(value) for value in vector]
