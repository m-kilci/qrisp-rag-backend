"""Validate upstream embedding responses without contacting Ollama."""

import unittest
from unittest.mock import Mock, patch

import httpx

from src.embeddings import EmbeddingResponseError, embed_text


class EmbeddingResponseTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("src.embeddings.OLLAMA_BASE_URL", "http://ollama.test"))
        self.response = Mock()
        self.post = self.enterContext(patch("src.embeddings.httpx.post", return_value=self.response))

    def test_valid_vector_returns_floats(self):
        self.response.json.return_value = {"embeddings": [[1, 0, -0.5]]}
        vector = embed_text("Some documentation")
        self.assertEqual(vector, [1.0, 0.0, -0.5])
        self.assertTrue(all(isinstance(value, float) for value in vector))

    def test_invalid_json_is_explicit(self):
        self.response.json.side_effect = ValueError("Invalid JSON")
        with self.assertRaisesRegex(EmbeddingResponseError, "invalid JSON"):
            embed_text("A question")

    def test_missing_or_multiple_vectors_are_rejected(self):
        for payload in (None, [], {}, {"embeddings": None}, {"embeddings": []},
                        {"embeddings": [[0.1], [0.2]]}):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                with self.assertRaisesRegex(EmbeddingResponseError, "one embedding vector"):
                    embed_text("A question")

    def test_invalid_vector_values_are_rejected(self):
        for vector in (None, [], {}, ["0.1"], [True], [float("nan")],
                       [float("inf")], [0, 0], [2 ** 4096]):
            with self.subTest(vector=vector):
                self.response.json.return_value = {"embeddings": [vector]}
                with self.assertRaises(EmbeddingResponseError):
                    embed_text("A question")

    def test_transport_errors_remain_http_errors(self):
        self.post.side_effect = httpx.ConnectError("Connection unavailable")
        with self.assertRaises(httpx.ConnectError):
            embed_text("A question")


if __name__ == "__main__":
    unittest.main()
