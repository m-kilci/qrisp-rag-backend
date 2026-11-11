# Setup and configuration

[Project overview](../README.md)

## Prerequisites and tested versions

The API needs Python, a reachable Ollama server, and a documentation index. A
Qrisp checkout with rendered reference HTML is needed to create that index. The
browser interface additionally requires a Qrisp documentation build containing
the chat assets.

| Component | Tested configuration | Requirement / scope |
| --- | --- | --- |
| Backend | Python 3.14 | Other Python versions have not been validated; no supported version range is declared in package metadata |
| Qrisp documentation | Qrisp 0.9.9 with Python 3.13 | That checkout declares Python `>=3.11, <3.14`; check its requirements when using another version |
| Inference | Ollama, `qwen3:30b`, `nomic-embed-text` | Both configured models must be available on the inference host |
| Browser libraries | Marked 18.1.2, DOMPurify 3.4.17 | Required by the separate chat frontend |

Use separate Python environments for the backend and Qrisp documentation. Qrisp
is not a backend runtime dependency. The commands below use POSIX shell syntax.
Ollama may run locally or on another reachable machine; model memory requirements
depend on the models and inference host.

`requirements.txt` pins the backend's direct and indirect dependencies to the
versions in the tested Python 3.14.10 Linux environment. Other Python versions
and operating systems have not been validated. These are version pins, not a
cross-platform lockfile with artifact hashes. Qrisp documentation dependencies,
Ollama models, and generated indexes are installed or prepared separately.

## Install the backend

From the repository root:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For a new installation without `.env`, copy the template:

```bash
cp .env.example .env
```

Retain an existing `.env`. Edit the file to match your inference host and model
names. Local configuration is excluded by `.gitignore`.

## Backend configuration

| Variable | Default / requirement | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | Required | Ollama HTTP origin, including port, for embeddings and chat |
| `OLLAMA_MODEL` | Required for `/chat` | Chat model available on that host |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Model for document and query vectors |
| `QRISP_DOCS_ROOT` | `~/projects/Qrisp/documentation/source` if unset or blank | Source input for indexing and related diagnostics |
| `CORS_ALLOW_ORIGINS` | `http://127.0.0.1:8001,http://localhost:8001` | Comma-separated browser origins allowed by the API |

Example for local Ollama:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:30b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
QRISP_DOCS_ROOT=/path/to/Qrisp/documentation/source
```

Existing shell variables take precedence over `.env`. Run backend commands from
the repository root: the store path is relative to the working directory.
`src/config.py` explicitly reads the backend-root `.env` for the documentation
path; other modules also use python-dotenv. Restart the backend after configuration
changes, since chat and embedding settings are read at module import time.

`QRISP_DOCS_ROOT` expands `~` and resolves relative paths against the working
directory. Rendered HTML is derived from this layout:

```text
Qrisp/documentation/
  source/                 <- QRISP_DOCS_ROOT
  build/html/reference/   <- rendered reference input
