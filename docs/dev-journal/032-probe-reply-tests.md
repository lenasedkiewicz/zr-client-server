---
id: 032
title: Cover off-protocol replies in the launcher's probe
commit: "test: cover off-protocol replies in the launcher's probe"
step: 16 — address the 2026-10-21 mentoring code review (pre-review fix 1 of 5 on batch 8)
date: 2026-11-24
tags: [python, unittest, tls, ssl, test-double, mutation-testing, launcher]
---

# Cover off-protocol replies in the launcher's probe

## What we did
The `pre-review` of `fix/launcher-cleanup` found that half of `probe_server` had no test:
the part after the TLS handshake (`run.py:58-69`), where it sends `help` and judges the
reply. The tests covered our real server, a plain listener, another certificate and
timeouts. They didn't cover a peer that passes the pinned handshake and then speaks another
protocol. The code was already right; a script in the pre-review proved it. But deleting
`ValueError` from that `except` would have broken nothing in the suite.

`tests/test_run.py` now has `fake_tls_peer(reply)`: a TLS server in a thread that holds
**our test certificate and key** from `tests/certs/`. It reads the probe's request, sends
`reply` and closes. With `None`, it stays silent. One positive control
(`test_fake_peer_with_a_real_help_reply_is_ready`) shows that the fake is faithful: a real
`help` reply gives `READY`. Then 14 `subTest`s, each with a fresh peer, all expect
`NOT_OURS`. They are the rows of the pre-review's hostile-input table that apply to a peer
the launcher reads from:
- non-UTF-8 bytes and invalid JSON
- `null`, `[]`, `5` and `"x"`
- a 5000-digit integer and nesting 20 000 levels deep (40 KB, so under the size limit but
  over the recursion limit)
- a line over `MAX_MESSAGE_SIZE`, and a reply without the final `\n`
- a close right after the handshake
- a reply for another command, a reply with no command at all, and silence

The "error reply, session goes on" rows of that table don't apply: the probe never keeps a
session.

The tests pass against the current code, so "fail first" took **hand-made mutations**. Each
run broke one line of a backup copy of `run.py`, ran the tests and restored the file:
- no `ValueError`: 7 subtests failed (non-UTF-8, invalid JSON, `null`, `[]`, `5`, `"x"`,
  the long integer)
- no `RecursionError`: 1 failed (deep nesting)
- no `MessageTooLong`: 1 failed (the long line)
- no `ConnectionClosed`: 2 failed (the missing newline, the early close)
- no `command == "help"` check: 2 failed (another command, no command)

Every mutation was caught, each by the cases meant to catch it. Afterwards `run.py` was
identical to HEAD (`git diff --quiet`).

## How it fits
- **Plan:** Step 16, the pre-review fixes for batch 8, 1 of 5. Next is fix 2: an unusable
  certificate gets a message instead of a traceback.
- **Practice:**
  - *Every `except` branch is a behaviour.* A branch no test reaches can be deleted in a
    refactor, and the suite stays green. The pre-review's question C1 ("would a test fail
    without this?") applies to old code as much as to new.
  - *Mutation testing tests the tests.* Break the code on purpose, and a good suite goes
    red. A mutation that survives shows a gap. Tools generate mutants automatically; for
    Python that's mutmut, which needs `fork`, so on Windows it runs only in WSL. For five
    branches, hand mutations were quicker and teach more. Check that each mutation really
    changed the file (`cmp -s`): a `sed` pattern that doesn't match changes nothing, and
    then "the tests passed" means nothing.
  - *A test double with real credentials.* The fake peer uses the test key, so it gets past
    the same pinned handshake a real peer would. The probe runs its real code end to end,
    with no mocking of `ssl` or `socket`.
  - *A positive control.* Without the `READY` case, a fake that was broken in some other
    way would make every `NOT_OURS` test pass for the wrong reason.
  - *When you'd skip this:* a branch that only logs, or code with one obvious path. Here
    each branch decides whether the launcher starts a client against a stranger.

## Commands used
- `python -m unittest -v tests.test_run.ProbeServerTest` — the new cases, all passing
  against the current code
