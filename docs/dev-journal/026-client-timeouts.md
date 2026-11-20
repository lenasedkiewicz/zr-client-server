---
id: 026
title: Time out and explain when the server does not answer
commit: "fix: time out and explain when the server does not answer"
step: 16 — address the 2026-10-21 mentoring code review (batch 7, task 7.2)
date: 2026-11-20
tags: [python, client, socket, tls, timeouts, backlog, exceptions, unittest, mock]
---

# Time out and explain when the server does not answer

## What we did
The client could wait for ever in three places. The one that really happened is the TLS
handshake. The server serves one client at a time, and while it is busy a second
client's TCP connect still succeeds, because the OS finishes the three-way handshake and
queues the connection in the `listen()` backlog. The TLS handshake that follows needs the
server *program*, which reads nothing until it calls `accept()`. So the second client sat
there with no message.

Each wait now has its own limit and its own message (constants in `config.py`):

| Wait | Constant | Value | On timeout |
|---|---|---|---|
| TCP connect | `CONNECT_TIMEOUT` | 5 s | `Cannot connect to 127.0.0.1:65432: timed out` (existing message) |
| TLS handshake | `HANDSHAKE_WAIT_TIMEOUT` | 10 s | `No answer from the server within 10 s - it may be busy with another client. Try again later.` |
| Each send and reply | `REPLY_TIMEOUT` | 10 s | `No reply from the server within 10 s - disconnecting` |

In `client.py`:
- **`connect`** passes `timeout=CONNECT_TIMEOUT` to `socket.create_connection`, then calls
  `raw_sock.settimeout(HANDSHAKE_WAIT_TIMEOUT)` *before* `wrap_socket`. The handshake runs
  inside `wrap_socket` (the socket is already connected and `do_handshake_on_connect` is on
  by default), and the `SSLSocket` takes its timeout from the raw socket. After the handshake
  the timeout becomes `REPLY_TIMEOUT`.
- **`except TimeoutError` comes before `except OSError`** in `connect` and in `run_session`.
  `TimeoutError` is a subclass of `OSError`, so in the other order the general clause would
  win. Before this commit a reply timeout would have printed "Connection closed by the
  server", which is wrong.
- After a reply timeout the client **disconnects and never reads again**. The `makefile()`
  buffer may be inconsistent after a timeout, and a late reply would be read as the answer to
  the *next* command. It's the same reasoning as the server's idle timeout (journal 021).
- The prompt is never timed out. `input()` doesn't touch the socket, and the timeout only
  limits socket calls.

The constants aren't called `CLIENT_...`, because `CLIENT_IDLE_TIMEOUT` already means the
opposite direction: how long the *server* waits for a client. The comment in `config.py`
says so.

**Tests.** `tests/test_client.py` adds three mock tests:
- each wait gets the right limit, and the handshake limit is set before `wrap_socket`;
- a handshake `TimeoutError` prints the "busy" message and closes the raw socket;
- a send or reply `TimeoutError` disconnects after one command.

`tests/test_server.py` adds one real end-to-end test,
`test_second_client_times_out_while_the_server_is_busy`. While the setUp client holds the
slot, `client.connect()` with a 0.2 s limit gives up with the busy message. When the first
client leaves, the server accepts the abandoned connection, logs a `WARNING` that the
handshake failed, and still serves the next client. A mock can't prove that `wrap_socket`
honours the raw socket's timeout. This test can. Against the old code the mock tests fail
(4 failures), and the end-to-end test hangs until `timeout` kills it, which is the bug itself.

## How it fits
- **Plan:** step 16, batch 7, task 7.2 of `docs/plans/001-code-review-2026-10-21.md`. It
  closes batch 7, so `pre-review` and the PR come next. Batch 8 (launcher) gains from it too:
  `run.py` starts this client, which can no longer hang silently against a busy server.
