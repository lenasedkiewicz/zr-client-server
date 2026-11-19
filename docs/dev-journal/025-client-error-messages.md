---
id: 025
title: Show clear client messages for network and reply errors
commit: "fix: show clear client messages for network and reply errors"
step: 16 — address the 2026-10-21 mentoring code review (batch 7, task 7.1)
date: 2026-11-19
tags: [python, client, exceptions, input-validation, trust-boundary, unittest, mock]
---

# Show clear client messages for network and reply errors

## What we did
The client handled a refused connection, a rejected certificate, a failed handshake and
a closed connection. Everything else ended in a traceback. We listed every way a connection,
a read and a decode can fail, and gave each one a message:

| Failure | Before | Now |
|---|---|---|
| Connect timeout, unreachable host, unknown host name | traceback | `Cannot connect to 127.0.0.1:65432: <reason>` |
| Ctrl+C during the handshake or while waiting for a reply | traceback | `Interrupted` |
| Reply longer than 64 KiB | traceback | `Reply from the server is too long - disconnecting` |
| Bad UTF-8 or JSON, huge int, deep nesting | traceback | `Unexpected reply from the server: <reason> - disconnecting` |
| Reply not an object, no valid `status`, login without `data.username` | `AttributeError` / `KeyError` | same "Unexpected reply" message |

In `client.py`:
- **`check_response`** raises `ValueError` unless the reply has the shape the client reads:
  an object whose `status` is `"ok"` or `"error"`, and for a successful `login` a string
  `data.username`. Because it raises `ValueError`, a wrong shape and malformed JSON
  (`JSONDecodeError` and `UnicodeDecodeError` are `ValueError`s too) share one `except`
  and one message.
- **`connect`** holds the connect and handshake steps. A new generic `except OSError`
  comes after the specific `ConnectionRefusedError`, so the "is the server running?" hint
  stays. `socket.gaierror` and `TimeoutError` are `OSError` subclasses.
- **`main`** wraps connecting and the session in one `except KeyboardInterrupt`. Ctrl+C at
  the prompt was already handled; this covers the other places it can land. The most
  likely one is the handshake, which hangs while the server is busy with another client.
- **`run_session`** is the old loop, unchanged apart from the new `except` clauses. After a
  too-long or unexpected reply it disconnects. A too-long reply leaves the rest of its
  line unread, which would parse as the next reply. An unexpected reply means the server
  is broken or isn't ours, so the session state (who is logged in) can't be trusted.

`tests/test_client.py` is new. `unittest.mock` replaces the TLS context,
`socket.create_connection`, `send_message`, `receive_message` and `input`, so each failure
happens on demand without a server. `contextlib.redirect_stdout` captures what the user
sees. Each test checks the message, that `main()` returned instead of raising, and for
session errors that the client didn't ask for another command and closed the socket.
Against the old `client.py` every new test fails with the original errors (for example
`AttributeError: 'list' object has no attribute 'get'`). The Ctrl+C tests even abort the
whole run, because the mocked `KeyboardInterrupt` escapes.

## How it fits
- **Plan:** task 7.1 of batch 7 (Step 16), on branch `fix/client-errors`. Task 7.2 adds
  connect, handshake and reply timeouts. They will raise `TimeoutError`, which today gets
  the generic "Cannot connect" or "Connection closed" message, so 7.2 will give it its own
  "the server may be busy" message. `PLAN.md` step 5 and the README's "Manual start" now
  describe this behaviour.
- **Practice:**
  - *Validate at the trust boundary, in both directions.* The server checks every request
    because the client is outside its control. To the client, the server is just as
    outside, and an attacker can listen on the port. Checking the shape once, where
    the data enters (`check_response`), lets the rest of the code use
    `response["data"]["username"]` without defensive checks everywhere. It checks only
    what the client reads (an allow-list of the fields it needs), not every field of every
    reply. YAGNI.
  - *Catch specific exceptions, not `except Exception`.* A blanket handler would turn real
    bugs in the client into a polite one-liner that hides the cause. Each `except` here
    names a failure we listed, and anything we didn't foresee still shows its traceback.
  - *Messages for users, tracebacks for developers.* The user can act on "is the server
    running?". A stack trace only helps the person debugging the code. In a library you'd
    raise instead and let the caller decide.
  - *Trade-off:* disconnecting after one bad reply is strict. A forgiving client could
    print the error and keep the prompt. We chose strict because a server sending broken
    replies is a bug or an impostor, and continuing could act on wrong state.

## Commands used
- `git fetch -q`: update `origin/master` before branching.
- `git checkout -q -b fix/client-errors origin/master`: the batch 7 branch, from the
  current `master`.
- `sed -n '/^## Batch 7/,/^## Batch 8/p' docs/plans/001-code-review-2026-10-21.md`: print
  the batch 7 part of the fix plan.
- `cat -n client.py`: read the client with line numbers to list every failure point.
- `grep -n -i -E "..." README.md`: find README lines about client behaviour to update.
- `python -m unittest tests.test_client -v`: run the new tests.
- `git stash push -q client.py` … `git stash pop -q`: put the old `client.py` back for a
  moment to prove the tests fail without the fix.
- `git diff --stat HEAD -- client.py`: check the stash really reverted the file.
- `python -m unittest -k CheckResponse -k refused ... tests.test_client 2>&1 | grep -E ... | sort | uniq -c`:
  run every new test except the Ctrl+C ones against the old code and count the error
  types.
