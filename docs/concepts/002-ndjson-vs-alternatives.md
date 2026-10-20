---
id: 002
title: Newline-delimited JSON vs other serialization formats and framing
date: 2026-10-20
asked-during: between commits
tags: [json, ndjson, serialization, pickle, framing, tcp, protocol]
---

# Newline-delimited JSON vs other serialization formats and framing

## What it is

`protocol.py` makes two separate decisions:

1. **Serialization** (how one message becomes bytes): JSON, using the stdlib `json` module.
2. **Framing** (where one message ends and the next begins): one JSON object per line,
   terminated by `\n`. This is NDJSON (newline-delimited JSON).

## Where it shows up in zr-client-server

- `protocol.py:14`: `json.dumps(message) + "\n"` serializes and frames a message in one step.
- `protocol.py:24-27`: `sock_file.readline()` reads one frame, and `json.loads` decodes it.
- `server.py:61-62`: a line that isn't valid JSON gets an `Invalid JSON` error reply, and the
  connection stays open.
- `client.py:37`: `json.dumps(response, indent=2)` pretty-prints a reply for the user.

## Why JSON from the stdlib

- **Task constraint:** standard library only, which rules out `orjson`, `ujson`, `msgpack` and
  `protobuf`.
- **Human-readable:** you can debug the protocol with `nc`/`telnet` and plain eyes.
- **Safe to decode:** `json.loads` only builds dicts, lists, strings, numbers, booleans and
  `None`. `pickle`, the other stdlib option, can **execute arbitrary code** while it unpickles,
  so it must never be fed data from a socket.
- **Language-neutral:** any language can write a client. `pickle` works only from Python.
- **Fits the data:** small request/response dicts map one-to-one onto JSON objects.

**When you'd choose differently:** use `orjson`/`ujson` when JSON parsing becomes a hotspot under
heavy traffic. Use msgpack or protobuf when message size matters or you send raw binary data
(JSON has no bytes type). Use protobuf when you need a schema and a versioned contract
between teams.

## Why a newline as the frame delimiter

TCP is a **byte stream, not a message stream**. One `sendall` can arrive in several `recv`s, and
two can arrive glued together. The application must mark the boundaries itself:

| Option | Pros | Cons |
|---|---|---|
| **Delimiter `\n` (ours)** | Trivial with `makefile()` + `readline()`. Testable by hand. | The delimiter must never appear in the payload. JSON guarantees this, because `json.dumps` escapes newlines inside strings as `\n`. Not suitable for binary payloads. |
| **Length prefix** (e.g. `struct.pack("!I", len)`) | Works for any bytes. The receiver knows exactly how much to read. | Needs a "read exactly n bytes" loop. Not human-readable. |
| **Fixed length** | Simplest receiver. | Wastes space or truncates. Inflexible. |
| **One message per connection** (HTTP/1.0 style) | No framing: EOF ends the message. | A new TCP handshake for every command, and the session has no state. |

Our client keeps one session open for many commands, and every payload is text. So a
delimiter gives the simplest correct framing.

**Known gap:** `readline()` has no size limit, so a peer that never sends `\n` can make the
server buffer without bound. A production protocol caps the frame size (`readline(limit)` or a
maximum length prefix).

## Interview answer

> "I used newline-delimited JSON. The task allowed only the standard library. JSON is readable
> and, unlike `pickle`, safe to decode from untrusted input. TCP has no message boundaries, so I
> needed framing. A newline is the cheapest correct delimiter here: `json.dumps` never emits a raw
> newline, and `readline()` gives me exactly one message. For binary payloads or high throughput
> I'd switch to a length prefix with a binary format like msgpack or protobuf, and I'd cap the
> maximum frame size either way."

## Read more

- [Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html) — docs.python.org · the four ways to mark message boundaries (fixed length, delimiter, length prefix, close the connection)
- [pickle: Comparison with json](https://docs.python.org/3/library/pickle.html#comparison-with-json) — docs.python.org · why unpickling untrusted data is arbitrary code execution and JSON is not
- [json module](https://docs.python.org/3/library/json.html) — docs.python.org · `dumps`/`loads` and the `python -m json` pretty-printer
- [Working with JSON](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/JSON) — MDN · beginner-friendly intro to the JSON format itself
- [NDJSON specification](https://github.com/ndjson/ndjson-spec) — GitHub · the formal rules: one RFC 8259 JSON text per line, UTF-8, `\n` or `\r\n`
- [Message Framing](https://blog.stephencleary.com/2009/04/message-framing.html) — Stephen Cleary · length prefix vs delimiters, partial reads, and capping message size against DoS
