---
id: 024
title: Stop a second server binding the same port on Windows
commit: "fix: stop a second server binding the same port on Windows"
step: 16 — address the 2026-10-21 mentoring code review (batch 6, task 6.3)
date: 2026-11-19
tags: [python, socket, so_reuseaddr, so_exclusiveaddruse, windows, cross-platform, unittest]
---

# Stop a second server binding the same port on Windows

## What we did
`Server.__init__` always set `SO_REUSEADDR` before `bind()`. The option has the same name
on every OS but not the same meaning:

- **Linux / macOS:** it only lets a restarted server bind while connections from its
  previous run are still in `TIME_WAIT`. A second socket still can't bind a port that a
  *listening* socket holds.
- **Windows:** it lets a socket "forcibly bind to a port in use by another socket". After
  that, Microsoft calls the behaviour of every socket on the port "indeterminate": new
  connections can reach either server. Windows doesn't need the option for a restart,
  because its `bind()` succeeds past `TIME_WAIT` anyway.

The reviewer flagged it without checking, so first we reproduced it with a scratch script
on Windows 11 / Python 3.13: with `SO_REUSEADDR`, a second listening bind to the same port
succeeded; with `SO_EXCLUSIVEADDRUSE` it failed with `WinError 10048`.

The fix picks the option by feature detection (`server.py:82`–`90`):
`SO_EXCLUSIVEADDRUSE` where the `socket` module has it (Windows only), `SO_REUSEADDR`
everywhere else. `socket.create_server` in the standard library makes the same split.

Two new tests in `PortExclusivityTest` (`tests/test_server.py`):
- **Every OS:** while one `Server` runs `serve_forever`, a second `Server` on its port raises
  `OSError`. The first server must be *listening*, not just bound. Linux lets two
  `SO_REUSEADDR` sockets share a port until one of them calls `listen()`, so a bound-only
  version of the test would fail on Linux even with the fix.
- **Windows only** (`skipUnless(hasattr(socket, "SO_EXCLUSIVEADDRUSE"))`): `getsockopt`
  shows the exclusive flag on and `SO_REUSEADDR` off.

Both failed without the fix (`git stash push -q server.py`) and pass with it. The
`ServerCloseTest` docstring said a rebind "would prove nothing" on Windows because of this
bug. It now gives the reason that still holds: a failed rebind can have other causes, so
`fileno() == -1` stays the direct check.

## How it fits
- **Plan:** the last task of batch 6 (server lifecycle and clocks). Together with task 6.2,
  which PR #9 missed and this branch cherry-picks, it completes the batch. `PLAN.md` step 4
  now names the platform split. Next is batch 7, client error handling.
- **Practice:**
  - *Same API, different semantics.* Socket options are passed straight to the OS, so a
    portable-looking line can do different things per platform. Read the platform docs
    before trusting the name.
  - *Feature detection over platform checks.* `hasattr(socket, "SO_EXCLUSIVEADDRUSE")`
    asks "does this OS offer the option?" instead of "is this Windows?". The code then has
    no OS name in it, and the test skip uses the same condition. `socket.create_server`
    checks `os.name` instead, because it is deciding to *leave out* an option, not to use
    one.
  - *Trade-off:* Microsoft notes that once an exclusive listening socket has accepted a
    connection and been closed, a new exclusive bind can fail until that connection is
    fully gone. With one client at a time and a graceful `close()`, a quick restart is
    rarely affected. You'd choose differently if several processes *should* share a port
    for load balancing. That is `SO_REUSEPORT` on Linux, a separate option with its own
    rules.

## Commands used
- `git fetch -q`: update `origin/master` after PRs #9 and #10 were merged.
- `git show --stat --format='%h %s' e872f44`: see which files the unpushed 6.2 commit
  touches before moving it.
- `git checkout -q -b fix/server-lifecycle-2 origin/master`: a new branch for batch 6 part 2,
  started from the merged `master`.
- `git cherry-pick e872f44`: copy the 6.2 commit (with its journal 023) onto the new branch.
- `python -I <scratchpad>/repro_reuse.py`: the throwaway repro that binds two listening
  sockets to one port, once per option.
- `python -m unittest tests.test_server.PortExclusivityTest tests.test_server.ServerCloseTest -v`:
  run only the new tests and the close tests.
- `git stash push -q server.py` … `git stash pop -q`: undo just the fix and rerun the new
  tests, to prove they fail without it.
- `git diff --stat`: check that the stash pop brought both files back.
- `python -m unittest discover tests`: the full suite (100 tests, 1 skipped).

