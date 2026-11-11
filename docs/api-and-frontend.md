# API and frontend

[Project overview](../README.md)

## HTTP contract

The API defaults to `http://127.0.0.1:8000`. FastAPI exposes an interactive
schema at `/docs`. The application has two custom routes in
[`src/main.py`](../src/main.py).

### GET /health

```json
{"status": "ok"}
```

This is process liveness only. It does not read the index, validate configuration,
or contact Ollama. A successful health check does not establish chat readiness.

### POST /chat

Request:

```json
{"message": "How do I apply a Hadamard gate in Qrisp? Show a short Python example."}
```

`message` is required and must be a nonblank string. Pydantic rejects invalid
types; its validator strips outer whitespace while keeping internal newlines and
indentation. Invalid requests return 422 before retrieval or model inference.

Successful response shape (answer and score are illustrative):

```json
{
  "answer": "Use `QuantumCircuit.h()` to apply the gate.",
  "sources": [
    {
      "source": "reference/Circuit Manipulation/generated/qrisp.QuantumCircuit.h.html",
      "score": 0.0243
    }
  ]
}
```

The answer is Markdown text, not HTML. Its formatting is preserved by the backend.
Each source is a selected context chunk's path and raw RRF score. Repeated page
paths can appear because multiple chunks belong to the same page. The API omits
chunk positions and individual semantic/BM25 scores. The
[retrieval diagnostic](development.md#inspect-real-retrieval) prints chunk
positions and RRF scores; individual ranking scores are returned by
`search_embeddings()`. Sources are not checked claim-by-claim citations, and
scores are not confidence percentages.

### Errors and timeouts

| Status | Current causes |
| --- | --- |
| 422 | Missing, non-string, empty, or whitespace-only message; other request parsing/validation failures |
| 500 | Missing chat configuration; missing, unreadable, empty, corrupt, or incompatible index/metadata; query/index dimension mismatch |
| 502 | Embedding connection/HTTP error or timeout; invalid embedding JSON/vector; chat connection/HTTP error; invalid chat JSON/content |
| 504 | Chat-generation request timeout |

Application errors use `{"detail": "Explanation..."}`. FastAPI validation errors
instead contain a list of error objects in `detail`. The frontend displays
string details; for non-string details it uses a generic HTTP-status message.

Embedding requests use a 60-second HTTPX timeout; generation requests use 300
seconds. These are HTTPX timeout settings, not a guaranteed total request budget.
The browser aborts after 390 seconds. Requests are not streamed, retried, or
cancelled server-side when the window is closed. Closing the chat hides it;
the pending operation can still finish. Client timeout/disconnection is not an
explicit mechanism to cancel the inference job on Ollama.

### Ollama interaction

`src/embeddings.py` sends `model` and string `input` to `/api/embed`. It requires
exactly one finite, nonzero numeric vector. Stored/query dimensions are checked
separately. The chat route sends `model`, one user message containing instructions,
documentation, and question, and `stream: false` to `/api/chat`. It requires a
nonempty `message.content` string in the JSON response.

Chat-model parameters such as context length, temperature, and output length are
not explicitly supplied by the backend; it relies on the host/model defaults.
Only the Ollama protocol is implemented; changing its base URL does not add
support for another provider.

## Frontend files

The installed integration uses these paths in the **separate Qrisp checkout**:

```text
documentation/source/conf.py
documentation/source/_static/js/chat.js
documentation/source/_static/css/chat.css
documentation/source/_static/js/vendor/marked.umd.js
documentation/source/_static/js/vendor/purify.min.js
```

The four static assets are bundled under `frontend/_static/`, together with vendor
licenses and attribution. No template override is needed: JavaScript creates the
widget. Follow [frontend installation](../frontend/README.md) to copy the assets
and configure `conf.py` manually. The browser libraries identify Marked 18.1.2
and DOMPurify 3.4.17 in their headers; preserve their license notices.
`conf.py` registers CSS and loads Marked at priority 490, DOMPurify at 491, and
`chat.js` at 500. No download is needed when those files are already included.

`conf.py` reads `QRISP_CHAT_API_URL` at documentation build time. It becomes the
script tag's `data-qrisp-chat-api-url`, read by `chat.js` on `DOMContentLoaded`.
There is also a loopback fallback in the script. Endpoint changes require a docs
rebuild; this setting is not read from the backend `.env` by Sphinx.

## Sending and displaying a message

`chat.js` constructs the floating button/window with DOM APIs on page load.
`sendMessage()` ignores blank input and blocks another send while one is pending.
It adds the user message, clears/disables input, adds a waiting message, and
performs `fetch(apiUrl)` with JSON and an `AbortController`.

On success it checks for answer text, renders the answer, and appends sources.
On failure it replaces the waiting message with an error. `finally` clears the
timer, removes the waiting style, re-enables controls, and scrolls to the latest
message. The page does not need refreshing to retry after a backend restart.

Messages are local DOM state. They are neither persisted nor submitted as a
conversation transcript. Navigating/reloading creates a new chat window and
welcome message. No server-side session or conversation memory exists.

## Markdown rendering

`addMessage()` uses `textContent` for user, waiting, and error messages.
`renderAnswer()` separately processes a successful assistant answer:

```text
Markdown string
  -> marked.parse()
  -> DOMPurify.sanitize()
  -> answer container innerHTML
  -> addSources() appends DOM-created links
```

Sanitizer settings use the HTML profile, forbid `img` and `style` tags, and forbid
inline `style` attributes. Rendering replaces the reply's children before sources
are appended, so the source list is not erased. CSS uses normal whitespace for
rendered Markdown and preserved whitespace/horizontal scrolling for code blocks.

Do not insert raw model HTML into `innerHTML`, or remove sanitization when
changing the parser. Sanitization concerns browser markup, not factual accuracy
or Python execution safety. Links inside model-generated Markdown are
distinct from the separately constructed Sources list and are not verified as
documentation citations. There is no syntax highlighter or code-copy button.

## Source URL construction

The frontend locates the loaded script URL ending in `/_static/js/chat.js` and
uses `new URL("../../", chatScript.src)` to derive the documentation root. This
avoids resolving sources against whichever nested page currently contains chat.
The script URL can include Sphinx's cache-busting query string.

`addSources()` deduplicates identical source strings, converts `.rst` and `.ipynb`
suffixes to `.html`, and resolves each candidate against that root:

| Indexed source | Rendered page path |
| --- | --- |
| `index.rst` | `index.html` |
| `general/tutorial/H2.ipynb` | `general/tutorial/H2.html` |
| `reference/Core/QuantumVariable.html` | unchanged |

Only `.html` candidates on the same origin and under the derived root pathname
are linked. URL construction encodes spaces, such as `Circuit Manipulation`.
Labels use the filename without extension, or the parent directory for `index`.
Links open a new tab with `noopener noreferrer`. Scores are not displayed.

The conversion assumes the normal Sphinx HTML layout, not a directory-HTML
builder or arbitrary renamed pages. Updating the index and site independently
can leave links pointing to outdated or
missing pages. Keep the built site and indexed documentation aligned.

## CORS and deployment boundary

Browser origin means scheme + host + port. Docs at port 8001 and the API at 8000
are different origins. The JSON POST triggers a preflight; FastAPI's
`CORSMiddleware` allows configured origins, POST, and the Content-Type header.
Both local hostnames on port 8001 are defaults. An unconfigured-origin preflight
is rejected; errors for allowed origins retain the response CORS header.

CORS is a browser communication policy, not authentication or protection against
non-browser clients. The current application has no authentication, rate limit,
or production deployment configuration. See [setup](setup.md#browser-endpoint-configuration)
for changing the frontend endpoint and allowed origins together.
