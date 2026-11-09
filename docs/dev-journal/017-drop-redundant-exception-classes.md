---
id: 017
title: Drop redundant exception classes and an unused constant
commit: "refactor: drop redundant exception classes and an unused constant"
step: 16 — address the 2026-10-21 mentoring code review (batch 3, task 3.2)
date: 2026-11-06
tags: [python, exceptions, exception-hierarchy, ssl, oserror, yagni, refactoring]
---

# Drop redundant exception classes and an unused constant

## What we did
Three `except` clauses listed a class next to its own parent, and all three now say
`except OSError`. `client.py:85` had `(ConnectionError, OSError)`. `client.py:58` and
`server.py:193` had `(ssl.SSLError, OSError)`. In a tuple, the parent already matches
everything the subclass does, so the extra name changed nothing and only suggested a
difference that doesn't exist. `BUFFER_SIZE` is gone from `config.py` and from the structure
tree in `PLAN.md`: nothing read it, because `makefile` and `readline` do the buffering.

Two things differ from the plan. The server's `(ConnectionError, OSError)` pair had already
gone in task 1.1, so only the client's was left. The two `ssl.SSLError` sites weren't listed,
but they are the same finding: `ssl.SSLError` is a subclass of `OSError`.

The behaviour is unchanged, so there is no new test: `except (A, B)` and `except B` match the
same exceptions when `A` is a subclass of `B`. The existing suite is the check.

## How it fits
- **Plan:** Step 16, batch 3, task 3.2. This finishes the batch, so
  `refactor/logging-and-cleanups` is ready for a PR. Batch 4 (protocol contract) is next.
- **Practice:**
  - **Code should say only what's true.** A reader assumes every listed class is there for a
    reason, so a redundant one sends them looking for a difference that isn't there.
  - **The narrowest class that is still correct.** Narrower is usually better, but it has to
    stay correct. `client.py:85` can't narrow to `ConnectionError`: `ssl.SSLEOFError` and
    `ssl.SSLZeroReturnError` are `OSError`s but not `ConnectionError`s, so a TLS failure would
    become a traceback instead of "Connection closed by the server".
  - **When a subclass next to its parent is worth it.** Only in separate clauses, subclass
    first, when the two cases are handled differently. `client.py:54` does this:
    `ssl.SSLCertVerificationError` gets its own message built from `verify_message`, and
    `client.py:58` takes the other failures. That pair stays. Swapped, the certificate clause
    could never run.
  - **YAGNI.** A dead constant isn't free. It looks like a setting, but changing it does
    nothing, and it had also spread into the docs.
- **When you'd choose differently:** some teams keep `ssl.SSLError` in the tuple as
  documentation of what they expect. That's a fair choice, but a comment says it without
  implying a difference. Here the `handle_client` docstring (`server.py:154`) already states
  that `OSError` includes `ssl.SSLError`.

## Commands used
- `git log --oneline -8` — see where the branch stood.
- `git show --stat HEAD` — check what the last commit touched.
- `git diff HEAD~1 HEAD -- PLAN.md` — see what the last commit recorded in the plan.
- `git branch -a` — list local and remote branches.
- `ls`, `cat`, `wc -l tests/*.py` — read the project layout, the sources and the test sizes.
- `grep -n -i -E 'batch 3|3\.[0-9]|BUFFER_SIZE|^#+ ' docs/plans/001-code-review-2026-10-21.md`
  — find the task in the fix plan.
- `grep -rn 'BUFFER_SIZE' .` — prove the constant had no readers.
- `grep -n 'except' server.py client.py run.py users.py throttle.py admin_setup.py protocol.py`
  — list every handler, which is how the two `ssl.SSLError` sites turned up.
- `sed -n 248,264p docs/plans/001-code-review-2026-10-21.md` — read the task.
- `python -c "import ssl;print(ssl.SSLError.__mro__)"` — check the class hierarchy instead of
  trusting memory.
- `python - <<'E' … E` — check that `SSLEOFError` and friends aren't `ConnectionError`s.
- `sed -i 's/except (ConnectionError, OSError):/except OSError:/; s/except (ssl.SSLError, OSError) as error:/except OSError as error:/' client.py server.py`
  — replace the three clauses.
- `sed -i '/^BUFFER_SIZE = 1024$/d' config.py` — delete the constant.
- `sed -i 's/# HOST, PORT, BUFFER_SIZE, ENCODING,/# HOST, PORT, ENCODING,/' PLAN.md` — fix the tree.
- `git diff --stat`, `git diff -U0` — review the change with no context lines.
- `python -m unittest discover tests` — before and after: 67 tests, OK (1 skipped).

