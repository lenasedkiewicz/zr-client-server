---
id: 023
title: Give the server an explicit close and guard start-up
commit: "refactor: give the server an explicit close and guard start-up"
step: 16 — address the 2026-10-21 mentoring code review (batch 6, task 6.2)
date: 2026-11-18
tags: [python, socket, resource-management, context-manager, try-finally, unittest, mock]
---

# Give the server an explicit close and guard start-up

## What we did
`Server` opened its listening socket in `__init__`, but the only code that closed it was
the `finally` at the end of `serve_forever`. That left three gaps:

1. If `setsockopt()` or `bind()` failed in `__init__` (port taken, bad address), the
   exception escaped with the socket still open. The caller never got a `Server` object, so
   nobody *could* close it. Now those calls sit in a `try` whose `except BaseException:`
   closes the half-built socket and re-raises (`server.py:81`–`89`). `BaseException`, not
   `Exception`, so a Ctrl+C at exactly that moment is covered too. Nothing is swallowed,
   because of the bare `raise`.
2. In `serve_forever`, `listen()` and `settimeout()` ran **before** the `try`. A `finally`
   only protects code *inside* its `try`, so if `listen()` raised, the `finally` never ran
   and the socket stayed open. Now everything from `listen()` on is inside the `try`
   (`server.py:307`), and the `finally` calls the new `close()` (`server.py:328`).
3. `__main__` and the tests cleaned up by reaching into the object: `server.sock.close()`
   on two exit paths in `__main__`, and `addCleanup(server.sock.close)` in three test
   classes. Now `Server` has `close()` (`server.py:288`), which clears `listening` and
   closes the socket. It is safe to call twice, because `socket.close()` on a closed socket
   does nothing. `Server` also has `__enter__`/`__exit__` (`server.py:297`). `__main__` wraps
   the admin set-up and `serve_forever()` in `with server:` (`server.py:344`), so both
   `sys.exit(1)` paths close the socket without repeating the call. `sys.exit` raises
   `SystemExit`, and `__exit__` runs for it like for any other exception.

This is the same design as `socketserver`: `server_close()` plus "it is recommended to use
the server in a `with` statement". `close()` does **not** stop a `serve_forever` running in
another thread. Stopping is still `running = False`. Closing a socket under a blocked
`accept()` in another thread behaves differently on each OS, so that stays out of scope.

**Tests** (`tests/test_server.py:158`, `ServerCloseTest`): `close()` closes the socket,
calling it twice is fine, a `with` block closes it *and* lets the exception through, a
failing `listen()` leaves no open socket, and a failing `bind()` closes the socket the
constructor made. Two details:
- **"Closed" means `sock.fileno() == -1`, not "the port can be bound again".** On Windows,
  `SO_REUSEADDR` lets a second bind succeed even while the port is still in use (task 6.3),
  so a rebind check would pass even when the bug is there. A test has to be able to fail
  when the bug is present.
- **Patching on the class.** `socket.socket` declares `__slots__`, so an instance has no
  `__dict__` and `mock.patch.object(server.sock, "listen", ...)` would fail. The tests patch
  `socket.socket.listen` / `.bind` instead. For the bind test the constructor raises, so the
  test never gets the object. It patches `close` with `autospec=True` and
  `side_effect=<the real close>`. The mock then records *which* socket was closed (the
  first argument, `self`) and still really closes it.

Run against the old `server.py` (`git stash push server.py`), the bind test failed with
"Expected 'close' to have been called once. Called 0 times", and the other four errored
because `close()` didn't exist. With the change, all 98 tests pass (1 skipped, as before).
One change the briefing didn't plan: the end-to-end `setUp` now also registers
`addCleanup(self.server.close)` right after building the server, which covers a thread that
never started. Calling `close()` twice is safe, so this costs nothing when `serve_forever`
has already closed the socket.

**Answer to the briefing question.** *Why is a `try` that starts after `listen()` not
good enough, even though its `finally` closes the socket?* A `finally` runs only for
exceptions raised *inside* its `try`. Anything that fails between acquiring the resource
(here, creating and binding the socket) and entering the `try` skips the clean-up
completely. So the protected region must start **right after** the resource is acquired,
not right before the main loop. The same rule is behind `addCleanup` straight after the
resource exists (journal 012), and behind `with`, which begins protecting at once.

