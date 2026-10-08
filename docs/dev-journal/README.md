# Dev journal

One entry per commit, written with the `learn-by-commit` skill
(`.claude/skills/learn-by-commit/SKILL.md`). Each entry explains the change, how it fits
`PLAN.md`, the commands used, verified reading, and a quiz.

Steps 1–7 of `PLAN.md` were built before the journal started and have no entries.

## Entries

<!-- - NNN · YYYY-MM-DD · [Title](NNN-slug.md): one-line hook -->
- 001 · 2026-10-05 · [Register user accounts with salted PBKDF2 hashes](001-register-user-accounts.md): store hashes, never passwords (salt, slow hash, constant-time check)
- 002 · 2026-10-05 · [Login, logout and access control](002-login-and-access-control.md): authentication vs authorisation, one login check in the dispatcher, per-connection sessions
- 003 · 2026-10-08 · [Encrypt client/server traffic with TLS](003-tls-encrypted-transport.md): TLS under NDJSON, pinned self-signed cert, fail closed, per-connection handshake with timeout