## Read more
- [Handling exceptions](https://docs.python.org/3/tutorial/errors.html#handling-exceptions) —
  Python tutorial · a class matches its derived classes, and the first matching clause wins.
- [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy) —
  Python docs · the tree that shows `ConnectionError` and its children under `OSError`.
- [ssl: exceptions](https://docs.python.org/3/library/ssl.html#exceptions) — Python docs ·
  `SSLError` is a subtype of `OSError`; `SSLEOFError` and `SSLCertVerificationError` are its
  subclasses.
- [PEP 3151: Reworking the OS and IO exception hierarchy](https://peps.python.org/pep-3151/) —
  peps.python.org · why `OSError` became the single parent in Python 3.3.
- [How to Handle Exceptions in Python](https://www.freecodecamp.org/news/exception-handling-python/)
  — freeCodeCamp · a beginner's view of tuples versus separate clauses. It doesn't cover
  hierarchy or order, so read it first and the tutorial after.
- [Yagni](https://martinfowler.com/bliki/Yagni.html) — martinfowler.com · the "cost of carry"
  of code nobody needs.
- [Concept 003: what an except clause catches](../concepts/003-except-clause-scope.md) — this
  repo · how Python picks a clause.

## Quiz

### Revise

1. Which of these is **not** a subclass of `ConnectionError`?
   a) `BrokenPipeError` b) `ConnectionResetError` c) `ssl.SSLEOFError` d) `ConnectionRefusedError`
   <details><summary>Answer</summary>

   c. `ssl.SSLEOFError` inherits from `ssl.SSLError`, which inherits from `OSError` directly.
   The other three are `ConnectionError`'s own children.
   </details>

2. What does this print?
   ```python
   class B(Exception): pass
   class C(B): pass

   try:
       raise C()
   except B:
       print("B")
   except C:
       print("C")
   ```
   <details><summary>Answer</summary>

   `B`. The first matching clause wins, and `except B` matches instances of its subclasses, so
   `except C` can never run.
   </details>

3. Spot the problem:
   ```python
   except (FileNotFoundError, OSError):
       print("Could not read the file")
   ```
   <details><summary>Answer</summary>

   `FileNotFoundError` is a subclass of `OSError`, so it adds nothing. Both get the same
   handling, and `except OSError:` does exactly the same.
   </details>

4. `tests/test_server.py:481` has `except (ConnectionError, socket.timeout):`. Is it redundant
   in the same way?
   <details><summary>Answer</summary>

   No. Both are subclasses of `OSError`, but neither is a parent of the other: they are
   siblings. Each name catches something the other doesn't, so listing both is meaningful and
   narrower than `OSError`.
   </details>

5. Why did removing `BUFFER_SIZE` need no code change anywhere else?
   <details><summary>Answer</summary>

   Nothing read it. The code uses `makefile("rb")` and `readline()`, which manage their own
   buffer, so no `recv(BUFFER_SIZE)` call exists. A search for the name found only the
   definition and the docs.
   </details>

### Defend the decision

1. Why does `client.py:85` catch `OSError` rather than the narrower `ConnectionError`?
   <details><summary>Model answer</summary>

   Because narrower would be wrong here. The socket is wrapped in TLS, and TLS failures like
   `ssl.SSLEOFError` are `OSError`s but not `ConnectionError`s. With `ConnectionError`, an
   abrupt TLS close would crash the client with a traceback. The handler does one thing for
   any failure of this network call, so the broad parent matches the intent. It is still
   limited to `send_message` and `receive_message`, so it can't hide unrelated bugs.
   </details>

2. `client.py:54` catches `ssl.SSLCertVerificationError` and `client.py:58` catches its
   ancestor `OSError`. Isn't that the redundancy you just removed?
   <details><summary>Model answer</summary>

   No. The redundant form was a tuple, where both classes got the same handling. Here they are
   separate clauses with different handling: a rejected certificate gets a clear message from
   `verify_message`, and everything else gets a generic handshake failure. The subclass comes
   first because the first match wins.
   </details>

3. You removed `ssl.SSLError` from `server.py:193`, so the code no longer says TLS errors are
   expected. Doesn't that make it less readable?
   <details><summary>Model answer</summary>

   It's a real trade-off, because the tuple worked as a hint. But the tuple also implies that
   `OSError` alone wouldn't catch TLS errors, which is false. The method is `tls_handshake` and
   the log line says "TLS handshake failed", so the context is clear. If it weren't, I'd add a
   comment rather than a redundant class.
   </details>

4. There was no new test in this commit. How do you know nothing broke?
   <details><summary>Model answer</summary>

   The change is behaviour-preserving by the language's rules: a parent class matches all its
   subclasses, so the old and new clauses catch the same exceptions. I checked the hierarchy
   with `__mro__` rather than from memory, and the existing suite passes. A new test would
   only test Python itself. The risky alternative, narrowing the class, would have needed one.
   </details>
