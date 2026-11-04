---
id: 013
title: Unit-test request handling and the protocol without sockets
commit: "test: unit-test request handling and the protocol without sockets"
step: 16 — address the 2026-10-21 mentoring code review (batch 2, task 2.2)
date: 2026-11-02
tags: [python, unittest, unit-tests, test-pyramid, test-doubles, mock, io, bytesio, ndjson]
---

# Unit-test request handling and the protocol without sockets

## What we did

Before this commit, every test started a TLS server in a thread and talked to it over a real
socket. That included the test that only checks the version string with a regex. `protocol.py` had
no tests of its own. Now there are three layers:

- **`tests/test_protocol.py`** (new) tests the NDJSON helpers without any network.
  `receive_message` only calls `readline()` on a binary file, so `io.BytesIO` stands in for
  `sock.makefile("rb")`. The tests cover one message, two messages read in turn, end of stream
  returning `None`, invalid JSON and invalid UTF-8 raising `ValueError`, and a bad line that
  doesn't corrupt the next one (the property 010 relied on). `send_message` only calls `sendall()`,
  so a `mock.Mock()` stands in for the socket. The tests check one call with one `\n`-terminated
  line, that a newline *inside* a string is escaped (otherwise one message would become two
  frames), and a send → receive round trip.
- **`HandleRequestTest`** (`tests/test_server.py:43`) calls `Server.handle_request(request, session)`
  directly. It covers every request shape: not an object, missing `command`, non-string `command`,
  `args` that isn't an object, unknown, trimmed/case-insensitive name, login required, ok, and a
  handler `ValueError` turned into an error reply. It also checks the one side effect of `stop`:
  it sets `running = False`, and does nothing without a login. `test_unknown_command` and
  `test_args_must_be_object` moved here from the end-to-end class.
- **`VersionTest`** (`tests/test_server.py:38`) holds the SemVer check, which starts no server.

The end-to-end `ServerTest` keeps the main flow, auth and lockout, TLS, `stop`, and the
malformed-bytes cases. Those prove that the framing, decoding and the accept loop work together.
The 19 new unit tests run in about 0.03 s. The full suite is 61 tests in about 3 s.

**Not foreseen in the briefing:** `Server.__init__` binds a real socket, so even the "unit" fixture
opens a port. The test closes it with `addCleanup(self.server.sock.close)`. A cleaner design would
bind in `serve_forever` or in a `start()` method, so that constructing a `Server` does no I/O. That's
a refactor for a later chunk (it fits batch 6, "server lifecycle").

## How it fits
- **Plan:** Step 16, batch 2, task 2.2. Task 2.3 (making the SemVer regex strict) can now add its
  negative cases to `VersionTest` without starting a server. Batches 4 and 5 (end of stream vs
  `null`, last frame without `\n`, maximum message size) will add fast `receive_message` cases to
  `ReceiveMessageTest`.
- **Practice: the test pyramid.** Write many cheap, fast tests for logic, and fewer slow tests for
  how the parts connect. Before this commit, the repo was an upside-down pyramid: almost every test
  was end-to-end. A unit test that fails points at one function. An end-to-end failure could be TLS,
  timing, the thread, framing or the logic.
- **Practice: test doubles.** `BytesIO` is a *fake*, a working lightweight implementation of the
  file interface. `Mock` is used as a *spy*: it records the calls so we can check them afterwards.
  Both work because of duck typing. `protocol.py` never checks for "a socket", only for an object
  with `readline()` or `sendall()`.
- **What only end-to-end tests catch:** TLS handshakes, partial reads on a real stream, `makefile`
  buffering, the single-client accept loop, threads and shutdown. That's why those tests stay.
- **When you'd choose differently:** if a mock starts checking *how* the code does something
  (the exact order of calls) instead of *what* it produces, the tests break on every refactor.
  Then a real `socket.socketpair()` is the better middle ground: a real kernel socket, no server.
  We didn't need it here because both helpers use a single method of their argument.

## Commands used
- `cd /d/Programming/zr-client-server && cat PLAN.md && ls -R docs …`: read the plan, docs and code
  to pick the next task (Git Bash)
- `grep -n "^## \|^### " PLAN.md`, `grep -n "^#\|…" docs/plans/001-code-review-2026-10-21.md`:
  outlined the plan and the fix plan to find task 2.2
- `sed -n 164,223p docs/plans/001-code-review-2026-10-21.md`, `sed -n 45,142p server.py`: read
  task 2.2 and `handle_request`
