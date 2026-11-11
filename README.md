# Qrisp documentation assistant

A retrieval-augmented assistant that answers Qrisp questions using its
documentation. A FastAPI backend retrieves relevant passages and requests an
answer from Ollama. The browser interface displays Markdown answers and links
to the documentation used as context.

## Installation

You need a backend Python environment, a reachable Ollama server with chat and
embedding models, and a compatible documentation index. Python 3.14 has been
tested for the backend. Follow [setup and configuration](docs/setup.md) for the
virtual environment, `.env`, models, and index preparation. Starting the server
does not create an index.

The API can be used directly. For the browser interface, install the bundled
[frontend assets](frontend/README.md) into a separate compatible Qrisp checkout.
The bundle includes a non-overwriting installer and manual Sphinx configuration.

## Usage

Run from the backend repository root:

```bash
./start_server.sh
```

Open <http://127.0.0.1:8000/docs> for the interactive API, or send a question:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How do I apply a Hadamard gate in Qrisp? Show a short Python example."}'
```

For the integrated chat, [run the Qrisp documentation preview](docs/setup.md#run-the-browser-interface)
on port 8001 while the backend runs on port 8000.

## Documentation

| Guide | Contents |
| --- | --- |
| [Setup and configuration](docs/setup.md) | Installation, tested versions, configuration, index preparation, and startup |
| [Architecture and request flow](docs/architecture.md) | Components, module responsibilities, retrieval, and context selection |
| [Indexing and stored data](docs/indexing.md) | Extraction, chunks, embeddings, record format, metadata, and rebuilds |
| [API and frontend](docs/api-and-frontend.md) | HTTP contract, browser behavior, Markdown rendering, source links, and CORS |
| [Testing and troubleshooting](docs/development.md) | Offline checks, retrieval diagnostics, and known limitations |

## Limitations

Answers can be incorrect despite relevant context. Source links identify supplied
passages, not verified citations for every claim. Questions are independent, and
generated examples are not executed. The application has no authentication,
streaming, or hosted-provider integration. See [known limitations](docs/development.md#known-limitations)
before extending or deploying it.

## License

Original application code and documentation are licensed under [MIT](LICENSE).
Bundled browser libraries have separate terms; see
[third-party notices](THIRD_PARTY_NOTICES.md). Generated indexes and local backups
are excluded from version control; create an index using the setup instructions.
