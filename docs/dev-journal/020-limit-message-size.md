---
id: 020
title: Limit the size of one message
commit: "fix: limit the size of one message"
step: 16 — address the 2026-10-21 mentoring code review (batch 5, task 5.1)
date: 2026-11-13
tags: [python, protocol, framing, ndjson, readline, dos, security, request-smuggling, unittest]
---

# Limit the size of one message

## What we did
`receive_message` called `readline()` with no size, so a client that kept sending bytes
without a `\n` made the server buffer all of them, with no upper bound on memory. Concept 002
had already listed this as a known gap. Now a message has at most `MAX_MESSAGE_SIZE` bytes
before its `\n` (`config.py:9`, 64 KiB). The unit is **bytes of the decrypted line**: since
task 4.1 the server reads a binary stream (`"rb"`), and TLS sits below `protocol.py`, so the
limit never sees the encrypted bytes on the wire. The real requests are far below it (`register`
is a few hundred bytes).

The trick is to read **one byte more than the limit**: `readline(max_size + 1)`
(`protocol.py:74`). A line that ends with `\n` is a complete message that fits. A full
`max_size + 1` bytes with no `\n` means the limit cut the line off, so `receive_message`
raises the new `MessageTooLong` (`protocol.py:36`). Anything shorter without a `\n` is still
a close, so `ConnectionClosed` is raised as before. `MessageTooLong` is a plain `Exception` for
the same reason as `ConnectionClosed`: as a `ValueError`, the server's "malformed line, carry
on" branch would catch it.

The server (`server.py:176`) logs a warning with the address and the limit (never the bytes)
and sends a best-effort error reply. Then it **closes the connection**. That's the key
decision: the rest of the over-long line is still unread. Reading on would return its tail as
the next message, and the client chose those bytes. 64 KiB of padding followed by
`{"command": "stop"}` would then run `stop`. This is a small cousin of HTTP request
smuggling. The reply code from task 4.2 is now shared: both `reject_unterminated_message` and
the new `reject_oversized_message` (`server.py:214`) call `send_last_error`
(`server.py:229`), which tries one send and logs a failure at DEBUG.

`Server` takes a `max_message_size` argument (`server.py:62`), like the other things it
already receives from outside (`users`, `tls_context`, `login_throttle`). Tests use that to set
a 200-byte limit and hit the boundary exactly. `test_nesting_too_deep` (`tests/test_server.py:353`)
needed it as well. It sends 200,000 bytes, which is over the new limit, so it raises the limit
for its own server instead of shrinking the depth. A smaller depth still raised
`RecursionError` on Python 3.10, 3.12 and 3.13, but 3.14 limits recursion by C stack size, and
no 3.14 was available locally to check.

Tests:
- `tests/test_protocol.py:106` covers the size limit in `receive_message`:
  - a message exactly at the limit is read, and one byte over raises;
  - the reader stops at `max_size + 1` bytes of a 10,000-byte line (`stream.tell()`), which is what bounds memory;
  - a short unterminated line is still a close;
  - the default comes from `config`.
- `tests/test_server.py:190-201` drive `handle_client` with fakes: one read, one reply, one
  warning, even if the reply fails.
- End to end over TLS (`tests/test_server.py:368-399`):
  - a request exactly at the limit is answered and the session goes on;
  - one byte over gets "too long" and then end of stream, and the content isn't logged;
  - the smuggling payload doesn't stop the server, and a new client is still served.

All 89 tests pass on Python 3.10, 3.12 and 3.13. We skipped the usual "break the fix and watch
the test fail" check for this commit.

## How it fits
- **Plan:** step 16, batch 5, task 5.1 (`docs/plans/001-code-review-2026-10-21.md`), on
  branch `fix/server-limits`. Task 5.2 (idle timeout) comes next. It deals with the opposite
  attack: a client that sends *nothing*, so the single-client server waits for it forever.
  The client reading the server's replies has the same unlimited `readline()`. That belongs to
  batch 7 (client errors).
- **Practice:**
  - **Bound every input you didn't produce.** OWASP lists "limit total request size" under
    resource exhaustion. HTTP servers cap header size (431) and body size (413).
  - **Agree on where a message ends, or close.** Once a reader loses track of message
    boundaries, every following byte is ambiguous. Closing the connection is the only safe way
    to resynchronise. Skipping to the next `\n` would mean reading an unbounded amount of data
    we've already decided to reject.
  - **Read one past the limit** so that "line ended exactly at the limit" and "line cut at the
    limit" look different. It's the same idea as `endswith(b"\n")` in task 4.2.
  - **When you'd choose differently:** with a length-prefixed protocol, you check the declared
    length *before* reading the payload. You can also skip an oversized frame and keep the
    session, because you know exactly how many bytes to discard. A protocol that carries files
    would stream them in chunks instead of raising the limit.

