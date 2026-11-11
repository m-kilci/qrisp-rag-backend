import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from src.embeddings import EmbeddingResponseError
from src.vector_store import EmbeddingStoreError, search_context

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

app = FastAPI()

# Use a separate port for Sphinx preview; Uvicorn keeps port 8000.
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS", "http://127.0.0.1:8001,http://localhost:8001"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Nonblank question; outer whitespace is trimmed.")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must contain non-whitespace text.")
        return value


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    if not OLLAMA_BASE_URL or not OLLAMA_MODEL:
        raise HTTPException(
            status_code=500,
            detail="Ollama configuration is missing.",
        )

    try:
        results = search_context(request.message, top_k=10)
    except EmbeddingResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve documentation embeddings.",
        ) from exc
    except EmbeddingStoreError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    if not results:
        context = "No relevant documentation chunks were found."
    else:
        context = "\n\n".join(
            (f"Source: {result['source']}\n" f"{result['text']}") for result in results
        )

    prompt = f"""You are an assistant that answers questions about Qrisp.

Use the documentation context below to answer the user's question.
Treat the context as the primary source of truth.
Do not invent Qrisp APIs or behavior.
If the context does not contain enough information, say so clearly.
You may explain relevant code examples, but distinguish them from
claims explicitly supported by the documentation.
When useful, mention the source file used.
Prefer documentation defining the API identifier named in the question.
Keep APIs from different classes and execution models distinct.
Check code examples against the documented signature. If an example conflicts
with the signature, omit the conflicting optional argument or explain the issue.
When adapting a documentation example, retain the imports for every function
and class used in the resulting snippet, even when shortening the example.

Documentation context:
{context}

User question:
{request.message}
"""

    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=300.0,
        )
        response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Ollama took too long to respond.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not communicate with Ollama.",
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Ollama returned invalid JSON for the chat response."
        ) from exc

    message = data.get("message") if isinstance(data, dict) else None
    answer = message.get("content") if isinstance(message, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(
            status_code=502,
            detail="Ollama returned an invalid chat response: expected nonempty message.content text.",
        )

    return {
        "answer": answer,
        "sources": [
            {
                "source": result["source"],
                "score": result["score"],
            }
            for result in results
        ],
    }
