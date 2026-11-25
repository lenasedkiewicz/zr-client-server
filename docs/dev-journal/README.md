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
- 013 · 2026-11-02 · [Unit-test request handling and the protocol without sockets](013-unit-tests-without-sockets.md): fix the upside-down test pyramid; BytesIO as a fake, Mock as a spy, end-to-end kept for wiring
- 014 · 2026-11-03 · [Make the SemVer check strict](014-strict-semver-check.md): `\d` is Unicode and `$` forgives a trailing newline in Python; re.ASCII + fullmatch, and watch the negative test fail first
- 015 · 2026-11-04 · [Run the tests on GitHub Actions](015-ci-on-github-actions.md): antivirus TLS interception caught by pinning; CI on clean Linux + Windows, matrix ends, SHA-pinned actions
- 016 · 2026-11-05 · [Log server events with logging instead of print](016-logging-instead-of-print.md): the entry point owns the configuration; NullHandler keeps imports quiet; a TLS 1.3 race that print had hidden
- 017 · 2026-11-06 · [Drop redundant exception classes and an unused constant](017-drop-redundant-exception-classes.md): a parent already matches its subclasses; keep the narrowest class that is still correct, and a subclass only in its own clause
- 018 · 2026-11-09 · [Tell a closed connection apart from a null message](018-closed-connection-vs-null-message.md): the semipredicate problem; end of stream raised out of band, so `null` is just data the server rejects
- 019 · 2026-11-11 · [Reject an unterminated final frame](019-reject-unterminated-final-frame.md): no `\n`, no message; log the size, never the bytes; a best-effort reply that fails quietly
- 020 · 2026-11-13 · [Limit the size of one message](020-limit-message-size.md): read one byte past the limit; on an over-long line reply and close, because the unread tail would be the next request
- 021 · 2026-11-16 · [Drop clients that stay idle too long](021-idle-timeout.md): a timeout on every read frees the single slot; TimeoutError before OSError; slowloris recorded as a known gap; Windows drops the last reply on reset
- 022 · 2026-11-17 · [Measure uptime with a monotonic clock](022-uptime-monotonic-clock.md): wall clock for "what time is it", monotonic for "how long"; an injected fake clock replaces a sleep in the test
- 023 · 2026-11-18 · [Give the server an explicit close and guard start-up](023-server-close-and-guarded-startup.md): a `finally` only covers its own `try`, so protection starts right after the acquire; the owner closes; test "closed", not "rebindable", on Windows
- 024 · 2026-11-19 · [Stop a second server binding the same port on Windows](024-exclusive-port-on-windows.md): `SO_REUSEADDR` means "restart past TIME_WAIT" on POSIX but "share a taken port" on Windows; reproduce first, then feature-detect `SO_EXCLUSIVEADDRUSE`
- 025 · 2026-11-19 · [Show clear client messages for network and reply errors](025-client-error-messages.md): list every failure, give each a message; validate replies at the trust boundary with `check_response`; catch specific exceptions, and Ctrl+C in one outer handler
- 026 · 2026-11-20 · [Time out and explain when the server does not answer](026-client-timeouts.md): the OS accepts into the backlog, the program may not; one timeout per phase, set before `wrap_socket`; TimeoutError before OSError
- 027 · 2026-11-21 · [Explain a taken port instead of a traceback](027-explain-a-taken-port.md): a fix can move the failure, not remove it; narrow `except` before broad; compare `errno`, not localised text; keep `__main__` thin so tests can call `main()`
- 028 · 2026-11-21 · [Always stop the background server the launcher started](028-always-stop-the-background-server.md): the `try` starts before the acquire; terminate, wait with a limit, then kill and wait; `sys.exit` is an exception a `finally` sees; own only what you started
- 029 · 2026-11-23 · [Exit non-zero when the client fails](029-client-exit-codes.md): a message is for people, the exit code for programs; 0 / 1 / 130 (128 + SIGINT); return the code from `main()`, exit in `__main__`; read the code before trusting the plan
- 030 · 2026-11-23 · [Exit with the client's exit code](030-launcher-exit-codes.md): a wrapper passes the child's code on and keeps its own (2) for its own failures; on Ctrl+C wait, don't kill; -N becomes 128 + N
- 031 · 2026-11-24 · [Confirm the protocol before reusing a server on the port](031-confirm-the-protocol-before-reuse.md): a TCP connect is not "our server answered"; probe with a pinned TLS handshake and `help`; FREE / READY / BUSY / NOT_OURS; say only what you know
- 032 · 2026-11-24 · [Cover off-protocol replies in the launcher's probe](032-probe-reply-tests.md): every `except` branch is a behaviour; a fake TLS peer with the test key; prove the tests with hand mutations, and check each mutation changed the file
- 033 · 2026-11-24 · [Explain an unusable TLS certificate instead of a traceback](033-unusable-certificate.md): load it, don't check it (EAFP, TOCTOU); `ssl.SSLError` is an `OSError`, so a broad bind clause called it "Could not listen"; narrow clauses first
- 034 · 2026-11-25 · [Explain a certificate that can't be read](034-unreadable-certificate.md): `PermissionError` is a third `OSError` from loading; one `try` per step whose errors mean different things, so the bind clause can't catch it; mock what differs between systems
