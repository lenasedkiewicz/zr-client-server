---
id: 021
title: Drop clients that stay idle too long
commit: "fix: drop clients that stay idle too long"
step: 16 — address the 2026-10-21 mentoring code review (batch 5, task 5.2)
date: 2026-11-16
tags: [python, socket, timeout, tls, dos, slowloris, exceptions, unittest]
---

# Drop clients that stay idle too long

## What we did
After the TLS handshake, `tls_handshake` set the socket back to fully blocking with
`settimeout(None)`. The server serves one client at a time, so a client that connected,
logged in and then went quiet kept the only slot indefinitely, and the next client waited in
the `listen()` backlog. Now the handshake leaves the socket in **timeout mode** with
`CLIENT_IDLE_TIMEOUT` (`config.py:37`, 120 s), at `server.py:276`. Every later read or send
on that connection waits at most that long. The value is generous because a person at the
prompt reads and types slowly. Like `max_message_size`, it is a `Server` argument
(`server.py:64`), so a test can use half a second.

When the timeout fires, the read raises `TimeoutError` (`socket.timeout` has been an alias of
it since Python 3.10). `handle_client` catches it in its own clause at `server.py:184`, which
must come **before** `except OSError`. `TimeoutError` is a subclass of `OSError`, so in the
other order the timeout would be logged as "Connection lost" (see concept 003). The new
`drop_idle_client` (`server.py:238`) logs a warning with the address and the timeout and sends
a best-effort "Idle too long" error through the existing `send_last_error`. Then the session
ends. It never reads again. The `socket.makefile()` docs warn that the file's buffer "may end
up in an inconsistent state if a timeout occurs", and CPython enforces this: after a timeout,
`SocketIO.readinto` raises `OSError("cannot read from timed out object")`.

**Who actually sees the reply depends on the OS.** Our interactive client sends a command
first and reads after. When the user comes back and types, the server's socket is already
closed, so the server's OS answers the new data with a TCP reset (RST). A probe in the
scratchpad ran this 20 times on each side. On **Linux** (WSL, 3.12) the client read the
waiting "Idle too long" reply every time, because the queued data is delivered before the
reset error. On **Windows** (3.13) the read failed with `ConnectionAbortedError` every time,
because Windows drops the unread data when the reset arrives. `client.py` already catches
`OSError` and prints "Connection closed by the server", so a Windows user gets a clean exit,
but without the reason. A client that is *reading* when the timeout fires (the end-to-end test)
gets the reply on both. Making the client show the reason on Windows belongs to batch 7
(client error handling).

A send that times out (a client that stopped reading while its receive buffer is full) goes to
the existing `except OSError` around `send_message` and ends the session as a lost
connection. That's what it is in practice, so it gets no special case.

**Known gap, recorded rather than fixed:** the timeout limits *each read*, not a whole
message or session. A client that sends one byte just under every 120 s ("slowloris") keeps
its slot. Stopping that needs a deadline per message, which means our own `recv` loop instead
of `readline()` on `makefile()`. That's a protocol rewrite for a localhost server serving one
client at a time, so `PLAN.md` (step 4) and `README.md` say it plainly instead.

Tests:
- `tests/test_server.py:205-218` drive `handle_client` with fakes. A `TimeoutError` gives one
  warning, exactly one read (no second read from a timed-out stream) and one "Idle" reply.
  If that reply fails, there is still only one warning.
- `tests/test_server.py:415` runs end to end over TLS. It sets a 0.5 s timeout, then
  reconnects, because the timeout is applied during the handshake and the `setUp` connection
  already had its 120 s. After that it logs in and sends nothing. It then gets "Idle" and end
  of stream well before the client's own 5 s timeout, and a new client is served.

The first two failed on the old code, with the fix stashed. The end-to-end test hung until
the client socket's 5 s timeout, and the unit test saw no reply sent. The "gone client" test
passed on the old code too, because a timeout used to be logged once as "Connection lost". It
stays as a regression guard. All 92 tests pass on Python 3.10, 3.12 and 3.13 (1 skipped: the
owner-only file mode test, which runs only on Linux).

