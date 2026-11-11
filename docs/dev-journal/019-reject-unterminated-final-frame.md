---
id: 019
title: Reject an unterminated final frame
commit: "fix: reject an unterminated final frame"
step: 16 — address the 2026-10-21 mentoring code review (batch 4, task 4.2)
date: 2026-11-11
tags: [python, protocol, framing, ndjson, eof, exceptions, logging, security, unittest]
---

# Reject an unterminated final frame

## What we did
The reviewer sent `{"command": "stop"}` **without** the final `\n` and closed the connection,
and the server stopped. `readline()` returns whatever it has when the stream ends, so a line
cut off by a close looked exactly like a complete one. The README promised that every message
ends with `\n`, but the code didn't check.

The rule is now **"no `\n`, no message"**. In `receive_message` (`protocol.py:58`), a line
that doesn't end with `b"\n"` raises `ConnectionClosed`, even if its bytes would parse.
`readline()` without a size stops only at `\n` or at end of stream, so a missing newline
always means the peer closed. That one check covers both a clean close (`b""`) and a close in
the middle of a message. `ConnectionClosed` now carries `discarded`, the size of the dropped
bytes (`protocol.py:30`), so the server can tell the two apart without a second exception
class.

The server (`server.py:162`) ends the session in both cases. Only for `discarded > 0` does it
call `reject_unterminated_message` (`server.py:186`), which does two things:
- **It logs a WARNING with the address and byte count, never the bytes.** A cut-off `login` or
  `register` carries a password, and OWASP lists passwords first among the things that don't
  belong in logs.
- **It tries one error reply.** A client that only half-closed (`shutdown(SHUT_WR)`) is still
  reading, and it learns why nothing happened. A client that fully closed is gone, so a failed
  send is *expected*. It's caught as `OSError` and logged at DEBUG, not as a second "Connection
  lost" warning. This was the owner's request ("handle reply using best coding practices"):
  make the reply best effort, contain the failure, and keep the noise down.

Tests: `tests/test_protocol.py:58-75` cover a clean close (`discarded == 0`), an unterminated
line, and a complete line followed by an unterminated one. `tests/test_server.py:175-196`
drive `handle_client` with fakes: the reply is sent, a failed reply still gives exactly one
warning, and a clean close logs nothing and sends nothing. The end-to-end test
`tests/test_server.py:493` sends `stop` without `\n` over TLS and closes. The server keeps
running, logs "unterminated", doesn't log `stop`, and serves the next client. Run against the
old code, that test failed as expected.

The decision itself (reject vs tolerate, with the specs) is concept 004.

## How it fits
- **Plan:** step 16, batch 4, task 4.2 (`docs/plans/001-code-review-2026-10-21.md`). This
  completes batch 4, so `fix/protocol-contract` is ready for a PR. It also prepares task 5.1:
  with `readline(limit)`, a line cut at the limit also lacks its `\n`, but the connection is
  still open. Then `endswith(b"\n")` needs a second branch ("too long"), and the comment at
  `protocol.py:59` must change with it.
- **Practice:**
  - **The newline as a commit marker.** A message counts only once the sender has said it's
    done, like a database transaction that isn't real until `COMMIT`.
  - **Strict receivers.** Postel's law ("be liberal in what you accept") invites flaws that
    become entrenched (RFC 9413). One strict rule now is cheaper than removing a tolerance
    later.
  - **Best-effort cleanup paths.** When the peer is probably gone, try once, catch the
    expected failure narrowly (`OSError`, not `Exception`), and log it at a level that matches
    how surprising it is.
  - **Never log secrets.** Log metadata (size, address), not payloads.
  - **When you'd choose differently:** a log or file reader, where the last line of a file
    still being written is often unterminated and losing it hurts. Tolerate there, and say so
    in the docs.

## Commands used
- `python -m unittest tests.test_protocol tests.test_server.DroppedClientLoggingTest`: run the
  new unit tests before the fix, to watch them fail (`TypeError: ConnectionClosed() takes no
  keyword arguments`, and `ConnectionClosed not raised`)
