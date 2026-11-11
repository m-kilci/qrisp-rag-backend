# Third-party material

The project's MIT license covers its original application code and documentation.
It does not relicense the external material described below.

## Locally generated Qrisp indexes

Generated indexes and backups are excluded from version control and are not part
of the public distribution. Follow [setup](docs/setup.md#prepare-an-index) to
create an index locally.

Indexes contain Qrisp documentation text as well as vectors. The application's
MIT license does not relicense that text. Qrisp's repository provides
[EPL 2.0](licenses/Qrisp-EPL-2.0.txt), while its
[documentation imprint](https://qrisp.eu/general/imprint.html) separately restricts
redistribution. Clarify the applicable terms with the Qrisp rights holders before
sharing a generated index.

## Browser libraries

The bundled Marked and DOMPurify builds retain their upstream licenses and
copyright headers. Versions, origins, checksums, and full license texts are
linked in the [browser dependency notices](frontend/_static/js/vendor/THIRD_PARTY_NOTICES.md).

Model weights are not included. Generating document or query embeddings requires
a separately available embedding model; this project's license does not cover
that model.
