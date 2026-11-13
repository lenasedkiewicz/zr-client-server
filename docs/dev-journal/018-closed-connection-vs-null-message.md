---
id: 018
title: Tell a closed connection apart from a null message
commit: "fix: tell a closed connection apart from a null message"
step: 16 — address the 2026-10-21 mentoring code review (batch 4, task 4.1)
date: 2026-11-09
tags: [python, protocol, exceptions, sentinel, semipredicate, eof, type-hints, git]
---

# Tell a closed connection apart from a null message

## What we did
`receive_message` returned `None` for two different things: "the connection is closed"
(`readline()` gave `b""`) and "the client sent `null`" (`json.loads("null")` is `None`). The
server checked `if request is None: return`, so a client that sent `null` was hung up on with
no reply, while `[]` or `{}` got a proper error. The test `test_null_message`
(`tests/test_server.py:308`) showed it: the client read end of stream instead of an answer.

Now the end of stream is **not a return value at all**. `receive_message` raises
`ConnectionClosed` (`protocol.py:19`, raised at `protocol.py:48`), and any JSON value, `null`
included, comes back as data. The server catches `ConnectionClosed` to end the session quietly
(`server.py:162`). `null` now goes to `handle_request` like every other value, and its
existing check (`server.py:130`) rejects anything that isn't an object. The client treats
`ConnectionClosed` like a network error (`client.py:85`). `protocol.py` also got type hints and
docstrings that tell the truth (any JSON value, plus the `OSError` a read can raise), and
`PLAN.md` step 3 no longer promises `-> dict | None`.

Two choices to notice:
- **`ConnectionClosed` inherits from plain `Exception`.** As a `ValueError` the server's
  "malformed line" branch would catch it and reply to a closed socket. As an `OSError` it
  would be logged as a lost connection at `WARNING`, though hanging up is normal. A unit test
  pins this down (`tests/test_protocol.py:71`).
- **`protocol.py` frames messages, `server.py` validates requests.** `receive_message` returns
  `[]`, `"x"` or `false` unchanged. Deciding what a request must look like is the server's job,
  so the client can reuse the same framing for replies.

Known gap, left for task 7.1 on purpose: a server replying `null` (or `[]`) still crashes
the client with `AttributeError` at `response.get`. Our server never sends either, and 7.1
validates every reply in one place.

Also in this chunk: all branches from merged PRs #1–#5 were checked for unmerged work
(none) and deleted, locally with `git branch -d` and on GitHub with `git push --delete`.

## How it fits
- **Plan:** step 16, batch 4, task 4.1 (`docs/plans/001-code-review-2026-10-21.md`).
  Unblocks task 4.2 (a last frame without `\n`) and batch 5 (size limit, idle timeout),
  which change the same function.
- **Practice:** this is the *semipredicate problem*: a function's "no result" signal is also
  a valid result. There are three classic fixes:
  - **A sentinel** that no real result can equal, like `_CLOSED = object()`. It's cheap, but
    every caller has to remember to check for it, and a caller who forgets passes it on as
    data without noticing.
  - **Two return values**, like `(ok, value)`. It's explicit, but the caller has to unpack it
    every time.
  - **An exception (out-of-band).** A caller can't silently ignore it: if they forget to
    handle it, it surfaces as a traceback, not as wrong data.

  Python's own iterators use the exception route (`StopIteration`), while file objects use an
  in-band value (`b""`). That's safe for them, because an empty read can never be a real
  line, since every line ends with `\n`. **When you'd choose differently:** keep the special
  value when it truly can't collide (`dict.get` on a dict whose values are never `None`), or
  in a hot loop where raising costs too much. Python 3.15 adds a built-in `sentinel` (PEP
  661) for the case where `None` itself is a valid value.

## Commands used
- `python -m unittest tests.test_server.ServerTest.test_null_message`: run the new test
  alone against the unfixed code, to watch it fail first (an error: `'NoneType' object is not
  subscriptable`)
- `python -m unittest discover tests`: full suite after the fix, 71 tests OK, 1 skipped
- `git checkout master`, `git pull --ff-only`: update `master` after PR #5 was merged
- `git fetch origin`, `git ls-remote --heads origin`: which branches exist on GitHub now
- `git for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin`: list every
  branch to check
- `git rev-list --count master..<branch>`, `git merge-base --is-ancestor <branch> master`,
  `git cherry master <branch>`: three ways to confirm a branch has nothing left to merge
- `gh pr list --state all --limit 10 --json number,headRefName,state,headRefOid --jq ...`:
  match each branch to its merged PR
- `git stash list`, `git worktree list`: make sure no work is hidden elsewhere
- `git branch -d feature/admin fix/server-survives-bad-client refactor/logging-and-cleanups test/test-foundations`:
  delete the merged local branches
- `git push origin --delete ci/github-actions fix/server-survives-bad-client refactor/logging-and-cleanups`:
  delete them on GitHub
- `git fetch --prune origin`, `git branch -a`: drop the stale `origin/...` refs and check
- `git checkout -b fix/protocol-contract`, `git branch -vv`: start the batch 4 branch
- `grep -n ...`: find every caller of `receive_message` and every doc that still promised `None`
- `git log --oneline -S'password' -- tests/test_server.py`: during the GitGuardian triage,
  find when test passwords first appeared

