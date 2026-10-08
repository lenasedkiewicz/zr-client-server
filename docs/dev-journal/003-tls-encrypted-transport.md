---
id: 003
title: Encrypt client/server traffic with TLS
commit: "feat: encrypt client/server traffic with TLS"
step: 10 — encrypted transport (TLS)
date: 2026-10-08
tags: [python, ssl, tls, certificates, pinning, security, defence-in-depth, fail-closed, unittest, openssl]
---

# Encrypt client/server traffic with TLS

## What we did
Every connection is now wrapped in TLS with the stdlib `ssl` module. Before this, a `login`
sent `{"password": "..."}` across the socket as plain text, which was the known limitation
from step 8. The server builds its TLS context once (`server.py:36`): TLS 1.2 is the
minimum (`server.py:39`), and the certificate chain comes from `server.crt`/`server.key`.
The context is built *before* the socket is bound (`server.py:49`), so a missing
certificate never leaves a port open. If the files are missing, `__main__` prints the
`openssl` command and exits with status 1 (`server.py:195`): the server **fails closed** and
never falls back to plain text.

The server wraps each *accepted* connection, not the listening socket
(`server.py:149`). The handshake runs under a 5-second timeout (`server.py:155`), and the
socket goes back to blocking for the request loop (`server.py:162`). A failed or silent
handshake prints one line, and the server returns to `accept()`. `run.py`'s plain-TCP
readiness probe shows up as exactly such a line. The client trusts only our own certificate
(`client.py:36`, `cafile=server.crt`), which is a simple form of **pinning**. It keeps
certificate *and* hostname verification on (`server_hostname=HOST`, `client.py:53`). The
NDJSON framing in `protocol.py` is unchanged, because `makefile`/`sendall` work the same on
an `SSLSocket`.

Tests run over TLS with a committed test-only pair in `tests/certs/` (PLAN option a). Three
new tests cover the failure paths: a plain-TCP client gets no JSON and the server keeps
serving (`tests/test_server.py:228`), a client that trusts a different certificate gets
`SSLCertVerificationError` (`:241`), and a silent client is dropped after the handshake
timeout, which the test shortens with `mock.patch` (`:249`).

## How it fits
- **Plan:** delivers Step 10 and closes the "plain-text password" limitation from Step 8.
  Next: rate limiting or lockout after failed logins, and `users.json` permissions.
