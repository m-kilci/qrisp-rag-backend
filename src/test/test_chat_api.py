"""Exercise HTTP/CORS behavior without calling Ollama."""

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from src.main import app
from src.embeddings import EmbeddingResponseError
from src.index_metadata import build_metadata, metadata_path


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_allowed_preview_preflight(self):
        for origin in ("http://127.0.0.1:8001", "http://localhost:8001"):
            with self.subTest(origin=origin):
                response = self.client.options("/chat", headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_unknown_origin_preflight_is_rejected(self):
        response = self.client.options("/chat", headers={
            "Origin": "https://unconfigured.example",
            "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_chat_returns_answer_and_sources_with_cors(self):
        upstream = Mock()
        upstream.json.return_value = {"message": {"content": "An answer.\n```python\nexample()\n```"}}
        records = [{"source": "reference/example.html", "text": "Documentation", "score": 0.02}]
        with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
             patch("src.main.OLLAMA_MODEL", "test-model"), \
             patch("src.main.search_context", return_value=records), \
             patch("src.main.httpx.post", return_value=upstream):
            response = self.client.post("/chat", json={"message": "A question"},
                                        headers={"Origin": "http://127.0.0.1:8001"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:8001")
        self.assertEqual(response.json()["answer"], upstream.json.return_value["message"]["content"])
        self.assertEqual(response.json()["sources"], [{"source": "reference/example.html", "score": 0.02}])

    def test_chat_timeout_returns_error_with_cors(self):
        with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
             patch("src.main.OLLAMA_MODEL", "test-model"), \
             patch("src.main.search_context", return_value=[]), \
             patch("src.main.httpx.post", side_effect=httpx.ReadTimeout("Test timeout")):
            response = self.client.post("/chat", json={"message": "A question"},
                                        headers={"Origin": "http://127.0.0.1:8001"})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"], "Ollama took too long to respond.")
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:8001")

    def test_missing_message_is_rejected(self):
        response = self.client.post("/chat", json={})
        self.assertEqual(response.status_code, 422)

    def test_blank_and_non_string_messages_stop_before_retrieval(self):
        for message in ("", "   ", "\n\t", None, 42, True, [], {}):
            with self.subTest(message=message):
                with patch("src.main.search_context") as search, \
                     patch("src.main.httpx.post") as generate:
                    response = self.client.post("/chat", json={"message": message})
                self.assertEqual(response.status_code, 422)
                search.assert_not_called()
                generate.assert_not_called()

    def request_with_upstream(self, upstream, question="A question"):
        records = [{"source": "sample.html", "text": "Documentation", "score": 0.02}]
        with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
             patch("src.main.OLLAMA_MODEL", "test-model"), \
             patch("src.main.search_context", return_value=records) as search, \
             patch("src.main.httpx.post", return_value=upstream):
            response = self.client.post("/chat", json={"message": question},
                                        headers={"Origin": "http://127.0.0.1:8001"})
        return response, search

    def test_question_trim_preserves_internal_code_indentation(self):
        upstream = Mock()
        answer = "  Answer\n```python\n    example()\n```\n"
        upstream.json.return_value = {"message": {"content": answer}}
        response, search = self.request_with_upstream(
            upstream, " \nExplain this:\n    example()\n ",
        )
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with("Explain this:\n    example()", top_k=10)
        self.assertEqual(response.json()["answer"], answer)

    def test_invalid_ollama_chat_json_returns_502(self):
        upstream = Mock()
        upstream.json.side_effect = ValueError("Invalid JSON")
        response, _ = self.request_with_upstream(upstream)
        self.assertEqual(response.status_code, 502)
        self.assertIn("invalid JSON", response.json()["detail"])
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:8001")

    def test_invalid_or_empty_ollama_answer_returns_502(self):
        payloads = [None, [], {}, {"error": "Upstream error"}, {"message": None},
                    {"message": []}, {"message": {}},
                    *[{"message": {"content": content}} for content in
                      (None, 1, False, [], {}, "", " \n\t")]]
        for payload in payloads:
            with self.subTest(payload=payload):
                upstream = Mock()
                upstream.json.return_value = payload
                response, _ = self.request_with_upstream(upstream)
                self.assertEqual(response.status_code, 502)
                self.assertIn("message.content", response.json()["detail"])

    def test_invalid_embedding_response_stops_chat_generation(self):
        with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
             patch("src.main.OLLAMA_MODEL", "test-model"), \
             patch("src.main.search_context", side_effect=EmbeddingResponseError(
                 "Ollama returned an invalid embedding response."
             )), \
             patch("src.main.httpx.post") as generate:
            response = self.client.post("/chat", json={"message": "A question"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("embedding response", response.json()["detail"])
        generate.assert_not_called()

    def test_unusable_index_stops_chat_before_any_ollama_request(self):
        with TemporaryDirectory() as directory:
            store = Path(directory) / "embeddings.json"
            for data, message in [(None, "missing"), ([], "empty"), ({}, "JSON list")]:
                with self.subTest(data=data):
                    if data is not None:
                        store.write_text(json.dumps(data))
                    with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
                         patch("src.main.OLLAMA_MODEL", "test-model"), \
                         patch("src.vector_store.STORE_PATH", store), \
                         patch("src.vector_store.embed_text") as embed, \
                         patch("src.main.httpx.post") as generate:
                        response = self.client.post("/chat", json={"message": "A question"})
                    self.assertEqual(response.status_code, 500)
                    self.assertIn(message, response.json()["detail"])
                    embed.assert_not_called()
                    generate.assert_not_called()

    def test_incompatible_query_vector_stops_before_chat_generation(self):
        with TemporaryDirectory() as directory:
            store = Path(directory) / "embeddings.json"
            store.write_text(json.dumps([{
                "text": "Sample", "source": "sample.html", "chunk_index": 0,
                "embedding": [0.1, 0.2],
            }]))
            with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
                 patch("src.main.OLLAMA_MODEL", "test-model"), \
                 patch("src.vector_store.STORE_PATH", store), \
                 patch("src.vector_store.embed_text", return_value=[0.1, 0.2, 0.3]), \
                 patch("src.main.httpx.post") as generate:
                response = self.client.post("/chat", json={"message": "A question"})
            self.assertEqual(response.status_code, 500)
            self.assertIn("dimensions", response.json()["detail"])
            generate.assert_not_called()

    def test_metadata_model_mismatch_returns_500_without_ollama_calls(self):
        with TemporaryDirectory() as directory:
            store = Path(directory) / "embeddings.json"
            content = json.dumps([{
                "text": "Documentation", "source": "sample.html", "chunk_index": 0,
                "embedding": [0.1, 0.2],
            }]).encode("utf-8")
            store.write_bytes(content)
            metadata_path(store).write_text(json.dumps(build_metadata(
                content, model="recorded-model", dimensions=2, chunk_count=1,
            )))
            with patch("src.main.OLLAMA_BASE_URL", "http://ollama.test"), \
                 patch("src.main.OLLAMA_MODEL", "test-model"), \
                 patch("src.embeddings.EMBEDDING_MODEL", "different-model"), \
                 patch("src.vector_store.STORE_PATH", store), \
                 patch("src.vector_store.embed_text") as embed, \
                 patch("src.main.httpx.post") as generate:
                response = self.client.post("/chat", json={"message": "A question"})
            self.assertEqual(response.status_code, 500)
            self.assertIn("embedding model", response.json()["detail"])
            embed.assert_not_called()
            generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
