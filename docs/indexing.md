# Indexing and stored data

[Project overview](../README.md)

## Entry point and input layout

Run explicit indexing from the backend environment and repository root:

```bash
python -m src.index_docs
```

`main()` resolves `QRISP_DOCS_ROOT`, passes the same size/overlap constants to
`build_chunks()` and `save_embeddings()`, and prints progress. It does not build
Sphinx HTML. Prepare that output first; see [setup](setup.md).

Given `/path/to/Qrisp/documentation/source`, the pipeline derives rendered HTML
at `/path/to/Qrisp/documentation/build/html`. `discover_documents()` returns a
sorted collection of:

- `.rst` files under the source tree, except those whose first relative component
  is `reference`;
- `.ipynb` notebooks under the source tree;
- all `.html` files under `build/html/reference`.

Missing rendered-reference input raises `FileNotFoundError`. Source Markdown
`.md` files are not currently discovered even though Sphinx can support Markdown.
The discovery code does not inherit all Sphinx exclusion patterns.

## Extraction

| Input | Extraction behavior |
| --- | --- |
| RST | Reads UTF-8 with BOM handling; RST syntax is retained rather than fully rendered |
| Notebook | Uses nbformat; combines Markdown cells and code cells wrapped in Python fences; ignores outputs and does not execute cells |
| HTML | BeautifulSoup removes navigation/script/style/footer/header/sidebar elements; selects `article.bd-article` or `main`; markdownify converts content to Markdown-like text |

HTML without a recognized content container raises an error. Whitespace cleanup
reduces excess blank lines without flattening paragraphs. Markdown escapes,
links, code, and tables can remain; technical identifiers and incidental link
tokens affect both semantic and keyword retrieval.

Rendered API references are used because source reference RST may contain only
autodoc directives rather than the full API documentation. Other source documents
are indexed directly to avoid requiring their rendered HTML for every input.

## Chunks and metadata

`chunk_text()` splits extracted text into passages with defaults defined in
`src/chunking.py`:

- `DEFAULT_CHUNK_SIZE = 1000` characters;
- `DEFAULT_CHUNK_OVERLAP = 150` characters.

It prefers spaces as boundaries. Overlap is approximate because the next start is
also adjusted to a word boundary. Long tokens can be split at the character
limit. The chunker does not preserve semantic sections, complete code blocks, or
all Markdown structures. Context expansion compensates for some split examples
but is itself bounded.

`build_chunks()` creates records with `text`, `source`, and zero-based
`chunk_index`. For source files, `source` is relative to the source directory;
for rendered HTML it is relative to `build/html`. For example:

```text
index.rst
general/tutorial/H2.ipynb
reference/Core/generated/qrisp.QuantumVariable.get_measurement.html
```

Preserve these root-relative paths. The frontend uses them to construct source
links. Absolute local paths are unnecessary for chunk attribution.

## Embeddings and persisted records

`embed_text()` calls Ollama's `/api/embed` once per chunk, using the configured
`OLLAMA_EMBEDDING_MODEL`. Inputs are plain text, without a task prefix. The helper
validates one finite, nonzero numeric vector and returns floats.

An embedding is a numerical representation used for similarity search; it does
not replace the chunk text. Keeping both allows the retriever to rank vectors and
then send readable passages to the chat model. Document vectors are generated
once during indexing. Each user question gets a new query vector at request time.

`save_embeddings()` keeps results in memory and writes a JSON list to
`data/embeddings.json`. A record has this shape (three vector components are shown
only to illustrate the format):

```json
{
  "text": "Documentation passage...",
  "source": "reference/Core/QuantumVariable.html",
  "chunk_index": 0,
  "embedding": [0.12, -0.03, 0.08]
}
```

Record counts depend on the corpus and chunking settings; vector dimensions
depend on the embedding model. They are not fixed by the record format. Vectors
must share a model and input convention; matching dimensions alone does not
establish compatibility.

## Index metadata

New writes also create `data/embeddings.metadata.json` via `src/index_metadata.py`.
The filename is derived from `STORE_PATH`, which also keeps temporary tests
isolated. The schema is:

| Field | Meaning |
| --- | --- |
| `schema_version` | Format version; currently 1 |
| `created_at` | UTC timestamp recorded after embedding generation, with timezone |
| `embedding_model` | Configured Ollama embedding model name |
| `embedding_input_prefix` | Empty string for the current plain-text helper |
| `vector_dimensions` | Components per vector |
| `chunk_count` | Records in the JSON list |
| `documentation_source` | Resolved source directory, or `null` if not supplied |
| `chunking` | Object with `unit: "characters"`, `chunk_size`, and `overlap`, or `null` |
| `index_sha256` | SHA-256 digest of the exact index-file bytes |

