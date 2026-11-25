---
id: 035
title: Handle Ctrl+C anywhere in the launcher
commit: "fix: handle Ctrl+C anywhere in the launcher"
step: 16 — address the 2026-10-21 mentoring code review (pre-review fix on batch 8)
date: 2026-11-25
tags: [python, keyboardinterrupt, signals, exceptions, subprocess, exit-codes, unittest, mock]
---

# Handle Ctrl+C anywhere in the launcher

## What we did
The launcher caught Ctrl+C in three places: at the admin prompt, while waiting for
start-up, and while the client runs. The pre-review found three more waits where it didn't,
and where `KeyboardInterrupt` escaped as a traceback:
- **The first `probe_server()`.** Against a peer that accepts and stays silent, it can take
  about 3 s (three 1 s timeouts).
- **The 5 s `wait()` in `stop_background_server`.** Here the interrupt also skipped the
  `kill()`. On POSIX, a server that ignored `terminate()` would then be left running.
- **`wait_for_server_exit`**, which probes a reused server after the client ends.

The README already promised exit code 130 for Ctrl+C before the client starts, so this was
a broken contract, not only an ugly one.

Two changes in `run.py`:
- **A last line of defence.** `main()` (`run.py:248`) is now a thin wrapper. It calls the
  old body, renamed `launch()` (`run.py:263`), catches `KeyboardInterrupt`, prints
  "Interrupted" and returns `EXIT_INTERRUPTED`. The specific handlers inside stay, because
  their messages know the context. `launch()`'s `finally` runs before the wrapper's
  `except`, so a background server is always stopped first.
- **Ctrl+C while stopping means "hurry up".** `stop_background_server` (`run.py:160`) kills
  at once on Ctrl+C during its wait, collects the exit status, and re-raises, so the run
  still reports 130.

Three tests in `CtrlCAnywhereTest` (`tests/test_run.py:138`) cover one wait each. Without
the fix, each one ended in `KeyboardInterrupt` and aborted the test run. A hand mutation
that removed only the new `except KeyboardInterrupt` in `stop_background_server` made
the stop test fail: "Expected 'kill' to have been called once. Called 0 times." Full suite:
161 tests, OK with 1 skip. The `assert_nothing_started` helper moved up to the shared base
class so the new tests can use it. While editing `PLAN.md` I also fixed a stale sentence:
it said a reused server "is not probed again", but `wait_for_server_exit` probes it.

## How it fits
- **Plan:** Step 16, a pre-review fix on batch 8 (`PLAN.md` step 7, the "Exit code" note;
  README "Exit codes", row 130). It completes task 8.2. Next: a background server that
  exits during start-up, then an unreadable `users.json` (journal 034).
- **Practice:**
  - *Specific handlers inside, one catch-all at the entry point.* The inner handlers give the
    best message ("Admin setup cancelled - server not started"). The outer one guarantees
    that no path ends in a traceback, including paths added later. The server uses the
    same layering: per-session handlers inside `serve_forever`.
  - *Catch `KeyboardInterrupt`, never `BaseException`.* `BaseException` would also catch
    the `SystemExit` that `sys.exit(EXIT_LAUNCHER_FAILED)` raises, so every exit code would
    become 130.
  - *Clean up, then let the interrupt go on.* `stop_background_server` does the one thing
    that must not be skipped (`kill()` and `wait()`), then re-raises. Swallowing it would
    report the client's 0 for a run the user cut short.
  - *The other view.* The `signal` docs advise programs that must stay consistent to
    "avoid catching KeyboardInterrupt as a means of gracefully shutting down" and to
    install a SIGINT handler instead, because the exception "may appear at any point". That
    matters for code with invariants to protect, like a file half written. The launcher's
    wrapper only prints and returns, and the state that matters (the child process) is
    handled in a `finally`. A signal handler would be the right tool if Ctrl+C had to be
    *ignored* during a critical section, for example while `users.json` is replaced.
  - *When you'd choose differently:* a library should let `KeyboardInterrupt` through, so
    the application decides. A long-running service handles `SIGTERM` too, which
    `KeyboardInterrupt` doesn't cover.

