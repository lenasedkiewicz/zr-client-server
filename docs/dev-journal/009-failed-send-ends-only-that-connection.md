---
id: 009
title: A failed send ends only that connection
commit: "fix: keep serving when sending a reply to a client fails"
step: 16 — address the 2026-10-21 mentoring code review (batch 1, task 1.1)
date: 2026-10-25
tags: [python, exceptions, socket, tcp, rst, so_linger, tls, unittest, threading, failure-isolation]
---

# A failed send ends only that connection

## What we did
The review found that one client could stop the whole server. `handle_client` protected
only the **read**. The reply was sent after the `try` statement, and the "Invalid JSON"
reply was sent *inside* the `except json.JSONDecodeError` handler, where the neighbouring
`except (ConnectionError, OSError)` couldn't reach it (concept 003). A client that hung up
abruptly made `sendall` raise `ConnectionResetError` (`WinError 10054` on Windows). The
exception left `handle_client`, passed through `serve_forever`, and its `finally` closed
the **listening** socket. Every later client got `ConnectionRefusedError`.

The fix (`server.py:142`) splits the loop into two narrow steps. Step 1 reads and decides
on a `response`. The `JSONDecodeError` handler only builds the error dict, and
`handle_request` runs in the `else:` branch. Step 2 sends the response in its own
`try ... except OSError` (`server.py:163`). A network error on either step returns from
`handle_client`, the `with` closes that connection, and `serve_forever` goes back to
`accept()`. `except OSError` replaces the redundant `(ConnectionError, OSError)` pair. It
also covers `ssl.SSLError`, which is a subclass of `OSError`.

`handle_request` is deliberately **outside** the network `try`. Inside it, an `OSError` from
saving `users.json` (disk full, no permission) would silently drop the client and look like
a network problem. A server-side failure should stay loud. Containing *that* one is a
separate decision, not part of this fix.

**The test took three tries** (`tests/test_server.py:330`). Version 1 sent 200 requests,
reset the connection and checked a new client. It failed only 1 run in 5: the server
usually finished all its sends before the RST arrived, so it noticed the reset during a
*read*, which was already protected. Version 2 sent 2000 requests and still failed only
6 runs in 10: Windows' loopback buffers can absorb all the replies. Version 3 **orders the
events**. It patches `server.send_message` with a wrapper that signals "request read" and
then waits on a `threading.Event` until the client has reset the connection. The send that
follows is a real socket send that fails for real. Result: 10/10 failures before the fix,
10/10 passes after it. The reset comes from `SO_LINGER` with a 0 s timeout, which makes
`close()` an *abortive* close: unsent data is dropped and an RST is sent instead of the
FIN handshake. On Windows the `linger` struct is two `u_short`s (on POSIX, two `int`s),
so the test packs `"HH"` or `"ii"` with `struct`.

## How it fits
- **Plan:** Step 16, batch 1, task 1.1, the first of the review's "fix before merge"
  items. Next: task 1.2 on the same branch (malformed input that crashes the server).
  Task 3.2 now has only the `client.py` exception pair left to clean up.
- **Practice:**
  - **Failure isolation.** An error caused by one client is handled at the level that owns
    that client (`handle_client`) and never reaches the loop shared by everyone. A peer
    reset is a normal event on a network, not a bug.
  - **Narrow `try` blocks.** Guard exactly the calls that can fail for the reason you're
    handling. Here, the `try` blocks cover only the network calls, not business logic.
  - **Deterministic concurrency tests.** If a test depends on which thread wins a race,
    don't add bigger bursts or sleeps. Control the order with synchronisation
    (`threading.Event`), and keep the real I/O you want to test.
  - **When you'd choose differently:** in a one-shot script a crash is the right outcome,
    so let the exception propagate. In a production server you'd also log the dropped
    connection (batch 3 adds `logging`).