- **Practice:**
  - *Every blocking network call needs a deadline.* A peer that never answers is a failure
    like any other, and it is the hardest one to see, because nothing is printed.
  - *One timeout per phase.* Each wait has a different likely cause: an unreachable host,
    a busy server, a broken server. A single global timeout could only say "timed out".
  - *"Connected" from the OS is not "served".* `connect()` returns once the kernel has
    queued you. The application may not have looked at you yet.
  - *Choosing the values:* the AWS article suggests a high latency percentile (p99.9) of the
    real call. Here the slowest reply is `login`/`register` at about 0.5 s (PBKDF2), so 10 s
    leaves a wide margin and false timeouts are unlikely.
  - *When you'd do it differently:* a program talking to a service, with no person
    involved, would retry with capped exponential backoff and jitter, not print "try again
    later". A server that handles many clients at once (threads, `selectors`) would rarely
    leave anyone waiting in the backlog. The whole-session deadline (slowloris, journal 021)
    is still out of scope.

## Commands used
- `python -m unittest discover tests` — full suite before and after the change (108 tests, 1
  skipped on Windows)
- `git stash push -q client.py config.py` — put the fix aside to run the new tests against
  the old code
- `printf 'CONNECT_TIMEOUT = 5.0\n...' >> config.py` and `sed -i 's/^from config import .../'
  client.py` — give the old code the new constants, so the tests import and fail on
  behaviour rather than on an `ImportError`
- `timeout 120 python -m unittest tests.test_client tests.test_server.ServerTest.test_second_client_times_out_while_the_server_is_busy`
  — the old code hung in the end-to-end test until killed
- `timeout 60 python -m unittest tests.test_client 2>&1 | grep -E "^(FAIL|ERROR|Ran|OK|FAILED)"`
  — the mock tests alone against the old code: 4 failures
- `git checkout -q client.py config.py && git stash pop -q` — drop the temporary edit and
  bring the fix back (⚠️ the checkout throws away uncommitted changes, see
  [git checkout](../commands.md#git-checkout-switch-branches))
- `git status --short`, `git diff --stat`, `git diff client.py` — check the fix came back intact
- `grep -n` / `sed -n` over `client.py`, `config.py`, `tests/`, `README.md` and
  `docs/commands.md` — read the code and docs before editing

## Read more
- [TCP handshake](https://developer.mozilla.org/en-US/docs/Glossary/TCP_handshake) — MDN ·
  SYN, SYN-ACK, ACK: what the kernel finishes for you before `accept()`, and that the TLS
  handshake comes after it
- [Beej's Guide, 5.5 `listen()`](https://beej.us/guide/bgnet/html/split/system-calls-or-bust.html)
  — Beej's Guide to Network Programming · "`backlog` is the number of connections allowed on
  the incoming queue": where the second client waits
- [socket.create_connection](https://docs.python.org/3/library/socket.html#socket.create_connection)
  — Python docs · the `timeout` argument is set on the socket before connecting
- [Notes on socket timeouts](https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts)
  — Python docs · blocking, non-blocking and timeout modes; see also `makefile()`'s warning
  about an inconsistent buffer after a timeout
- [SSLContext.wrap_socket](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.wrap_socket)
  — Python docs · `do_handshake_on_connect`: why the handshake happens inside `wrap_socket`
  for an already-connected socket
- [Timeouts, retries, and backoff with jitter](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter)
  — AWS Builders' Library · set connection *and* request timeouts, choose them from
  latency percentiles, and retry with capped backoff and jitter

## Quiz

### Revise
1. A second client connects while the server is serving the first. Which of these
   finishes, and which waits? a) TCP connect b) TLS handshake c) both finish d) both wait
   <details><summary>Answer</summary>

   a) finishes and b) waits. The kernel completes the TCP handshake and queues the
   connection in the `listen()` backlog. The TLS handshake needs the server program to
   read, which it does only after `accept()`.
   </details>