## Commands used
- `python -m unittest discover tests` — the full suite: 161 tests, OK with 1 skip
- `git stash push -q -- run.py && python -m unittest -v -k CtrlCAnywhere tests.test_run 2>&1 | tail -6; git stash pop -q`
  — the new tests without the fix: the mocked Ctrl+C escaped and aborted the run
  ([git stash](../commands.md#git-stash-put-changes-aside-for-a-moment),
  [python -m unittest](../commands.md#python--m-unittest-run-the-test-suite) `-k`)
- `for t in …; do printf '%s: ' $t; python -m unittest tests.test_run.CtrlCAnywhereTest.$t 2>&1 | grep -E "…" | head -1; done`
  — each new test alone, so one abort can't hide the others
  ([for loop](../commands.md#for-loop--sleep-retry-and-wait), [printf](../commands.md#printf-print-text-with-escapes))
- `cp run.py "$S/run.py.fixed"`, a `python -` heredoc that cut the new `except` block,
  then `cp "$S/run.py.fixed" run.py` — a hand mutation to prove the `kill()` test. The first
  attempt didn't match because `run.py` has CRLF endings on disk, so its "OK" meant nothing.
  The second converted `\r\n` first ([cp](../commands.md#cp-copy-files),
  [python -](../commands.md#python---run-a-script-from-stdin))
- `grep -c 'process.kill()' run.py` — count the `kill()` calls, to check that the mutation
  really changed the file and the restore brought it back
  ([grep](../commands.md#grep-search-text))

## Read more
- [KeyboardInterrupt](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt) — Python docs · it "inherits from BaseException so as to not be accidentally caught by code that catches Exception", and it can leave a program "in an inconsistent state".
- [Note on signal handlers and exceptions](https://docs.python.org/3/library/signal.html#note-on-signal-handlers-and-exceptions) — Python docs · "a KeyboardInterrupt may appear at any point during execution", and the advice to use a SIGINT handler where consistency matters: the counterpoint discussed above.
- [Popen.terminate / Popen.kill](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.kill) — Python docs · SIGTERM versus SIGKILL on POSIX. On Windows both call `TerminateProcess()`, which is why the fast path matters on POSIX.
- [Control-C handling in Python and Trio](https://vorpus.org/blog/control-c-handling-in-python-and-trio/) — Nathaniel J. Smith · deeper: "The problem with KeyboardInterrupt is that it can happen anywhere", and what that means for cleanup code.
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/) — freeCodeCamp · beginner-friendly: how `except` clauses are matched, the base for "catch the specific class".
- Related: [journal 028](028-always-stop-the-background-server.md) (the `finally` this relies on), [journal 030](030-launcher-exit-codes.md) (the exit codes), [concept 003](../concepts/003-except-clause-scope.md).

## Quiz

### Revise
1. Why doesn't `except Exception:` catch Ctrl+C?
   <details><summary>Answer</summary>

   `KeyboardInterrupt` inherits from `BaseException`, not `Exception`, so that broad
   handlers don't stop the user from interrupting a program. Only `except
   KeyboardInterrupt`, `except BaseException` or a bare `except:` catch it.
   </details>

2. Multiple choice. In `main()`, `launch()` raises `KeyboardInterrupt` while a background
   server runs. In which order do things happen?
   a) "Interrupted" is printed, then the server is stopped
   b) the server is stopped (`launch()`'s `finally`), then "Interrupted" is printed
   c) the server keeps running, because the exception skips `finally`
   d) the order depends on the OS
   <details><summary>Answer</summary>

   b. An exception leaving `launch()` runs its `finally` first. Only then does it reach the
   `except` in `main()`.
   </details>

3. What would go wrong if `main()` caught `BaseException` instead of `KeyboardInterrupt`?
   <details><summary>Answer</summary>

   `sys.exit(EXIT_LAUNCHER_FAILED)` raises `SystemExit`, a `BaseException`. It would be
   caught and turned into "Interrupted" and 130, so the start-up timeout and the
   "port used by another program" errors would report the wrong code.
   </details>

4. Spot the bug:
   ```python
   process.terminate()
   try:
       process.wait(timeout=5)
   except subprocess.TimeoutExpired:
       process.kill()
       process.wait()
   ```
   The user presses Ctrl+C during the 5 s wait. What happens to the child on POSIX?
   <details><summary>Answer</summary>

   `KeyboardInterrupt` isn't `TimeoutExpired`, so the `except` doesn't run and `kill()` is
   skipped. If the child ignored SIGTERM, it keeps running with no owner. The fix handles
   `KeyboardInterrupt` too: kill, wait, then re-raise.
   </details>

5. Why does each new test run alone in the "without the fix" check, and not all together
   with `-k`?
   <details><summary>Answer</summary>

   A `KeyboardInterrupt` escaping a test isn't reported as a failure: it stops the whole
   `unittest` run, as Ctrl+C would. The first one hides the rest, so each test needs its own
   run to show that it fails.
   </details>

### Defend the decision
1. "The `signal` docs say to avoid catching `KeyboardInterrupt` for a graceful shutdown.
   Why does your launcher do it?"
   <details><summary>Model answer</summary>

   The advice is for code with invariants that an exception at a random point could break,
   like a file half written or a data structure half updated. There, a SIGINT handler that
   sets a flag is safer. The launcher's wrapper only prints a line and returns a code, and
   the one thing that must happen, stopping the child, is in a `finally` and in the stop
   function's own handler. A signal handler would add global state, and for this job it
   gives nothing that the exception doesn't. I'd switch if Ctrl+C had to be ignored during a
   critical section.
   </details>

2. "Why keep the specific handlers ('Start-up cancelled', 'Admin setup cancelled') if
   `main()` now catches everything?"
   <details><summary>Model answer</summary>

   They say more. "Admin setup cancelled - server not started" tells the user that no
   server is running, and a generic "Interrupted" doesn't. The catch-all is for the waits
   that have nothing extra to say, and for paths added later. Removing the specific ones
   would make the messages worse, to save a few lines.
   </details>

3. "Why re-raise after `kill()` instead of returning normally?"
   <details><summary>Model answer</summary>

   The user pressed Ctrl+C, so the honest exit code is 130. If `stop_background_server`
   swallowed it, `main()` would return the client's code, often 0, and a script calling
   `run.py` would think the run ended normally. Re-raising after the cleanup keeps both: the
   server is gone, and the caller learns the run was interrupted.
   </details>
