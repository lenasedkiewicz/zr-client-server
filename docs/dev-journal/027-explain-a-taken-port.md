---
id: 027
title: Explain a taken port instead of a traceback
commit: "fix: explain a taken port instead of a traceback"
step: 16 — address the 2026-10-21 mentoring code review (follow-up to task 6.3)
date: 2026-11-21
tags: [python, socket, bind, errno, exceptions, exception-hierarchy, main-function, unittest, mock, pre-review]
---

# Explain a taken port instead of a traceback

## What we did
Task 6.3 (journal 024) made the server set `SO_EXCLUSIVEADDRUSE` on Windows, so a second
server can no longer share a port that ours listens on. Before that, the second `bind()`
quietly succeeded. After it, `bind()` raises `OSError`. But `__main__` caught only
`FileNotFoundError` around `Server()`, so starting a second server printed a traceback with
the Windows message in the local code page: `OSError: [WinError 10048] Tylko jedno użycie…`.
The `pre-review` skill found it: an A7/E5 finding, proven by holding port 65432 and running
`python server.py`. Linux had the same traceback before this branch. On Windows, 6.3 made it
the normal outcome.

The start-up code moved from the `if __name__ == "__main__":` block into `main()`
(`server.py:341`), so tests can call it. It now has three `except` clauses around
`Server(host=HOST, port=PORT)`:
1. `FileNotFoundError`: the certificate message, unchanged.
2. `OSError` with `errno == errno.EADDRINUSE`: "Could not listen on 127.0.0.1:65432: the
   port is already in use", plus what to do: stop the other program or change `PORT`.
3. Any other `OSError`: the address and the error, for example WinError 10013 (a port
   Windows reserves) or a `HOST` this machine doesn't have.

Every path exits with code 1. `logging.basicConfig` stays in the `__main__` block, so a
test that calls `main()` doesn't add handlers to the root logger. `ServerMainTest`
(`tests/test_server.py`) has three tests. The first uses a real conflict: a plain socket
listens on a free port, `server.PORT` points there, and `main()` must print the message and
exit 1. The second mocks a `PermissionError` (`errno.EACCES`) for the generic message. The
third checks that a missing certificate still gets the `openssl` hint. Before the new
`except` clauses existed, the first two failed with the raw `WinError 10048` and
`PermissionError`. The third already passed, and it is there to guard the order.

## How it fits
- **Plan:** Step 16, a follow-up to task 6.3. This is the last fix before the batch 6 PR
  (tasks 6.2 and 6.3) opens. The PR's "how to check by hand" step 2 now shows this message
  instead of a traceback. `PLAN.md` Step 4 and the README's "Manual start" describe it.
- **Practice:**
  - *A fix can move the failure, not remove it.* 6.3 turned "two servers share a port
    silently" into "the second one fails". That is the right trade, but the new failure
    path needed handling too. When a change makes an error *likely*, review who sees it.
  - *Order `except` clauses from narrow to broad.* `FileNotFoundError` is a subclass of
    `OSError`. If `except OSError` came first, a missing certificate would get the bind
    message. Python picks the first clause that matches, not the best one
    ([concept 003](../concepts/003-except-clause-scope.md)).
  - *Compare error codes, not message text.* `str(error)` is localised (Polish here) and
    differs between systems. `errno.EADDRINUSE` is 98 on Linux and 10048 on Windows: on
    Windows, Python's `errno` module uses the Winsock values, so one comparison works on
    both systems. `winerror` exists only on Windows.
  - *Keep `__main__` thin.* The logic goes in `main()`, which a test can call with mocks
    (the same move as `client.main()` in 7.1). Process-wide setup stays in the real entry
    point: logging handlers, and later perhaps signal handlers.
  - *When you wouldn't do this:* in a library, or under a service manager that logs
    tracebacks and restarts the process, letting the exception propagate is better. The
    translation belongs only at the edge where a person reads the output.

