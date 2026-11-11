document.addEventListener("DOMContentLoaded", () => {
  // Sphinx supplies this attribute from QRISP_CHAT_API_URL in conf.py.
  const apiUrl =
    document
      .querySelector("script[data-qrisp-chat-api-url]")
      ?.getAttribute("data-qrisp-chat-api-url") || "http://127.0.0.1:8000/chat";

  const chatScript = [...document.scripts].find((script) =>
    new URL(script.src, document.baseURI).pathname.endsWith(
      "/_static/js/chat.js",
    ),
  );

  const docsRoot = chatScript ? new URL("../../", chatScript.src) : null;

  let requestPending = false;

  // ------------------------------------------------------------
  // Floating chat button
  // ------------------------------------------------------------

  const chatButton = document.createElement("button");

  chatButton.id = "qrisp-chat-button";
  chatButton.innerHTML = "💬";
  chatButton.setAttribute("aria-label", "Open Qrisp Assistant");
  chatButton.title = "Qrisp Assistant";

  document.body.appendChild(chatButton);

  // ------------------------------------------------------------
  // Chat window
  // ------------------------------------------------------------

  const chatWindow = document.createElement("div");

  chatWindow.id = "qrisp-chat-window";

  chatWindow.innerHTML = `
        <div id="qrisp-chat-header">
            <span>Qrisp Assistant</span>

            <button
                id="qrisp-chat-close"
                aria-label="Close chat"
            >
                ×
            </button>
        </div>

        <div id="qrisp-chat-messages" role="log" aria-live="polite" aria-label="Chat messages"></div>

        <div id="qrisp-chat-input-area">

            <input
                id="qrisp-chat-input"
                type="text"
                placeholder="Ask about Qrisp..."
                aria-label="Chat message"
            />

            <button
                id="qrisp-chat-send"
                aria-label="Send message"
            >
                ➤
            </button>

        </div>
    `;

  document.body.appendChild(chatWindow);

  // ------------------------------------------------------------
  // Get references to UI elements
  // ------------------------------------------------------------

  const messages = document.getElementById("qrisp-chat-messages");

  const input = document.getElementById("qrisp-chat-input");

  const sendButton = document.getElementById("qrisp-chat-send");

  const closeButton = document.getElementById("qrisp-chat-close");

  // ------------------------------------------------------------
  // Welcome message
  // ------------------------------------------------------------

  addMessage(
    "Hello! I'm the Qrisp Assistant. Ask me something about the Qrisp documentation.",
    "assistant",
  );

  // ------------------------------------------------------------
  // Open / close chat
  // ------------------------------------------------------------

  chatButton.addEventListener("click", () => {
    openChat();
  });

  closeButton.addEventListener("click", () => {
    closeChat();
  });

  function openChat() {
    chatWindow.style.display = "flex";
    input.focus();
  }

  function closeChat() {
    chatWindow.style.display = "none";
  }

  // ------------------------------------------------------------
  // Sending messages
  // ------------------------------------------------------------

  sendButton.addEventListener("click", sendMessage);

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    const text = input.value.trim();

    // Don't send empty messages
    if (!text || requestPending) {
      return;
    }

    // Display user's message
    addMessage(text, "user");

    // Clear input
    input.value = "";

    requestPending = true;
    sendButton.disabled = true;
    input.disabled = true;
    const reply = addMessage(
      "Looking through the documentation. This may take a minute…",
      "assistant",
    );
    reply.classList.add("pending");
    const controller = new AbortController();
    // Allow for the backend's embedding and generation timeouts combined.
    const timeoutId = window.setTimeout(() => controller.abort(), 390000);

    try {
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error(
          "The assistant returned an unreadable response. Please try again.",
        );
      }
      if (!response.ok) {
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `The assistant request failed (HTTP ${response.status}). Please try again.`,
        );
      }
      if (typeof data?.answer !== "string" || !data.answer.trim()) {
        throw new Error(
          "The assistant returned an empty answer. Please try again.",
        );
      }
      // Keep model output as text rather than interpreting it as HTML.
      renderAnswer(reply, data.answer);
      addSources(reply, data.sources);
    } catch (error) {
      reply.classList.add("error");
      reply.textContent =
        error.name === "AbortError"
          ? "The assistant took too long to respond. Please try again."
          : error instanceof TypeError
            ? "Could not reach the assistant. Please try again."
            : error.message || "Something went wrong. Please try again.";
    } finally {
      window.clearTimeout(timeoutId);
      reply.classList.remove("pending");
      requestPending = false;
      sendButton.disabled = false;
      input.disabled = false;
      messages.scrollTop = messages.scrollHeight;
      if (chatWindow.style.display !== "none") {
        input.focus();
      }
    }
  }

  // ------------------------------------------------------------
  // Add a message to the chat
  // ------------------------------------------------------------

  function addMessage(text, sender) {
    const message = document.createElement("div");

    message.classList.add("qrisp-chat-message", sender);

    message.textContent = text;

    messages.appendChild(message);

    // Scroll to newest message
    messages.scrollTop = messages.scrollHeight;
    return message;
  }

  function addSources(message, sources) {
    if (!docsRoot || !Array.isArray(sources)) {
      return;
    }

    const paths = [
      ...new Set(
        sources
          .map((source) => source?.source)
          .filter((path) => typeof path === "string" && path.trim()),
      ),
    ];

    const links = [];

    for (const path of paths) {
      const htmlPath = path.replace(/\.(rst|ipynb)$/i, ".html");

      // Only accept documentation paths, not external URLs.
      if (!htmlPath.endsWith(".html")) {
        continue;
      }

      const url = new URL(htmlPath, docsRoot);

      if (
        url.origin !== docsRoot.origin ||
        !url.pathname.startsWith(docsRoot.pathname)
      ) {
        continue;
      }

      const link = document.createElement("a");
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      const filename = htmlPath
        .split("/")
        .pop()
        .replace(/\.html$/, "");
      link.textContent =
        filename === "index"
          ? htmlPath.split("/").slice(-2, -1)[0] || "Documentation"
          : filename;

      links.push(link);
    }

    if (!links.length) {
      return;
    }

    const container = document.createElement("div");
    container.className = "qrisp-chat-sources";

    const title = document.createElement("strong");
    title.textContent = "Sources";
    container.appendChild(title);

    const list = document.createElement("ul");

    for (const link of links) {
      const item = document.createElement("li");
      item.appendChild(link);
      list.appendChild(item);
    }

    container.appendChild(list);
    message.appendChild(container);
  }

  function renderAnswer(message, markdown) {
    const answer = document.createElement("div");
    answer.className = "qrisp-chat-answer";

    const html = marked.parse(markdown);

    answer.innerHTML = DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["img", "style"],
      FORBID_ATTR: ["style"],
    });

    message.replaceChildren(answer);
  }
});
