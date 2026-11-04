---
id: 011
title: Wait for the server to listen before connecting
commit: "test: wait for the server to listen before connecting"
step: 16 — address the 2026-10-21 mentoring code review (batch 2, task 2.1, first half)
date: 2026-10-29
tags: [python, threading, event, race-condition, socket, listen, unittest, flaky-tests]
---

# Wait for the server to listen before connecting

## What we did

`ServerTest.setUp` started `serve_forever` in a thread and connected straight away. But
`listen()` runs *inside* that thread, so nothing guaranteed it had run before the test's
`connect()`. A socket that is bound but not yet listening refuses connections, so the test
could fail at random. It's rare on a fast Windows machine and more likely on a loaded CI
runner.

The server now has a `threading.Event` called `listening` (`server.py:54`). `serve_forever`
sets it right after `listen()` (`server.py:193`) and clears it in the `finally` that closes
the socket (`server.py:213`), so the flag always means "listening now". `setUp` waits for it
with a timeout before connecting (`tests/test_server.py:56`). If the server never starts,
the test fails with "server did not start listening" instead of an unclear
`ConnectionRefusedError`. A new test, `test_listening_is_set_only_while_serving`, checks
the whole cycle: not set after `bind`, set while serving, cleared after the loop ends.
Without the server change, 36 server tests fail with `AttributeError`.

## How it fits
- **Plan:** Step 16, batch 2 ("test foundations"), first half of task 2.1. Every later
  batch adds socket tests on top of this `setUp`. The second half (cleanups registered
  with `addCleanup`) is the next commit.
- **Practice:** *synchronise on a signal, not on time.* `time.sleep(0.1)` before
  `connect()` would still be a race, just a rarer one, and it slows every test. Waiting on
  a flag the server sets itself is exact and costs nothing when the server is fast. It's
  the same idea as a readiness probe (Kubernetes) or `sd_notify(READY=1)` (systemd): the
  service announces it is ready instead of the caller guessing. The timeout on `wait()`
  matters too. Without it, a server that crashes before `listen()` would hang the suite
  instead of failing it.
- **When you'd choose differently:** an `Event` only works between threads of one process.
  To wait for a server in another process (`run.py`, batch 8), you'd retry `connect()`
  with a deadline, or have the child process write "ready" to a pipe. Martin Fowler's
  advice applies to both cases: use a callback if you have one, otherwise poll with a
  small interval and a generous limit, never a bare sleep.
- **Trade-off:** `Server` gains an attribute that only the tests use today. It describes
  real server state, though, and a future health check or launcher could use it too.

## Commands used
- `git checkout master` / `git pull --ff-only` / `git checkout -b test/test-foundations`: update `master` after PR #2 was merged and branch for batch 2
- `git status -sb`, `git log --oneline origin/fix/server-survives-bad-client -1`: check whether batch 1 was pushed
- `gh pr list --head fix/server-survives-bad-client`: check whether batch 1 already had a PR
- `grep -n "def \|listen\|bind\|threading\|Event\|class " server.py`, `sed -n 1,80p tests/test_server.py`: find where `listen()` runs and how `setUp` starts the server
- `python - <<'EOF' … EOF`: apply the exact string replacements to `server.py` and `tests/test_server.py`
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED)|Error|FAIL:"`: full suite, summary only (45 tests, OK, 1 skipped)
- `git stash -q -- server.py`: temporarily undo only the server change, to check that the tests fail without it
- `python -m unittest tests.test_server 2>&1 | grep -E "…AttributeError" | sort | uniq -c`: count the identical failures (36 × `AttributeError`)
- `git stash pop -q`: bring the server change back
- `git diff --stat`, `git status --short`: check what is about to be committed

