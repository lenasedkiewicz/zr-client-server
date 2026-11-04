---
id: 012
title: Register test cleanups with addCleanup
commit: "test: register test cleanups with addCleanup"
step: 16 — address the 2026-10-21 mentoring code review (batch 2, task 2.1, second half)
date: 2026-10-30
tags: [python, unittest, addCleanup, teardown, resource-lifecycle, lifo, threading, socket]
---

# Register test cleanups with addCleanup

## What we did

`tearDown` used to do four things in a row: send `stop`, close the socket and its file, join
the server thread and delete the temp dir. If one step raised, every step after it was
skipped. A `stop` that timed out, for example, left the thread running and the temp dir on
disk. And if `setUp` failed partway (say, the new `listening.wait` assert from 011),
`tearDown` didn't run at all, so the half-built fixture leaked.

Now there's no `tearDown`. Each cleanup is registered with `addCleanup` right after its
resource exists. In `setUp`, the temp dir comes first (`tests/test_server.py:44`), then
`thread.join` and `stop_server` (`:58`–`:59`). `connect()` registers `sock.close` and
`sock_file.close` for **every** connection it opens (`:82`, `:84`), so the reconnects in
`assert_server_still_serves` get cleaned up too. Cleanups run last-in-first-out, so by the
time `stop_server` (`:64`) runs, the test's own socket is already closed. That matters
because the server takes one client at a time: `stop_server` opens a fresh connection, logs
in as `teardown` and sends `stop`. Its `finally` sets `server.running = False` (`:73`), so
even if `stop` fails, the accept loop exits within a second and the `join` that follows
doesn't hang. I checked this with a throwaway subclass whose `request` raises: the error was
reported, the thread ended and the temp dir was gone.

## How it fits
- **Plan:** Step 16, batch 2, the second half of task 2.1 (the first half was 011). With
  start-up and cleanup both reliable, 2.2 (unit tests without sockets) and 2.3 (a stricter
  SemVer regex) finish batch 2. All later batches add tests on top of this fixture.
- **Practice:** *register the undo right after the do.* It's the same idea as `with`,
  `try/finally`, `contextlib.ExitStack` and Go's `defer`. A cleanup is registered only once
  its resource exists, so a half-finished `setUp` releases exactly what it created and
  nothing else. `unittest` runs each cleanup in its own guard (`doCleanups` wraps each one in
  `testPartExecutor`), so one failing cleanup is reported and the others still run. A
  `tearDown` is a single function, and its first exception ends it. LIFO order matches
  dependencies: what was created later may depend on what was created earlier, so it should
  go first.
- **Trade-off:** cleanup is now spread across `setUp` and `connect()` instead of sitting in
  one place. You read it as "each resource carries its own cleanup", not as a list at the
  bottom. Closing a socket twice (`disconnect()`, then its cleanup) is harmless, because
  `close()` is idempotent.
- **When you'd choose differently:** a trivial fixture that can't fail half-way reads fine
  with `tearDown`. A resource that fits one block reads better as `with`. On Python 3.11+,
  `self.enterContext(cm)` does enter-plus-`addCleanup` in one call, but the project supports
  3.10, so not here. pytest would use a `yield` fixture, where the code after `yield` is the
  cleanup.

## Commands used
- `python -m unittest discover tests 2>&1 | Select-Object -Last 8`: ran the suite in
  PowerShell (45 tests, OK, 1 skipped on Windows)
- `SP="…/scratchpad"`: stored the scratch directory path in a shell variable for the next
  commands (Git Bash)
- `cat > "$SP/check_cleanup.py" <<'EOF' … EOF`: wrote a throwaway check whose `request`
  raises during cleanup
- `cd /d/Programming/zr-client-server && python "$SP/check_cleanup.py" 2>&1 | grep -E "errors reported|thread alive|tmp dir|RuntimeError" | head`:
  ran it from the repo root and kept only the result lines
- `python -c "…" 2>&1 | tail -1`: confirmed that cleanups run LIFO and keep going after one
  raises
- `git add` / `git commit -F -`: staged and committed the code with this entry