```

Changing the source path does not rebuild the index or change the browser site.

## Ollama host

Install Ollama on the machine that will host inference using the
[official installation instructions](https://docs.ollama.com/quickstart).
Start the Ollama app or service; if it is not already running, use `ollama serve`
in a separate terminal. On that machine, download the tested models and check
that they appear in the model list:

```bash
ollama pull qwen3:30b
ollama pull nomic-embed-text
ollama ls
```

`qwen3:30b` generates answers; `nomic-embed-text` generates document and query
embeddings. If both are already installed on your Ollama host, no download is
needed for a new backend checkout. These commands run outside the backend's
Python environment; see the [Ollama CLI reference](https://docs.ollama.com/cli).

For remote inference, set
`OLLAMA_BASE_URL` to that host's reachable address and ensure its listening
interface and firewall permit the backend's connection. Check connectivity using
the configured host:

```bash
curl http://YOUR_OLLAMA_HOST:11434/api/version
```

Both chat and embedding requests use this address. When moving Ollama, make both
models available on the new host and retain the embedding model and input
convention used by the index. Moving only Ollama does not change the browser API
URL or CORS. Separate inference hosts and non-Ollama providers are not supported.

## Prepare an index

The backend requires `data/embeddings.json`; startup does not generate it. Generated
indexes are not distributed with the repository. If you already have a
compatible file, retain it and its metadata sidecar if present. Indexes without
metadata remain usable with a provenance warning; see [legacy indexes](indexing.md#legacy-indexes).

To create an index, first build Qrisp's HTML references. For the tested Qrisp
version, prepare a separate environment:

```bash
cd /path/to/Qrisp
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[docs]" sphinx-autobuild
cd documentation
make html
```

Follow the Qrisp checkout's build prerequisites for system tools such as Pandoc.
Its `make docs-install` target includes an `apt` command and is not portable to
every operating system. Sphinx extensions and notebooks may require additional
dependencies in this environment; they do not belong in the backend environment.

Return to the backend repository and activate its environment:

```bash
deactivate
cd /path/to/qrisp-rag-backend
source .venv/bin/activate
```

Set `QRISP_DOCS_ROOT` in the backend `.env` to the Qrisp source directory, then run:

```bash
python -m src.index_docs
```

This performs real embedding inference and replaces the index and metadata after
generation. Retain copies of an existing file pair before rebuilding. See
[indexing](indexing.md) for the data format, validation, and replacement behavior.
Serving an existing index does not require source files on the API host.

## Run the API

From the backend root:

```bash
./start_server.sh
```

The script activates `.venv` and runs `uvicorn src.main:app --reload` on
`127.0.0.1:8000`. Keep the process running; stop it with Ctrl+C.

```bash
curl http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok"}`. This checks process liveness, not the index
or inference host. Use [POST /chat](api-and-frontend.md#post-chat) for a full request.
Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Browser interface availability

The API can be used independently. Browser assets, pinned libraries, and license
texts are included in this repository under `frontend/`; no separate frontend
download is needed. They run inside a separate Qrisp documentation checkout.
The upstream repository, its `conf.py`, and generated HTML are not bundled.

Follow [frontend installation](../frontend/README.md) for the compatible reference
revision, the non-overwriting installer, and the additive `conf.py` configuration.
The installer copies assets only; Sphinx registration remains manual. No runtime
CDN download or backend Python package is needed for Markdown rendering.

## Run the browser interface

With the backend running, open a second terminal in the Qrisp checkout containing
the frontend files:

```bash
cd /path/to/Qrisp
source .venv/bin/activate
cd documentation
sphinx-autobuild source build/html --open-browser --port 8001
```

Open <http://127.0.0.1:8001>. `make html` builds files once; `sphinx-autobuild`
also serves them and rebuilds on edits. Use HTTP rather than `file://` for chat.
Port 8001 avoids the API's default port 8000. The browser and backend must be on
the same machine for these loopback defaults to address the intended services.

## Browser endpoint configuration

`QRISP_CHAT_API_URL` is a **documentation-build** environment variable, defaulting
to `http://127.0.0.1:8000/chat`. Sphinx reads it in `conf.py` and supplies a script
attribute consumed by `chat.js`. It does not read the backend `.env`.

To change it, restart the docs builder with the desired value:

```bash
QRISP_CHAT_API_URL=http://YOUR_API_HOST:8000/chat sphinx-autobuild source build/html --open-browser --port 8001
```

Set the browser's exact docs origin in backend `CORS_ALLOW_ORIGINS` and restart
the backend when that changes. An origin consists of scheme, host, and port,
without a path; `localhost` and `127.0.0.1` are different origins. See
[CORS and deployment boundary](api-and-frontend.md#cors-and-deployment-boundary)
for the scope of this policy. No production deployment procedure is provided.

## Switch chat models

On the Ollama host, use `ollama ls` to list models or `ollama pull MODEL_NAME` to
download one, substituting its actual identifier. Set `OLLAMA_MODEL` in backend
`.env` to that name/tag, then restart the backend with `./start_server.sh`. Check
for overriding shell variables. A chat-only change requires neither reindexing
nor a documentation rebuild.

Send a question through [POST /chat](api-and-frontend.md#post-chat) or the browser
to check the model; `/health` does not test its availability. The backend uses
host/model defaults for context length, temperature, and output length, with a
300-second generation timeout. Model availability and memory requirements depend
on the inference host.

For embedding-model changes, follow [switch embedding models](indexing.md#switch-embedding-models);
matching vector dimensions alone is insufficient.
