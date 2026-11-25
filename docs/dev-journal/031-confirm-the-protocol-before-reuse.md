---
id: 031
title: Confirm the protocol before reusing a server on the port
commit: "fix: confirm the protocol before reusing a server on the port"
step: 16 — address the 2026-10-21 mentoring code review (task 8.3)
date: 2026-11-24
tags: [python, socket, tls, ssl, health-check, enum, launcher, unittest, mock]
---

# Confirm the protocol before reusing a server on the port

## What we did
The launcher decided "a server is running" from one TCP connect. In 8.2's third real run, a
plain listener on port 65432 was "reused": the launcher started a client, which waited
10 s and then blamed a busy server. Each probe also showed up in our server's log as a
"TLS handshake failed" warning.

`probe_server()` (`run.py:38`) now does what the client does, in miniature: connect, a TLS
handshake that trusts only our certificate, then `help` (no login needed), with the reply
checked by the client's own `check_response`. Each step has a limit of `PROBE_TIMEOUT` (1 s,
`run.py:25`). It returns a `ServerState` (`run.py:29`):
- `FREE`: the connect was refused.
- `READY`: a valid `help` reply.
- `BUSY`: TCP connected, but the handshake timed out. Our server serves one client at a
  time and calls `accept()` only when it's free.
- `NOT_OURS`: no TLS, another certificate, a reset, or a reply that isn't our protocol.

The probe is used in three places:
- **`main()`** (`run.py:242`) reuses only `READY`. `NOT_OURS` and `BUSY` print what's going
  on and exit with `EXIT_LAUNCHER_FAILED` before anything starts.
- **`wait_for_server()`** (`run.py:72`) waits for `READY`, and stops at once on
  `NOT_OURS`: another program won the race for the port.
- **`wait_for_server_exit()`** waits until the server is no longer `READY`.

Two smaller parts of the finding are fixed too:
- **The window case:** after a start-up timeout with a server window, the launcher prints
  how to see the window's error. A console window closes when its program exits, and the
  error goes with it. It does **not** start a second server, because the first may just be
  slow.
- **The certificate:** `main()` checks for `BASE_DIR/server.crt` first (`run.py:246`).
  The client's `make_client_context()` defaults to `server.crt` *in the current folder*,
  and `run.py` can be started from anywhere, so the probe passes the full path.

`tests/test_run.py` grew to 29 tests:
- *Real sockets:* our real `Server` in a thread is `READY`, and is still `READY` for the
  next probe (the control question). A refused port is `FREE`. A listener that accepts and
  sends an HTTP error is `NOT_OURS`, the review's acceptance test. A listener that never
  calls `accept()` and our server holding another client are both `BUSY`. Our server
  probed with another certificate is `NOT_OURS`.
- *Mocks:* `main()` starts nothing for `NOT_OURS` or `BUSY`, the window timeout prints the
  hint and starts no second server, and a missing certificate stops before the probe.
- *A fake clock:* the wait loops without sleeping.

For the fail-first run, `probe_server` first kept the old TCP-only logic. 14 tests failed,
for example `READY != NOT_OURS` for the plain listener, and `READY != BUSY` for a server
holding another client.

Real runs, on a copy of the repo:
- *Background start:* exit 0, and the probes now log as INFO connect/disconnect pairs.
- *An accepting stranger on the port:* refused in 0.2 s with exit 2. Before this fix, the
  launcher reused it and the client waited 10 s.
- *Our server holding another client:* "busy", exit 2.

One run taught a limit. A listener that never accepts looks exactly like our busy server:
the OS completes the TCP connect from the backlog, and nobody answers. No probe can tell
them apart, so the `BUSY` message now says only what is known: "Something … accepted the
connection but did not answer within 1 s. If it is this server, it is busy…".

## How it fits
- **Plan:** Step 16, task 8.3 (`PLAN.md` Step 7; README launcher notes and exit code 2).
  This is the last task of batch 8. Next: the `pre-review` on `fix/launcher-cleanup`, then
  the PR.
- **Practice:**
  - *"Something answered" is not "our server answered"* (pre-review item B7). A TCP
    connect proves only that the OS queued the connection (journal 026). Knowing more takes
    a real exchange in the real protocol. That is a health check, like a `/health` endpoint
    behind a load balancer or `pg_isready` for PostgreSQL: "the process is running" and
    "it can serve" are different facts.
  - *Make the states explicit.* One boolean hid three different situations, each needing
    its own message and its own decision. An `Enum` names them, and `is` comparisons can't
    be broken by a typo the way string constants can.
  - *Say only what you know.* `BUSY` covers two cases that look the same from outside, so
    the message names both.
  - *Don't retry into a conflict.* Starting a second server after a timeout could fight a
    slow first one for the port.
  - *Reuse the client's code.* The probe imports `make_client_context`, `check_response`
    and the framing helpers, so "what our server looks like" is defined once.
  - *When you'd choose differently:* a dedicated `ping` command would be a cleaner probe
    than `help`, because it has no output to parse. That's a protocol change, so it's out
    of scope here. In production, an orchestrator such as Kubernetes runs the health
    checks, and the launcher wouldn't exist.

## Commands used
- `python -m unittest -v tests.test_run` — the fail-first run against the old TCP-only
  probe (14 failures), then 29 passing
- `python -m unittest tests.test_run 2>&1 | grep -a -E "^[A-Za-z]*Error:" | sort | uniq -c`
  — group the failures by reason
- `grep -n "server_is_running" run.py tests/*.py *.md docs/*.md .claude/skills/*/SKILL.md`
  — check that no caller of the old function is left