- **Practice:**
  - **Defence in depth.** Passwords are salted PBKDF2 hashes at rest (001), and now they
    are encrypted in transit too. Each layer covers a different attacker: someone who
    steals the file versus someone who sniffs the network.
  - **Fail closed.** If security setup fails, refuse to run; a silent downgrade to plain
    text is worse than an outage, because nobody notices it.
  - **Layering.** TLS sits under the application protocol, so `protocol.py` didn't change.
    This is the same idea as HTTPS, which is plain HTTP inside TLS.
  - **Isolate failures.** Wrapping per accepted connection and timing out the handshake
    means one bad client can't take down or freeze a single-threaded server.
  - **When you'd choose differently:** a public service uses a certificate from a CA such as
    Let's Encrypt, and clients use the system trust store, not a pinned file. Production
    apps often terminate TLS at a reverse proxy (nginx, a load balancer) instead of in the
    app. OWASP warns that pinning in apps you can't update easily causes outages when
    certificates rotate. It suits this project only because client and server ship
    together.
  - **Gotcha hit while building:** an edit script written as `python - <<'EOF'` turned `\\n`
    into a real line break, and then a Windows path with `\U` broke a non-raw string. The
    fix was a script file with raw strings; see
    [python -](../commands.md#python--run-a-script-from-stdin).

## Commands used
- `which openssl`: check that OpenSSL is available in Git Bash
- `mkdir -p tests/certs`: create the test-certificate folder
- `MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -keyout test-server.key -out test-server.crt -days 36500 -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"`: create the test pair (and `other.crt`, then `rm other.key`)
- `MSYS_NO_PATHCONV=1 openssl req … -keyout server.key -out server.crt -days 365 …`: create the real, git-ignored pair for the manual run
- `sed -n 1,80p tests/test_server.py`, `grep -n`, `grep -c`, `cat -A | cut -c1-140`: read code and debug a text match
- `cat >> config.py <<'EOF'`, `cat >> .gitignore <<'EOF'`: append settings
- `python - <<'EOF'`, `python <scratch>/edit_commands.py`: scripted edits
- `sed -i 's/…/…/' client.py README.md PLAN.md`: one-line edits
- `python -m unittest discover tests` and `… -v | grep -E …`: run the suite (24 tests, OK)
- `python server.py` / `python client.py` without certificates: check fail-closed exits
- `(python -u server.py > "$TEMP/srv.log" 2>&1 &)`, a `for` retry loop, `printf 'help\n' | python client.py`, `sleep 1`: end-to-end smoke run over real TLS (negotiated TLS 1.3)
- `python -c "…"`: remove the smoke-test account from `users.json`

## Read more
- [ssl — TLS/SSL wrapper for socket objects](https://docs.python.org/3/library/ssl.html) — Python docs · `SSLContext`, `wrap_socket(server_side=True)`, `create_default_context(cafile=…)`; read "Security considerations"
- [Transport Layer Security (TLS)](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) — MDN · beginner overview: what the handshake agrees on, why TLS 1.0/1.1 are retired, what a certificate binds
- [Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html) — OWASP · prefer TLS 1.3, allow 1.2, disable 1.0/1.1; backs our `minimum_version`
- [Pinning Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html) — OWASP · what pinning is, and why "the risk of outages almost always outweighs" its benefit for most apps
- [Register user accounts with salted PBKDF2 hashes](001-register-user-accounts.md) — dev journal 001 · the at-rest half of defence in depth

## Quiz

### Revise
1. What does TLS give you that plain TCP doesn't? (a) reliable delivery (b) message framing (c) confidentiality, integrity and server authentication (d) compression
   <details><summary>Answer</summary>

   (c). TCP already gives reliable, ordered delivery. TLS adds encryption (confidentiality), tamper detection (integrity) and proof of the server's identity via its certificate. Framing is still our NDJSON's job.
   </details>
2. Why did `protocol.py` need no changes?
   <details><summary>Answer</summary>

   TLS is a layer beneath the application protocol. An `SSLSocket` offers the same `sendall`/`recv`/`makefile` interface as a plain socket, so the newline-delimited JSON code works unchanged on top of it.
   </details>
3. Spot the bug: `ssl.create_default_context(cafile="server.crt").wrap_socket(sock, server_hostname="example.com")` while connecting to `127.0.0.1`.
   <details><summary>Answer</summary>

   Hostname verification fails: the certificate's subjectAltName lists `127.0.0.1` and `localhost`, not `example.com`. `server_hostname` must match a name in the certificate, which is why we pass `HOST`.
   </details>
4. What is `-nodes` in the `openssl req` command for, and what does it imply?
   <details><summary>Answer</summary>

   It stores the private key unencrypted ("no DES"), so the server can start without a passphrase prompt. The key file itself must then be protected, which is why `/server.key` is git-ignored.
   </details>
5. Why does the server call `settimeout(TLS_HANDSHAKE_TIMEOUT)` before the handshake and `settimeout(None)` after it?
   <details><summary>Answer</summary>

   The server handles one client at a time, so a client that connects and never sends a ClientHello would block `accept()` forever. The timeout bounds that wait. After a successful handshake, the socket goes back to blocking, so an idle logged-in user isn't disconnected.
   </details>
6. What does the leading `/` in the `.gitignore` line `/server.key` change?
   <details><summary>Answer</summary>

   It anchors the pattern to the repository root. `server.key` without it would match a file of that name in any folder, so a test key called `tests/certs/server.key` would silently never be committed. With `/`, only the real key in the root is ignored.
   </details>

### Defend the decision
1. "You committed a private key to the repo. Isn't that a security bug?"
   <details><summary>Model answer</summary>

   It's a test-only key that protects nothing: it's labelled as such, its README says so, and the real `server.key` is git-ignored. CPython's own test suite does the same. The alternative was generating certificates in `setUpClass` with `openssl`, but then the TLS tests would silently skip in a PowerShell without `openssl` on PATH. I chose deterministic tests that always run, and accepted that secret scanners will flag the file.
   </details>
2. "Why wrap each accepted connection instead of wrapping the listening socket once?"
   <details><summary>Model answer</summary>

   If you wrap the listening socket, the handshake happens inside `accept()`, so one bad client (plain TCP, wrong certificate) raises from `accept()` and can break the loop. Wrapping after `accept()` keeps each failure local: catch `SSLError`/`OSError`, log one line, accept the next client. It also gives a natural place for the handshake timeout. The cost is a few more lines of code.
   </details>
3. "Why pin a self-signed certificate rather than use a real CA certificate?"
   <details><summary>Model answer</summary>

   There is one known server on `127.0.0.1`, and the client ships with it, so we can distribute the certificate out of band. Pinning then trusts *only* that certificate, which is stricter than trusting every public CA. For a public service, I'd use a CA-issued certificate (Let's Encrypt) and the system trust store. OWASP advises against pinning when you can't update clients together with certificate rotation.
   </details>
4. "If TLS setup fails, why not just log a warning and run unencrypted?"
   <details><summary>Model answer</summary>

   That's failing open: the system looks fine while passwords cross the network in clear text, and nobody notices. Failing closed turns a silent security hole into a loud, easy-to-fix error. Here, the error message even prints the exact `openssl` command.
   </details>