## How it fits
- **Plan:** Step 16, batch 6 (server lifecycle), task 6.2, on branch
  `fix/server-lifecycle`. `PLAN.md` Step 4 now says the server owns its socket. Next is
  task 6.3 (`SO_EXCLUSIVEADDRUSE` on Windows). Its test, "a second `Server` on the same port
  raises `OSError`", can now clean up with `close()`, and once 6.3 is in, a rebind check
  will finally mean something.
- **Practice: whoever acquires a resource releases it.** This is RAII in Python: the
  object that opens the socket also has the method that closes it, and a context manager
  ties the release to leaving a block. Without that, every caller has to know *how* to
  clean up (`server.sock.close()`). Callers then grow out of step: here there were two
  copies in `__main__` and three in the tests. Python's own `socket`, `socketserver` and file
  objects all work this way.
- **Practice: the `try` starts right after the acquire.** The pattern is
  `r = acquire(); try: use(r) finally: release(r)`, with nothing in between. A `with` block
  enforces that shape.
- **When you'd skip it:** in a short script that runs once and exits, the OS releases
  everything at process exit, and garbage collection closes a forgotten socket (with a
  `ResourceWarning`). It matters here because the tests create many servers in one
  process, and because `__main__` has several exit paths.
- **Alternative:** `contextlib.ExitStack` for several resources acquired in sequence, or
  `contextlib.closing(obj)` to get `with` support for an object that only has `close()`.
  With one resource that we own, adding `__enter__`/`__exit__` to the class is the clearest
  choice.

## Commands used
- `git log`, `grep -n "^## " PLAN.md`, `cat`/`sed -n`/`awk` on `PLAN.md` and
  `docs/plans/001-code-review-2026-10-21.md`: find the next open task (6.2) in the fix plan
- `grep -n "def \|sock\.\|close()\|listen\|try:\|finally" server.py`, `grep -n "Server(\|\.sock\|close()" tests/*.py run.py`:
  find every place that opens or closes the listening socket
