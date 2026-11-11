---
id: 004
title: Rejecting vs tolerating an unterminated final frame
date: 2026-11-11
asked-during: task 4.2 (before the briefing), fix/protocol-contract
tags: [ndjson, framing, protocol, tcp, robustness-principle, security]
---

# Rejecting vs tolerating an unterminated final frame

## What it is

In newline-delimited JSON (NDJSON), the `\n` ends a message. Something has to happen when the
peer closes the connection after sending a complete JSON value but **no** final `\n`:

```
{"command": "stop"}<EOF>
```

`readline()` returns everything up to the newline, or up to EOF if no newline comes, so the
current code can't tell the two apart. It decodes the bytes, and the server runs `stop`. The
review (task 4.2) asks us to pick a rule and make the code, the README and `PLAN.md` agree on it.

## Where it shows up in zr-client-server

- `protocol.py:33-50`: `receive_message` calls `sock_file.readline()` and only checks for an
  empty result (`ConnectionClosed`). It never checks that the line ends with `b"\n"`.
- `server.py:161`: the server handles whatever `receive_message` returns.
- `client.py:84`: the client reads replies with the same function, so the rule applies in both
  directions. The server always sends `\n` (`protocol.py:30`), so replies are not affected.

## What the specs say

- **NDJSON spec, 3.1:** each JSON text "MUST be written to the stream followed by the newline
  character `\n`". It says nothing explicit about the last line.
- **JSON Lines** (a sibling format): a terminator after the last value is "strongly
  recommended but not required". That is the tolerant reading, written down.

Neither spec decides this for us, so it's our protocol's call.

## Option A: reject the unterminated frame

The rule: **no `\n`, no message.** A line that ends at EOF is incomplete, so it's dropped (and
logged) and the session ends. *Chosen, see dev-journal 019:* the server also tries one error
reply and ignores a failed send.

**Pros**
- **One framing rule.** "A message ends with `\n`" is the whole contract. Tolerating EOF adds a
  second, hidden rule ("or the connection closing").
- **Matches what we already promise.** The README and `PLAN.md` already say every message ends
  with `\n`, and NDJSON says MUST.
- **Intent is explicit.** The newline acts as the sender's "send" button. Without it, a
  half-written request from a crashing client is processed only if the bytes happen to form
  valid JSON. For our objects, a truncated `{...}` is always invalid JSON, so the practical risk
  is small. A bare number (`123` cut to `12`) shows that in general a truncated frame can still
  parse.
- **No effect from a vanished client.** With tolerance, a `stop` takes effect on a connection
  whose sender has already gone, so nobody receives the reply. A destructive command shouldn't
  run silently.
- **Simplifies task 5.1 (maximum message size).** With `readline(limit)`, "no `\n` at the end"
  means "cut at the limit" or "EOF mid-message". Both mean "not a complete message", so one
  check covers both.
- **Strict receivers age better.** RFC 9413 argues that tolerated flaws become entrenched:
  once a client relies on them, you can't remove them without breaking that client.

**Cons**
- **A little code and a behaviour change.** It needs an `endswith(b"\n")` check, a decision
  about logging, and a test. Anyone who scripted the server with `printf '...'` (no newline)
  would break, but nobody has.
- **The client may get no error.** If the peer fully closed, an error reply has nowhere to go.
  It can only reach a client that half-closed (`shutdown(SHUT_WR)`) and is still reading.
- **Less forgiving for hand testing**, for example when a tool doesn't add a trailing newline.

## Option B: tolerate it and document it

The rule: **a message ends with `\n`, or with the connection closing.** Code stays as it is,
and the README and `PLAN.md` gain a sentence.

**Pros**
- **No code change.** Only docs, so there's no risk of regressions.
- **Robustness principle (Postel's law):** "be liberal in what you accept". JSON Lines takes
  this stance.
- **Friendly to quick scripts:** `echo -n`, or a client that closes right after its last
  request (HTTP/1.0 style).

**Cons**
- **Two ways to end a message,** so every future reader (task 5.1, another client
  implementation) has to handle both.
- **Contradicts NDJSON's MUST.** We'd be documenting a deviation, not following a standard.
- **Commands without a listener:** `stop` runs, and the reply goes to a closed socket.
- **Hard to undo later.** Once a client depends on it, removing it is a breaking protocol
  change (a MAJOR bump under SemVer, see concept 001).

## Recommendation

**Reject (option A).** It keeps one rule that matches the spec and our own docs, it makes task
5.1 simpler, and it costs a few lines. Tolerance would be the better choice for a log-file
reader, where the last line of a file being written is often unterminated and losing it hurts.
Our live request/response session is not that case.

## Interview answer

> "In my NDJSON protocol, the newline is the end-of-message marker, so a frame that ends at EOF
> without one is incomplete and I drop it. The alternative, tolerating it, adds a second
> framing rule (EOF also ends a message). It contradicts the NDJSON spec, and it lets a command
> like `stop` run from a client that has already gone. Postel's law says to be liberal in what
> you accept, but RFC 9413 shows how that entrenches bugs. For a file reader I'd tolerate a
> missing last newline. For a live command protocol I prefer one strict rule."

## Read more

- [NDJSON specification](https://github.com/ndjson/ndjson-spec) — GitHub · section 3.1: each JSON text MUST be followed by `\n`; silent on the last line
- [JSON Lines](https://jsonlines.org/) — jsonlines.org · the tolerant counterpart: a final terminator is "strongly recommended but not required"
- [IOBase.readline](https://docs.python.org/3/library/io.html#io.IOBase.readline) — docs.python.org · why `readline()` returns a line without `\n` at EOF, and the `size` argument used in task 5.1
- [Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html) — docs.python.org · `recv` returning 0 bytes means the peer closed; its example treats EOF mid-message as "connection broken"
- [Robustness principle](https://en.wikipedia.org/wiki/Robustness_principle) — Wikipedia · beginner-friendly: Postel's law and its critics (RFC 3117, RFC 9413)
- [RFC 9413: Maintaining Robust Protocols](https://www.rfc-editor.org/rfc/rfc9413.html) — RFC Editor · why tolerating faulty input entrenches it; fix problems at the source
- Concept [002](002-ndjson-vs-alternatives.md) — why we frame with `\n` at all
