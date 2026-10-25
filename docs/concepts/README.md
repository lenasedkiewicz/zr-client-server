# Concept notes

Answers to concept questions asked while building this project, saved as standalone notes
(numbered separately from the dev journal). Each note covers what the concept is, where it
appears in zr-client-server, alternatives and trade-offs, and a short interview answer.

## Notes

<!-- - NNN · YYYY-MM-DD · [Title](NNN-slug.md): one-line hook -->
- 001 · 2026-10-19 · [Semantic Versioning and pre-releases](001-semantic-versioning.md): what MAJOR.MINOR.PATCH and `-alpha` promise, and why we report 0.1.0-alpha
- 002 · 2026-10-20 · [Newline-delimited JSON vs alternatives](002-ndjson-vs-alternatives.md): why stdlib JSON over pickle/msgpack/protobuf, and a `\n` delimiter over a length prefix
- 003 · 2026-10-25 · [What an except clause catches](003-except-clause-scope.md): clauses guard only the try body; an error raised in a handler skips its siblings
