"""Check index provenance using temporary stores and mocked embeddings."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from src.index_docs import main
from src.index_metadata import metadata_path
from src.vector_store import EmbeddingStoreError, load_embeddings, save_embeddings, search_embeddings


class IndexMetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.store = self.directory / "embeddings.json"
        self.sidecar = metadata_path(self.store)
        self.enterContext(patch("src.vector_store.STORE_PATH", self.store))
        self.enterContext(patch("src.embeddings.EMBEDDING_MODEL", "test-embed"))
        self.chunks = [{"text": "Documentation", "source": "sample.html", "chunk_index": 0}]

    def save(self, **settings):
        with patch("src.vector_store.embed_text", return_value=[0.1, 0.2]):
            save_embeddings(self.chunks, **settings)
        return json.loads(self.sidecar.read_text())

    def test_roundtrip_records_generation_settings_and_checksum(self):
        root = self.directory / "Qrisp/documentation/source"
        metadata = self.save(docs_root=root, chunk_size=1000, overlap=150)
        self.assertEqual(metadata["embedding_model"], "test-embed")
        self.assertEqual(metadata["documentation_source"], str(root.resolve()))
        self.assertEqual(metadata["chunking"], {"unit": "characters", "chunk_size": 1000, "overlap": 150})
        self.assertEqual(metadata["index_sha256"], hashlib.sha256(self.store.read_bytes()).hexdigest())
        self.assertIsNotNone(datetime.fromisoformat(metadata["created_at"]).utcoffset())
        self.assertEqual(len(load_embeddings()), 1)

    def test_unspecified_chunk_provenance_is_not_guessed(self):
        metadata = self.save()
        self.assertIsNone(metadata["documentation_source"])
        self.assertIsNone(metadata["chunking"])
        self.assertEqual(len(load_embeddings()), 1)

    def test_legacy_index_warns_without_adding_guessed_metadata(self):
        records = [{**self.chunks[0], "embedding": [0.1, 0.2]}]
        self.store.write_text(json.dumps(records))
        before = self.store.read_bytes()
        with self.assertWarnsRegex(UserWarning, "provenance is unverified"):
            self.assertEqual(load_embeddings(), records)
        self.assertFalse(self.sidecar.exists())
        self.assertEqual(self.store.read_bytes(), before)

    def test_different_model_same_dimensions_stops_before_embedding(self):
        self.save()
        with patch("src.embeddings.EMBEDDING_MODEL", "different-model"), \
             patch("src.vector_store.embed_text") as embed:
            with self.assertRaisesRegex(EmbeddingStoreError, "configured model is 'different-model'"):
                search_embeddings("A question")
            embed.assert_not_called()

    def test_changed_index_rejects_stale_metadata(self):
        self.save()
        records = json.loads(self.store.read_text())
        records[0]["text"] = "Changed documentation"
        self.store.write_text(json.dumps(records))
        with self.assertRaisesRegex(EmbeddingStoreError, "checksum"):
            load_embeddings()

    def test_malformed_metadata_json_is_explicit(self):
        self.save()
        self.sidecar.write_text("{")
        with self.assertRaisesRegex(EmbeddingStoreError, "invalid JSON"):
            load_embeddings()

    def test_invalid_metadata_fields_are_rejected(self):
        original = self.save()
        invalid = [None, {}, {**original, "schema_version": 2}]
        for field, value in [
            ("vector_dimensions", 3), ("chunk_count", 2), ("embedding_model", ""),
            ("embedding_input_prefix", "search_document: "), ("created_at", "unknown"),
            ("documentation_source", []), ("chunking", {}),
            ("chunking", {"unit": "characters", "chunk_size": 10, "overlap": 10}),
        ]:
            invalid.append({**original, field: value})
        for data in invalid:
            with self.subTest(metadata=data):
                self.sidecar.write_text(json.dumps(data))
                with self.assertRaises(EmbeddingStoreError):
                    load_embeddings()

    def test_failed_generation_preserves_existing_file_pair(self):
        self.save()
        previous = self.store.read_bytes(), self.sidecar.read_bytes()
        with patch("src.vector_store.embed_text", side_effect=[[0.1, 0.2], RuntimeError("Offline")]):
            with self.assertRaisesRegex(RuntimeError, "Offline"):
                save_embeddings(self.chunks * 2)
        self.assertEqual((self.store.read_bytes(), self.sidecar.read_bytes()), previous)

    def test_empty_generation_does_not_create_index_or_metadata(self):
        with patch("src.vector_store.embed_text") as embed:
            with self.assertRaisesRegex(EmbeddingStoreError, "empty index"):
                save_embeddings([])
            embed.assert_not_called()
        self.assertFalse(self.store.exists())
        self.assertFalse(self.sidecar.exists())

    def test_indexer_passes_the_same_chunk_settings_to_pipeline_and_store(self):
        root = self.directory / "documentation/source"
        with patch("src.index_docs.get_docs_root", return_value=root), \
             patch("src.index_docs.build_chunks", return_value=self.chunks) as build, \
             patch("src.index_docs.save_embeddings") as save:
            main()
        build.assert_called_once_with(root, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP)
        save.assert_called_once_with(self.chunks, docs_root=root,
                                     chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP)

    def test_indexer_script_entrypoint_has_settings_available_before_main(self):
        root = self.directory / "documentation/source"
        script = Path(__file__).resolve().parent.parent / "index_docs.py"
        with patch("src.config.get_docs_root", return_value=root), \
             patch("src.pipeline.build_chunks", return_value=self.chunks) as build, \
             patch("src.vector_store.save_embeddings") as save:
            runpy.run_path(str(script), run_name="__main__")
        build.assert_called_once_with(root, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP)
        save.assert_called_once_with(self.chunks, docs_root=root,
                                     chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP)


if __name__ == "__main__":
    unittest.main()