## Commands used
- `git checkout -q master`, `git pull -q --ff-only`: update `master` after merging PR #7 (`-q` new in [git pull](../commands.md#git-pull-fetch-and-update-the-current-branch) and [git checkout](../commands.md#git-checkout-switch-branches))
- `git checkout -b fix/server-limits`: start the batch 5 branch
- `git log --oneline -3`: confirm the merge landed on `master`
- `sed -n '/^### Task 5.1/,/^### Task 5.2/p' docs/plans/001-code-review-2026-10-21.md`: read the task
- `cat protocol.py config.py`, `sed -n 46,64p PLAN.md`, `head -60`, `tail -3`: read the code and docs to change
- `grep -n -E "receive_message|ConnectionClosed|…" server.py`, `grep -n -A1 …`: find the lines to change and the lines the heredoc broke
- `python --version`; `python -c "import json; json.loads('['*d+']'*d)"` for several depths: find which nesting depths raise `RecursionError`
- `py -0`; `py -3.10 -c …`; `py -3.12 -c …`: the same check on other installed versions ([py](../commands.md#py-the-windows-python-launcher), new)
- `python - <<'EOF' … EOF`: apply the multi-line edits to `server.py`, the tests and `docs/commands.md`
- `sed -n 358,368p tests/test_server.py | cat -A | cut -c1-110`: see that `\n` in the heredoc had become a real line break, which caused the `SyntaxError`
- `grep -n -E '\S {10,}\S' …`: check that no line had been joined by a lost `\` line continuation
- `python -m unittest discover tests`; `py -3.10 -m unittest discover tests`; `py -3.12 -m unittest discover tests`: run the suite on three versions
- `sed -i 's/^date: 2026-10-20$/date: 2026-11-13/' docs/concepts/002-ndjson-vs-alternatives.md`: update the note's date
- `git status --short`, `git diff --stat`: check what changed before committing

## Read more
- [io.IOBase.readline](https://docs.python.org/3/library/io.html#io.IOBase.readline) — docs.python.org · "If *size* is specified, at most *size* bytes will be read". This is the whole mechanism. For a text stream (`TextIOBase`) it counts characters instead.
- [Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html) — OWASP · "Limit total request size", filed under resource exhaustion
- [431 Request Header Fields Too Large](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/431) — MDN · how HTTP refuses an over-long request: the same idea in a protocol you use every day
- [HTTP request smuggling](https://portswigger.net/web-security/request-smuggling) — PortSwigger Web Security Academy · what goes wrong when two readers disagree on where a request ends; the reason we close instead of reading on
- [Concept 002: NDJSON vs alternatives](../concepts/002-ndjson-vs-alternatives.md) — this repo · the framing choice, and the "known gap" this commit closes

## Quiz

### Revise
1. Why does `receive_message` call `readline(max_size + 1)` and not `readline(max_size)`?
   <details><summary>Answer</summary>

   A message of exactly `max_size` bytes needs one more byte for its `\n`. With
   `readline(max_size)` that message would come back without its newline and look the same as
   a line cut off at the limit. The extra byte makes "fits exactly" and "too long" different.
   </details>
2. With `max_size = 16`, what does `receive_message` do for each stream? (a) 16 bytes + `\n`,
   (b) 17 bytes + `\n`, (c) 10 bytes and then end of stream, (d) empty stream.
   <details><summary>Answer</summary>

   (a) returns the decoded message, (b) raises `MessageTooLong` after reading 17 bytes,
   (c) raises `ConnectionClosed(discarded=10)`, (d) raises `ConnectionClosed(discarded=0)`.
   </details>
3. Which unit does `MAX_MESSAGE_SIZE` use, and why not characters?
   <details><summary>Answer</summary>

   Bytes of the decrypted line, without the `\n`. The server reads a binary stream
   (`makefile("rb")`), and `readline(size)` on a binary stream counts bytes. A character limit
   would let a client send up to four times as many bytes with 4-byte UTF-8 characters.
   </details>
4. Spot the bug: `class MessageTooLong(ValueError): ...`
   <details><summary>Answer</summary>

   `handle_client` catches `ValueError` as "malformed line, reply and continue". The session
   would go on, and the next read would parse the unread tail of the over-long line as a new
   request.
   </details>
5. What does `stream.tell() == LIMIT + 1` prove in `test_reading_stops_one_byte_past_the_limit`?
   <details><summary>Answer</summary>

   That `receive_message` read only `LIMIT + 1` bytes of a 10,000-byte line. A wrong version
   that read the whole line and then checked its length would still raise `MessageTooLong`,
   but it wouldn't limit memory at all.
   </details>

### Defend the decision
1. "Why close the connection on an over-long message instead of skipping it and carrying on?"
   <details><summary>Model answer</summary>

   With newline framing, the end of the message is the next `\n`, and I don't know how far
   away that is. To skip the message I'd have to keep reading an unknown number of bytes, which
   is the unbounded work the limit exists to prevent. If I simply read on, the tail of the line
   becomes the next request. Someone could pad past the limit and add `{"command": "stop"}`,
   which is the same idea as HTTP request smuggling. Closing is the only safe way to
   resynchronise. With a length prefix I could skip the frame, because the header tells me
   exactly how many bytes to discard.
   </details>
2. "Why 64 KiB, and why a constant in `config.py` plus a `Server` argument?"
   <details><summary>Model answer</summary>

   It's much larger than any real request (`register` is a few hundred bytes), so a legitimate
   client never hits it, and small enough that one connection can't use much memory. The
   constant lives in `config.py` with the other protocol settings, as one source of truth. The
   constructor argument follows how `Server` already receives `users`, `tls_context` and
   `login_throttle`: tests can set a 200-byte limit and hit the boundary exactly, without
   monkeypatching a module global. If we added a command that uploads files, I'd stream the
   file in chunks rather than raise the limit.
   </details>
3. "Why put the check in `protocol.py` and not in `server.py`?"
   <details><summary>Model answer</summary>

   The size has to be checked *while reading*. Once `readline()` has returned an unbounded
   line, the memory is already used, so the server can't check it afterwards. Framing is
   `protocol.py`'s job, and "where does a message end, and how long may it be" is framing. What
   to *do* about it (log, reply, close) is server policy, so that stays in `server.py`. The
   same split as task 4.1: `protocol.py` knows what a message is, the server knows what a
   request is.
   </details>
