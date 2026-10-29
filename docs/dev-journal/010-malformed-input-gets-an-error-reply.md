---
id: 010
title: Malformed input gets an error reply, never a crash
commit: "fix: reply with an error to malformed input instead of crashing"
step: 16 — address the 2026-10-21 mentoring code review (batch 1, task 1.2)
date: 2026-10-26
tags: [python, exceptions, unicode, utf-8, json, framing, makefile, trust-boundary, dos, unittest]
---

# Malformed input gets an error reply, never a crash

## What we did
The review crashed the server with three lines a client can send. `handle_client` caught
only `json.JSONDecodeError`, so each of these escaped to `serve_forever` and stopped the
server:
- bytes that aren't valid UTF-8, which raise `UnicodeDecodeError`
- an integer of more than 4300 digits, which raises a plain `ValueError`
- very deep nesting, which raises `RecursionError`

On Python 3.13, 2000 levels of nesting parse fine and 100,000 don't. We ran a throwaway
probe to find these out instead of guessing.

The probe also showed that catching the errors wasn't enough. With a **text-mode**
`makefile("r")`, we sent a bad line followed by a valid `{"command": "info"}`. The first
`readline()` raised `UnicodeDecodeError`, and the second one *hung*. The text layer had
read a whole chunk of bytes, failed to decode it, and lost the valid line along with the
bad one. So "reply with an error and keep the session" would have stalled the session.

The fix moves decoding after framing:
- Every side now opens the connection as `makefile("rb")`.
- `receive_message` (`protocol.py:21`) reads one line of **bytes** and then decodes just
  that line, strictly (`protocol.py:35`). The bad bytes are gone from the stream before
  decoding starts, so the next line is untouched.
- The server catches `(ValueError, RecursionError)` (`server.py:151`). `ValueError` covers
  `UnicodeDecodeError`, `JSONDecodeError` and the int-limit error. `RecursionError` is a
  `RuntimeError`, so it needs its own entry.
- The reply is now `"Invalid message: expected one line of UTF-8 JSON"`.

**The decision:** a malformed *message* rejects only that message. An `OSError` on the
*connection* ends only that session (task 1.1). Nothing a client sends reaches
`serve_forever`.

`errors="replace"`/`"ignore"` were rejected on purpose. They would quietly change the
request before it reaches the server's logic instead of refusing it. `json` and `ENCODING`
became unused in `server.py`, and `ENCODING` in `client.py`, so those imports were removed.

The tests (`tests/test_server.py:145`) share one helper. It sends the raw line, expects an
`error` reply, expects `info` to still work **on the same connection**, then disconnects
and checks that a new client is served. All three tests failed before the fix with the
log line "Server stopped", and they pass after it. The full suite: 44 tests, OK (1 skip on
Windows, as before).

## How it fits
- **Plan:** Step 16, batch 1, task 1.2. Batch 1 is now complete, so
  `fix/server-survives-bad-client` is ready for a PR. Batch 5 (message size limit, idle
  timeout) builds on this `receive_message`. A size limit would also cap how deep the
  nesting can get and how long an integer can be.
- **Practice:**
  - *Validate at the trust boundary.* Bytes from the network are untrusted.
    `receive_message` + `handle_request` is the boundary. Every failure there becomes a
    reply, never an exception leaving the session.
  - *Frame first, then decode each message.* Splitting on `\n` works on bytes (UTF-8 never
    uses byte `0x0A` inside a multi-byte character). Decoding per message keeps one bad
    message from damaging the next. HTTP/1.1 works the same way: headers are framed as
    bytes and decoded afterwards.
  - *Catch by base class, deliberately.* `except ValueError` is broad, but here every
    `ValueError` comes from parsing one line, so it means the same thing.
  - *When you'd choose differently:* a protocol that can't trust a client's later messages
    after garbage (a binary stream that has lost its framing) should drop the connection.
    A length-prefixed protocol checks the length before reading anything.

## Commands used
- `git log --oneline master..HEAD`: what this branch already has (task 1.1).
- `git show --stat HEAD~1`: which files the planning commit touched.
- `grep -n -i -A40 "step 16\|16\." PLAN.md`, `grep -n -i "^#\|branch" docs/plans/001-code-review-2026-10-21.md`: find the task in the plan.
- `sed -n 92,163p docs/plans/001-code-review-2026-10-21.md`: read batch 1.
- `cat protocol.py`, `sed -n '/def handle_client/,/^    def [a-z_]*(/p' server.py`: read the code being changed.
- `ls docs/dev-journal docs/concepts`: next free journal number.
- `python --version`: the exceptions depend on the version (3.13.1).
- `cat > probe.py <<'EOF' … EOF`, then `timeout 60 python -I -u probe.py`: the experiment. The first run had no `-u` and no socket timeout, so it hung silently on the second `readline()`, which is itself the finding.
- `sed -i 's/…/…/' probe.py`: add `b.settimeout(2)` to the probe.
- `timeout 120 python -m unittest tests.test_server.ServerTest.test_invalid_utf8 …`: the new tests fail before the fix.
- `timeout 300 python -m unittest discover tests 2>&1 | grep -a "^Ran\|^OK\|FAIL\|Error"`: full suite after the fix.
- `grep -n "\bENCODING\b\|\bjson\b" server.py client.py`, `git grep -n "skip" tests`: find imports that became unused, and confirm the skip was already there.
- `python -c "import client, server"`: the modules still import after removing them.