2. Why does `client.py` catch `TimeoutError` *before* `OSError`?
   <details><summary>Answer</summary>

   `TimeoutError` is a subclass of `OSError`, and `except` clauses are tried in order. If
   `OSError` came first it would catch the timeout too, and print the wrong message
   ("Connection closed by the server" or "TLS handshake failed").
   </details>
3. What does `socket.create_connection((HOST, PORT), timeout=5.0)` limit, and what limits
   the handshake that follows?
   <details><summary>Answer</summary>

   The timeout is set on the socket before connecting, so it limits the connect and stays on
   the socket afterwards. The client then sets `HANDSHAKE_WAIT_TIMEOUT` on the raw socket.
   The `SSLSocket` from `wrap_socket` takes its timeout from the raw socket, so that value
   limits the handshake.
   </details>
4. Spot the bug:
   ```python
   sock = context.wrap_socket(raw_sock, server_hostname=HOST)
   raw_sock.settimeout(HANDSHAKE_WAIT_TIMEOUT)
   ```
   <details><summary>Answer</summary>

   The handshake already ran inside `wrap_socket`, so the limit comes too late, and the
   handshake used the connect timeout (or none). Setting a timeout on `raw_sock` after
   wrapping also doesn't change the `SSLSocket`. The timeout must be set before wrapping.
   </details>
5. The user leaves the client at the `> ` prompt for an hour. Does `REPLY_TIMEOUT`
   disconnect them?
   <details><summary>Answer</summary>

   No. A socket timeout limits only socket calls, and `input()` doesn't touch the socket. The
   *server's* `CLIENT_IDLE_TIMEOUT` (120 s) drops them, and the client finds out when it next
   sends something ("Connection closed by the server").
   </details>
6. Why does the client disconnect after a reply timeout instead of waiting a bit longer?
   <details><summary>Answer</summary>

   After a timeout the `makefile()` buffer may be inconsistent, so the docs advise against
   reading from it again. And if the late reply did arrive, it would be read as the answer to
   the next command, so the session would be shifted by one reply.
   </details>

### Defend the decision
1. "Why three separate timeouts instead of one `socket.setdefaulttimeout(10)`?"
   <details><summary>Model answer</summary>

   Each phase fails for a different reason and needs a different message. A connect timeout
   means an unreachable host, a handshake timeout here means "busy with another client", and
   a reply timeout means a broken server. They could also use different values. A global
   default would change every socket in the process, including any in imported code, and
   could only say "timed out". The price is three constants instead of one.
   </details>
2. "Your server serves one client at a time. Isn't a timeout just hiding that design flaw?"
   <details><summary>Model answer</summary>

   One client at a time is a deliberate simplification for this task (the review called it
   conscious, and changing it is out of scope, YAGNI). The timeout doesn't fix the queue. It
   turns a silent hang into a clear message, which every client needs anyway, because a
   server can also be overloaded, stuck or unreachable. With threads or `selectors` the busy
   case would become rare, but the connect and reply timeouts would stay.
   </details>
3. "Why print 'try again later' instead of retrying automatically?"
   <details><summary>Model answer</summary>

   A person is at the prompt, and they can decide better than a loop whether to wait. The
   other session could last up to the server's 120 s idle timeout, and silent retries would
   look like the hang we just removed. For a program calling a service, I'd retry a limited
   number of times with capped exponential backoff and jitter, in one layer only, as the AWS
   article recommends.
   </details>
4. "How do you know the handshake timeout works, if the unit tests mock the socket?"
   <details><summary>Model answer</summary>

   The mocks only check that the right values are passed in the right order. One end-to-end
   test in `tests/test_server.py` uses a real server and keeps it busy with one client. A
   second, real `client.connect()` with a 0.2 s limit must give up with the busy message.
   The test then checks the server logs the abandoned handshake as a warning and still
   serves the next client. Against the old code that test hangs, which is the bug.
   </details>
