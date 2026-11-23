---
id: 030
title: Exit with the client's exit code
commit: "fix: exit with the client's exit code"
step: 16 — address the 2026-10-21 mentoring code review (task 8.2, part 2)
date: 2026-11-23
tags: [python, subprocess, exit-codes, signals, keyboardinterrupt, launcher, unittest, mock]
---

# Exit with the client's exit code

## What we did
After journal 029 the client reports how a session ended (0, 1 or 130), but `python run.py`
still threw that away. It ran the client with `subprocess.run`, ignored the result, and
exited with 0. Its own failures all exited with 1, the same code as "the client failed".

Now `main()` (`run.py:186`) returns the client's code, and `__main__` calls
`sys.exit(main())` (`run.py:210`). The launcher keeps two codes of its own, for failures
before the client starts:
- `EXIT_LAUNCHER_FAILED` (2, `config.py:55`): no terminal for the admin prompt, end of input
  at that prompt, or a server that didn't start within 5 s.
- `EXIT_INTERRUPTED` (130): Ctrl+C at the admin prompt or during the start-up wait. It's
  the same code the client uses, because the meaning is the same: the user gave up.

Two details needed more than passing a number on:
- **Ctrl+C while the client runs.** Ctrl+C goes to every process in the terminal, so the
  client gets it too and handles it: "Disconnecting" at the prompt, "Interrupted" while
  waiting. `subprocess.run` reacts to the `KeyboardInterrupt` by waiting 0.25 s and then
  killing the child (the CPython source, bpo-25942; the docs don't describe it), and the
  real code is lost. `run_client()` (`run.py:171`) now uses `with subprocess.Popen(...)`
  and calls `wait()` again after each `KeyboardInterrupt`, so the client decides when it
  ends.
- **A child killed by a signal.** On POSIX, `Popen.returncode` is -N for "killed by signal
  N". `sys.exit(-2)` would show up as 254 in a shell, so `shell_exit_code()`
  (`run.py:162`) turns -N into 128 + N, the shell's own rule.

`tests/test_run.py` now has a base class with the mocks and no tests (`LauncherTestCase`).
The 8.1 cleanup tests and the new `ExitCodeTest` both inherit it, so nothing runs twice. The
new tests cover:
- the review plan's case (the client returns 3, `main()` returns 3)
- a client failure passed on from a reused server
- Ctrl+C while the client runs (wait again, no kill)
- -2 → 130
- the three admin-prompt outcomes

Before the fix, 5 tests failed with `1 != 2` or `1 != 130`. The other 8 errored because the
old `subprocess.run` called the mocked `Popen` and couldn't unpack `communicate()`. Then
three real runs: no admin and end of input → 2; a real background server and end of input
→ 0; a plain TCP listener on the port → the client's 1, passed through.

## How it fits
- **Plan:** Step 16, task 8.2, done (`PLAN.md` Step 7; README "Exit codes"). Next is 8.3:
  the third real run shows why. The launcher "reused" a listener that wasn't our server,
  and the client blamed a busy server.
- **Practice:**
  - *A wrapper is transparent.* A program that runs another one passes on the child's
    code and keeps codes of its own only for its own failures. GNU `timeout` returns the
    command's status, except 124 when it had to stop the command. `make` and `npm run`
    also fail with the failing step's code.
  - *Let the process that owns the signal handle it.* Both processes share the terminal, and
    the client already has a good answer to Ctrl+C, so the parent waits and doesn't kill.
    The opposite choice, killing after a short grace period, is right for `subprocess.run`
    as a general tool: it can't know whether the child handles SIGINT.
  - *Translate conventions at the boundary.* Python's -N and the shell's 128 + N mean the
    same thing in different notations. The launcher speaks to a shell, so it uses the
    shell's.
  - *Distinct codes for distinct callers' decisions.* 2 lets a script tell "set-up problem,
    fix your environment" apart from "the client failed, maybe retry".
  - *When you'd choose differently:* a supervisor that restarts children logs their codes
    instead of passing them on. A launcher for a GUI app often doesn't wait at all.

## Commands used
- `python -m unittest -v tests.test_run` — the fail-first run (5 failures, 8 errors), then
  14 passing
- `python -m unittest tests.test_run 2>&1 | grep -a -E "^[A-Za-z]*Error:" | sort | uniq -c`
  — group the failures by reason
  ([sort / uniq -c](../commands.md#sort--uniq--c-count-repeated-lines))
- `sed -i 's/…run.EXIT_FAILURE…/…1  # EXIT_FAILURE…/' tests/test_run.py` — `run` doesn't
  import `EXIT_FAILURE`, so the tests compare with the plain value
- `python -m unittest discover tests` — the full suite, OK with 1 skip
- `python run.py < /dev/null; echo "… $?"` — a real run without an admin: exit code 2
- `git status --short users.json` — meant to show the run didn't write the users file. It
  proves nothing: the file is git-ignored, so `git status` never lists it
  ([gotcha](../commands.md#git-status-show-the-working-tree-state))
- `git check-ignore -v users.json` — confirm that it's ignored, and by which rule
  ([git check-ignore](../commands.md#git-check-ignore-why-is-a-file-ignored))
- `ls -l --time-style=full-iso users.json` and `python -c "from users import UserStore; …"`
  — the real check: last changed 2026-10-08, no accounts ([ls](../commands.md#ls-list-files))
- `git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S"` — a scratch copy with a throwaway
  admin, for the background run
- `timeout 60 python -c "import sys, run; run.start_server_in_window = lambda: False; sys.exit(run.main())" < /dev/null`
  — the real background path: exit code 0, server stopped, port free
- `timeout 60 python -c "import socket, subprocess, sys; …"` — hold the port with a plain
  TCP listener and run `run.py` under it: the client's 1 comes through
- `python -c "import subprocess; print(subprocess.__file__)"`, then `grep -n` and `sed -n`
  on that file — read what `subprocess.run` does on `KeyboardInterrupt`, since the docs
  don't say
- `rm -rf "$S"` — delete the scratch copy

## Read more
- [Popen and CompletedProcess.returncode](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.returncode) — Python docs · "A negative value -N indicates that the child was terminated by signal N (POSIX only)", the reason for `shell_exit_code`.
- [Popen as a context manager](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Python docs · "on exit, standard file descriptors are closed, and the process is waited for": why `run_client` uses `with Popen(...)`.
- [timeout(1)](https://man7.org/linux/man-pages/man1/timeout.1.html) — Linux man pages · a well-known transparent wrapper: 124 if the command timed out, "the exit status of COMMAND otherwise".
- [Exit Codes With Special Meanings](https://tldp.org/LDP/abs/html/exitcodes.html) — Advanced Bash-Scripting Guide · 128 + N for a fatal signal, 130 for Ctrl+C.
- [Bash Scripting Tutorial](https://www.freecodecamp.org/news/bash-scripting-tutorial-linux-shell-script-and-command-line-for-beginners/) — freeCodeCamp · beginner-friendly: `$?`, and 0 means success.
- Related: [journal 029](029-client-exit-codes.md) (the codes this commit passes on), [journal 028](028-always-stop-the-background-server.md) (the `try/finally` the exit code now leaves through).

## Quiz

### Revise
1. A client killed by SIGTERM (signal 15) on Linux. What is `Popen.returncode`, and what
   does `run.py` exit with?
   <details><summary>Answer</summary>

   `returncode` is -15. `shell_exit_code` turns it into 128 + 15 = 143, the code a shell
   shows for a command killed by SIGTERM. Passing -15 to `sys.exit` would show 241, because
   the status is cut to 8 bits: -15 mod 256.
   </details>

2. Multiple choice. Which `run.py` exit code means "the launcher itself failed"?
   a) 1
   b) 2
   c) 124
   d) 130
   <details><summary>Answer</summary>

   b. 1 is the client's failure, passed on. 130 is Ctrl+C, from either program. 124 is GNU
   `timeout`'s own code, not ours.
   </details>

3. What happens to the client when you press Ctrl+C while `subprocess.run([...client...])`
   is waiting for it?
   <details><summary>Answer</summary>

   Both processes get SIGINT. `run` catches the `KeyboardInterrupt`, waits 0.25 s for the
   child, then calls `kill()` and re-raises. If the client takes longer to finish, it's
   killed, and its exit code is lost. `run_client` waits again instead.
   </details>

4. Why does `main()` need `exit_code = run_client()` *inside* the `try`, with
   `return exit_code` *after* the `finally`?
   <details><summary>Answer</summary>

   The code is only known once the client has run, which happens inside the `try`. The
   `finally` must stop the background server first, and the "Server is still running"
   message comes after it. If the `try` exits early through `sys.exit(…)`, `exit_code` is
   never needed, because the `SystemExit` carries the code.
   </details>

5. Spot the bug:
   ```python
   class ExitCodeTest(BackgroundServerCleanupTest):
       def test_client_exit_code_is_passed_on(self): ...
   ```
   <details><summary>Answer</summary>

   unittest collects every `test_*` method of a class, inherited ones included, so all the
   cleanup tests would run a second time under `ExitCodeTest`. Put the shared `setUp` in a
   base class with no tests (`LauncherTestCase`) and inherit that.
   </details>

### Defend the decision
1. "Why does the launcher keep waiting on Ctrl+C instead of killing the client?"
   <details><summary>Model answer</summary>

   Both processes share the terminal, so the client gets the same SIGINT, and it has its own
   answer. At the prompt it disconnects cleanly and exits 0; while waiting it exits 130. If
   the launcher killed it, as `subprocess.run` does after 0.25 s, the client could be cut
   off mid-disconnect, and its exit code would be lost. The risk is a client that ignores
   Ctrl+C and hangs. Ours doesn't, and a second terminal can still kill it. A general tool
   like `subprocess.run` can't assume the child handles SIGINT, so it is right to kill;
   we know our child.
   </details>

2. "Why give the launcher its own code 2 instead of reusing 1?"
   <details><summary>Model answer</summary>

   Because the caller reacts differently. 1 from the client means the session failed: the
   server is down or busy, so maybe retry. 2 means the launcher couldn't even set up a server:
   there's no admin, no terminal to create one, or the server didn't start. That's an
   environment problem to fix, not something to retry. Python suggests 2 for usage errors,
   but the launcher takes no arguments, and the client never returns 2, so the code is
   unambiguous here. The README table documents it.
   </details>

3. "Why convert -N to 128 + N? Python already tells you the signal."
   <details><summary>Model answer</summary>

   The launcher's caller is a shell or a script, not Python. Shells report "killed by signal
   N" as 128 + N, and `sys.exit(-N)` doesn't give that: the exit status is 8 bits, so -2
   becomes 254, which means nothing. Translating at the boundary keeps the launcher
   transparent. A script sees the same 130 whether the client was run directly or through
   `run.py`.
   </details>
