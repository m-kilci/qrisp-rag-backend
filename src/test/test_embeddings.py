from src.embeddings import embed_text

text = "A QuantumVariable can be measured in Qrisp."
vector = embed_text(text)

print(f"Input text: {text}")
print(f"Vector dimensions: {len(vector)}")
print(f"First 5 values: {vector[:5]}")

assert len(vector) > 0
assert all(isinstance(value, float) for value in vector)

print("Embedding test passed.")