## Commands used
- `PYTHONPATH=. python "$S/hold_port.py"` — the pre-review proof: hold `127.0.0.1:65432`
  with a plain socket, run `python server.py` in a subprocess, show its exit code and
  output ([PYTHONPATH](../commands.md#pythonpath-extra-folders-to-import-from))
- `git archive HEAD | tar -x -C "$S/c1"` — a throwaway copy of the branch for the
  "does the test fail without the fix?" check
  ([git archive](../commands.md#git-archive-export-a-commits-files))
- `git show 65d08cd:server.py > "$S/c1/server.py"` — put the 6.2 version (no exclusive
  flag) into the copy, so the 6.3 tests can be shown to fail for the right reason
- `rm -rf "$S/c1"` — delete the copy afterwards (scratchpad only)
- `python -c "import errno, socket; …"` — check that a taken port on Windows has
  `errno == errno.EADDRINUSE` (both 10048), before relying on it
- `python -m unittest tests.test_server.ServerMainTest -v` — the new tests: two failing
  before the fix, all three passing after
- `python -m unittest discover tests` — the full suite: 118 tests, OK, 1 skipped (the
  POSIX-only file-mode test)
- `python -c "import socket, subprocess, sys; …"` — the same end-to-end check after the fix:
  exit code 1, the two message lines, empty stderr
- `grep -a -E "Error:"` — show the raised exceptions. `-a` because the Polish Windows message
  made grep report "Binary file matches"

## Read more
- [Built-in Exceptions: OSError](https://docs.python.org/3/library/exceptions.html#OSError) — Python docs · `errno` is "a numeric error code from the C variable errno"; `winerror` exists only on Windows; the "OS exceptions" section lists the subclasses (`FileNotFoundError`, `PermissionError`, …) chosen from the error code.
- [errno — Standard errno system symbols](https://docs.python.org/3/library/errno.html) — Python docs · the named constants, including `EADDRINUSE` ("Address already in use"), to compare instead of numbers or message text.
- [Windows Sockets Error Codes](https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2) — Microsoft Learn · `WSAEADDRINUSE` 10048 "Address already in use" and `WSAEACCES` 10013 "Permission denied": the two Windows bind failures in this commit's messages.
- [`__main__` — Top-level code environment](https://docs.python.org/3/library/__main__.html) — Python docs · "Putting as few statements as possible in the block below `if __name__ == '__main__'` can improve code clarity and correctness."
- [Python if \_\_name\_\_ == \_\_main\_\_ Explained](https://www.freecodecamp.org/news/if-name-main-python-example/) — freeCodeCamp · beginner-friendly: why the block runs only when the file is the program, so importing `server` from a test doesn't start a server.
- [unittest.mock: where to patch](https://docs.python.org/3/library/unittest.mock.html#where-to-patch) — Python docs · patch where the name is looked up. That is why the test patches `server.PORT` and `server.make_server_context`, not the names in `config`.
- Related: [journal 024](024-exclusive-port-on-windows.md) (the change that made this path likely), [concept 003](../concepts/003-except-clause-scope.md) (which clause catches).

## Quiz

### Revise
1. Which clause runs for a missing certificate, and why?
   ```python
   try:
       server = Server()
   except OSError:
       print("Could not listen")
   except FileNotFoundError:
       print("Certificate not found")
   ```
   <details><summary>Answer</summary>

   `except OSError` runs and prints "Could not listen". `FileNotFoundError` is a subclass of
   `OSError`, and Python takes the first matching clause, so the second clause can never run.
   Put the narrower class first.
   </details>

2. Why does the code check `error.errno == errno.EADDRINUSE` and not `"in use" in str(error)`?
   <details><summary>Answer</summary>

   The message text comes from the operating system. It is localised (Polish on this machine)
   and worded differently on Windows and Linux. The numeric code and its named constant are
   stable, and Python sets `errno.EADDRINUSE` to the right value for each system (98 on
   Linux, 10048 on Windows).
   </details>

3. Multiple choice. On Windows, a taken port raises `OSError` with which values?
   a) `errno` 98, no `winerror`
   b) `errno` 10048, `winerror` 10048
   c) `errno` 13, `winerror` 10013
   d) `errno` 10048, no `winerror`
   <details><summary>Answer</summary>

   b. Measured in this commit: `errno 10048 winerror 10048`, and `errno.EADDRINUSE` is also
   10048 on Windows. `winerror` exists only on Windows. c is the reserved-port case (WinError
   10013), which gets the generic message.
   </details>

4. Why did `logging.basicConfig(...)` stay in the `if __name__ == "__main__":` block instead
   of moving into `main()`?
   <details><summary>Answer</summary>

   `basicConfig` adds a handler to the root logger for the whole process. If `main()` did
   that, every test calling `main()` would install a handler, and later tests would print
   stray log lines. Configuring logging is the application's choice, so it belongs to the
   real entry point only.
   </details>

5. Spot the problem: a test does `mock.patch("config.PORT", port)` and then calls
   `server.main()`. What does `main()` bind to?
   <details><summary>Answer</summary>

   Still 65432. `server.py` did `from config import PORT`, which copied the value into the
   `server` module's own name `PORT` at import time. `main()` reads `server.PORT`, so that is
   the name to patch: "patch where it is looked up".
   </details>

### Defend the decision
1. "Task 6.3 was a fix. Why did it need another fix?"
   <details><summary>Model answer</summary>

   6.3 was right: two servers sharing a port without anyone noticing is worse than the second
   one failing. But it changed which path is likely. Before, the second `bind()` succeeded on
   Windows. After it, the second `bind()` fails, and that failure path had never been designed,
   so it showed a traceback. The pre-review checklist asks "does the user see a message, never
   a traceback?" for every changed path. Proving it took one script, so it was fixed before
   the PR, not after a reviewer found it.
   </details>

2. "Why catch the error in `main()` instead of inside `Server.__init__`?"
   <details><summary>Model answer</summary>

   `Server` is used by tests and could be used by other code. A class shouldn't decide to print
   and exit the process, because the caller may want to retry another port, or a test may want
   the exception. `__init__` does its own part: it closes the half-built socket and re-raises
   (6.2). Turning the exception into a message for a person is the job of the command-line
   edge, which is `main()`. The alternative, a library that calls `sys.exit()`, is hard to
   test and surprises the code that calls it.
   </details>

3. "Why one message for 'port in use' and a generic one for everything else, not a message per
   error code?"
   <details><summary>Model answer</summary>

   "In use" is the case we cause ourselves (a second server, after 6.3) and the one with a
   clear action: stop it or change `PORT`. Other bind errors are rare and varied: a reserved
   port (10013), a wrong `HOST`, or a permission problem below port 1024 on Linux. For those,
   the address plus the OS's own error says more than a guess would. Adding a branch per code
   is YAGNI until one of them actually happens to someone.
   </details>