## Read more
- [threading: Event objects](https://docs.python.org/3/library/threading.html#event-objects): Python docs · `set`, `clear`, `is_set`, and `wait(timeout)` returning `False` on timeout (which is why the test asserts on its return value)
- [socket.listen](https://docs.python.org/3/library/socket.html#socket.socket.listen): Python docs · "Enable a server to accept connections". Before this call, a bound socket refuses connections
- [Eradicating Non-Determinism in Tests](https://martinfowler.com/articles/nonDeterminism.html): martinfowler.com · the "Asynchronous Behavior" section: "never use bare sleeps", use a callback or polling with a limit instead
- [Race condition](https://en.wikipedia.org/wiki/Race_condition): Wikipedia · behaviour that "is dependent on the sequence or timing of uncontrollable events"
- [How to Fix a Race Condition With Timing in Python](https://superfastpython.com/thread-race-condition-timing/): Super Fast Python · a worked example of a timing race fixed with a `threading.Event`
- [Entering into the World of Concurrency with Python](https://www.freecodecamp.org/news/concurrency-in-python/): freeCodeCamp · beginner intro to `threading.Thread`, `start()` and `join()` (the building blocks `setUp` uses)
- Related: [concept 003, except clause scope](../concepts/003-except-clause-scope.md) and journal [009](009-failed-send-ends-only-that-connection.md), which used an `Event` to make an RST test deterministic

## Quiz

### Revise
1. What does `Event.wait(timeout=5)` return if the flag is never set?
   <details><summary>Answer</summary>

   `False`, after about 5 seconds. It returns `True` as soon as the flag is set. That's why
   the test wraps it in `assertTrue(..., "server did not start listening")`. A bare
   `wait(5)` would carry on silently and fail later with a less helpful error.
   </details>
2. A socket has had `bind()` called but not `listen()`. A client calls `connect()` to it.
   What happens? a) the connection waits in the backlog; b) it is refused; c) it succeeds
   and hangs; d) `bind` raises.
   <details><summary>Answer</summary>

   b. Without `listen()`, the kernel has no queue of pending connections for that socket,
   so a TCP SYN is answered with RST, and the client sees `ConnectionRefusedError`. Linux
   refuses at once. Windows retries the SYN a few times first, so the refusal can take
   about 2 s there.
   </details>
3. Why is `listen()` the right moment to set the flag, and not the end of `__init__` (after
   `bind()`)?
   <details><summary>Answer</summary>

   `bind()` reserves the address, but only `listen()` makes the socket accept
   connections. If the flag were set in `__init__`, the race would still be there: the
   event would say "ready" before the server thread had called `listen()`.
   </details>
4. Spot the bug: `time.sleep(0.1); self.connect()` in `setUp`, as a fix for the race.
   <details><summary>Answer</summary>

   It still assumes the thread reaches `listen()` within 100 ms. On a loaded machine it
   may not, so the test stays flaky. It also adds 0.1 s to every test even when the server
   was ready at once. A signal is both exact and free.
   </details>
5. Why does `serve_forever` call `listening.clear()` in its `finally`?
   <details><summary>Answer</summary>

   So the flag stays true to its name: after the loop ends, the socket is closed and no
   longer listening. Anyone checking `is_set()` after a stop, such as the new test, gets
   the truth instead of a stale `True`.
   </details>

### Defend the decision
1. "Why did you add a `threading.Event` to the production `Server` class just for tests?
   Isn't that test code leaking into production?"
   <details><summary>Model answer</summary>

   The event describes real server state ("am I accepting connections?"), not a test hook.
   A health check or launcher could use it too. The alternative was a retry loop around
   `connect()` in the test. That works, but it hides the reason for the wait, and it
   catches every `ConnectionRefusedError`, including ones from real bugs. I'd keep
   test-only seams out of production code. This is a readiness signal, which is a normal
   part of a server's interface.
   </details>
2. "The launcher (`run.py`) also starts a server and then connects. Why not use the same
   `Event` there?"
   <details><summary>Model answer</summary>

   `run.py` starts the server in a *separate process* (a new console window), and a
   `threading.Event` lives in one process's memory. Across processes you need an OS-level
   channel: retry `connect()` until a deadline, have the child write "ready" to a pipe, or
   use `multiprocessing.Event`. That fix belongs to batch 8 of the plan.
   </details>
3. "Why a 5-second timeout? Why not wait forever?"
   <details><summary>Model answer</summary>

   Without a timeout, a server that crashed before `listen()`, for example on a bad
   certificate, would hang the whole suite with no output. 5 s is far more than a healthy
   start needs (milliseconds), so it never causes a false failure, and a real failure
   still shows up quickly with a clear message. It matches the 5 s the tests already use
   for socket and `join` timeouts.
   </details>
