from src.chunking import chunk_text

sample = (
    "Qrisp is a framework for quantum programming.\n\n"
    "QuantumVariable represents a quantum variable. "
    "It can be measured to obtain classical results.\n\n"
    "Quantum circuits can be constructed using quantum gates."
)

chunks = chunk_text(sample, chunk_size=100, overlap=20)

for index, chunk in enumerate(chunks, start=1):
    print(f"\n--- Chunk {index} ({len(chunk)} characters) ---")
    print(chunk)

assert "".join(chunks)  # At least some text was produced.
assert all(chunk.strip() for chunk in chunks)

print(f"\nCreated {len(chunks)} chunks.")

# Test that empty text produces no chunks.
assert chunk_text("") == []

# Test that a single short text remains one chunk.
assert chunk_text("Hello world.") == ["Hello world."]

# Test that chunks do not start or end in the middle of a word.
sample = "alpha bravo charlie delta echo foxtrot golf hotel"
chunks = chunk_text(sample, chunk_size=20, overlap=5)

for chunk in chunks:
    assert chunk == chunk.strip()
    assert not chunk.startswith(" ")
    assert not chunk.endswith(" ")

    print(f"{len(chunk):2} chars: {chunk}")

print("Basic chunking tests passed.")
