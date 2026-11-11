"""Provenance and compatibility checks for the embedding index sidecar."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings


def metadata_path(store: Path) -> Path:
    return store.with_suffix(".metadata.json")


def build_metadata(
    index_bytes: bytes, *, model: str, dimensions: int, chunk_count: int,
    docs_root: Path | None = None, chunk_size: int | None = None,
    overlap: int | None = None,
) -> dict:
    """Record known generation settings; leave unspecified provenance null."""
    chunking = None
    if chunk_size is not None or overlap is not None:
        if (type(chunk_size) is not int or type(overlap) is not int
                or chunk_size <= 0 or not 0 <= overlap < chunk_size):
            raise ValueError("Metadata requires positive chunk_size and 0 <= overlap < chunk_size.")
        chunking = {"unit": "characters", "chunk_size": chunk_size, "overlap": overlap}
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": model,
        "embedding_input_prefix": "",
        "vector_dimensions": dimensions,
        "chunk_count": chunk_count,
        "documentation_source": str(docs_root.resolve()) if docs_root is not None else None,
        "chunking": chunking,
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
    }


def check_metadata(
    store: Path, index_bytes: bytes, *, model: str, dimensions: int, chunk_count: int,
) -> None:
    """Check new indexes; allow legacy indexes with an explicit warning."""
    path = metadata_path(store)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        warnings.warn(
            f"No metadata found at {path}; index provenance is unverified. "
            "Embedding model identity cannot be checked. Rebuild intentionally "
            "to record verified generation settings; do not guess legacy settings.",
            UserWarning, stacklevel=2,
        )
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("metadata contains invalid JSON") from exc
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("metadata must be an object with schema_version 1")
    if data.get("index_sha256") != hashlib.sha256(index_bytes).hexdigest():
        raise ValueError("metadata checksum does not match the index; use the matching file pair")
    if type(data.get("vector_dimensions")) is not int or data["vector_dimensions"] != dimensions:
        raise ValueError("metadata vector dimensions do not match the index")
    if type(data.get("chunk_count")) is not int or data["chunk_count"] != chunk_count:
        raise ValueError("metadata chunk count does not match the index")
    recorded_model = data.get("embedding_model")
    if not isinstance(recorded_model, str) or not recorded_model.strip():
        raise ValueError("metadata embedding_model must be nonempty text")
    if recorded_model != model:
        raise ValueError(
            f"index was created with embedding model '{recorded_model}', "
            f"but the configured model is '{model}'; use the recorded model or rebuild"
        )
    if data.get("embedding_input_prefix") != "":
        raise ValueError("metadata uses incompatible embedding input prefixes")
    created_at = data.get("created_at")
    try:
        if not isinstance(created_at, str) or datetime.fromisoformat(created_at).utcoffset() is None:
            raise ValueError
    except ValueError as exc:
        raise ValueError("metadata created_at must be an ISO timestamp with a timezone") from exc
    if "documentation_source" not in data or (
        data["documentation_source"] is not None
        and (not isinstance(data["documentation_source"], str) or not data["documentation_source"].strip())
    ):
        raise ValueError("metadata documentation_source must be nonempty text or null")
    if "chunking" not in data:
        raise ValueError("metadata must include chunking settings or null")
    chunking = data["chunking"]
    if chunking is not None:
        if not isinstance(chunking, dict):
            raise ValueError("metadata chunking must be an object or null")
        size, overlap = chunking.get("chunk_size"), chunking.get("overlap")
        if (chunking.get("unit") != "characters" or type(size) is not int
                or type(overlap) is not int or size <= 0 or not 0 <= overlap < size):
            raise ValueError("metadata chunking settings are invalid")
