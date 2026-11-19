---
id: 005
title: What to check when reviewing a Python server (beyond the bugs already found)
date: 2026-11-14
asked-during: between commits (after "chore: add pre-review skill built from the 2026-10-21 review findings")
tags: [code-review, security, authentication, denial-of-service, concurrency, persistence, python]
---

# What to check when reviewing a Python server (beyond the bugs already found)

## What it is
The `pre-review` skill lists the mistakes one review already found in this repo. A checklist
built from past findings only catches what has happened before. This note lists the other
areas a reviewer of a server looks at, so new code can be checked for problems nobody has
reported yet.

A server differs from a script in three ways, and each one gives a group of questions:

1. **It runs for a long time.** Anything that grows, leaks or drifts will eventually break
   it.
2. **It talks to strangers.** Every input is chosen by someone else, possibly on purpose.
3. **It holds state that outlives one request.** Accounts, sessions and files must stay
   correct after a crash, a restart or two things happening at once.

## The areas

### 1. State that grows for ever
Ask of every dict, list, file and log: **who chooses the keys, and what removes entries?**
If a client chooses the key and nothing removes it, memory is a denial-of-service target.
The same goes for anything a client can make the server create: accounts, files, log lines.

### 2. Expensive work a stranger can ask for
Which requests cost a lot of CPU, disk or time, and can someone who isn't logged in send
them without limit? Password hashing is slow on purpose, so every endpoint that hashes is
an amplifier: a few bytes from the client buy a lot of server work. Put the cheap checks
first, and limit how often the expensive ones can run.

### 3. Authentication and authorization
- **One answer for every failure.** Login, registration and password reset must not reveal
  whether an account exists, by message *or* by timing.
- **Compare secrets in constant time** (`hmac.compare_digest`), and create them with
  `secrets`, never `random`.
- **Lockout cuts both ways.** A lockout per username stops guessing, but lets anyone lock a
  victim out. Decide and write down the trade-off.
- **Authorization is checked per command, on the server.** "Logged in" is not "allowed".
  Hiding a command from `help` isn't access control.
- **Session state changes cleanly.** What happens to the session on logout, on a second
  login, when the account is deleted while logged in?

### 4. Semantic validation
The `pre-review` skill checks that input *parses*. A reviewer also asks whether the parsed
value *makes sense*: length limits on every string, an allowlist for names, numbers in
range, no control characters or newlines in anything that is logged or printed (log
injection), and no client input inside a file path (path traversal). Validate with an
allowlist ("only these characters"), not a denylist.

### 5. What the error reply gives away
`str(error)` in a reply is safe only while every error raised on that path has a message
written for the user. One `KeyError` or `OSError` on the same path sends an internal detail
(a key name, a file path) to a stranger. Replies need one stable shape, so the client can
handle them without guessing.

### 6. Files the server trusts
A file the server wrote is still input when it reads it back: a person may have edited it,
or a crash may have cut it short. Ask: what happens on start-up if the file is empty,
invalid JSON, or missing a field? Is it written atomically (temporary file, then
`os.replace`)? What are its permissions? Can two processes write it at the same time?

### 7. Concurrency (as soon as there is more than one thread or process)
This server serves one client at a time, so there are no data races *inside* it today. The
question still applies between processes (the launcher and the server both open the users
file), and it becomes the main review topic the day threads or `selectors` arrive: every
shared object needs a lock or an owner, and "check, then act" sequences (does the user
exist? then create it) must be atomic.

### 8. Python traps
- `except Exception` or a bare `except` that hides bugs. A bare `except` also catches
  `KeyboardInterrupt` and `SystemExit`.
- `assert` used for validation: it is removed when Python runs with `-O`.
- Mutable default arguments (`def f(items=[])`): one list shared by every call.
- `pickle`, `eval`, `exec` or `subprocess` with `shell=True` anywhere near client input.
- `random` for tokens, `tempfile.mktemp`, `open()` without `encoding=`.

### 9. Configuration and deployment
Safe defaults: bind to `127.0.0.1`, not `0.0.0.0`, unless exposure is intended. TLS
verification never switched off, a minimum TLS version set, the private key readable only
by its owner. Secrets and generated files are git-ignored. A bad configuration value fails
at start-up with a clear message, not at the first request.

