---
id: 029
title: Exit non-zero when the client fails
commit: "fix: exit non-zero when the client fails"
step: 16 — address the 2026-10-21 mentoring code review (task 8.2, part 1)
date: 2026-11-23
tags: [python, exit-codes, sys-exit, signals, cli, unittest, mock]
---

# Exit non-zero when the client fails

## What we did
Task 8.2 says the launcher should pass on the client's exit code. But the client always
exited with 0: `client.main()` printed a clear message for each failure (journal 025) and
then returned `None`, which Python turns into exit status 0. Passing that on would still
report success for a refused connection. So 8.2 became two commits, and this is the first:
the client says how the session ended.

`main()` (`client.py:110`) now returns an exit code, and the `__main__` block calls
`sys.exit(main())` (`client.py:190`). There are three codes, in `config.py:50`:
- `EXIT_OK` (0): the user ended the session (end of input, Ctrl+C at the prompt) or the
  server confirmed `stop`.
- `EXIT_FAILURE` (1): a missing certificate, any connect or handshake failure
  (`connect()` returns `None`), a lost connection, a reply timeout, or a reply too long,
  malformed or the wrong shape.
- `EXIT_INTERRUPTED` (130): Ctrl+C while connecting or waiting for a reply.

`run_session` (`client.py:130`) returns `EXIT_OK` or `EXIT_FAILURE` at each of its exits.
No message changed. `tests/test_client.py` already reproduced every failure, so each case
gained an `assert_exit_code`, and four cases are new: `stop`, Ctrl+C at the prompt, a
missing certificate, and end of input. Before the fix, all 23 checks failed the same way
(`None != 1`, `None != 0`, `None != 130`). Then three real runs, without mocks: no server →
1, no certificate in the current folder → 1, and end of input against a real server in a
scratch copy → 0.

## How it fits
- **Plan:** Step 16, task 8.2, part 1 (`PLAN.md` Step 5, client; README "Exit codes").
  Part 2 makes `run.py` pass this code on and gives the launcher's own failures a code of
  their own.
- **Practice:**
  - *The exit code is a program's return value to its caller* (a shell, a CI job, a
    script, `run.py`). A printed message is for people; the exit code is for programs. A
    tool that prints "Cannot connect" and exits 0 tells a script that everything worked.
    The review plan assumed the client already did this, and reading the code before
    coding found that it didn't.
  - *Return the code from `main()` and exit only in `__main__`.* Tests call `main()` and
    compare a return value, with no `SystemExit` to catch. The same "thin `__main__`" idea
    as journal 027.
  - *Use shell conventions.* 0 is success, 1 a general error, and 128 + N "killed by signal
    N". Ctrl+C is SIGINT, signal 2, so 130. A script can then tell "the user gave up" from
    "it broke". Python's own advice is 2 for a command-line syntax error. The client takes
    no arguments, so it doesn't need that one.
  - *Ending a session yourself is a success.* End of input and Ctrl+C *at the prompt* are
    how a user leaves, so they give 0, the same as `stop`. Ctrl+C *while waiting* cuts off
    a request in progress, so it gets 130.
  - *When you'd choose differently:* a long-running service reports through logs and its
    supervisor, not through one exit code. Tools with many distinct failures, such as curl
    or git, define many codes. Three are enough for an interactive client.

## Commands used
- `python -m unittest tests.test_client` — the fail-first run (23 failures, all `None !=
  <code>`), then the passing run
- `python -m unittest discover tests` — the full suite after the fix, OK with 1 skip
- `grep -n -E "^\s+return$" client.py` — check that no bare `return` (exit code `None`) is
  left