- `python -m unittest discover tests` — the full suite, OK with 1 skip
- `git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S"` — a scratch copy with a throwaway
  admin, for the real runs
- `timeout 60 python -c "import sys, run; run.start_server_in_window = lambda: False; sys.exit(run.main())" < /dev/null`
  — the real background start (exit 0), then `cat server.log` for the probe's log lines
- `timeout 60 python -c "import socket, subprocess, sys, threading, time; …"` — a listener on
  65432 that accepts and answers HTTP, then `run.py` under it: exit 2 after 0.2 s
- `(python server.py > server2.log 2>&1 < /dev/null &)` and a script holding one TLS
  connection open — our server busy with another client: `run.py` says busy, exit 2
- `netstat -ano | grep "127.0.0.1:65432" | grep LISTENING | awk '{print $NF}'`,
  `tasklist //FI "PID eq <pid>"`, ⚠️ `taskkill //PID <pid> //F` — find, check and stop the
  throwaway server
- `rm -rf "$S"` — delete the scratch copy

## Read more
- [Pattern: Health Check API](https://microservices.io/patterns/observability/health-check-api.html) — microservices.io · "a service instance can be incapable of handling requests yet still be running": why a probe must do real work, not only connect.
- [ssl.create_default_context](https://docs.python.org/3/library/ssl.html#ssl.create_default_context) — Python docs · `cafile` sets the CA certificates to trust: passing only our `server.crt` is what makes the probe "pinned", so another TLS server fails the handshake.
- [Transport Layer Security (TLS)](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security) — MDN · beginner-friendly: the handshake, and the server proving who it is with a certificate. That proof is what `NOT_OURS` relies on.
- [Enum HOWTO](https://docs.python.org/3/howto/enum.html) — Python docs · "a set of symbolic names bound to unique values", compared by identity (`is`), as `ServerState` is.
- Related: [journal 026](026-client-timeouts.md) (the `listen()` backlog: why a TCP connect succeeds while the server is busy), [journal 030](030-launcher-exit-codes.md) (`EXIT_LAUNCHER_FAILED`), [concept 005](../concepts/005-reviewing-a-python-server.md) (the trust-boundary questions behind B7).

## Quiz

### Revise
1. Our server is busy with client A. Client B connects. Why does B's TCP connect succeed,
   and what happens to its TLS handshake?
   <details><summary>Answer</summary>

   The OS completes the TCP handshake and puts B in the `listen()` backlog. That needs no
   `accept()`. The TLS handshake needs the server program, which calls `accept()` only
   after A leaves. So B's handshake waits, and the probe reports `BUSY` after its timeout.
   </details>

2. Multiple choice. A web server on the port accepts the probe's connection, reads the TLS
   ClientHello and answers `HTTP/1.1 400 Bad Request`. What does `probe_server` return?
   a) `FREE`
   b) `READY`
   c) `BUSY`
   d) `NOT_OURS`
   <details><summary>Answer</summary>

   d. `wrap_socket` raises an `ssl.SSLError`, because the reply isn't a TLS record. That's
   an `OSError`, caught after `TimeoutError`, so the answer is `NOT_OURS`. This is the
   review's acceptance test.
   </details>

3. Why is `except TimeoutError` placed before `except OSError` around `wrap_socket`?
   <details><summary>Answer</summary>

   `TimeoutError` is a subclass of `OSError`. Python takes the first matching clause, so
   with `OSError` first a timeout would become `NOT_OURS`, and a busy server would be
   reported as a stranger.
   </details>

4. Why does the probe build its context with `make_client_context(CERT_FILE)` instead of
   `make_client_context()`?
   <details><summary>Answer</summary>

   The default is `server.crt` relative to the *current folder*. `run.py` can be started
   from any folder, and then the default path wouldn't exist. `CERT_FILE` is
   `BASE_DIR/server.crt`, next to `run.py`. The client itself runs with `cwd=BASE_DIR`, so
   it is fine.
   </details>

5. A program listens on the port and never calls `accept()`. What does the probe report,
   and why can't it do better?
   <details><summary>Answer</summary>

   `BUSY`. From outside, it looks exactly like our busy server: the OS accepts the TCP
   connection and nobody answers the handshake. No probe can tell the two apart, so the
   message names both possibilities instead of guessing.
   </details>

### Defend the decision
1. "Why a full TLS handshake and a request? Isn't connecting to the port enough?"
   <details><summary>Model answer</summary>

   A connect only proves that *something* listens. We saw the cost: the launcher reused a
   stranger, and the client hung for 10 s with a wrong explanation. The handshake with our
   pinned certificate proves it's our server, because nobody else has the key. The `help`
   reply proves it speaks our protocol and is serving now. It costs one short connection,
   and that now logs as INFO instead of a warning. It's the health-check idea: the process
   being up isn't the same as it working.
   </details>

2. "Why not start a second server when the first one doesn't answer in time?"
   <details><summary>Model answer</summary>

   The review warned against it. The first server may just be slow, for example a cold start
   or a PBKDF2 setup. A second one would either fail to bind (journal 024 made the port
   exclusive) or, worse, race the first. The launcher can't know which, so it reports the
   timeout and tells the user how to see the window's error. A human decides.
   </details>

3. "Why use `help` as the probe and not add a `ping` command?"
   <details><summary>Model answer</summary>

   `help` already exists, needs no login and is cheap, so the probe needed no protocol
   change and no server change in a launcher commit. `ping` would be cleaner, with a fixed
   tiny reply and nothing to parse, and it would make the probe's intent visible in the
   server's command list. That's a reasonable follow-up, but it changes the protocol and
   the README's command table, so it's its own decision, not part of this fix.
   </details>
