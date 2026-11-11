# Qrisp documentation chat

Browser assets for the backend's `/chat` API. No Qrisp source, templates, or built
documentation are bundled. The widget creates its own HTML.

Reference checkout: Qrisp commit `1289c180f67627cc727e0f282626fc91302f7dfb`
(declared version 0.9.9), Python 3.13, Sphinx `>=7,<9`, PyData Sphinx Theme 0.17.1.
Other revisions need verification. The installer checks the directory layout,
not the Git revision. Source links assume the standard Sphinx HTML layout and
the installed script location `_static/js/chat.js`.

## Install assets

From this backend repository, using Python 3.10+ (standard library only):

```bash
python frontend/install_assets.py /path/to/Qrisp --dry-run
python frontend/install_assets.py /path/to/Qrisp
```

The installer copies only its explicit asset list into
`documentation/source/_static/`, including vendor licenses/notices. It checks all
destinations first, skips identical files, and aborts if any differ. It rejects
symlink destinations and never edits `conf.py`. There is no overwrite/force mode.
An I/O failure during copying can leave new files partially installed; existing
files are never replaced. Inspect an error before retrying.

Manual alternative: copy the files under `frontend/_static/` to the matching
locations under `Qrisp/documentation/source/_static/`, retaining their relative
paths and license files. Check existing destinations first; do not replace
different files without reviewing them. The installer is recommended because it
performs these checks automatically.

## Register assets in Sphinx

Edit the target `documentation/source/conf.py` manually. Keep its existing theme,
extensions, templates, and asset registrations. Ensure `_static` is included in
`html_static_path` (already true at the reference revision).

Add this block **once, after existing CSS/JS configuration**. If the chat is
already registered, compare its entries instead of appending duplicates:

```python
import os

html_css_files = [*globals().get("html_css_files", []), "css/chat.css"]
html_js_files = [
    *globals().get("html_js_files", []),
    ("js/vendor/marked.umd.js", {"priority": 490}),
    ("js/vendor/purify.min.js", {"priority": 491}),
    (
        "js/chat.js",
        {
            "priority": 500,
            "data-qrisp-chat-api-url": os.getenv(
                "QRISP_CHAT_API_URL", "http://127.0.0.1:8000/chat"
            ),
        },
    ),
]
```

## Run and check

After registering the assets, follow [Run the API](../docs/setup.md#run-the-api)
and [Run the browser interface](../docs/setup.md#run-the-browser-interface).
The setup guide also covers [endpoint and CORS configuration](../docs/setup.md#browser-endpoint-configuration).

Ask a question and check loading, formatted answers, sources, and error/retry
behavior. Test source links from a nested page as well.

See [offline checks](../docs/development.md#offline-checks) for installer tests;
they require no Qrisp build, backend, or Ollama.

Vendor origins, checksums, and attribution are in
[`THIRD_PARTY_NOTICES.md`](_static/js/vendor/THIRD_PARTY_NOTICES.md). The included
license texts apply to those dependencies. The project's [MIT license](../LICENSE)
covers its original frontend code; it does not replace those dependency licenses.
