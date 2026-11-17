---
id: 022
title: Measure uptime with a monotonic clock
commit: "fix: measure uptime with a monotonic clock"
step: 16 — address the 2026-10-21 mentoring code review (batch 6, task 6.1)
date: 2026-11-17
tags: [python, time, monotonic, wall-clock, dependency-injection, unittest, flaky-tests]
---

# Measure uptime with a monotonic clock

## What we did
`uptime` used to be `time.time() - self.start_time`. `time.time()` is the **wall clock**:
seconds since 1970 as the operating system currently believes it. An NTP sync, a manual
change or a VM resuming from a snapshot can move that clock, in either direction. If it moved
back after the server started, `uptime_seconds` came out negative, and `datetime.timedelta`
then formatted it as something like `-1 day, 23:59:50`. Now `Server` takes a
`clock=time.monotonic` argument (`server.py:65`), stores `self.start_time = self.clock()`
(`server.py:70`), and `cmd_uptime` subtracts two readings of the same clock
(`server.py:97`). A monotonic clock never goes backwards and system clock updates don't
affect it. Its starting point is undefined, though, so only the **difference** between two
readings means anything.

The clock is injected the same way `LoginThrottle` takes one (`throttle.py:20`, journal 005).
The new unit test `test_uptime_is_the_difference_between_clock_readings`
(`tests/test_server.py:128`) uses a fake clock, a one-element list read by a lambda. It sets
the clock to 100.0, then to 3725.5, and expects exactly `3625.5` and `"1:00:25"`. The
end-to-end `test_uptime` used to `sleep(0.05)` and check that the second reading was larger.
That was slow, and it would have been flaky on a coarse clock: Windows' old `GetTickCount64`
ticks every ~15.6 ms, while Python 3.13 uses `QueryPerformanceCounter`. Now it only checks the
shape of the reply over a real connection, and the arithmetic lives in the deterministic test.

## How it fits
- **Plan:** Step 16, batch 6 (server lifecycle), task 6.1, on branch `fix/server-lifecycle`
  stacked on `fix/server-limits` because batch 5 is not merged yet. `PLAN.md` Step 4 now
  says `start_time = clock()` with `time.monotonic`. Next: 6.2 (`Server.close()` and a guarded
  start-up), then 6.3 (`SO_EXCLUSIVEADDRUSE` on Windows).
- **Practice:** pick the clock for the question you are asking. *"What time is it?"* (log
  timestamps, "started at 14:02", expiry dates stored in a file or sent to another machine)
  needs the wall clock. *"How long did it take?"* (uptime, timeouts, lockouts, rate limits)
  needs a monotonic clock. Use `time.perf_counter()` for benchmarks, because it has the
  highest resolution. Since Python 3.13 it uses the same clock as `monotonic()`. A monotonic
  value is useless outside its process: you can't store it, compare it across machines or
  across a reboot.
- **Practice (testing):** "wrap the system clock so it can be substituted for testing"
  (Fowler). Passing the clock in as a plain callable is the smallest form of dependency
  injection: no interface or framework is needed, and production code gets the real
  `time.monotonic` by default. Patching `time.monotonic` with `unittest.mock.patch` would also
  work, but it's tied to *where* the name is looked up, and it reaches every caller that
  looks the name up while the patch is active, not just this server.

## Commands used
- `git checkout -b fix/server-lifecycle`: start the batch 6 branch, stacked on
  `fix/server-limits`
- `git status -sb`, `git log --oneline -1 origin/fix/server-limits`,
  `gh pr list --state all --limit 5`: check that batch 5 was pushed and had no PR yet
- `grep -n "time\|clock\|uptime" server.py throttle.py tests/*.py`, `sed -n 305,325p tests/test_server.py`:
  find every use of the clock and the old uptime test