- `python -I - <<'EOF' … EOF`: a scripted edit of `docs/commands.md`. Its exact-text match
  failed, most likely on the file's Windows line endings, so the change was made in the
  editor instead. `cat -A` shows such `\r` characters.
- `python -m unittest discover tests`: the full suite (104 tests, 1 skipped).

## Read more
- [Where to patch](https://docs.python.org/3/library/unittest.mock.html#where-to-patch) — Python docs · "patch where an object is *looked up*": why the tests patch `client.receive_message`, not `protocol.receive_message`.
- [Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) — OWASP · validate syntax *and* semantics, allow-list what you accept, and check data whenever it crosses a trust boundary, even from "internal" sources.
- [How to Handle Exceptions in Python: A Detailed Visual Introduction](https://www.freecodecamp.org/news/exception-handling-python/) — freeCodeCamp · beginner-friendly: why naming specific exceptions beats a bare `except`.
- [Built-in exceptions: KeyboardInterrupt and the hierarchy](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt) — Python docs · `KeyboardInterrupt` is a `BaseException` "so as to not be accidentally caught by code that catches `Exception`"; the hierarchy also shows `UnicodeDecodeError` under `ValueError`.
- [json.JSONDecodeError](https://docs.python.org/3/library/json.html#json.JSONDecodeError) — Python docs · "Subclass of `ValueError`", plus the warning that a malicious JSON string can consume lots of CPU and memory (why the size limit also applies to replies).
- [contextlib.redirect_stdout](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stdout) — Python docs · how the tests capture `print` output to assert on the message.

## Quiz

### Revise
1. Why can one `except (ValueError, RecursionError)` handle both "the reply isn't valid JSON"
   and "the reply is JSON with the wrong shape"?
   <details><summary>Answer</summary>

   `json.JSONDecodeError` and `UnicodeDecodeError` are subclasses of `ValueError`, and
   `check_response` deliberately raises `ValueError` for a wrong shape. So every "the reply
   is unusable" case reaches the same handler. `RecursionError` (too deep nesting) isn't a
   `ValueError`, so it's listed separately.
   </details>

2. The test patches `client.receive_message`. Why not `protocol.receive_message`?
   <details><summary>Answer</summary>

   `client.py` does `from protocol import receive_message`, so it holds its own name for
   the function in the `client` module. Patching `protocol.receive_message` would replace
   only the name in `protocol`, and the client would still call the real one. You patch
   where the name is looked up.
   </details>

3. What does this print when the server is down, and what's wrong with the order?
   ```python
   try:
       socket.create_connection((HOST, PORT))
   except OSError as error:
       print(f"Cannot connect: {error}")
   except ConnectionRefusedError:
       print("Is the server running?")
   ```
   a) "Is the server running?" b) "Cannot connect: [Errno 111] Connection refused"
   c) both d) a traceback
   <details><summary>Answer</summary>

   b. `ConnectionRefusedError` is a subclass of `OSError`, and Python uses the first
   matching `except`, so the specific hint is unreachable. Put the subclass first, as
   `connect()` does.
   </details>

4. Why does `main()` catch `KeyboardInterrupt` explicitly, when the session already has an
   `except` around `input()`?
   <details><summary>Answer</summary>

   Ctrl+C can land anywhere, not just at the prompt: during `create_connection`, during the
   TLS handshake (which waits while the server is busy with another client) or while
   waiting for a reply. `KeyboardInterrupt` is a `BaseException`, so no `except OSError`
   or `except Exception` catches it. The outer handler covers every place in one spot.
   </details>

5. Why does the client disconnect after `MessageTooLong` instead of reading the next reply?
   <details><summary>Answer</summary>

   `receive_message` reads at most 64 KiB + 1 bytes, so the rest of the over-long line is
   still in the stream. The next read would parse that tail, which the server controls, as
   if it were a new reply. It's the same reason the server closes the connection on an
   over-long request (task 5.1).
   </details>

### Defend the decision
1. "The server is yours. Why validate its replies at all?"
   <details><summary>Model answer</summary>

   Because the client can't know it's talking to our server, or to a correct version of
   it. Another process could own the port, a future server version could change a field,
   or a bug could send the wrong shape. TLS pinning makes an impostor unlikely but doesn't
   protect against bugs. Without the check, a wrong shape is a crash
   (`AttributeError` at `response.get`) and, worse, `user` could be set from garbage. The
   check is a few lines, once, at the boundary, and it covers only the fields the client
   actually reads.
   </details>

2. "Why not wrap `main()` in `except Exception: print('Something went wrong')`?"
   <details><summary>Model answer</summary>

   It would hide bugs. A typo in the client would look like a network problem and leave no
   trace to debug. And it still wouldn't catch Ctrl+C, which is a `BaseException`. Naming
   each failure we listed gives the user a specific message they can act on, and anything
   we didn't foresee still produces a traceback the developer can fix.
   </details>

3. "Disconnecting after one bad reply seems harsh. Why not show the error and continue?"
   <details><summary>Model answer</summary>

   The line was fully read, so continuing is technically possible. But a malformed reply
   means the peer is broken or isn't our server, and the client's state depends on the
   replies: the prompt shows who is logged in, and `stop` exits. Continuing could act on a
   state the server doesn't share. Failing fast with a clear message is safer, and the
   user can simply reconnect. The server is more forgiving of malformed requests because it
   always answers with a well-formed error, so the session state stays consistent.
   </details>
