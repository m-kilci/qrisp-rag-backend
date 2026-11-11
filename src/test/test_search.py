"""Inspect real retrieval without generating an answer or changing the index."""

import argparse

from src.vector_store import (
    EmbeddingStoreError,
    load_embeddings,
    prepare_retrieval_query,
    search_embeddings,
    select_context_chunks,
)

DEFAULT_QUERY = "How do I measure a QuantumVariable? Show a short Python example."
TARGET_SOURCE = "reference/Core/generated/qrisp.QuantumVariable.get_measurement.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--excerpts", action="store_true", help="Show context excerpts")
    args = parser.parse_args()

    # Use production ranking once: no copied scoring or second embedding call.
    try:
        count = len(load_embeddings())
        ranked = search_embeddings(args.query, top_k=count)
    except EmbeddingStoreError as exc:
        parser.exit(1, f"Index error: {exc}\n")
    context = select_context_chunks(args.query, ranked, top_k=10)

    print(f"Question: {args.query}")
    print(f"Retrieval query: {prepare_retrieval_query(args.query)}")
    print(f"Indexed chunks: {count}")
    print("\nTop ten raw results (RRF scores, not probabilities):")
    for rank, result in enumerate(ranked[:10], start=1):
        print(
            f"{rank:2}. {result['score']:.4f}  {result['source']} "
            f"(chunk {result['chunk_index']})"
        )

    print("\nContext selected for chat:")
    for result in context:
        print(f"  {result['source']} (chunk {result['chunk_index']})")
        if args.excerpts:
            print("    " + " ".join(result["text"].split())[:300])
    print(
        f"Context: {len(context)} chunks, "
        f"{sum(len(r['text']) for r in context):,} characters"
    )

    if args.query == DEFAULT_QUERY:
        target_ranks = [
            (r["chunk_index"], rank)
            for rank, r in enumerate(ranked, start=1)
            if r["source"] == TARGET_SOURCE
        ]
        print("\nMeasurement page raw ranks (chunk, rank):", target_ranks)
        target_chunks = {
            r["chunk_index"] for r in context if r["source"] == TARGET_SOURCE
        }
        assert {0, 3} <= target_chunks, "Measurement description or example missing"
        print("Measurement context check passed (description and example present).")

    assert len(context) <= 10


if __name__ == "__main__":
    main()
