---
id: 028
title: Always stop the background server the launcher started
commit: "fix: always stop the background server the launcher started"
step: 16 — address the 2026-10-21 mentoring code review (task 8.1)
date: 2026-11-21
tags: [python, subprocess, process-lifecycle, try-finally, signals, unittest, mock, launcher]
---

# Always stop the background server the launcher started

## What we did
When no terminal window can be opened (an SSH session, for example), `run.py` starts the
server as its own child process, writing to `server.log`. That process belongs to the
launcher, but only one exit path cleaned it up: the normal end after the client exits.

- **Ctrl+C during the 5 s start-up wait** raised `KeyboardInterrupt` out of `main()`. The
  user got a traceback, and the server kept running with no owner. It held the port and
  kept writing the log.
- **A start-up timeout** called `terminate()` and then `sys.exit(1)` without `wait()`, so
  nothing checked that the process had actually gone.
- **The normal end** waited with no time limit.

Now `main()` (`run.py:162`) opens its `try` before anything is started, and the `finally`
calls `stop_background_server` (`run.py:98`) whenever a background process exists. It
returns at once if the server already exited (the client sent `stop`). Otherwise it calls
`terminate()`, then `wait(timeout=STOP_TIMEOUT)` (5 s), and only on
`subprocess.TimeoutExpired` it calls `kill()` and `wait()`. Ctrl+C during the start-up wait
prints "Start-up cancelled" and exits with code 1. The `finally` still runs, because
`sys.exit` is an exception (`SystemExit`) too.

To make that readable, `main()` was split into `start_server()`, `wait_until_started()` and
`run_client()`. A server in its own window, or one that was already running, is never
stopped, and is not probed again either: every probe of the TLS port shows up in that
server's log as a failed handshake (task 8.3). `start_server_in_background` now opens
`server.log` in a `with` block, so the file is closed even if `Popen` raises.
`tests/test_run.py` is new: 7 tests, all with mocks. Before the fix, 5 of them failed for
the reasons above. The two that passed (a server that already exited, a server already
running) guard the "own only what you started" rule.

## How it fits
- **Plan:** Step 16, batch 8, task 8.1 (`PLAN.md` Step 7, launcher). Task 8.2 (exit with
  the client's exit code) builds on the same `main()`. Task 8.3 (check that the port belongs
  to *our* server) replaces `server_is_running`.
- **Practice:**
  - *Protection starts right after the acquire.* The same lesson as 6.2's `listen()`
    ([journal 023](023-server-close-and-guarded-startup.md)), with a process instead of a
    socket. Here the `try` even starts *before* the acquire, and the `finally` checks
    `background_server is not None`. So a Ctrl+C between `Popen` returning and the next
    line is covered too.
  - *Escalate when stopping a process:* ask (`terminate`, SIGTERM on POSIX, which a
    process may handle), wait with a limit, then force (`kill`, SIGKILL, which can't be
    caught). Then `wait()` again, so the parent collects the exit status and no zombie
    stays in the process table on POSIX. On Windows, `terminate()` already ends the process
    at once (`TerminateProcess`), and `kill()` is the same call.
  - *Own only what you started.* The launcher doesn't stop a server it found on the port,
    or one it opened in a window the user can see and close.
  - *When you'd choose differently:* under a service manager (systemd, a Windows service)
    the manager owns the process, and a launcher shouldn't kill it. `with Popen(...)` alone
    is not enough here: its `__exit__` waits for the child but never terminates it, so a
    server would keep the launcher waiting for ever.