The normal indexer supplies source and chunking settings. Direct callers of
`save_embeddings()` may not know where/how their supplied chunks were produced;
omitted provenance is recorded as `null`, never inferred from current defaults.

Metadata is provenance/compatibility information, not an improvement to retrieval
quality. Model-name comparison is exact, including tags. It does not inspect
Ollama model digests: equivalent aliases can be rejected, while changed weights
under an unchanged name cannot be detected. Source location and timestamp also
do not capture a documentation checkout revision. The absolute provenance path
may include a local username; consider that when sharing newly generated files.

## Load-time validation

`load_embeddings()` rejects missing/unreadable files, invalid JSON, empty/wrong
top-level containers, and unusable records. Required fields are nonempty text and
source strings, a nonnegative integer `chunk_index`, and a nonempty numeric vector
that is finite, nonzero, and dimensionally consistent with the other records.

When a sidecar is present, the loader checks schema, checksum, count, dimensions,
model name, input convention, timestamp, and provenance field structure. Errors
become `EmbeddingStoreError`; the chat route returns HTTP 500 with an explanatory
`detail`. A query-vector dimension mismatch is also an index error. It does not
silently repair data, switch models, or regenerate embeddings.

### Legacy indexes

Indexes without a metadata sidecar remain usable after structural checks, but
loading emits a `UserWarning` that provenance is unverified and model identity
cannot be checked. No generation settings are backfilled from current configuration.

A deliberate rebuild records the actual generation settings. Do not invent
metadata for an old index or remove a sidecar to suppress a mismatch; this loses
compatibility information rather than resolving it.

## Replace, restore, and rebuild

Retain the existing populated index unless a rebuild is intentional. Indexing
performs one sequential embedding request per chunk and can take significant
time. There is no batching, resume checkpoint, or incremental document update.

Empty input is rejected. An embedding failure before publication leaves the
previous files intact. Both output files are staged in a temporary directory
before replacement. Each file replacement is atomic, but the pair is not a single
transaction. Interruption or concurrent reads between replacements can expose a
mismatched pair; checksum validation rejects it. Avoid rebuilding during use.

Copy/restore the index and its sidecar together. For a legacy index, do not attach
an unrelated sidecar. Keep copies before replacing a working index. The generated
`data/embeddings.json`, `data/embeddings.metadata.json`, and `local-backups/`
are excluded by `.gitignore` and should remain outside public distributions.

| Change | Re-index? |
| --- | --- |
| Chat model, prompt, UI formatting, BM25 rules, or context selection | No |
| Documentation content, chunk size/overlap, extraction, or embedding model/convention | Yes, to apply the change to stored data |
| Documentation source location only | Existing records still work; a future rebuild uses the new location |

Changing `QRISP_DOCS_ROOT` alone neither rebuilds the store nor moves browser
documentation. Changing embedding prefixes requires consistent changes to both
document/query embedding and the recorded/checked convention; do not change only
the query prefix and treat the old index as fully compatible.

## Switch embedding models

Document and query vectors must use the same model and input convention. To
change `OLLAMA_EMBEDDING_MODEL`:

1. Make the new model available on the configured Ollama host.
2. Stop chat use and save copies of the current index and metadata sidecar, if
   present.
3. Set `OLLAMA_EMBEDDING_MODEL` in backend `.env`; check for overriding shell
   variables. Keep `OLLAMA_MODEL` unchanged for an embedding-only change.
4. With the intended documentation and rendered references ready, run
   `python -m src.index_docs` from the backend environment and repository root.
5. Restart the backend and [inspect retrieval](development.md#inspect-real-retrieval)
   before assessing generated answers.

To restore the previous setup, restore its embedding-model setting and matching
index/sidecar pair, then restart. Do not remove metadata to bypass a mismatch.
Model-name and provenance checks have the [limits described above](#index-metadata).

## Distribution and attribution

The index includes Qrisp documentation text, not only numeric vectors. Generated
indexes are kept locally and are not part of the public distribution. The
application's MIT license does not relicense the extracted text. Before sharing
an index, clarify permission and applicable terms with the Qrisp rights holders;
metadata validation does not establish redistribution rights.
