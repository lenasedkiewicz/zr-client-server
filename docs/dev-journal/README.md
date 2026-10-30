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
- 004 · 2026-10-14 · [Create the users file with owner-only permissions](004-owner-only-users-file.md): least privilege, mode set at creation (no chmod race), skip on Windows
- 005 · 2026-10-15 · [Lock out logins after repeated failures](005-login-lockout.md): online vs offline attacks, count per account, temporary lock, monotonic clock injected for tests
- 006 · 2026-10-16 · [Create an admin account on first start](006-admin-on-first-start.md): bootstrap trust out of band, safe default role, injected prompts
- 007 · 2026-10-19 · [Report an alpha SemVer version in info](007-alpha-version-in-info.md): 1.0.0 → 0.1.0-alpha, guarded by the official SemVer regex
- 008 · 2026-10-21 · [Merge master into feature/admin (merge vs rebase)](008-merge-master-into-feature.md): merge keeps pushed history, rebase rewrites it; IDs numbered on two branches collide in meaning, not in git
- 009 · 2026-10-25 · [A failed send ends only that connection](009-failed-send-ends-only-that-connection.md): narrow try blocks, a sibling except can't help, and a deterministic RST test with threading.Event
- 010 · 2026-10-26 · [Malformed input gets an error reply, never a crash](010-malformed-input-gets-an-error-reply.md): read bytes, decode per line, catch ValueError + RecursionError; a text stream loses the line after a decode error
- 011 · 2026-10-29 · [Wait for the server to listen before connecting](011-wait-for-the-server-to-listen.md): a threading.Event set after listen() replaces guessing; sync on a signal, not on time
- 012 · 2026-10-30 · [Register test cleanups with addCleanup](012-register-test-cleanups.md): register the undo right after the do; LIFO cleanups that run after a failed setUp and survive each other's errors