## Commands used
- `git checkout master`, `git pull --ff-only`, `git checkout -b fix/server-survives-bad-client`: start the batch branch from an up-to-date master
- `python sibling.py` (scratch file): demo that a sibling `except` doesn't catch an exception raised in a handler
- `python -m unittest tests.test_server.ServerTest.test_client_reset_does_not_stop_server`: run only the new test
- `for i in $(seq 10); do python -m unittest … 2>&1 | grep -a -E "^(OK|FAILED)|^[A-Za-z]+Error" | tr '\n' ' '; echo; done`: run the test 10 times to measure flakiness, one summary line per run (`-a` because the Windows error text isn't UTF-8)
- `python -m unittest discover tests 2>&1 | grep -a -E "^Ran|^OK|^FAILED|^(ERROR|FAIL):"`: full suite (41 tests, OK, 1 skipped on Windows)
- `python - <<'EOF' … EOF`: scripted edits to `tests/test_server.py` and `docs/commands.md`
- `cat -A`, `file`, `git diff --stat`: check line endings after a scripted replace failed, and review the changes
- `grep -n`, `sed -n`: find line numbers and read parts of files
- `git add`, `git commit`: record the change

See [commands.md](../commands.md) (new in this entry: `grep -a`, `seq` / `$(…)` in a `for` loop, `tr`).

## Read more
- [The try statement](https://docs.python.org/3/reference/compound_stmts.html#the-try-statement): Python Language Reference · clauses are searched in turn; exceptions in `else` aren't handled by the preceding clauses
- [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy): Python docs · `BrokenPipeError` and `ConnectionResetError` are `ConnectionError`s, which are `OSError`s; see also [`ssl.SSLError`](https://docs.python.org/3/library/ssl.html#ssl.SSLError), "a subtype of OSError"
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/): freeCodeCamp · beginner-friendly tour of `try`/`except`/`else`/`finally`
- [Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html): Python docs · what a closed or dead peer looks like from `recv`/`send`
- [Graceful shutdown, linger options, and socket closure](https://learn.microsoft.com/en-us/windows/win32/winsock/graceful-shutdown-linger-options-and-socket-closure-2): Microsoft Learn · graceful vs abortive close; with the [`linger` struct](https://learn.microsoft.com/en-us/windows/win32/api/winsock/ns-winsock-linger) (two `u_short`s on Windows)
- [Event objects](https://docs.python.org/3/library/threading.html#event-objects): Python docs · `set()` / `wait(timeout)` and its `True`/`False` return value
- Concept note: [003 What an except clause catches](../concepts/003-except-clause-scope.md)

## Quiz

### Revise
1. Which calls in the old `handle_client` loop touched the network, and which were protected?
   <details><summary>Answer</summary>

   Three: `receive_message` (the read), the "Invalid JSON" `send_message`, and the normal-reply `send_message`. Only the read was in the `try` body. The first send was inside a handler, and the second was after the `try` statement.
   </details>
2. What does this print?
   ```python
   try:
       raise ValueError
   except ValueError:
       raise OSError
   except OSError:
       print("caught")
   ```
   a) `caught` · b) nothing, the `OSError` propagates (with the `ValueError` as context) · c) a `SyntaxError` · d) nothing, the `OSError` is silently dropped
   <details><summary>Answer</summary>

   b) Once the `ValueError` handler runs, the sibling clauses aren't searched. The `OSError` leaves the whole `try`, and the traceback shows "During handling of the above exception, another exception occurred".
   </details>
3. Why is `except (ConnectionError, OSError)` the same as `except OSError`? Does `except OSError` catch `ssl.SSLError`?
   <details><summary>Answer</summary>

   `ConnectionError` is a subclass of `OSError`, and a clause matches instances of subclasses, so listing both adds nothing. Yes: `ssl.SSLError` is also a subtype of `OSError`.
   </details>
4. Before the fix, why did the *next* client get `ConnectionRefusedError` rather than an error reply?
   <details><summary>Answer</summary>

   The `ConnectionResetError` escaped `handle_client` and `serve_forever`, whose `finally` closed the listening socket. With no socket listening on the port, the OS refuses new connections.
   </details>
5. What does `SO_LINGER` with `l_onoff=1, l_linger=0` change about `close()`?
   <details><summary>Answer</summary>

   It turns `close()` into an abortive close: unsent data is discarded and the connection is reset with an RST, instead of the graceful FIN exchange. The peer's next send or receive fails with "connection reset".
   </details>
6. Spot the problem: a test sends 200 requests, resets the connection and expects the server to crash on a send. It fails only sometimes. Why?
   <details><summary>Answer</summary>

   It's a race. If the server finishes writing all replies into the socket buffers before the RST arrives, it notices the reset during its next read, which was already protected, so the bug doesn't show. The fix is to control the order (an `Event` between "request read" and "send"), not to add bigger bursts or sleeps.
   </details>

### Defend the decision
1. Why not wrap the whole loop body, including `handle_request`, in one `try ... except OSError`?
   <details><summary>Model answer</summary>

   It would be shorter, but it would treat a server-side failure as a network one. `handle_request` can raise `OSError` when it saves `users.json`, and a broad `try` would quietly drop the client, hiding a real problem. Narrow `try` blocks around the network calls keep "the client went away" separate from "the server is broken". The trade-off is two small `try` blocks instead of one.
   </details>
2. Your test patches `server.send_message`. Doesn't that make it a mock test instead of a real reproduction?
   <details><summary>Model answer</summary>

   The patch only adds a pause. It calls the real `send_message`, which does a real TLS `sendall` on a real socket that was really reset with an RST. What it controls is the *order* of events, so the failing call is guaranteed to be the send. Without it the test reproduced the bug only 10–60% of the time, depending on socket buffer sizes. A flaky test is worse than none, because people learn to ignore it.
   </details>
3. Why does the server just return on a network error instead of trying to send the client an error message?
   <details><summary>Model answer</summary>

   An `OSError` on this socket means the connection is unusable: reset, broken pipe, or a TLS error. Nobody would read a reply, and sending one would raise again. The right response is to end the session cleanly: the `with` closes the socket, and the server moves on to the next client. Telling the *operator* (logging) is still useful, and batch 3 adds it.
   </details>
4. Why keep one client at a time instead of moving each client to its own thread, which would also stop one client's crash from killing the others?
   <details><summary>Model answer</summary>

   Threads would contain the damage to one thread, but the bug would still be there: an unhandled exception in a handler thread. They would also change the concurrency model, which the review plan puts out of scope (YAGNI). Fixing the error handling at the right level is needed with either model, and it's the smaller and safer change.
   </details>