## Read more
- [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy): Python docs · `UnicodeDecodeError` → `UnicodeError` → `ValueError`; `RecursionError` → `RuntimeError`. That's why the `except` names two classes.
- [Integer string conversion length limitation](https://docs.python.org/3/library/stdtypes.html#integer-string-conversion-length-limitation): Python docs · the 4300-digit default exists "to mitigate denial of service attacks" (CVE-2020-10735), because base-10 conversion isn't linear.
- [json: security note and implementation limitations](https://docs.python.org/3/library/json.html): Python docs · "A malicious JSON string may cause the decoder to consume considerable CPU and memory"; the module sets no nesting limit of its own.
- [Unicode HOWTO](https://docs.python.org/3/howto/unicode.html): Python docs · `bytes.decode` with `errors='strict'` vs `'replace'`/`'ignore'`, and why strict is the right choice for a trust boundary.
- [socket.makefile](https://docs.python.org/3/library/socket.html#socket.socket.makefile): Python docs · modes `'r'`/`'b'`, and the warning that the internal buffer may be inconsistent after a timeout (relevant to batch 5).
- [UTF-8](https://developer.mozilla.org/en-US/docs/Glossary/UTF-8): MDN · beginner-friendly: one to four bytes per character, ASCII-compatible.
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html): OWASP · validate at every trust boundary; syntactic vs semantic validation.
- Concept 003, [What an except clause catches](../concepts/003-except-clause-scope.md): why the reply is still only *built* inside the handler.

## Quiz

### Revise
1. Which of these does `except ValueError` catch? (a) `UnicodeDecodeError` (b) `json.JSONDecodeError` (c) `RecursionError` (d) the error from `int("1" * 5000)`
   <details><summary>Answer</summary>

   a, b and d. `UnicodeDecodeError` and `JSONDecodeError` both inherit from `ValueError`, and the int-limit error is a plain `ValueError`. `RecursionError` inherits from `RuntimeError`, so it needs its own entry.
   </details>
2. Why does CPython refuse to convert a 5000-digit decimal string to `int` by default?
   <details><summary>Answer</summary>

   Converting between base 10 and a binary bignum isn't linear-time, so a long enough number can tie up the CPU. The 4300-digit limit (since 3.11) mitigates that denial-of-service vector (CVE-2020-10735). Bases that are powers of two aren't limited.
   </details>
3. What does this print?
   ```python
   print(b"\x80abc".decode("utf-8", "replace"), b"\x80abc".decode("utf-8", "ignore"))
   ```
   <details><summary>Answer</summary>

   `�abc abc`. `replace` substitutes U+FFFD and `ignore` drops the bad byte. Neither raises, which is exactly why the server uses the strict default.
   </details>
4. Spot the bug: a server reads with `f = conn.makefile("r", encoding="utf-8")`, catches `UnicodeDecodeError` around `f.readline()`, replies with an error and keeps looping.
   <details><summary>Answer</summary>

   The text layer decodes a whole buffered chunk, not one line. When it fails, the valid lines that came after the bad one in that chunk are lost. In our probe, the next `readline()` blocked waiting for data the client had already sent. Read bytes (`"rb"`) and decode per line instead.
   </details>
5. Why is it safe to split UTF-8 bytes on `b"\n"` *before* decoding?
   <details><summary>Answer</summary>

   In UTF-8, every byte of a multi-byte character has its high bit set (`0x80`–`0xFF`), so the byte `0x0A` only ever means a newline. Byte-level framing can't cut a character in half.
   </details>

### Defend the decision
1. "Why not just add `errors='replace'` to `makefile` and be done?"
   <details><summary>Model answer</summary>

   It would stop the crash, but it changes untrusted input without telling anyone. A username with a bad byte would become a different username containing `�`, and the server would act on a request the client never sent. At a trust boundary, rejecting is safer than repairing. Strict decoding plus an error reply tells the client exactly what went wrong. `replace` makes sense for *displaying* text, like logs, not for input you act on.
   </details>
2. "Why keep the session after garbage instead of disconnecting the client?"
   <details><summary>Model answer</summary>

   With NDJSON the framing survives a bad line: the `\n` still marks where the next message starts, and the line has already been consumed. So one bad message can be rejected cheaply, the way we already handled invalid JSON. Disconnecting would be simpler and stricter. It's the right call when framing itself is lost, or for a client that keeps sending garbage. Repeated abuse is better handled by the size and time limits in batch 5.
   </details>
3. "Catching `RecursionError` feels like a hack. Why not limit the nesting depth yourself?"
   <details><summary>Model answer</summary>

   The stdlib `json` has no depth option, so enforcing a limit would mean pre-scanning the line or writing a custom parser. That's a lot of code for this project. `RecursionError` here is raised in the session's own call to `json.loads` and is caught right there, so it's contained. The cleaner long-term guard is a maximum message size (batch 5, task 5.1), which caps how deep the nesting can get and how long an integer can be before parsing starts.
   </details>
4. "You changed `receive_message` to take a binary file. Isn't that a breaking API change?"
   <details><summary>Model answer</summary>

   Yes, but it's internal: the server, the client and the tests are the only callers, and all three changed in this commit. The docstring states the new contract and lists the exceptions it raises. If `protocol.py` were a published library, I'd accept both kinds of stream or add a new function and deprecate the old one.
   </details>
