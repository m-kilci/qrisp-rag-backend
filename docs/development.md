# Testing and troubleshooting

[Project overview](../README.md)

## Offline checks

Activate the backend environment and run from its root:

```bash
python -m unittest \
  src.test.test_context_selection \
  src.test.test_index_validation \
  src.test.test_index_metadata \
  src.test.test_embedding_responses \
  src.test.test_chat_api

python -m src.test.test_chunking
python -m unittest discover -s frontend -p 'test_install_assets.py'
```

| Module | Coverage |
| --- | --- |
| `test_context_selection` | Identifier scope, spaced names, fallback, parent pages, example continuations, budgets |
| `test_index_validation` | Missing/corrupt/empty indexes, invalid records/vectors, dimensions |
| `test_index_metadata` | Generation settings, checksums, model mismatch, legacy behavior, failed-generation preservation, indexer entry point |
| `test_embedding_responses` | Valid vectors, malformed responses, transport errors |
| `test_chat_api` | Request/response validation, CORS, timeouts, index rejection |

These modules mock Ollama and use temporary stores; they do not perform inference
or change the real index. API tests use an in-process HTTP client. They do not
automate browser behavior or assess generated-answer quality. A provenance
warning is expected for test fixtures representing indexes without metadata.

Several manual diagnostic modules execute at import time. Use the explicit list
above: broad test discovery is not guaranteed to remain offline.

The frontend installer tests use temporary checkout layouts to check dry runs,
identical files, conflicts, and symlink rejection. They require only the standard
library and do not build Qrisp documentation.

## Inspect real retrieval

These commands require a populated index and reachable Ollama embedding model:

```bash
python -m src.test.test_search
python -m src.test.test_search "How can I simulate a quantum circuit? Show a short Python example." --excerpts
```

The diagnostic calls production ranking once, then production context selection.
It prints the prepared query, top ten raw results, selected paths/chunk positions,
and context size. `--excerpts` adds text previews. It generates no chat answer and
does not write the index.

The default measurement query checks for description chunk 0 and example chunk 3
from the method page. These positions depend on the indexed corpus and can change
after rebuilding. That assertion is not a general relevance metric.

## Other manual diagnostics

Run individually as `python -m MODULE`:

| Module | Prerequisites and effects |
| --- | --- |
| `src.test.test_ingestion` | Reads configured docs; reports discovery and extraction |
| `src.test.test_html_ingestion` | Reads built `general/tutorial/tutorial.html` derived from the configured source root |
| `src.test.test_pipeline` | Reads docs and creates chunks in memory |
| `src.test.test_embeddings` | Requests one embedding; checks basic vector shape |
| `src.test.test_vector_store` | Reads docs, embeds three chunks, saves/loads a temporary index and sidecar |

The vector-store diagnostic uses a temporary index. Its dimension assertion
assumes 768 components and will fail for other embedding sizes.

## Browser checks

With [both services running](setup.md#run-the-browser-interface), check formatted
answers and source links from the homepage and a nested page. Stop the backend,
check that a failed request leaves the input usable, then restart and retry.
Markdown sanitization needs a separate browser check; generated code is never
executed by the application.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| `sphinx-autobuild` missing | Activate the Qrisp docs environment and install the preview tool there |
| Qrisp rejects Python 3.14 | Check its declared Python range; the tested docs environment uses Python 3.13 |
| Sphinx reports missing tools/extensions | Resolve the build error in the Qrisp environment, not the backend |
| Port already in use | API defaults to 8000; docs preview uses 8001 |
| Health works but chat fails | Inspect the chat status/detail; health does not check configuration, the index, or Ollama |
| HTTP 422 | Submit a JSON object with a nonblank string `message` |
| HTTP 500 index error | Check working directory, index validity, and matching metadata/model; see [index validation](indexing.md#load-time-validation) |
| Provenance warning only | The sidecar is absent; see [legacy indexes](indexing.md#legacy-indexes) |
| HTTP 502 during retrieval | Check Ollama connectivity, embedding-model availability, and returned vectors |
| HTTP 502 after retrieval | Check chat-model availability, upstream errors, and returned JSON/content |
| HTTP 504 | Generation hit the backend timeout; inspect the inference host |
| Browser cannot reach the assistant | Inspect Network/Console, API process, URL, and CORS; curl does not enforce CORS |
| Browser shows old behavior | Rebuild docs, inspect loaded assets, and force refresh; endpoint configuration is build-time |
| Missing formatting | Check `typeof marked.parse` and `typeof DOMPurify.sanitize`; verify assets and script order |
| Wrong answer with plausible sources | Inspect actual selected text; relevant context does not guarantee a correct answer |
| Broken source link | Check indexed path, Sphinx output layout, and alignment between site and indexed docs |

## Known limitations

- Models can produce incorrect API behavior, output labels, or physical
  explanations despite relevant context. Source links expose supplied context,
  not claim-level verification; generated examples are not executed.
- Retrieval uses English tokenization/stopwords, measurement-specific expansion,
  narrow example-request removal, and filename heuristics. It has no relevance
  threshold, general intent extraction, or reranker.
- Identifier scoping can exclude tutorials. Complete spaced-name matching does
  not cover arbitrary plurals or paraphrases. Bounded example/context selection
  can omit needed passages; it is not token-aware.
- Documentation can itself be inconsistent: the measurement example uses
  `transpilation_kwargs`, while its signature accepts `compilation_kwargs`.
- Each search reloads/revalidates JSON and rebuilds ranking structures. There is
  no caching, incremental indexing, batching, or inference cancellation workflow.
- Metadata checks names and file integrity, not model digests or documentation
  revisions. Index/sidecar replacement is not transactional. See [index metadata](indexing.md#index-metadata).
- There is no conversation memory, streaming, authentication, rate limiting,
  production deployment procedure, or hosted-provider integration.

No automated answer-quality benchmark or model-comparison dataset is included.