- `wc -l *.py tests/*.py`: checked how big each file is
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`: full suite, 61 tests,
  OK (1 skipped on Windows)
- `python -m unittest -v tests.test_protocol tests.test_server.HandleRequestTest tests.test_server.VersionTest 2>&1 | tail -30`:
  ran only the new fast tests, 19 in 0.025 s
- `git add` / `git commit -F -`: staged and committed the code with this entry

## Read more
- [How to Write Unit Tests for Python Functions](https://www.freecodecamp.org/news/how-to-write-unit-tests-for-python-functions/): freeCodeCamp · `unittest` basics: test classes, assertions, checking exceptions
- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html): martinfowler.com (Ham Vocke) · "the more high-level you get, the fewer tests you should have"; what unit vs end-to-end tests are each good at
- [Test Double](https://martinfowler.com/bliki/TestDouble.html): martinfowler.com · dummy, fake, stub, spy and mock; here `BytesIO` is a fake and `Mock` a spy
- [io.BytesIO](https://docs.python.org/3/library/io.html#io.BytesIO): Python docs · an in-memory binary stream; `readline()` splits on `b"\n"`, the same way the socket file does
- [unittest.mock: call_args](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.call_args): Python docs · how to read back what a mock was called with, and `assert_called_once`
- [Concept 002: NDJSON vs alternatives](../concepts/002-ndjson-vs-alternatives.md) · why a newline inside a value must be escaped for line framing to work

## Quiz

### Revise
1. Why can `io.BytesIO` replace `sock.makefile("rb")` in `receive_message`'s tests?
   <details><summary>Answer</summary>

   `receive_message` only calls `readline()` on its argument and expects bytes. `BytesIO` is a
   binary stream with the same `readline()` behaviour, so duck typing lets it stand in.
   </details>
2. What does `receive_message(io.BytesIO(b""))` return, and why does that matter to the server?
   <details><summary>Answer</summary>

   `None`. `readline()` returns `b""` at end of stream, which is how the server sees that the
   client has closed the connection and ends that session.
   </details>
3. Which test double is `mock.Mock()` in `SendMessageTest`?
   a) dummy  b) fake  c) spy  d) stub
   <details><summary>Answer</summary>

   c) spy. It records the `sendall` call, and the test checks the recorded arguments afterwards.
   (`unittest.mock` calls everything a "mock", but Fowler's terms describe how it's used.)
   </details>
4. What does this unpack, and what fails if `sendall` was never called?
   `(data,), _ = sock.sendall.call_args`
   <details><summary>Answer</summary>

   `call_args` is a `call` object of `(args, kwargs)`. This takes the single positional argument
   into `data` and ignores the kwargs. If there was no call, `call_args` is `None` and the unpacking
   raises `TypeError`. That's why the test asserts `assert_called_once()` first, for a clearer
   failure message.
   </details>
5. Spot the bug: a test builds `Server(port=0, ...)` to call `handle_request` but has no cleanup.
   What leaks, and why does it matter more on a big test suite?
   <details><summary>Answer</summary>

   The listening socket that `__init__` binds. Each test leaks one file descriptor until garbage
   collection, which prints `ResourceWarning`s and can exhaust descriptors or ports. The fix is
   `addCleanup(server.sock.close)`, or better, a constructor that doesn't bind.
   </details>

### Defend the decision
1. "Why keep end-to-end tests at all, now that `handle_request` is fully unit-tested?"
   <details><summary>Model answer</summary>

   Unit tests prove the logic. They can't prove that the pieces are wired together: the TLS
   handshake, `makefile` and framing on a real stream, the one-client-at-a-time accept loop, and
   `stop` actually ending the thread. Those bugs exist only when everything is connected. So: many
   unit tests for every branch, a few end-to-end tests for the main paths and the hostile-input
   cases. The trade-off is speed and a precise failure location versus realism.
   </details>
2. "Why a `Mock` socket and not `socket.socketpair()`?"
   <details><summary>Model answer</summary>

   `send_message` uses only `sendall`, and the property under test is "one call, one line". A
   mock checks that directly and needs no kernel resources. `socketpair()` would be more realistic
   (real buffers, real `makefile`). I'd switch to it if the protocol started using partial
   `send`/`recv` or timeouts, where a mock would just repeat my assumptions back to me.
   </details>
3. "Your 'unit' test opens a socket. Isn't that a smell?"
   <details><summary>Model answer</summary>

   Yes. `Server.__init__` mixes configuration with I/O (`bind`). I kept this commit to tests only
   and closed the socket with `addCleanup`. The proper fix is to move binding to `serve_forever` or
   a `start()` method, so that constructing a server is pure. That refactor belongs to the
   server-lifecycle batch, together with an explicit `close()`. Changing production code inside a
   `test:` commit would mix two concerns.
   </details>