## Read more
- [How to Write Unit Tests for Instance Methods in Python](https://www.freecodecamp.org/news/how-to-write-unit-tests-for-instance-methods-in-python/): freeCodeCamp · `setUp`/`tearDown` and `setUpClass`/`tearDownClass` from the basics; read it first if fixtures are new
- [TestCase.addCleanup](https://docs.python.org/3/library/unittest.html#unittest.TestCase.addCleanup): Python docs · LIFO order, "still called if `setUp()` fails", `doCleanups`, and `enterContext` (3.11+)
- [`unittest/case.py`, `doCleanups`](https://github.com/python/cpython/blob/3.13/Lib/unittest/case.py): CPython source · each cleanup runs inside its own `testPartExecutor`, which is why one failure doesn't stop the rest (the docs don't say this)
- [contextlib.ExitStack](https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack): Python docs · the same LIFO cleanup stack outside tests, including "cleaning up in an `__enter__` implementation"

## Quiz

### Revise
1. In what order do cleanups registered with `addCleanup` run?
   <details><summary>Answer</summary>

   Last-in-first-out: the most recently registered cleanup runs first. That's the reverse
   of creation order, the same as nested `with` blocks.
   </details>
2. `setUp` creates a temp dir, then fails on an assert before starting the server thread.
   What happens with (a) a `tearDown`, (b) an `addCleanup` registered right after the temp
   dir was created?
   <details><summary>Answer</summary>

   (a) `tearDown` isn't called when `setUp` raises, so the temp dir leaks. (b) The
   cleanup runs anyway: `doCleanups` is called after a failed `setUp`, and only the
   cleanups registered so far (here, just the temp dir) run.
   </details>
3. Three cleanups are registered: A, then B (which raises), then C. Which run, and how is
   the test reported?
   a) C only, error  b) C and B, error  c) C, B and A, error  d) A, B and C, pass
   <details><summary>Answer</summary>

   c). They run in the order C, B, A. B's exception is caught by its own
   `testPartExecutor` and recorded as an error, and the loop moves on to A.
   </details>
4. Why does `stop_server` open a **new** connection instead of reusing `self.sock`?
   <details><summary>Answer</summary>

   Cleanups are LIFO. `self.sock` was registered after `stop_server`, so it is already
   closed by the time `stop_server` runs. Besides, a test may have left its connection
   mid-conversation (for example, with a half-sent line). The server serves one client at a
   time, so once the old socket is closed, it accepts the fresh one.
   </details>
5. Spot the bug: `self.addCleanup(self.thread.join(timeout=5))`
   <details><summary>Answer</summary>

   `join` is called immediately, during `setUp`. The server thread is still running, so the
   call blocks for 5 seconds. Its return value, `None`, is what gets registered, and calling
   it at cleanup time raises `TypeError`. Pass the function and its arguments separately:
   `self.addCleanup(self.thread.join, timeout=5)`.
   </details>

### Defend the decision
1. "Why `addCleanup` instead of wrapping `tearDown` in `try/finally`?"
   <details><summary>Model answer</summary>

   `try/finally` in `tearDown` would need one nested block per resource to make each step
   independent. It still wouldn't run after a failed `setUp`, and it couldn't know which
   resources were actually created. `addCleanup` puts the release next to the acquire,
   runs only what exists, isolates each step's failure and supports reconnects: every
   `connect()` registers its own socket. The cost is that cleanup isn't all in one place.
   For a trivial fixture, `tearDown` is fine.
   </details>
2. "Why the `server.running = False` fallback, if you already send `stop`?"
   <details><summary>Model answer</summary>

   `stop` goes over the network and needs a working server and a login, so if a test
   broke the server, it may fail. Without the fallback, the next cleanup, `join(timeout=5)`,
   would wait five seconds and return with a thread still running, which leaks into later
   tests. Setting the flag directly makes the accept loop exit on its next one-second
   timeout. Why not *only* use the flag? Every test would then pay up to a second at
   teardown, so the fast path (`stop`) stays and the flag is the safety net.
   </details>
3. "Why not `self.enterContext(tempfile.TemporaryDirectory())`? It's shorter."
   <details><summary>Model answer</summary>

   `enterContext` was added in Python 3.11, and the project promises 3.10+. It's the
   same mechanism (it registers `__exit__` with `addCleanup`), so after a bump to 3.11 it
   would be a pure readability refactor. Until then, `addCleanup(self.tmp_dir.cleanup)` does
   the same job.
   </details>