## Read more
- [The semipredicate problem](https://en.wikipedia.org/wiki/Semipredicate_problem): Wikipedia ·
  the name for this bug, and the three fixes compared; note `str.find` returning `-1`, a
  valid index
- [User-defined exceptions](https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions):
  Python tutorial · "derived from the `Exception` class, either directly or indirectly"
- [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy):
  Python docs · `EOFError` and `StopIteration` sit directly under `Exception`, not under
  `ValueError`/`OSError`, the same place `ConnectionClosed` now sits
- [Error handling in Python](https://www.freecodecamp.org/news/error-handling-in-python-introduction/):
  freeCodeCamp · beginner-friendly; the "Custom Exceptions" section (its example misspells
  the class name, so spot the bug)
- [PEP 661: Sentinel Values](https://peps.python.org/pep-0661/): Final, Python 3.15 · why
  `None` can't be the sentinel when `None` is a valid value
- [typing.Any](https://docs.python.org/3/library/typing.html#typing.Any): `typing` docs ·
  "use `object` to indicate that a value could be any type in a typesafe manner"; see Defend
  question 3
- Concept 002, [NDJSON vs alternatives](../concepts/002-ndjson-vs-alternatives.md): the
  line framing underneath `receive_message`

## Quiz

### Revise
1. Before this commit, what did a client get after sending each line?
   a) `{}` b) `[]` c) `null` d) `{"command": "help"}`
   <details><summary>Answer</summary>

   a and b got an error reply ("Request must be ..."), c got no reply because the server
   hung up, d got the help listing. `null` decoded to `None`, which the server read as
   "connection closed".
   </details>

2. Why is `readline()` returning `b""` at end of stream safe, while `receive_message`
   returning `None` was not?
   <details><summary>Answer</summary>

   Every line `readline()` returns ends with `\n` (only the very last one may not), so a real
   line is never empty and `b""` can't collide with data. After decoding, `None` *is* a
   possible message: the JSON `null`.
   </details>

3. Spot the bug: `class ConnectionClosed(ValueError): pass` with the server's
   `except ConnectionClosed: return` placed *after* `except (ValueError, RecursionError):`.
   <details><summary>Answer</summary>

   Clauses are tried top to bottom, so the `ValueError` clause catches it first and the
   `ConnectionClosed` clause never runs. The server treats end of stream as a malformed line:
   it sends "Invalid message" to a client that has gone, and goes back to reading. It gets
   end of stream again, replies again, and so on, until a send fails with `OSError` and it's
   logged as a lost connection. Inheriting from `Exception` avoids the overlap entirely.
   </details>

4. What does `receive_message(io.BytesIO(b"[]\n"))` return now, and who rejects it?
   <details><summary>Answer</summary>

   `[]`. `protocol.py` only frames and decodes; `Server.handle_request` (`server.py:130`)
   rejects anything that isn't a dict with a string `command`.
   </details>

5. Name the three classic fixes for the semipredicate problem and one cost of each.
   <details><summary>Answer</summary>

   - **Sentinel value:** callers must remember to check, and one who forgets passes the
     sentinel on as data.
   - **Two return values / a tuple:** every caller has to unpack it.
   - **Exception:** it costs more than a return and adds a control-flow path, which is why
     hot loops sometimes avoid it.
   </details>

### Defend the decision
1. "Why an exception for a closed connection, not a sentinel object?"
   <details><summary>Model answer</summary>

   Every caller of `receive_message` must treat a closed connection differently from a
   message. With a sentinel, a caller who forgets the check passes it on as data; with an
   exception, forgetting gives a traceback that a test catches. Closing happens once per
   session, so raising costs nothing worth measuring. A sentinel would be the better choice
   in a hot loop, or if callers usually want to keep going after the "special" case.
   </details>

2. "Why doesn't `protocol.py` reject non-object messages itself?"
   <details><summary>Model answer</summary>

   Separation of concerns: the protocol module knows what a *message* is (one line of UTF-8
   JSON), the server knows what a *request* is. The same function reads the client's replies,
   whose rules differ. Checking request shape in one place, `handle_request`, also keeps one
   error message for `null`, `[]` and `{}`. The cost is that each caller has to remember to
   validate, which is exactly the client gap task 7.1 fixes.
   </details>

3. "`receive_message` is hinted `-> Any`. Wouldn't `-> object` be safer?"
   <details><summary>Model answer</summary>

   `Any` means "don't check", so `response.get(...)` in `client.py` passes a type checker even
   though `response` might be a list. `object` would force an `isinstance` check before use,
   and a type checker would have flagged the very client bug left for 7.1. `Any` matches what
   `json.loads` itself returns. With no type checker configured here, the difference is
   documentation only, but `object` is the stricter choice once one runs.
   </details>

4. "The name `ConnectionClosed` doesn't end in `Error`. Why?"
   <details><summary>Model answer</summary>

   The tutorial says most exception names end in "Error", but this isn't an error: a client
   hanging up is how every session normally ends. It follows `StopIteration`, an exception used
   as a signal. The name says what happened, and the server ends that session without
   logging a warning.
   </details>