- `sed -i 's/self\.addCleanup(self\.server\.sock\.close)/self.addCleanup(self.server.close)/; s/.../.../' tests/test_server.py`:
  switch the existing test cleanups to `close()` (see [sed -i](../commands.md#sed--i-edit-a-file-in-place))
- `git stash push server.py -q && python -m unittest tests.test_server.ServerCloseTest; git stash pop -q`:
  run the new tests against the old server, to prove that they fail
  (see [git stash](../commands.md#git-stash-put-changes-aside-for-a-moment))
- `python -m unittest discover tests`: the full suite, 98 tests, OK (1 skipped)
- `python -c "import server"`: check that the module still imports cleanly
- `python -c "import socket; from unittest import mock; ..."`: confirm two claims in this
  entry: a second `close()` is a no-op (`fileno()` stays -1), and patching a socket
  *instance* raises `AttributeError`
- `git diff --stat`, `git diff server.py`, `git config core.autocrlf`, `file server.py tests/test_server.py`:
  check that a large diff was real changes and not line endings (`sed -i` left the test
  file with LF; `core.autocrlf=true` normalises it on commit)

## Read more
- [socketserver: Server Creation Notes and `server_close()`](https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.server_close):
  Python docs · "call `server_close()` to close the socket (unless you used a `with`
  statement)". This is the stdlib design that `Server.close()` copies.
- [socket.close()](https://docs.python.org/3/library/socket.html#socket.socket.close):
  Python docs · "Sockets are automatically closed when they are garbage-collected, but it is
  recommended to close() them explicitly, or to use a with statement around them."
- [What Are Context Managers in Python?](https://www.freecodecamp.org/news/context-managers-in-python/):
  freeCodeCamp · a class with `__enter__`/`__exit__` that opens and closes a resource,
  and what the three `__exit__` arguments hold.
- [PEP 343: The "with" Statement](https://peps.python.org/pep-0343/): peps.python.org ·
  the translation of `with` into `try/finally`. It shows why the protection starts at once,
  and why `__exit__` returning a true value would swallow the exception.
- [unittest.mock: Autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing):
  Python docs · mocked methods keep "the same call signature as the original". That's why
  the patched `close` receives the socket as `self`, and the test can check which one was
  closed.
- Related in this repo: journal 012 (register a cleanup right after the resource exists:
  the same rule in the tests), journal 013 (unclosed sockets and `ResourceWarning`).

## Quiz

### Revise
1. What does this print, and is the socket closed?
   ```python
   s = socket.socket()
   s.bind(("127.0.0.1", 0))
   s.listen()            # suppose this raises OSError
   try:
       serve(s)
   finally:
       s.close()
   ```
   <details><summary>Answer</summary>

   The `OSError` from `listen()` propagates, and the socket is **not** closed: the `try`
   hadn't started yet, so its `finally` never runs. The socket stays open until garbage
   collection, which prints a `ResourceWarning`. Move `listen()` inside the `try`, or use
   `with socket.socket() as s:`.
   </details>
2. `__exit__` here is `def __exit__(self, exc_type, exc_value, traceback): self.close()`.
   An exception is raised inside `with server:`. What happens?
   a) it is swallowed b) it propagates after `close()` runs c) `close()` is skipped
   d) it is wrapped in a new exception
   <details><summary>Answer</summary>

   b. `__exit__` returns `None`, which is false, so Python re-raises the exception after
   `__exit__` has run. Returning `True` would swallow it (PEP 343).
   </details>
3. Why does `__init__` catch `BaseException` rather than `Exception` around `bind()`?
   <details><summary>Answer</summary>

   `KeyboardInterrupt` and `SystemExit` inherit from `BaseException`, not `Exception`. The
   clean-up should run whatever the reason for leaving, and the bare `raise` re-raises it
   unchanged, so nothing is swallowed. Catching `BaseException` is fine when you always
   re-raise. It's a bug only when you swallow it.
   </details>
4. Why does `mock.patch.object(server.sock, "listen", side_effect=OSError())` fail, while
   `mock.patch.object(socket.socket, "listen", ...)` works?
   <details><summary>Answer</summary>

   `socket.socket` defines `__slots__`, so instances have no `__dict__` and you can't set a
   new attribute such as `listen` on one. Python 3.13 reports
   `AttributeError: 'socket' object attribute 'listen' is read-only`. Patching the class sets a class attribute, which
   every instance then finds. It's safe in this test because nothing else calls `listen()`
   while the patch is active.
   </details>
5. Calling `server.close()` twice: what happens on the second call, and why does that matter
   for `addCleanup(server.close)` in the end-to-end test?
   <details><summary>Answer</summary>

   Nothing: `socket.close()` on a closed socket is a no-op, and `listening.clear()` on a
   cleared event is too. That lets the test register the cleanup unconditionally, even
   though `serve_forever` normally closes the socket first. An idempotent release is what
   makes "register the cleanup right away" safe.
   </details>

### Defend the decision
1. "Why add `close()` and `__enter__`/`__exit__` when `serve_forever` already closes the
   socket in its `finally`?"
   <details><summary>Model answer</summary>

   `serve_forever` only covers a server that *serves*. The socket exists from `__init__`
   onwards, and between those two points there's admin set-up in `__main__` (two exit
   paths) and, in the tests, servers that never serve at all (`HandleRequestTest`). Each of
   those callers had to do `server.sock.close()`, which spreads knowledge of the internals
   around. Giving the owner a `close()` puts the rule in one place, the same as
   `socketserver.server_close()`. The cost is about ten lines.
   </details>
2. "Your test checks `fileno() == -1`. Wouldn't 'the port can be bound again' be a more
   realistic check?"
   <details><summary>Model answer</summary>

   It would be, on Linux. On Windows, our `SO_REUSEADDR` lets a second bind succeed even
   while the first socket is still open, so the rebind test would pass with the bug still
   there. A test that can't fail proves nothing. `fileno() == -1` checks exactly what we
   changed (the socket object is closed) on every OS. The rebind check comes with task 6.3,
   once `SO_EXCLUSIVEADDRUSE` makes it meaningful on Windows.
   </details>
3. "Why doesn't `close()` also stop a running `serve_forever`?"
   <details><summary>Model answer</summary>

   Two jobs, two mechanisms. Stopping is `running = False`, which the accept loop checks at
   least once a second. Closing a socket while another thread is blocked in `accept()` on
   it behaves differently on each OS (an immediate error, or a hang until the timeout), and
   nothing in this app needs it: `stop` and Ctrl+C both end the loop, and the loop's
   `finally` then calls `close()`. `socketserver` splits it the same way, with `shutdown()`
   to stop and `server_close()` to release.
   </details>