- `git diff --quiet -- run.py && echo "run.py clean"` — check that there are no uncommitted
  changes before mutating, and that the file is back to HEAD afterwards
  ([git diff](../commands.md#git-diff-show-unstaged-changes))
- `cp run.py "$S/run.py.orig"` — back up the file before mutating
- `mutate() { cp …; sed -i "$1" run.py; cmp -s …; python -m unittest …; }` — one mutation
  per call, then `mutate 's/…ValueError, //' "no ValueError"` and so on
  ([shell function](../commands.md#shell-function-name-a-repeated-sequence),
  [cmp -s](../commands.md#cmp--s-are-two-files-identical))
- `… | grep -a -oE "^ERROR: [a-z_]+|^(OK|FAILED.*)$" | sed -E 's/ \(tests[^)]*\)//'` — cut
  unittest's output down to what failed ([grep](../commands.md#grep-search-text) `-o`,
  [sed](../commands.md#sed--i-edit-a-file-in-place) `-E`)
- `cp "$S/run.py.orig" run.py` and `rm "$S/run.py.orig"` — restore, then delete the backup
- `python -m unittest discover tests` — the full suite, OK with 1 skip

## Read more
- [mutmut: Python mutation tester](https://mutmut.readthedocs.io/) — mutmut docs · "a mutation testing system for Python": it changes your code in small ways, and "if your tests do not detect such a change" that code isn't properly tested. It needs `fork`, so it runs on Windows only inside WSL.
- [The Logic, Philosophy, and Science of Software Testing](https://www.freecodecamp.org/news/the-logic-philosophy-and-science-of-software-testing-handbook-for-developers/) — freeCodeCamp · a beginner-friendly handbook that names mutation testing as the way to check the unhappy path, and "a failure indicates that the tested implication is false".
- [ssl: socket creation, server side](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.wrap_socket) — Python docs · the server example: `SSLContext(PROTOCOL_TLS_SERVER)`, `load_cert_chain(...)`, then `wrap_socket(sock, server_side=True)`, exactly what the fake peer does.
- Related: [journal 031](031-confirm-the-protocol-before-reuse.md) (the probe under test), [journal 010](010-malformed-input-gets-an-error-reply.md) (the same hostile inputs, sent to the server), [journal 019](019-reject-unterminated-final-frame.md) (why a reply without `\n` is not a message).

## Quiz

### Revise
1. The new tests passed the first time they ran. Why is that not enough to trust them, and
   what did this commit do instead of watching them fail?
   <details><summary>Answer</summary>

   A test that has never failed might not be able to: it could check the wrong thing, or
   reach the code through another path. Since the code was already right, the commit broke
   it on purpose, one line at a time, and checked that each break made the expected
   subtests fail. That's mutation testing by hand.
   </details>

2. Why does the fake peer use `tests/certs/test-server.key` and not a certificate of its own?
   <details><summary>Answer</summary>

   The probe pins our certificate. A peer with any other certificate fails the handshake,
   which tests the handshake branch, already covered by the "another certificate" test.
   To reach the code *after* the handshake, the peer must hold our key. The test key is
   public on purpose and used only by the tests.
   </details>

3. Multiple choice. Which exception does a 5000-digit integer in the reply raise inside
   `receive_message`?
   a) `RecursionError`
   b) `MessageTooLong`
   c) `ValueError`
   d) `OverflowError`
   <details><summary>Answer</summary>

   c. Since Python 3.11 (and 3.10.7, where it was backported), converting a decimal string
   of more than 4300 digits to `int` raises `ValueError` (the integer string conversion
   limit). 5000 digits is far under
   `MAX_MESSAGE_SIZE`, so it isn't b.
   </details>

4. Why is the deep-nesting reply 20 000 levels and not 100 000?
   <details><summary>Answer</summary>

   100 000 levels of `[` and `]` are 200 KB, over `MAX_MESSAGE_SIZE` (64 KB). The probe
   would stop with `MessageTooLong` and never parse it, so the test would check the size
   limit twice and the recursion branch not at all. 20 000 levels are 40 KB: under the size
   limit, far over the recursion limit.
   </details>

5. Spot the problem in this mutation run:
   ```bash
   sed -i 's/ValueError, RecursionError/RecursionError/' run.py
   python -m unittest tests.test_run   # OK
   ```
   "The tests still pass, so the `ValueError` branch isn't tested!"
   <details><summary>Answer</summary>

   Maybe the `sed` pattern didn't match. In `run.py` the tuple reads `OSError, ValueError,
   RecursionError`. If the text differs at all, `sed` changes nothing and reports no error,
   so the tests ran on unchanged code. Check that the file changed (`cmp -s`, or
   `git diff --stat`) before drawing a conclusion.
   </details>

### Defend the decision
1. "Why write tests for code that already works?"
   <details><summary>Model answer</summary>

   Because "works" was only proven by a one-off script, and scripts don't run in CI. Each
   `except` branch in the probe decides whether the launcher starts a client against a
   stranger. Without a test, a refactor could quietly drop `ValueError` from the tuple, and
   the first person to notice would be a user with a hung client. The mutations showed that
   each new subtest guards a specific branch, so the tests earn their place.
   </details>

2. "Why hand mutations instead of a tool like mutmut?"
   <details><summary>Model answer</summary>

   The question was narrow: five branches in one function. Five `sed` edits answered it in a
   minute, and each one is easy to explain. mutmut would mutate the whole project, needs WSL
   on Windows (it relies on `fork`), and adds a third-party dev tool to a stdlib-only repo.
   For a regular check on a larger codebase, a tool is the better choice.
   </details>

3. "Why a real TLS peer in a thread and not a mock of `wrap_socket` and `receive_message`?"
   <details><summary>Model answer</summary>

   A mock would test my idea of what `ssl` and the framing raise, not what they actually
   raise. With a real peer, the bytes go through the real TLS stack and the real
   `receive_message`. That's how we know, for example, that a close right after the
   handshake reaches the `ConnectionClosed` branch. It costs a thread and half a second for
   the silent case, which is cheap.
   </details>