### 10. Shutdown and operation
Does the server stop cleanly on Ctrl+C **and** on `SIGTERM` (how a service manager or
`terminate()` stops it)? Is a reply in progress finished or cut? Does it exit with a
non-zero code after a failure? Can someone diagnose a problem from the log alone, without
the log containing secrets?

### 11. Design and readability
What Google's review guide lists first: is the design right for this code base, is it more
complex than today's problem needs, can the next reader understand it, do names and comments
say *why*? A reviewer reads every line. If a line can't be explained, that is a finding.

## Where it shows up in zr-client-server
Reading the current code with these questions gives candidates the 2026-10-21 review did
not list. They are read from the code, not reproduced with a test, so treat each as a
question to check:

- **Area 1:** `throttle.py:26`. `failures` is keyed by the username the client sent, and
  unknown usernames are counted on purpose. An entry is removed only by a successful login
  or an expired lockout that is checked again. A client sending a different username each
  time makes the dict grow without bound.
- **Area 2:** `server.py:97`. `register` needs no login, runs PBKDF2 and rewrites the users
  file. Nothing limits how many accounts one client creates.
- **Area 3:** `users.py:65`. `register` answers "User already exists: <name>", while
  `login` takes care to hide which usernames exist (`server.py:111`, `users.py:84`). The
  two endpoints disagree. Also `cmd_stop` (`server.py:121`): any logged-in user may stop
  the server (already planned as task 9.2 and step 13).
- **Area 6:** `users.py:35`. `_load` handles a missing file but not an invalid one, and
  `verify_password` (`users.py:88`) reads `record["hash"]`, `["salt"]` and `["iterations"]`
  from that file. A damaged file is a traceback at start-up or a `KeyError` during login.
  The write side is already done well: owner-only temporary file, then `os.replace`
  (`users.py:42`).
- **Area 7:** `run.py` and `server.py` each build a `UserStore` on the same file, and both
  write through the same `users.json.tmp` name.

Things the code already gets right, worth naming in an interview: constant-time comparison
(`users.py:90`), a dummy hash for unknown users (`users.py:86`), `re.fullmatch` on the
username (`users.py:60`), a monotonic clock for the lockout (`throttle.py:20`), TLS with a
minimum version and a pinned certificate.

## Alternatives and trade-offs
- **Checklist vs reading with questions.** A checklist is fast and repeatable but only
  finds known patterns. The three questions at the top (long-running, strangers, state)
  find new ones but depend on the reader. Use both: the checklist first, so the reading
  time goes to design.
- **Fix vs document.** Not every item needs code. For a learning project on localhost,
  "any logged-in user can stop the server" can be a written assumption. A reviewer accepts
  a known, written gap much more easily than an unnoticed one.
- **Tools.** Linters and scanners (`ruff`, `bandit`, `mypy`) catch several items in area 8
  automatically. They are third-party, so they could only run in CI here, never as a
  dependency of the app.

## Interview answer
"When I review server code I ask three things beyond 'does it work'. It runs for a long
time, so what grows without a limit? It talks to strangers, so what can an unauthenticated
client make it do, how much does that cost, and what do the replies reveal? And it keeps
state, so is that state still correct after a crash or two writers at once? In my own
project a review found the crash bugs, and I turned them into a checklist. Asking these
questions afterwards showed me things the review hadn't listed, for example a lockout
table keyed by client-chosen usernames that never shrinks, and a register reply that
reveals which usernames exist although login hides it."

## Read more
- [What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) — Google Engineering Practices · the reviewer's order of concerns: design, functionality, complexity, tests, naming, comments
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — OWASP · generic error messages for login *and* registration, timing, and lockout as a denial-of-service risk
- [Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html) — OWASP · cheap validation first, no resource allocation driven by user input, timeouts
- [Security Considerations](https://docs.python.org/3/library/security_warnings.html) — Python docs · the standard-library modules with known traps: `pickle`, `random`, `subprocess`, `tempfile`, `ssl`
- [threading: Lock objects](https://docs.python.org/3/library/threading.html#lock-objects) — Python docs · what protects shared state once there is more than one thread
- [How to Give Good Feedback for Effective Code Reviews](https://www.freecodecamp.org/news/code-review-tips/) — freeCodeCamp · beginner-friendly; the reviewer's side, useful for reading review comments
- Concept 003 (what an `except` clause catches) and concept 002 (NDJSON framing) in this repo