## Commands used
- `git fetch -q --prune` — update `origin/master` and mark deleted remote branches `[gone]`
- `gh run list --branch master --limit 3` and `gh run list --limit 3 --json … -q …` — check
  that CI passed on PR #11's merge before starting the batch
  ([gh run list](../commands.md#gh-run-list-list-github-actions-runs))
- `git checkout -q master && git pull --ff-only -q` — bring the local `master` up to date,
  fast-forward only
- `diff <(git diff e872f44^ e872f44 -- …) <(git diff 65d08cd^ 65d08cd -- …)` — confirm the
  stale branch's commit was the same change as the merged one
  ([diff <(…) <(…)](../commands.md#diff---compare-two-commands-output))
- `git branch -d chore/pre-review-skill fix/protocol-contract fix/server-limits fix/server-lifecycle-2 fix/client-errors`
  — delete merged local branches
- ⚠️ `git branch -D fix/server-lifecycle` — force-delete the unmerged old copy of 6.2, safe
  only after the `diff` check ([git branch](../commands.md#git-branch---show-current-print-the-current-branch))
- `git checkout -b fix/launcher-cleanup` — the batch 8 branch, from the local `master`, so it
  doesn't track `origin/master`
- `sed -i 's/^STARTUP_TIMEOUT = 5.0$/STARTUP_TIMEOUT = 5.0\nSTOP_TIMEOUT = 5.0/' run.py` —
  add only the constant first, so the new tests fail on behaviour, not on a missing name
- `python -m unittest -v -k start_up_timeout -k normal_run … tests.test_run` — the fail-first
  run without the Ctrl+C test, because unittest re-raises a `KeyboardInterrupt` and stops the
  whole run
- `python -m unittest -v -k ctrl_c tests.test_run` — the Ctrl+C test on its own
- `python - <<'EOF' … EOF` — rewrite `main()`. It hit the documented `\n` trap: two
  `print("\n…")` became real line breaks, fixed with exact edits
  ([python -](../commands.md#python---run-a-script-from-stdin))
- `python -c "import ast; ast.parse(open('run.py', encoding='utf-8').read())"` — check that
  the file parses after the repair
- `python -m unittest tests.test_run` and `python -m unittest discover tests` — 7 launcher
  tests, then the full suite: 125 OK, 1 skipped
- `git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S/e2e"` — a scratch copy of the repo
  for a real run, with a throwaway admin in its own `users.json`
  ([git ls-files](../commands.md#git-ls-files-list-tracked-files),
  [xargs](../commands.md#xargs-turn-input-lines-into-arguments))
- `timeout 60 python -c "import run; run.start_server_in_window = lambda: False; run.main()" < /dev/null`
  — the real background path: the server starts, the client gets end of input at once, and
  the launcher stops the server (exit code 0, port free afterwards)
- `rm -rf "$S/e2e"` — delete the scratch copy

## Read more
- [Popen.terminate / Popen.kill](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.terminate) — Python docs · SIGTERM vs SIGKILL on POSIX; on Windows both call `TerminateProcess()`, and "kill() is an alias for terminate()".
- [Popen.wait](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.wait) — Python docs · with `timeout`, it raises `TimeoutExpired` if the process hasn't ended, and it is safe to catch that and wait again. The `communicate()` entry shows the same "kill, then still collect the child" pattern.
- [Errors and Exceptions: Defining Clean-up Actions](https://docs.python.org/3/tutorial/errors.html#defining-clean-up-actions) — Python tutorial · "The finally clause runs whether or not the try statement produces an exception"; an unhandled one is re-raised after it.
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/) — freeCodeCamp · beginner-friendly `try/except/finally`. Spot the bug in its file example: if `open()` fails, the name the `finally` closes was never assigned. That's why `run.py` sets `background_server = None` *before* its `try`.
- [signal(7)](https://man7.org/linux/man-pages/man7/signal.7.html) — Linux man pages · "SIGKILL and SIGSTOP cannot be caught, blocked, or ignored"; SIGTERM is the ordinary termination signal a process may handle.
- Related: [journal 023](023-server-close-and-guarded-startup.md) (the same guard for a socket), [concept 003](../concepts/003-except-clause-scope.md) (which handler catches what; here the `finally` has no `except` at all, so it sees every exception, `SystemExit` and `KeyboardInterrupt` included).

## Quiz

### Revise
1. What does this print, and is the server stopped?
   ```python
   try:
       print("waiting")
       sys.exit(1)
   finally:
       print("cleanup")
   ```
   <details><summary>Answer</summary>

   It prints "waiting", then "cleanup", and then the program exits with code 1.
   `sys.exit()` raises `SystemExit`, and a `finally` runs for every exception, handled or
   not. So the start-up timeout's `sys.exit(1)` in `run.py` still reaches
   `stop_background_server`.
   </details>

2. Multiple choice. On Linux, what is the difference between `process.terminate()` and
   `process.kill()`?
   a) none, both send SIGKILL
   b) `terminate` sends SIGTERM, which the process may handle; `kill` sends SIGKILL, which it can't
   c) `terminate` waits for the process, `kill` doesn't
   d) `kill` also deletes the process's log file
   <details><summary>Answer</summary>

   b. Neither one waits: that is `wait()`'s job. On Windows both call `TerminateProcess`,
   so there is no difference there.
   </details>

3. Why does `stop_background_server` call `wait()` again after `kill()`?
   <details><summary>Answer</summary>

   `kill()` only sends the signal. Until the parent reads the child's exit status (with
   `wait()`), a dead child stays in the process table as a zombie on POSIX. The second
   `wait()` collects it. It has no timeout, because SIGKILL can't be ignored.
   </details>

4. Spot the bug:
   ```python
   try:
       server = subprocess.Popen(cmd)
       wait_for_server()
   finally:
       server.terminate()
   ```
   <details><summary>Answer</summary>

   If `Popen` itself raises, `server` was never assigned, and the `finally` raises
   `NameError`, which hides the real error. It also terminates without waiting. `run.py`
   sets `background_server = None` before the `try` and checks it in the `finally`.
   </details>

5. Why does the Ctrl+C test have to run on its own during the fail-first run?
   <details><summary>Answer</summary>

   Before the fix, `main()` let `KeyboardInterrupt` escape. unittest treats an escaping
   `KeyboardInterrupt` as the user stopping the run, not as a test failure, so it stops the
   whole run and hides the results of the other tests. After the fix, `main()` turns it into
   `SystemExit(1)`, and the test asserts on that.
   </details>

### Defend the decision
1. "Why not just use `with subprocess.Popen(...) as server:`?"
   <details><summary>Model answer</summary>

   `Popen.__exit__` closes the pipes and *waits* for the child. It never terminates it. A
   server runs until told to stop, so the launcher would hang in `__exit__` instead of
   stopping it. Stopping it is a policy decision (terminate, a 5 s limit, then kill), and
   that is explicit in `stop_background_server`, called from a `finally`. A `with` block
   would fit if the child exited by itself, like the client under `subprocess.run`.
   </details>

2. "The launcher stops the background server but not the one in a window. Isn't that
   inconsistent?"
   <details><summary>Model answer</summary>

   It's the "own only what you started, and only what nobody else can reach" rule. A
   background server has no window, so if the launcher leaves it, nobody can see or stop it
   short of finding its process. A windowed server is visible: the user can keep it for
   another client, or press Ctrl+C there. A server already running on the port wasn't
   started by this launcher at all. Killing it could end someone else's session.
   </details>

3. "Why a 5 s limit before `kill()`, and why in `run.py` and not `config.py`?"
   <details><summary>Model answer</summary>

   `terminate()` gives the server a chance to close its socket and log "Server stopped". A
   healthy server exits in well under a second, so 5 s is generous and only matters for a
   stuck one. Without a limit, a stuck server would hang the launcher, the same "never wait
   for ever" rule as task 7.2. The value lives next to `STARTUP_TIMEOUT` because both are
   launcher-only. `config.py` holds what the server and client share.
   </details>