## How it fits
- **Plan:** step 16, batch 5, task 5.2, the last task on `fix/server-limits`. The batch now
  bounds input in both directions: too much (5.1, size) and too little (5.2, time). Next: open
  the batch 5 PR. Its merge is a release candidate (`0.1.2-alpha`) and is followed by the
  `trust-boundary-check` skill, which the plan schedules after batch 5. The client still waits
  indefinitely for a silent server. That's task 7.2.
- **Practice:**
  - **Bound every untrusted input:** size, time and type. A blocking call with no timeout means
    "the peer decides how long I wait", which isn't acceptable for a peer you don't control.
  - **Idle timeout vs deadline.** An idle timeout resets on every byte, so it catches a dead
    or forgetful client, not a malicious slow one. nginx's `client_body_timeout` works the same
    way ("between two successive read operations, not for the transmission of the whole
    request body"). Apache's `mod_reqtimeout` adds a minimum *rate* for that reason.
  - **After a timeout, end the stream.** A buffered reader that timed out mid-line can't tell
    you where the next message starts. It's the same principle as 5.1: once you lose
    framing, close.
  - **When you'd choose differently:** with `selectors` or asyncio, one idle client doesn't
    block the others, so an idle timeout is about reclaiming file descriptors and memory,
    usually via a timer per connection, not `settimeout`. Behind a reverse proxy, the proxy
    often enforces both timeouts and rates for you.

## Commands used
- `git switch fix/server-limits`: from the already-merged batch 4 branch back to batch 5
  (see [git checkout](../commands.md#git-checkout-switch-branches)).
- `git status -sb`, `git branch -a`, `git log --oneline -25`, `git log --oneline -3 master`,
  `git log --oneline master..fix/server-limits`: where each batch stands, and whether PR #7
  is on `master` (see [git log](../commands.md#git-log-list-commits)).
- `git merge-base --is-ancestor master fix/server-limits && echo "based on master"`: the batch
  5 branch already contains the merged batch 4.
- `git rev-parse fix/server-limits origin/fix/server-limits`: local and remote branch at the
  same commit (see [git rev-parse](../commands.md#git-rev-parse-turn-a-name-into-a-commit-hash)).
- `git show fix/server-limits:server.py | sed -n 161,256p`, `git show fix/server-limits:config.py`,
  `git show fix/server-limits --stat`, `git show ab438a5 -- README.md`: read the branch's code
  and what task 5.1 touched, before switching
  (see [git show](../commands.md#git-show-print-a-file-from-a-commit)).
- `grep -n "…" server.py tests/test_server.py PLAN.md`, `grep -n "…" -A8 tests/test_server.py`,
  `sed -n 309,358p docs/plans/001-code-review-2026-10-21.md`, `ls docs/concepts 2>/dev/null`:
  find the code, the task text and the docs to update
  (see [grep](../commands.md#grep-search-text), [sed -n](../commands.md#sed--n-print-selected-lines),
  [2>/dev/null](../commands.md#-file---redirect-stdin-read-the-exit-code)).
- `python -m unittest discover tests`: the full suite with the fix.
- `git stash push -- server.py config.py && python -m unittest tests.test_server.ServerTest.test_idle_client_is_dropped_and_the_next_one_served tests.test_server.DroppedClientLoggingTest.test_idle_client_gets_an_error_reply_and_ends_the_session … ; git stash pop`:
  the new tests against the old code, to watch them fail
  (see [git stash](../commands.md#git-stash-put-changes-aside-for-a-moment)).
- `python -c "import inspect, socket; print(inspect.getsource(socket.SocketIO.readinto))"`:
  confirm that CPython refuses to read from a stream after a timeout
  (see [python -c](../commands.md#python--c-run-a-one-line-program)).
- `py -0` and `for v in 3.10 3.12 3.13; do py -$v -m unittest discover tests; done`: the
  suite on each installed Python (see [py](../commands.md#py-the-windows-python-launcher)).
- `cat > "$SP/idle_probe.py" <<'EOF' … EOF`, then `python "$SP/idle_probe.py"`: a throwaway
  probe in the scratchpad that lets a client idle 20 times past a 0.3 s timeout and counts
  what its next command gets back. `sed -i` added a note of which call failed (send or read)
  (see [heredoc](../commands.md#heredoc-multi-line-input-to-a-command),
  [sed -i](../commands.md#sed--i-edit-a-file-in-place)).
- `cp "$SP/idle_probe.py" ./_idle_probe.py && timeout 120 wsl.exe -d Ubuntu -- bash -c 'rm -rf /tmp/zr && mkdir -p /tmp/zr && cp -r … /tmp/zr/ && cd /tmp/zr && python3 _idle_probe.py'; rm -f ./_idle_probe.py`:
  the same probe on Linux, in a throwaway copy under WSL's `/tmp`. ⚠️ `rm -rf` is safe here
  only because `/tmp/zr` is a copy this command made
  (see [wsl.exe](../commands.md#wslexe-run-a-command-in-a-linux-distribution),
  [timeout](../commands.md#timeout-stop-a-command-that-runs-too-long),
  [cp](../commands.md#cp-copy-files), [rm](../commands.md#rm-delete-files)).

## Read more
- [socket: Notes on socket timeouts](https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts)
  (Python docs): blocking, non-blocking and timeout mode. On the same page, `makefile()` warns
  about an inconsistent buffer after a timeout, and `socket.timeout` is listed as an alias of
  `TimeoutError` since 3.10.
- [Built-in exceptions: TimeoutError](https://docs.python.org/3/library/exceptions.html#TimeoutError)
  (Python docs): where `TimeoutError` sits under `OSError`, next to `ConnectionError`. That
  placement is why the clause order matters.
- [408 Request Timeout](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/408)
  (MDN): HTTP's version of "idle too long". The server closes an unused connection and should
  say so (`Connection: close`), as our final error reply does.
- [nginx: client_body_timeout](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_body_timeout)
  (nginx docs): a production idle timeout that, like ours, counts between two reads, not
  across the whole request.
- [What is Slowloris?](https://www.imperva.com/learn/ddos/slowloris/) (Imperva): how partial
  requests sent slowly fill a server's connection slots, and the mitigations (limits on
  connection time, per-IP limits, reverse proxies).
- [Beej's Guide, 7.1 Blocking](https://beej.us/guide/bgnet/html/split/slightly-advanced-techniques.html)
  (beej.us): what a blocked `recv()` does to a server, and the `poll()`/`select()` model that
  avoids it.
- Related notes: [concept 003: what an except clause catches](../concepts/003-except-clause-scope.md)
  (why `TimeoutError` needs its own clause first), and
  [journal 020: limit the size of one message](020-limit-message-size.md) (the other half of
  batch 5).

## Quiz

### Revise
1. What does each call put the socket into? (a) `settimeout(None)` (b) `settimeout(0)`
   (c) `settimeout(120.0)`
   <details><summary>Answer</summary>

   (a) blocking mode: wait as long as it takes. (b) non-blocking mode: fail immediately if the
   operation can't complete. (c) timeout mode: wait up to 120 s, then raise `TimeoutError`.
   Before this commit the server used (a) after the handshake.
   </details>
2. Spot the bug:
   ```python
   try:
       request = receive_message(conn_file)
   except OSError:
       logger.warning("Connection lost")
       return
   except TimeoutError:
       self.drop_idle_client(conn, addr)
       return
   ```
   <details><summary>Answer</summary>

   `TimeoutError` is a subclass of `OSError`, so the first clause catches every timeout, and
   the second clause can never run. An idle client is logged as a lost connection and never
   gets the "Idle too long" reply. The more specific clause must come first.
   </details>
3. On Python 3.10+, is `except socket.timeout:` different from `except TimeoutError:`?
   <details><summary>Answer</summary>

   No. Since 3.10, `socket.timeout` is a deprecated alias of `TimeoutError`, the same class.
   The code uses `TimeoutError` because it's the non-deprecated name, and `serve_forever`'s
   `socket.timeout` catches the same thing.
   </details>
4. The end-to-end test sets `self.server.idle_timeout = 0.5` and then reconnects before
   logging in. Why can't it skip the reconnect?
   <details><summary>Answer</summary>

   The timeout is applied to a connection once, in `tls_handshake`, right after the handshake.
   The connection from `setUp` was already accepted with the default 120 s, so changing the
   attribute afterwards doesn't affect it. Only a new connection picks up 0.5 s.
   </details>
5. After a read times out, why does `handle_client` return instead of trying to read the next
   message?
   <details><summary>Answer</summary>

   The `makefile()` reader may hold part of a line in its buffer, so it no longer knows where
   the next message starts. Python's docs warn it "may end up in an inconsistent state", and
   CPython's `SocketIO` raises `OSError("cannot read from timed out object")` on any later
   read anyway.
   </details>
6. Why doesn't a 120-second idle timeout stop a slowloris client?
   <details><summary>Answer</summary>

   The timeout measures the gap between reads, and each received byte starts a new read. A
   client that sends one byte every 119 s never trips it and can hold the single slot
   indefinitely. Only a total deadline per message or session (or a minimum rate) stops it.
   </details>

### Defend the decision
1. "Why did you only *record* the slowloris gap instead of fixing it?"
   <details><summary>Model answer</summary>

   A real fix is a deadline per message, which means replacing `readline()` on `makefile()`
   with our own `recv` loop that tracks a monotonic deadline and a buffer. That's a rewrite of
   the protocol layer we just stabilised in batches 4 and 5. The server listens on localhost
   and serves one client at a time by design, and the plan keeps that model (YAGNI). The idle
   timeout fixes the likely problem, a forgotten or crashed client, cheaply. The deliberate
   attack is written down in `PLAN.md` and `README.md` with what would fix it, so it's a known
   trade-off rather than a hidden one. If the server ever faced untrusted networks, I'd add the
   deadline, or better, put it behind a proxy that enforces rates.
   </details>
2. "Why `socket.settimeout` and not `select` or a thread per client?"
   <details><summary>Model answer</summary>

   With one client at a time, the only question is "how long do I wait for this one peer?",
   and `settimeout` answers it in one line using the standard library. `select`/`selectors`
   or threads solve a different problem: serving many clients at once. That would change the
   concurrency model, which the review explicitly left alone, and each model still needs a
   timeout per connection to free resources. In a multiplexed server I'd keep a last-activity
   time per connection and close the stale ones from the event loop instead.
   </details>
3. "Why is the timeout 120 seconds, and why is it a constructor argument?"
   <details><summary>Model answer</summary>

   The client is a person at a prompt, who reads `help` output and types a password slowly, so
   a few seconds (like the 5 s handshake timeout, which is machine-to-machine) would drop real
   users. 120 s is long for a person to be idle, yet it caps how long one forgotten client can
   block everyone. It lives in `config.py` as the single place to change it. The constructor
   argument is dependency injection, like `max_message_size` or `login_throttle`: tests pass
   0.5 s instead of patching a module constant or sleeping for two minutes.
   </details>
4. "The server sends an error before closing an idle connection. Isn't that pointless if the
   client isn't listening?"
   <details><summary>Model answer</summary>

   It's best effort, the same as for an over-long or unterminated message: a failed send costs
   one DEBUG line, not a second warning. It isn't pointless, though, and I measured it. A
   client that is reading when the timeout fires always gets it. Our interactive client sends
   first and reads after, so the server's reset races the reply. Linux delivers the queued
   reply first (20 of 20 runs), so the user sees "Idle too long" instead of a mystery
   disconnect. Windows drops it (20 of 20 runs), so the user sees "Connection closed by the
   server". The reply costs nothing and helps wherever it arrives, and HTTP does the same with
   `408` plus `Connection: close`. A client that wants the reason everywhere has to read while
   idle, which is a client change (batch 7), not a server one.
   </details>
