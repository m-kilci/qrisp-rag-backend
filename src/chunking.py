DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks at word boundaries."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        target_end = min(start + chunk_size, len(text))

        if target_end == len(text):
            end = target_end
        else:
            # Find the last space before the target limit.
            end = text.rfind(" ", start + 1, target_end)

            if end == -1:
                # A single word is longer than the chunk limit.
                end = target_end

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        # Aim for the requested overlap, then move to a word boundary.
        next_start = max(start + 1, end - overlap)

        next_space = text.find(" ", next_start, end)
        if next_space != -1:
            next_start = next_space + 1
        else:
            next_start = end

        start = next_start

    return chunks
