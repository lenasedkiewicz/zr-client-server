---
id: 016
title: Log server events with logging instead of print
commit: "refactor: log server events with logging instead of print"
step: 16 — address the 2026-10-21 mentoring code review (batch 3, task 3.1)
date: 2026-11-05
tags: [python, logging, unittest, assertlogs, tls, race-condition, security]
---

# Log server events with logging instead of print

## What we did
The server's runtime messages now go through a module-level logger (`server.py:33`) instead
of `print`. They have a level and a timestamp, and they stay out of the test output: a full
test run used to print 217 server lines and now prints none. Connect, disconnect, start and
stop are `INFO`. A failed handshake (`server.py:194`) is a `WARNING`, and so is a connection
lost on a read or a send (`server.py:172`, `server.py:181`). Those two losses were silent
before, so `handle_client` now takes `addr` to say who was dropped. `logging.basicConfig`
runs only under `__main__` (`server.py:230`), with `LOG_LEVEL` and `LOG_FORMAT` from
`config.py`.

Three decisions went beyond the plan. Messages for the person at the terminal (missing
certificate, admin setup) stay `print`, as the Logging HOWTO recommends for ordinary console
output. `server.py:36` adds a `NullHandler`, because an unconfigured `logger.warning` would
otherwise reach Python's last-resort handler and print to stderr during the tests. Output
moves from stdout to stderr; `run.py` already sends both to `server.log`
(`stderr=subprocess.STDOUT`), so the background mode keeps its log.

Task 3.1 was started on another machine and parked in a stash that was never pushed (see
journal 015 on `ci/github-actions`). This entry is a fresh implementation from `master`, so
that stash is now a duplicate. The number 016 leaves 015 free for that branch.

## How it fits
- **Plan:** Step 16, batch 3, task 3.1. Later batches can log new events with this logger
  from the start. Task 3.2 (redundant `except` classes, `BUFFER_SIZE`) is next on this branch.
- **Practice:**
  - **The entry point owns the configuration.** A module emits events; the application
    decides where they go. If an imported module called `basicConfig`, importing it would
    change global logging for its importer.
  - **Don't log secrets.** `login` and `register` carry passwords, so requests are never
    logged. `test_logs_never_contain_passwords` guards this, including a wrong password.
  - **Watch a test fail for the right reason.** Two new tests first failed with a
    `TypeError` on the new `addr` argument, not on a missing log line. They only prove the
    logging once the signature exists.
  - **A flaky test is information.** Logging exposed a race that `print` had hidden. In
    TLS 1.3 the client is done once it has sent its last handshake message, while the server
    still has to read it. `wrap_socket` can return on the client, and a quick `close()` then
    aborts the server's handshake (`WinError 10053`). `master` logs the same failures, so
    the race wasn't new; only the new tests depended on it. The fix was to wait for a reply
    before disconnecting and to match log lines by port, not by position in the list.
- **When you'd choose differently:** `print` is fine for a small throwaway script. A
  long-running service often logs structured JSON to stdout for a collector to read.
  A published library uses `NullHandler` the same way, but some teams leave the last-resort
  output on, since the docs call it the best default behaviour.
- **Known gaps:** `run.py`'s readiness probe connects with plain TCP and closes, so every
  launch logs one harmless `TLS handshake failed` warning. Batch 8 owns the launcher
  readiness work. Malformed messages aren't logged, because that session continues.

