"""Shared documentation location for indexing and manual diagnostics."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_docs_root() -> Path:
    """Read the source directory; relative paths use the working directory."""
    configured = os.getenv("QRISP_DOCS_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / "projects" / "Qrisp" / "documentation" / "source"
