---
id: 034
title: Explain a certificate that can't be read
commit: "fix: explain a certificate that can't be read"
step: 16 — address the 2026-10-21 mentoring code review (pre-review fix on batch 8)
date: 2026-11-25
tags: [python, ssl, tls, exceptions, exception-hierarchy, try-scope, unittest, mock]
---

# Explain a certificate that can't be read

## What we did
Journal 033 handled two ways the certificate could fail: missing (`FileNotFoundError`) and
broken (`ssl.SSLError`). The pre-review run on the branch found a third: a `server.crt`
with no read permission, or one that is a **folder**. On Windows both raise
`PermissionError: [Errno 13] Permission denied`, a sibling of the other two under `OSError`.
A script showed:
- `run.main()` and `client.main()` crashed with a traceback.
- `server.main()` printed "Could not listen on 127.0.0.1:65432 ([Errno 13] Permission
  denied: 'server.crt')". That is the same wrong message journal 033 fixed for
  `ssl.SSLError`, now with another subclass.

The fix is different on each side:
- **Client and launcher** (`client.py:117`, `run.py:252`): `except ssl.SSLError` became
  `except OSError`, still after `FileNotFoundError`. Here every error in that `try` comes
  from loading one file, so one broad clause is right: "can't be used: <reason>", and the
  OS's reason ("Permission denied") says what to check. `run.py` no longer needs
  `import ssl`.
- **Server** (`server.py:351`): the real cause was that **one `try` covered two steps**.
  `Server()` loaded the certificate *and* bound the port, and both raise `OSError`. Now
  `main()` builds the TLS context in its own `try`. Then it passes it in with
  `Server(..., tls_context=tls_context)` (`server.py:367`), a parameter the tests already
  used. The `except OSError` after `Server()` can then only mean "could not listen". The
  correctness no longer depends on the order of the `except` clauses.

Three new tests (`tests/test_server.py:318`, `tests/test_client.py:124`,
`tests/test_run.py:249`) make the loader raise `PermissionError`. With `git stash` of the
three fixed files, they failed as expected: two errors (tracebacks) and one failure
("Could not listen"). With the fix, all 158 tests pass. `ServerMainTest.run_main` now
mocks `make_server_context` by default with the test certificate, because `main()`
loads the certificate before `Server()` and `server.crt` isn't in CI. The test for a
missing certificate now uses the real loader on a path that doesn't exist, instead of
making the whole `Server` raise.

## How it fits
- **Plan:** Step 16, a pre-review fix on batch 8 (`PLAN.md` Step 10, the "Unusable" note;
  README "Setup"). It completes journal 033. Next: Ctrl+C in the launcher's remaining
  waits, and a background server that exits during start-up.
- **Practice:**
  - *One `try` per step whose errors mean different things.* When two calls can raise the
    same exception class for different reasons, a shared `try` forces you to sort them
    out by clause order, and each new subclass can land in the wrong clause. That is what
    happened twice here (`ssl.SSLError`, then `PermissionError`). Separate `try` blocks
    sort them out by structure. The Python tutorial gives the same reason for the `else`
    clause: it "avoids accidentally catching an exception that wasn't raised by the code
    being protected".
  - *A broad clause is fine when everything in the `try` is one thing.* On the client
    side, the `try` holds only "load this file", so `except OSError` after
    `FileNotFoundError` is accurate, not lazy. Ask "what else can land here?" If the
    answer is "only other ways this one step fails", a broad catch is right.
  - *When you'd choose differently:* when every error leads to the same action, one `try`
    is simpler. The client's `except (ConnectionClosed, OSError)` means "the connection
    is gone" whatever the cause.
  - **Still open (K1):** `Server()` also reads `users.json` through `UserStore()`. An
    unreadable users file would still be reported as "Could not listen". It is a separate
    finding, to be fixed in its own commit.