## Commands used
- `git fetch --all --prune` — download every remote's branches and forget deleted ones.
  See [git fetch](../commands.md#git-fetch-download-new-commits-from-the-remote).
- `git for-each-ref --sort=-committerdate --format='…' refs/heads refs/remotes`,
  `git rev-list --count master..$b` — list branches by date and count commits ahead of
  `master`, to find yesterday's work.
  See [git for-each-ref](../commands.md#git-for-each-ref-list-branches-and-tags-with-a-format),
  [git rev-list](../commands.md#git-rev-list---count-count-commits).
- `git stash list`, `git worktree list`, `git reflog -15 --date=short` — look for the parked
  work on this machine.
  See [git reflog](../commands.md#git-reflog-show-where-head-has-been),
  [git worktree](../commands.md#git-worktree-list-list-working-folders).
- `git fsck --unreachable --no-reflogs` — look for a dropped stash; found only October ones.
  See [git fsck](../commands.md#git-fsck-check-the-repository-and-find-lost-commits).
- `git grep -n -i -E '…' origin/ci/github-actions`, `git show`, `git diff master...<branch>`,
  `git merge-base --is-ancestor` — read the CI branch without checking it out.
  See [git grep](../commands.md#git-grep-search-tracked-files).
- `gh pr list --state all --limit 6`, `gh api repos/…/actions/runs --jq '…'`,
  `gh api repos/…/branches --jq '.[].name'` — check PRs, CI runs and remote branches.
  See [gh api](../commands.md#gh-api-call-the-github-api).
- `git config user.email`, `hostname`, `python --version`, `wsl.exe -l -q` — compare this
  machine with the one journal 015 describes.
  See [git config](../commands.md#git-config-read-a-setting).
- `git checkout -b refactor/logging-and-cleanups` — start the batch 3 branch.
- `python - <<'EOF' … EOF` — apply exact text replacements, keeping CRLF line endings.
  See [python -](../commands.md#python---run-a-script-from-stdin).
- `python -m unittest tests.test_server.DroppedClientLoggingTest …` — watch the new tests
  fail first. See [python -m unittest](../commands.md#python--m-unittest-run-the-test-suite).
- `python -m unittest discover tests` — final result: 67 tests pass, 1 skipped on Windows.
- `for i in $(seq 1 20); do python -m unittest discover tests 2>&1 | grep -a -E '^(OK|FAILED|FAIL:|ERROR:)'; done | sort | uniq -c`
  — repeat the suite to catch the race: 20 of 20 passed after the fix.
- `python "$SP/probe.py"` — throwaway check of the certificate and ports seen on loopback.
  It ruled out interception on this machine.
- `tasklist | grep -i -E 'avast|…'` — look for security software; none matched.
  See [tasklist](../commands.md#tasklist-list-running-processes).
- `git stash push -q -u -m '…'`, `git stash pop -q` — run the suite on `master` for a
  baseline, including no untracked files left behind.
  See [git stash](../commands.md#git-stash-put-changes-aside-for-a-moment).
- `python "$SP/realrun.py" "$REPO" "$SP/run"` — start the real `server.py` from a scratch
  folder with test certificates and a throwaway admin, log in, send `stop`.
- `cat`, `sed -n`, `grep`, `cut`, `wc -l`, `cp`, `mkdir -p` — read files and filter output.
- `git add …`, `git commit` — record this chunk.

## Read more
- [Logging HOWTO](https://docs.python.org/3/howto/logging.html) — Python docs · the "when to use logging" table: `print` for console output, `logger.info` for normal events, `logger.warning` for problems worth noting
- [Configuring Logging for a Library](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library) — Python docs · `lastResort`, `NullHandler`, and why handlers are the application's choice
- [TestCase.assertLogs](https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs) — Python docs · what it captures, and that it fails when nothing is logged
- [Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — OWASP · "Data to exclude": passwords, access tokens and connection strings
- [RFC 8446: TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html) — IETF · Section 2, Figure 1: the message flow behind the race in the tests
- [What Are Logs in Programming?](https://www.freecodecamp.org/news/what-are-logs-in-programming/) — freeCodeCamp · a beginner's view of levels, and why logs beat `print`

## Quiz

### Revise

1. Which level fits "a client's TLS handshake failed, but the server carries on"?
   a) `DEBUG` b) `INFO` c) `WARNING` d) `CRITICAL`
   <details><summary>Answer</summary>

   c. Something unexpected happened, but the program keeps working. `CRITICAL` means the
   program itself may be unable to continue, and `INFO` means things are working as expected.
   </details>

2. What does `logging.getLogger(__name__)` return in `server.py` when you run
   `python server.py`, and when a test imports it?
   <details><summary>Answer</summary>

   A logger named `__main__` when it runs as a script, and `server` when imported. That's why
   the tests use `assertLogs("server", ...)`. Both propagate to the root logger.
   </details>

3. Without the `NullHandler` and with no configuration, what happens to
   `logger.info("x")` and `logger.warning("y")`?
   <details><summary>Answer</summary>

   `info` is dropped, because the effective level defaults to `WARNING`. `warning` goes to
   `logging.lastResort`, which writes the bare message to stderr. This is why the plan's "stay
   quiet by default" needed one more line.
   </details>

4. What happens to this test if the code logs nothing inside the block?
   ```python
   with self.assertLogs("server", level="WARNING") as logs:
       do_something()
   self.assertNotIn("secret", "\n".join(logs.output))
   ```
   <details><summary>Answer</summary>

   It fails at the end of the `with` block, because `assertLogs` needs at least one matching
   message. To assert that nothing is logged, use `assertNoLogs` (Python 3.10+).
   </details>

5. Spot the bug in this test, given a TLS 1.3 connection:
   ```python
   self.connect()
   self.disconnect()
   self.assertIn("Client connected", logs_from_server())
   ```
   <details><summary>Answer</summary>

   `connect()` can return while the server is still reading the client's last handshake
   message. Closing at once can abort the server's handshake, so it logs `TLS handshake
   failed` and never `Client connected`. Wait for a reply before disconnecting.
   </details>

6. Why write `logger.info("Client connected: %s:%s", host, port)` instead of an f-string?
   <details><summary>Answer</summary>

   The message is formatted only if a handler will really emit it, so a disabled level costs
   almost nothing. The record also keeps the template and arguments separately. Here it's
   mainly convention, because connect events are rare.
   </details>

### Defend the decision

1. Why is logging configured only under `__main__`, and never in an imported module?
   <details><summary>Model answer</summary>

   Logging configuration is global to the process. If `server.py` configured it on import,
   anything that imported it, such as the tests, would get its handlers and format. The module
   emits events and the application chooses the destination. The cost is one extra step in the
   entry point. It would be different in a single-file script that nobody imports.
   </details>

2. Which requests must never be logged in full here, and how do you know they aren't?
   <details><summary>Model answer</summary>

   `login` and `register`, because their `args` hold a plain-text password. TLS protects it on
   the wire and PBKDF2 protects it at rest, so a log file would be the weakest copy. Log files
   are often kept longer and read by more people. The server therefore logs connection events
   and never request bodies, and a test captures logs at `DEBUG` through a registration and a
   failed login. A test can't prove every future path, so a code review still matters.
   </details>

3. Why keep `print` for the missing-certificate message but use `logging` for connections?
   <details><summary>Model answer</summary>

   The audience differs. The certificate help is instructions for the person who just ran the
   command, and timestamps and levels would only add noise. Connection events are a record of
   what a running server did, read later, perhaps from a file. The alternative was one
   mechanism for everything, which is simpler but makes the setup instructions harder to read.
   </details>

4. A new test failed on every run, and another failed in about one run out of four. Why not
   add a `sleep` or a retry?
   <details><summary>Model answer</summary>

   A sleep only makes a race less likely and slows every run. The cause was a test that
   assumed the handshake had finished on both sides. A reply from the server is a real signal
   that it had, so the test now waits for that, like the `listening` event from journal 011.
   The second test assumed a position in the log list, so it now matches on the client's port.
   After the fix, 20 full runs passed in a row. That's strong evidence, not proof, so the
   reasoning about the cause matters as much as the count.
   </details>
