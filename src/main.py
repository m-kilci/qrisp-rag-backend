from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

app = FastAPI()

class ChatRequest(BaseModel):
  message: str

@app.get("/health")
def health():
  return {"status": "ok"}

@app.post("/chat")
def chat(request: ChatRequest):
  if not OLLAMA_BASE_URL or not OLLAMA_MODEL:
    raise HTTPException(
      status_code=500,
      detail="Ollama configuration is missing",
    )

  try:
    response = httpx.post(
      f"{OLLAMA_BASE_URL}/api/chat",
      json={
        "model": OLLAMA_MODEL,
        "messages": [
          {
            "role": "user",
            "content": request.message,
          }
        ],
        "stream": False,
      },
      timeout=300.0,
    )
    response.raise_for_status()

  except httpx.TimeoutException:
    raise HTTPException(
      status_code=504,
      detail="Ollama took too long to respond",
    )
  except httpx.HTTPError:
    raise HTTPException(
      status_code=502,
      detail="Could not communicate with Ollama",
    )

  data = response.json()

  return {"answer": data["message"]["content"]}