- `python -c "import time;print(time.get_clock_info('monotonic'), time.get_clock_info('time'))"`:
  see which OS clocks Python uses on this machine (see [python -c](../commands.md#python--c-run-a-one-line-program))
- `python -m unittest discover tests`: the full suite, 93 tests, OK (1 skipped, as before)

## Read more
- [time.monotonic](https://docs.python.org/3/library/time.html#time.monotonic): Python docs ·
  "a clock that cannot go backwards … only the difference between the results of two calls is
  valid". Compare it with the warning under `time.time()` that it can return a lower value.
- [PEP 418: Add monotonic time, performance counter, and process time functions](https://peps.python.org/pep-0418/):
  peps.python.org · why the system clock breaks timeouts and scheduling, and which clock to
  use for timeouts, benchmarks and CPU profiling.
- [Performance: now()](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now):
  MDN · the same idea in JavaScript: `Date.now()` follows the system clock and its adjustments,
  while `performance.now()` is monotonic.
- [Eradicating Non-Determinism in Tests](https://www.martinfowler.com/articles/nonDeterminism.html):
  martinfowler.com · the "Time" section: always wrap the system clock so a test can freeze
  or set it.
- Related in this repo: journal 005 (the same monotonic, injectable clock for the login
  lockout), concept 001 (versioning; `info` reports a *date*, which is a wall-clock question).

## Quiz

### Revise
1. Which call should measure how long a request took?
   a) `time.time()` b) `time.monotonic()` c) `datetime.datetime.now()` d) `time.localtime()`
   <details><summary>Answer</summary>

   b. The other three read the wall clock, which can be moved while the request runs.
   </details>
2. `time.monotonic()` returns `81234.56` on your machine. What does that number mean on its own?
   <details><summary>Answer</summary>

   Nothing useful. The reference point is undefined (often system boot, but not guaranteed),
   so only the difference between two readings in the same process is valid.
   </details>
3. Spot the bug: a session token stores `expires = time.monotonic() + 3600` in `users.json`,
   and the server checks it after a restart.
   <details><summary>Answer</summary>

   A monotonic value doesn't survive a restart or a reboot, because the new process (or boot)
   has a different reference point. Anything stored or shared needs wall-clock time, such as
   `time.time()` or an aware `datetime` in UTC.
   </details>
4. What does this test do, and why does it need no `sleep`?
   `now = [100.0]; server = Server(..., clock=lambda: now[0]); now[0] = 3725.5`
   <details><summary>Answer</summary>

   It gives the server a fake clock that the test controls. The server reads 100.0 at start,
   and the test then "moves time" to 3725.5, so uptime must be exactly 3625.5 s. Time passes
   only when the test says so, so the result is exact and instant. The list is there so the
   lambda sees the new value, because the lambda reads `now[0]` on each call.
   </details>
5. Why did the old end-to-end test (`sleep(0.05)`, then assert `second > first`) risk being
   flaky with a monotonic clock on some systems?
   <details><summary>Answer</summary>

   Clock resolution. On a coarse clock (Windows' `GetTickCount64` ticks every ~15.6 ms) two
   readings close together, rounded to 0.01 s, can be equal or differ by less than expected.
   Python 3.13 on Windows uses `QueryPerformanceCounter`, but a test shouldn't depend on that.
   `time.get_clock_info()` shows the resolution.
   </details>

### Defend the decision
1. "Why not keep `time.time()`? Nobody changes the clock on a server."
   <details><summary>Model answer</summary>

   Nobody changes it by hand, but NTP does, and so does a VM restored from a snapshot or a
   laptop waking from sleep. Uptime is a duration, and a duration should come from a clock
   built for durations. The fix costs one line, while a negative uptime is a confusing bug
   that's hard to reproduce. The wall clock stays the right tool when we show a start *date*.
   </details>
2. "Why inject the clock as a constructor argument instead of patching `time.monotonic`
   with `unittest.mock.patch` in the test?"
   <details><summary>Model answer</summary>

   Injection makes the dependency visible in the signature. It matches `LoginThrottle`, so
   the codebase has one pattern, and it changes the clock only for that `Server` object.
   `patch` depends on where the name is looked up (`server.time.monotonic` versus
   `time.monotonic`), and it affects every Python caller that looks the name up while the
   patch is active, not just the object under test. The cost is one more keyword argument
   with a sensible default.
   </details>
3. "Why `time.monotonic()` and not `time.perf_counter()`?"
   <details><summary>Model answer</summary>

   They answer different needs. `perf_counter` is for benchmarking short intervals at the
   highest resolution. `monotonic` is the documented choice for timeouts and long-running
   elapsed time, which is what uptime and the lockout are. Since Python 3.13 they use the
   same clock, so the choice expresses intent and keeps us consistent with `throttle.py`.
   </details>