## Commands used
- `python -I -c "import ssl; … ssl.create_default_context(cafile=p) …"` (in the scratchpad)
  — what loading a folder and an empty file raises: `PermissionError` and `ssl.SSLError`
  ([python -I](../commands.md#python--i-isolated-mode))
- `python -c "… mock.patch.object(run, 'CERT_FILE', d) … run.main() … server.main()"` —
  the traceback and the "Could not listen" message with a folder as the certificate,
  before the briefing
- `sed -i '/^import ssl$/d' run.py` — remove the import that became unused
  ([sed -i](../commands.md#sed--i-edit-a-file-in-place))
- `python -m unittest discover tests` — the full suite: 158 tests, OK with 1 skip
- `git stash push -q -- run.py client.py server.py && python -m unittest tests.test_run tests.test_client tests.test_server -k unreadable; git stash pop -q`
  — the new tests without the fix: 2 errors and 1 failure
  ([git stash](../commands.md#git-stash-put-changes-aside-for-a-moment) with several paths)
- `git diff --stat` and `git ls-files --eol run.py client.py` — check that `sed -i` changed
  one line, not every line ending ([git ls-files](../commands.md#git-ls-files-list-tracked-files) `--eol`)

## Read more
- [OS exceptions](https://docs.python.org/3/library/exceptions.html#os-exceptions) — Python docs · `FileNotFoundError`, `PermissionError` ("without the adequate access rights - for example filesystem permissions") and `IsADirectoryError` are all subclasses of `OSError`, picked by the OS error code.
- [ssl.SSLError](https://docs.python.org/3/library/ssl.html#ssl.SSLError) — Python docs · "This error is a subtype of OSError": the reason a shared `except OSError` mixed up "fix the file" and "free the port".
- [Handling exceptions](https://docs.python.org/3/tutorial/errors.html#handling-exceptions) — Python tutorial · the `else` clause "avoids accidentally catching an exception that wasn't raised by the code being protected": the same idea as one `try` per step.
- [Limit Your Try Clauses in Python](https://adamj.eu/tech/2019/10/02/limit-your-try-clauses-in-python/) — Adam Johnson · "limit our `try` clause to the lines that can raise the expected error", with examples of what goes wrong otherwise.
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/) — freeCodeCamp · beginner-friendly: one `except` block per error you expect, and why a bare `except` is a bad idea.
- Related: [journal 033](033-unusable-certificate.md) (the first half of this fix), [journal 027](027-explain-a-taken-port.md) (the bind clause), [concept 003](../concepts/003-except-clause-scope.md) (which handler catches what).

## Quiz

### Revise
1. What does `ssl.create_default_context(cafile="certdir")` raise on Windows when
   `certdir` is a folder, and which `except` clause in the old `server.main()` caught it?
   <details><summary>Answer</summary>

   `PermissionError: [Errno 13] Permission denied`. It isn't `FileNotFoundError` or
   `ssl.SSLError`, so it fell through to `except OSError`, the bind clause, which printed
   "Could not listen".
   </details>

2. Multiple choice. Which of these is **not** a subclass of `OSError`?
   a) `PermissionError`
   b) `ssl.SSLError`
   c) `TimeoutError`
   d) `ValueError`
   <details><summary>Answer</summary>

   d. `ValueError` is a direct child of `Exception`. The other three are all `OSError`s,
   which is why one `except OSError` catches so many different problems.
   </details>

3. Why is `except OSError` correct in `client.main()`, but was wrong in `server.main()`
   before this commit?
   <details><summary>Answer</summary>

   In the client, the `try` holds one step, loading the certificate. Every `OSError` there
   is a certificate problem. In the server, the `try` held `Server()`, which loaded the
   certificate *and* bound the port. An `OSError` there could mean either, and the
   message assumed the port.
   </details>

4. Spot the bug:
   ```python
   try:
       config = load_config(path)
       sock.bind((HOST, PORT))
   except FileNotFoundError:
       print("config missing")
   except OSError as error:
       print(f"could not bind: {error}")
   ```
   <details><summary>Answer</summary>

   A config file that exists but can't be read raises `PermissionError`, an `OSError`, so
   it is reported as "could not bind". So is `IsADirectoryError`. Put the two steps in
   separate `try` blocks, so each `except OSError` belongs to one step.
   </details>

5. Why did `ServerMainTest.run_main` need to mock `make_server_context` after this change?
   <details><summary>Answer</summary>

   `main()` now loads the certificate itself, before `Server()`. Tests that mock `Server`
   (for example the bind-error test) would otherwise load the real `server.crt`, which
   isn't in CI, and fail with "not found" before reaching the code under test.
   </details>

### Defend the decision
1. "Journal 033 put `except ssl.SSLError` before the bind clause. Why restructure now,
   instead of adding `except PermissionError` there too?"
   <details><summary>Model answer</summary>

   Adding a clause works until the next subclass. `IsADirectoryError` or some other
   `OSError` from loading would fall into the bind clause again, as `PermissionError` just
   did. The problem was the scope of the `try`, not a missing clause. Two `try` blocks
   make it impossible for a loading error to reach the bind clause. Journal 033 assumed
   that splitting meant changing the `Server` API, but `Server` already took
   `tls_context=`, so `main()` only had to pass it in.
   </details>

2. "Journal 033 argued for testing with a real broken file. Why mock `PermissionError`
   here?"
   <details><summary>Model answer</summary>

   Because the real trigger depends on the OS. On Windows a folder as `cafile` gives
   `PermissionError`. On Linux it may give a different `OSError` or an `ssl.SSLError`, and
   `chmod 000` does nothing for a user with admin rights. A real-file test could pass on
   Linux without the fix, so it wouldn't prove anything there. The handling, "any
   `OSError` from loading becomes a message", is the same everywhere, so a mocked
   `PermissionError` tests it on both CI systems. The real-file test from 033 still covers
   a broken file, and I ran a real folder once by hand to learn what it raises.
   </details>

3. "The message says 'check that both are readable files, or create them again'. Why not
   detect permission problems and give a separate message?"
   <details><summary>Model answer</summary>

   The OS's own text ("Permission denied") is printed with it, and it is already specific.
   A separate branch for each subclass would mean more code paths and more tests for a
   rare case, and on Windows a folder and a missing permission look the same (errno 13).
   One message that covers all the causes and shows the real reason is clear enough for a
   local setup problem.
   </details>