## Read more
- [Using SO_REUSEADDR and SO_EXCLUSIVEADDRUSE](https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse) — Microsoft Learn · the source for this fix. Read "Using SO_REUSEADDR" (the hijack) and "Application Strategies" ("All server applications must set SO_EXCLUSIVEADDRUSE"), plus the caveat about rebinding after accepted connections.
- [socket.create_server](https://docs.python.org/3/library/socket.html#socket.create_server) — Python docs · "On POSIX platforms the SO_REUSEADDR socket option is set": the stdlib's own server helper makes the per-platform choice.
- [CPython `Lib/socket.py`](https://github.com/python/cpython/blob/main/Lib/socket.py) — CPython source · search for "Note about Windows" in `create_server`: the two reasons it skips `SO_REUSEADDR` on Windows, with a link to the Microsoft page.
- [socket(7): SO_REUSEADDR](https://man7.org/linux/man-pages/man7/socket.7.html) — Linux man pages · on Linux the bind is refused while a listening socket holds the address, which is why the test needs a *listening* first server.
- [Python OSError: [Errno 98] Address already in use](https://bobbyhadz.com/blog/socket-error-errno-98-address-already-in-use-in-python) — bobbyhadz · beginner-friendly: why a restarted Python server hits `TIME_WAIT` on Linux, and why `SO_REUSEADDR` is the usual POSIX fix.
- [Skipping tests and expected failures](https://docs.python.org/3/library/unittest.html#skipping-tests-and-expected-failures) — Python docs · `skipUnless` and the "skip unless it has an attribute" pattern used for the Windows-only test.

## Quiz

### Revise
1. What does `SO_REUSEADDR` let a server do on Linux, and what does it let a socket do on Windows?
   <details><summary>Answer</summary>

   On Linux it lets a restarted server bind its port while old connections are still in
   `TIME_WAIT`; it never allows a second listener. On Windows it lets a socket bind a port
   that another socket is already using, after which incoming connections can reach either
   one (port hijacking).
   </details>

2. Which is the safer check, and why?
   a) `if sys.platform == "win32":`
   b) `if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):`
   c) `if os.name == "posix":`
   d) `try: socket.SO_EXCLUSIVEADDRUSE` in every call site
   <details><summary>Answer</summary>

   b. It checks for the exact feature the code is about to use, so it can't name a
   constant that doesn't exist, and it reads as "use this option where it exists". a and c
   are platform checks: they work here, but they encode an assumption about which OS has
   which option. d repeats the check everywhere.
   </details>

3. Why does `test_second_server_on_a_listening_port_is_refused` start `serve_forever` in a
   thread instead of just constructing the first `Server`?
   <details><summary>Answer</summary>

   `Server.__init__` only binds; `listen()` runs in `serve_forever`. On Linux two
   `SO_REUSEADDR` sockets may share a port until one listens, so with a bound-only first
   server the second bind would succeed and the test would fail on Linux even though the
   code is correct.
   </details>

4. Spot the bug:
   ```python
   sock = socket.socket()
   sock.bind((HOST, PORT))
   sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
   ```
   <details><summary>Answer</summary>

   The option is set after `bind()`. Both `SO_REUSEADDR` and `SO_EXCLUSIVEADDRUSE` change
   how `bind()` checks the address, so they must be set before it. Here the bind already
   happened without exclusivity.
   </details>

5. Why doesn't the Windows branch set `SO_REUSEADDR` as well, "to be safe" about restarts?
   <details><summary>Answer</summary>

   Windows `bind()` already succeeds past `TIME_WAIT` without it (that's the first reason in
   CPython's `create_server` comment), so it would add nothing but the hijack risk. And the
   two options conflict: with `SO_REUSEADDR` already on, setting `SO_EXCLUSIVEADDRUSE`
   fails with `WSAEINVAL` (error 10022, checked on Windows 11).
   </details>

### Defend the decision
1. "The reviewer only suspected this bug. Why did you reproduce it before fixing it?"
   <details><summary>Model answer</summary>

   A fix for an unverified bug can't be tested properly: you don't know whether the test
   would have failed before. The 20-line repro showed the hijack on Windows with
   `SO_REUSEADDR` and the refusal with `SO_EXCLUSIVEADDRUSE`. That confirmed both the bug
   and the fix, and gave the regression test its shape. The two new tests then fail without
   the fix and pass with it.
   </details>

2. "Why keep `SO_REUSEADDR` at all? Why not drop it everywhere and accept slower restarts?"
   <details><summary>Model answer</summary>

   On Linux and macOS, restarting the server within about a minute of a client
   disconnecting would fail with "Address already in use" while the old connection sits in
   `TIME_WAIT`. That is a real annoyance during development and the tests. On POSIX the
   option has no hijack risk, since a second listener is still refused. So the per-platform
   choice keeps fast restarts where they're safe and removes the option where it's
   dangerous. The stdlib's `socket.create_server` makes the same trade-off.
   </details>

3. "What does `SO_EXCLUSIVEADDRUSE` cost you?"
   <details><summary>Model answer</summary>

   After an exclusive listener has accepted a connection and been closed, a new exclusive
   bind can fail until that connection is fully closed at the TCP level. A peer that never
   finishes the close could delay a restart. Here the server serves one client at a time and
   closes cleanly, so in practice a restart works. If it ever didn't, the fix would be a
   graceful shutdown (`shutdown(SHUT_WR)` and drain) rather than giving up exclusivity.
   </details>