- `python -m unittest discover tests`: full suite after the fix, 78 tests OK, 1 skipped
- `git stash push protocol.py server.py -q`, then `python -m unittest
  tests.test_server.ServerTest.test_stop_without_final_newline_does_not_stop_the_server`, then
  `git stash pop -q`: run the end-to-end test against the old code only (it errored, so it
  really catches the bug), then bring the fix back; see
  [git stash](../commands.md#git-stash-put-changes-aside-for-a-moment)
- `git status --short`: check that the stash came back completely
- `grep -n ...`: find the line numbers referenced above

## Read more
- [NDJSON specification](https://github.com/ndjson/ndjson-spec) — GitHub · section 3.1: every JSON text "MUST be … followed by the newline character"
- [IOBase.readline](https://docs.python.org/3/library/io.html#io.IOBase.readline) — docs.python.org · why a line can come back without `\n`, and the `size` argument used next in task 5.1
- [socket.shutdown](https://docs.python.org/3/library/socket.html#socket.socket.shutdown) — docs.python.org · `SHUT_WR` closes only the sending half, the one case where our error reply arrives
- [RFC 9413: Maintaining Robust Protocols](https://www.rfc-editor.org/rfc/rfc9413.html) — RFC Editor · why tolerating faulty input entrenches it
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — OWASP · "Data to exclude": passwords first, so we log the byte count only
- [Error handling in Python](https://www.freecodecamp.org/news/error-handling-in-python-introduction/) — freeCodeCamp · beginner-friendly; its custom exception with an `__init__` and an attribute is the pattern `ConnectionClosed(discarded=...)` uses
- Concept [004](../concepts/004-unterminated-final-frame.md), rejecting vs tolerating, and concept [002](../concepts/002-ndjson-vs-alternatives.md), why we frame with `\n`

## Quiz

### Revise
1. What does `io.BytesIO(b'{"a": 1}').readline()` return, and what does `receive_message` do
   with it now?
   <details><summary>Answer</summary>

   `b'{"a": 1}'`, without a newline, because the stream ended first. `receive_message` sees
   that it doesn't end with `b"\n"` and raises `ConnectionClosed` with `discarded == 8`. It
   never calls `json.loads`.
   </details>

2. Why can one check, `line.endswith(b"\n")`, replace the old `if not line` check?
   <details><summary>Answer</summary>

   `b""` doesn't end with `b"\n"` either, so a clean close fails the same check, with
   `discarded == len(b"") == 0`. Without a size argument, `readline()` returns a line without
   `\n` only at end of stream.
   </details>

3. Which of these does the server log when a client closes mid-message?
   a) the address b) the byte count c) the bytes received d) the logged-in username
   <details><summary>Answer</summary>

   a and b. Never c: a cut-off `login` contains a password. d isn't logged here either; the
   warning is about the connection, not the account.
   </details>

4. Spot the bug:
   ```python
   try:
       send_message(conn, response)
   except Exception:
       pass
   ```
   <details><summary>Answer</summary>

   `except Exception` also swallows programming errors, for example a `TypeError` from a
   response that `json.dumps` can't serialise, and `pass` hides that anything happened. Catch
   only the expected failure (`OSError`, the client is gone) and log it, even if only at
   DEBUG.
   </details>

5. Why is the failed reply logged at DEBUG and not at WARNING?
   <details><summary>Answer</summary>

   It's expected: the client usually closed fully, so the send has nowhere to go. The
   noteworthy event, the dropped message, is already one WARNING. A second warning for the
   same incident would be noise that trains people to ignore warnings.
   </details>

### Defend the decision
1. "A complete JSON object arrived. Why not just run it?"
   <details><summary>Model answer</summary>

   Our protocol says a message ends with `\n`, and so does NDJSON ("MUST"). Running it anyway
   adds a second, hidden framing rule (EOF also ends a message). That rule would have to be
   documented, kept in every future reader such as the size limit in task 5.1, and kept for
   ever once a client relied on it (RFC 9413). It would also let a destructive command like
   `stop` run for a client that has already gone and can't see the reply. JSON Lines tolerates
   a missing final newline, which suits files. For a live command protocol, I'd rather have
   one strict rule.
   </details>

2. "Why an attribute on `ConnectionClosed` instead of a new `IncompleteMessage` exception?"
   <details><summary>Model answer</summary>

   Both cases mean the same thing to every caller: the peer closed and there are no more
   messages. The client and the session loop end the same way, so one `except` clause is
   right. Only logging and the reply differ, and an `if closed.discarded:` covers that. A
   subclass would also have worked (`except ConnectionClosed` still catches it), but after
   journal 017 removed redundant exception classes, I'd add one only if a caller needed to
   *catch* it separately. A different exception would be right for task 5.1's "line too
   long", where the connection is still open and must be closed by the server.
   </details>

3. "The reply rarely arrives over TLS. Why send it at all?"
   <details><summary>Model answer</summary>

   It costs one send in a path that's already ending, and it helps exactly the client that
   can use it: one that half-closed its writing side and is still reading. The cost is
   contained: the failure is expected, caught narrowly as `OSError`, logged at DEBUG, and the
   session ends either way, so it can't affect the next client. The alternative, a silent
   drop, is simpler, but gives a confused client nothing. The honest limit is that a fully
   closed client never sees it, which the README states.
   </details>