- `python - <<'EOF' … EOF` — two scripted edits. The test edit worked; the `client.py` one
  stopped at its own check (`\\n` arrived as a real line break, the trap in
  [python -](../commands.md#python---run-a-script-from-stdin)). No file was changed, and
  exact edits did the rest
- `python client.py < /dev/null; echo "no server -> exit code $?"` — a real run with no
  server: exit code 1 ([`$?`](../commands.md#-file---redirect-stdin-read-the-exit-code))
- `(cd "$S" && python ".../client.py" < /dev/null; echo …)` — a real run from a folder
  without `server.crt`: exit code 1
- `(python server.py > server.log 2>&1 < /dev/null &)` — a throwaway server in a scratch
  copy (made with `git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S"`, plus a
  throwaway admin)
- `printf 'stop\n' | python client.py | tail -1; echo "${PIPESTATUS[1]}"` — the client's own
  exit code in a pipeline (0: the user-ended session, since `stop` needs a login)
- `netstat -ano | grep "127.0.0.1:65432" | grep LISTENING | awk '{print $NF}'` — the PID of
  the throwaway server ([netstat](../commands.md#netstat--ano-which-process-uses-a-port))
- `tasklist //FI "PID eq 44316"` — check that the PID is that `python.exe` before stopping it
- ⚠️ `taskkill //PID 44316 //F` — stop the throwaway server
  ([taskkill](../commands.md#taskkill-stop-a-windows-process))
- `rm -rf "$S/e2e"` — delete the scratch copy

## Read more
- [sys.exit](https://docs.python.org/3/library/sys.html#sys.exit) — Python docs · an integer argument is the exit status, `None` counts as 0, it raises `SystemExit`, and "Unix programs generally use 2 for command line syntax errors and 1 for all other kinds of errors".
- [`__main__`: the `sys.exit(main())` idiom](https://docs.python.org/3/library/__main__.html) — Python docs · "the return value of main is passed into sys.exit()", the pattern this commit adopts.
- [Exit Codes With Special Meanings](https://tldp.org/LDP/abs/html/exitcodes.html) — Advanced Bash-Scripting Guide · the table of reserved codes: 130 is "Script terminated by Control-C" (128 + 2). Old but still accurate on the conventions.
- [Bash Scripting Tutorial](https://www.freecodecamp.org/news/bash-scripting-tutorial-linux-shell-script-and-command-line-for-beginners/) — freeCodeCamp · beginner-friendly: `$?` and "a value of `0` indicates success, while any other value indicates an error".
- Related: [journal 025](025-client-error-messages.md) (the messages these codes go with), [journal 027](027-explain-a-taken-port.md) (the server's start-up failures exit 1 the same way).

## Quiz

### Revise
1. What exit status does this script end with, and why?
   ```python
   def main():
       print("Cannot connect")
       return

   if __name__ == "__main__":
       main()
   ```
   <details><summary>Answer</summary>

   0. `main()` returns `None`, and nothing calls `sys.exit`, so the interpreter ends
   normally with status 0. Even `sys.exit(None)` means 0. This was the client's bug.
   </details>

2. Multiple choice. The client is interrupted with Ctrl+C while waiting for a reply. Which
   code does it exit with, and where does the number come from?
   a) 1, a general error
   b) 2, a command-line syntax error
   c) 130, which is 128 + SIGINT (signal 2)
   d) -1, because it was killed
   <details><summary>Answer</summary>

   c. Shells report a command ended by signal N as 128 + N, and Ctrl+C sends SIGINT (2).
   The client catches the `KeyboardInterrupt` itself, prints "Interrupted" and returns 130
   to follow that convention.
   </details>

3. Why does Ctrl+C *at the prompt* exit with 0, while Ctrl+C *while waiting* exits with 130?
   <details><summary>Answer</summary>

   At the prompt, no request is in progress. Ctrl+C there is the user's way of leaving, like
   end of input, so the session ended normally. While waiting, a request was cut off, and
   the result of that command is unknown. A script should be able to tell those apart.
   </details>

4. In Bash, `printf 'help\n' | python client.py | tail -1; echo $?` prints which exit code?
   <details><summary>Answer</summary>

   `tail`'s, almost always 0. `$?` after a pipeline is the last command's status. The
   client's is in `${PIPESTATUS[1]}`, read straight after the pipeline. Running the client
   without a pipe also works.
   </details>

5. Spot the problem in this test:
   ```python
   def test_refused(self):
       self.create_connection.side_effect = ConnectionRefusedError
       with self.assertRaises(SystemExit) as raised:
           client.main()
       self.assertEqual(raised.exception.code, 1)
   ```
   <details><summary>Answer</summary>

   `main()` now *returns* the code. Only the `__main__` block calls `sys.exit`, so nothing
   raises `SystemExit`, and the test fails. Compare the return value instead:
   `self.assertEqual(client.main(), client.EXIT_FAILURE)`. That's the reason for
   `sys.exit(main())`: the code is a plain value that tests can check.
   </details>

### Defend the decision
1. "The plan said the launcher should pass on the client's exit code. Why did you change
   the client first?"
   <details><summary>Model answer</summary>

   Before coding, I read what the client actually returned. Every path ended in a bare
   `return`, so the exit code was always 0, even after "Cannot connect". Passing that on
   would have made the launcher report success for every failure: the fix would have looked
   done and fixed nothing. So the client reports failure first, in its own commit with its
   own tests, and the launcher change builds on that. Each commit is correct on its own.
   </details>

2. "Why only three exit codes? Wouldn't one per failure help a script more?"
   <details><summary>Model answer</summary>

   A script calling this client has three different reactions: carry on (0), report or
   retry (1), or stop because the user gave up (130). Separate codes for "refused" and
   "timed out" would be an API we'd have to keep stable, with no caller asking for it, so
   that's YAGNI. The printed message already says which failure it was. Tools such as curl
   need many codes because scripts branch on them. If one ever needs to here, say "retry
   when busy", that code can be added.
   </details>

3. "Why do the exit codes live in `config.py`?"
   <details><summary>Model answer</summary>

   They are a contract between two programs. The client sets them, and `run.py` will read
   them in part 2. `config.py` is the repo's single source for values that more than one
   module shares, like `HOST` and `PORT`. If the codes were literals in each file, they
   could drift apart without anything noticing. The README table documents them for people.
   </details>
