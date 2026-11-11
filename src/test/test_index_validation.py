"""Check invalid indexes using temporary files and mocked query embeddings."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.vector_store import (
    EmbeddingStoreError, load_embeddings, search_context, search_embeddings,
)


def record(**changes):
    return {"text": "Sample documentation", "source": "reference/sample.html",
            "chunk_index": 0, "embedding": [0.1, 0.2], **changes}


class IndexValidationTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.store = Path(directory) / "embeddings.json"
        self.enterContext(patch("src.vector_store.STORE_PATH", self.store))

    def write(self, data):
        self.store.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_index_loads_without_changes(self):
        records = [record(), record(chunk_index=1, embedding=[1, 2])]
        self.write(records)
        self.assertEqual(load_embeddings(), records)

    def test_missing_index_has_recovery_instruction(self):
        with self.assertRaisesRegex(EmbeddingStoreError, "missing.*"):
            load_embeddings()

    def test_unreadable_index_is_explicit(self):
        self.store.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(EmbeddingStoreError, "could not be read"):
            load_embeddings()

    def test_invalid_json_is_explicit(self):
        self.store.write_text("[{", encoding="utf-8")
        with self.assertRaisesRegex(EmbeddingStoreError, "invalid JSON"):
            load_embeddings()

    def test_wrong_root_and_empty_index_are_rejected(self):
        for data, message in [(None, "JSON list"), ({}, "JSON list"), ([], "empty")]:
            with self.subTest(data=data):
                self.write(data)
                with self.assertRaisesRegex(EmbeddingStoreError, message):
                    load_embeddings()

    def test_bad_records_are_rejected_with_their_position(self):
        invalid = [
            None, {}, record(text=" "), record(source=1),
            record(chunk_index=-1), record(chunk_index=True),
            record(embedding=[]), record(embedding="vector"),
            record(embedding=[0, 0]), record(embedding=[True, 0.1]),
            record(embedding=[float("nan"), 1]),
            record(embedding=[float("inf"), 1]),
            record(embedding=["0.1", 0.2]),
            record(embedding=[1, 2, 3]),
        ]
        for item in invalid:
            with self.subTest(record=item):
                self.write([record(), item])
                with self.assertRaisesRegex(EmbeddingStoreError, "record 1 is invalid"):
                    load_embeddings()

    def test_empty_index_stops_before_embedding_request(self):
        self.write([])
        with patch("src.vector_store.embed_text") as embed:
            for search in (search_embeddings, search_context):
                with self.subTest(search=search.__name__):
                    with self.assertRaisesRegex(EmbeddingStoreError, "empty"):
                        search("A question")
            embed.assert_not_called()

    def test_query_dimension_mismatch_is_explicit(self):
        self.write([record()])
        with patch("src.vector_store.embed_text", return_value=[0.1, 0.2, 0.3]):
            with self.assertRaisesRegex(EmbeddingStoreError, "3 dimensions.*index has 2"):
                search_embeddings("A question")


if __name__ == "__main__":
    unittest.main()
