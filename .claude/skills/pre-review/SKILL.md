---
name: pre-review
description: Use before opening a pull request or asking for a code review in this repository, or when the user asks to "check my branch", "pre-review" or "self-review". Runs a checklist built from the findings of past reviews (error handling, trust boundary, negative tests, resource lifecycle, clocks and platform, logging, docs drift) over the branch's diff and reports each problem as file:line, so it is fixed before the reviewer sees it.
---

# Pre-review

A reviewer's time is best spent on what a checklist can't find. This skill finds the rest
first. Every item below is a mistake a reviewer has already found in this repo, written as a
question to ask of new code. The tag after an item (`1.1`, `4.2`, …) is the task in
`docs/plans/001-code-review-2026-10-21.md` that taught it; read that task when an item is
unclear. Items tagged `c005` are general server practice that no review here has reported
yet; `docs/concepts/005-reviewing-a-python-server.md` explains them.

The root pattern behind most findings: **the code assumed the other side behaves
correctly.** The peer, the file, the user at the keyboard and the operating system can each
do the wrong thing at the worst moment. Ask that of every changed line.

For code that no item below covers, ask the three questions a server always raises (c005):
1. **It runs for a long time.** What grows, leaks or drifts without a limit?
2. **It talks to strangers.** What can a client that isn't logged in make it do, what does
   that cost, and what do the replies reveal?
3. **It keeps state.** Is the state still correct after a crash, a restart, or two writers
   at once?

## How to run it

1. **Get the change.** Default scope is the branch against `master`:
   `git diff master...HEAD` plus `git status --short` for uncommitted work. If the user
   names a commit, a file or a range, use that instead.
2. **Read whole functions, not hunks.** For every changed function, read the full function
   and its callers. Most past findings were about what the code around a line did *not* do
   (a send with no `try`, a `listen()` outside the guarded region).
3. **Pick sections by file** (table below), then ask every item in those sections. Sections
   G and H apply to every change, and L to every change in a `.py` file.
4. **Prove it where it's cheap.** A suspected crash or wrong reply is a finding only once
   you can name the input that triggers it. If a five-line script or a test can show it, run
   it and say what happened. Never claim something was run when it wasn't.
5. **Report, don't fix.** Output the report below and stop. Fixes are separate chunks and go
   through `learn-by-commit`, one finding (or one closely related group) per commit, test
   first.

| Changed files | Sections |
|---|---|
| `server.py`, `protocol.py` | A, B, C, D, E, F, I, J |
| `client.py` | A, B, C, D |
| `run.py` | A, B (the probe), D, E, K (it opens the users file too) |
| `users.py`, `throttle.py`, `admin_setup.py` | A, B, D, E, F, I, J, K |
| `tests/` | C, D |
| `config.py` | G (is every constant used? does it state its unit?), E5 |
| docs, skills, `PLAN.md`, `README.md` | H |

## Report format

Order by severity, then by file. Keep each finding to a few lines.

```markdown
## Pre-review: <branch> against master (<n> files, <n> findings)

### Critical: one bad peer or input stops or hangs the program
- `server.py:142` [A1] <what is wrong, in one sentence>
  Trigger: <the concrete input or event>. Seen before: task 1.1.
  Question: <the guiding question from the checklist item>

### Important: wrong behaviour, a missing limit, or a missing test for new behaviour
### Recommended: clarity, drift, dead code

### Checked and clean
<the sections that were run and found nothing, one line each>

### Not checked
<what the checklist can't reach here: manual Windows check, interactive prompt, …>
```

Rules for the report:
- Give the **question before the answer**. The owner learns by working the fix out; add the
  fix itself only if they ask.
- No finding without a `file:line` and a trigger. "Consider adding more tests" is not a
  finding; "no test sends a line without `\n`" is.
- If nothing is found, say so plainly and list what was checked. Don't invent findings to
  look thorough.
- A known, written-down gap (in `PLAN.md`, README "Security assumptions" or a code comment)
  is not a finding. An unwritten one is.

## The checklist

### A. Error handling

- **A1. Every network or I/O call is inside a `try` whose `except` really covers it.** List
  the calls in the function (`accept`, `wrap_socket`, `readline`, `sendall`, `connect`,
  `open`, `Popen`). Include calls made *inside* an `except` or `finally` block: an
  exception raised in a handler is not caught by its sibling `except` clauses. (1.1)
- **A2. One connection's error stays in that connection.** Can any exception from serving
  one client reach `serve_forever` and close the listening socket? (1.1)
- **A3. List what each call can raise, from the docs, not from memory.** `readline()` on a
  text stream raises `UnicodeDecodeError`; `json.loads` raises `JSONDecodeError`, plain
  `ValueError` (an integer over 4300 digits) and `RecursionError` (deep nesting);
  `wrap_socket` and TLS reads raise `ssl.SSLError`; a timeout raises `TimeoutError`. Check
  the hierarchy: which `except` catches which? (1.2)
- **A4. No parent and child in one `except`.** `(ConnectionError, OSError)` and
  `(ssl.SSLError, OSError)` say the same as `OSError` and suggest a difference that doesn't
  exist. Catch the narrowest class that is still correct. (3.2)
- **A5. Each failure has a decided outcome, written in a comment:** reject this message and
  keep the session, end this session, or stop the program. After the failure, is the stream
  still usable? If part of a message is unread, the session must end. (1.2, 5.1)
- **A6. Nothing is swallowed silently.** `except …: pass` and `return None` need a log line
  or a comment that says why silence is right. (3.1)
- **A7. The user sees a message, never a traceback.** Client and launcher: a refused or
  timed-out connection, Ctrl+C while waiting for a reply, a reply that isn't a JSON object
  (`response.get` on a list raises `AttributeError`). (7.1)
- **A8. Failures are reported to the caller.** A launcher or script exits non-zero when
  what it ran failed. (8.2)

### B. Trust boundary: anything read from a socket, file, argument or environment

- **B1. Trace bytes → text → JSON value → request shape.** At each step: what can it raise,
  and where is that handled? Which layer checks that the value is an object, that `command`
  is a string and that `args` has the right type? (1.2, 4.1)
- **B2. There is a size limit.** No `readline()`, `read()` or `recv` loop without a bound.
  The limit states its unit (bytes or characters). After cutting a line short, the rest is
  never parsed as the next message. (5.1)
- **B3. There is a time limit.** No blocking read, connect or handshake without a timeout.
  With one client at a time, one silent peer blocks everyone. After a timeout on a
  `makefile()` stream, close it; don't read on. (5.2, 7.2)
- **B4. A special return value can't collide with real data.** `None` for "connection
  closed" collided with a decoded JSON `null`. Use an exception or a unique sentinel for
  out-of-band signals. (4.1)
- **B5. The framing rule in the README is the rule in the code.** If a message ends with
  `\n`, a final frame without it must not run. (4.2)
- **B6. Both directions.** The client trusts the server no more than the server trusts the
  client: it validates the reply before using it. (7.1)
- **B7. "Something answered" is not "our server answered".** A successful `connect()` only
  means the OS queued the connection. A probe that must know more does a real protocol
  exchange. (7.2, 8.3)
- **B8. Who may do this?** For a new command or side effect: which account or process can
  trigger it? If the answer is "anyone logged in", is that written in the README? (9.2)
- **B9. The value makes sense, not only parses.** Every string from the peer has a length
  limit, names match an allowlist (`re.fullmatch`), numbers are in range. Check the type
  before using the value: `args.get("username")` may be a list or `None`. (c005)
- **B10. Peer input never reaches a log line, a terminal or a file path unchecked.** A
  newline in a logged value forges a log line; `..` in a path leaves the folder. (c005)
- **B11. An error reply gives away nothing internal.** `str(error)` in a reply is safe only
  if every exception that can reach that `except` carries a message written for the user.
  Could a `KeyError`, an `OSError` with a path, or a library message get there? Replies
  keep one shape (`status`, `command`, `message` or `data`). (c005)

### C. Tests

- **C1. Every new behaviour and every fix has a test that fails without the change.** Say
  how that was checked (stash the fix, run the test, watch it fail).
- **C2. Hostile inputs are tested, not only the happy path.** For anything that reads from
  the peer, go through this table and name the test for each row, or say why it doesn't
  apply. (1.1, 1.2, 4.1, 4.2, 5.1, 5.2)

  | Input | What must happen |
  |---|---|
  | bytes that aren't valid UTF-8 | error reply, session goes on |
  | invalid JSON | error reply, session goes on |
  | valid JSON that isn't an object: `null`, `[]`, `5`, `"x"` | error reply, session goes on |
  | an integer with more than 4300 digits | error reply, no crash |
  | JSON nested thousands of levels deep | error reply, no crash |
  | a line longer than the limit, or one that never ends | error, connection closed |
  | a complete message without the final `\n`, then close | not run |
  | several requests, then close without reading the replies | only that connection ends |
  | a reset (RST: `SO_LINGER` with a zero timeout) | only that connection ends |
  | connect, then silence | dropped after the timeout |
  | plain TCP to the TLS port | handshake fails, server goes on |

- **C3. Every server test of a failure ends with the control question:** a *new* client
  connects and still gets an answer.
- **C4. Logic is tested without sockets where it can be.** `handle_request` is called
  directly; `protocol.py` reads from `io.BytesIO`. A test starts a server only if it needs
  one. `client.py` and `run.py` are tested with `unittest.mock`. (2.2, 7.1, 8.x)
- **C5. No race and no `sleep`.** The test waits for a signal (`threading.Event`) with a
  timeout, not for a guessed delay. Time-dependent code takes an injectable clock, as
  `throttle.py` does. (2.1, 6.1)
- **C6. Cleanup is registered with `addCleanup` right after the resource is created,** so it
  runs when `setUp` or an earlier cleanup fails. (2.1)
- **C7. Checks check the whole value.** `re.fullmatch`, not `match` with `$` (`$` also
  matches before a trailing newline). `re.ASCII` when `\d` must mean `0-9`. Negative cases
  for each. (2.3)
- **C8. Important events are asserted** with `assertLogs`, and the test output has no stray
  server lines. (3.1)

### D. Resource lifecycle: sockets, files, threads, subprocesses

- **D1. For each resource: who opens it, who closes it, on every path?** Include the error
  paths and Ctrl+C. Prefer `with`, then `try/finally`. (6.2, 8.1)
- **D2. Start-up that half-succeeds leaves nothing open.** Is the work between "resource
  created" and the `try` able to raise (`listen()`, `settimeout()`, a prompt)? (6.2)
- **D3. A class that acquires in `__init__` has an explicit `close()`.** Callers don't reach
  into `server.sock.close()` by hand. (6.2)
- **D4. Child processes: `terminate` → `wait` with a timeout → `kill`,** inside a `finally`
  that covers the child's whole life. (8.1)
- **D5. Own only what you started.** Never stop a server that was already running. (8.1)
- **D6. Threads are joined** (with a timeout), in tests too. (2.1)
- **D7. The program stops cleanly however it is stopped:** Ctrl+C, the `stop` command and
  `SIGTERM` (what `terminate()` and a service manager send; on Windows `terminate()` kills
  at once, so nothing after it runs). Is a reply in progress finished or cut? (c005)

### E. Clocks and platform

- **E1. Durations use `time.monotonic()`.** `time.time()` only for showing a date; the wall
  clock can go backwards. (6.1)
- **E2. Socket options are right on both systems.** `SO_REUSEADDR` on Windows lets a second
  process bind a port in use; `SO_EXCLUSIVEADDRUSE` exists only there. (6.3)
- **E3. Ctrl+C works on Windows.** A blocking `accept()` isn't interrupted there, so
  blocking calls in the main loop need a timeout. (step 4, 7.1)
- **E4. Paths, file modes and process flags.** File modes mean little on Windows (ACLs
  instead); `CREATE_NEW_CONSOLE` is Windows-only; `python` vs `python3`. CI runs Linux and
  Windows, but it can't open a window: put the manual check under "Not checked".
- **E5. Defaults are safe and bad configuration fails at start-up.** The server binds to
  `127.0.0.1` unless exposure is meant. TLS verification and the hostname check are never
  switched off, a minimum TLS version is set, and the private key, certificate and users
  file are git-ignored. A wrong value in `config.py` or a missing file gives a clear message
  before the first client connects, not a traceback at the first request. (c005)

### F. Logging and output

- **F1. `logging` in server code, not `print`.** One module-level logger; handlers and
  levels are configured only under `if __name__ == "__main__"`. (3.1)
- **F2. Levels mean something.** `INFO` for connect and disconnect, `WARNING` for a dropped
  or misbehaving client, `logger.exception` only where the traceback is wanted. (3.1)
- **F3. No secrets in logs or error replies.** Never log a whole request or raw bytes from
  the peer: `login` and `register` carry passwords, and so does a cut-off or over-long
  message. Log sizes and addresses. (3.1, 4.2)
- **F4. Lazy formatting:** `logger.info("x: %s", value)`, not an f-string.

### G. Contract and clean code (every change)

- **G1. The docstring tells the truth:** what the function returns (every type) and every
  exception it can raise. Re-read it after changing the body. (4.1)
- **G2. New and changed functions have type hints** where the module already has them.
  (4.1)
- **G3. Nothing dead.** Every constant, import, parameter and branch is used:
  `git grep -n <name>` for each new or changed name. (3.2)
- **G4. Constants live in `config.py`, with a comment** giving the unit and the reason for
  the value.
- **G5. Stdlib only.** No new third-party import.
- **G6. One commit, one logical change,** Conventional Commits subject, version bumped in
  `config.py` if the batch is a release.

### H. Docs drift (every change)

- **H1. Which sentence stopped being true?** For each name or behaviour that changed, run
  `git grep -n <name> -- '*.md' '*.py'` and re-read every hit: README (protocol, commands,
  project structure), `PLAN.md` (structure tree, steps), module docstrings,
  `.claude/skills/`, `docs/concepts/`. (4.1, 4.2, 9.1)
- **H2. Counts and lists that go stale.** "Steps 1–7", "a two-file app", file lists. Prefer
  a pointer to the source over a copy. (9.1)
- **H3. Decisions are written where the next reader looks:** a trade-off or known gap goes
  in a code comment and, if it affects users, in the README.

### I. State and cost: what a stranger can make the server keep or compute

- **I1. Nothing grows without a limit.** For every dict, list, set, file and log the change
  touches: who chooses the keys, and what removes an entry? If the peer chooses the key and
  only a later, optional event removes it, memory is a denial-of-service target. (c005)
- **I2. What can a client that isn't logged in make the server create?** Accounts, files,
  sessions, log lines. Is there a limit per connection or per period of time? (c005)
- **I3. Expensive work is guarded.** Which requests hash a password, write a file or loop
  over input? Can they be sent without a login and without a limit? Run the cheap checks
  (type, length, lockout) before the expensive step. (c005)
- **I4. A regex applied to peer input can't backtrack badly:** no nested quantifiers such as
  `(a+)+`, and the input length is limited first. (c005)

### J. Authentication and authorization

- **J1. Every endpoint gives the same answer about whether an account exists.** Compare
  `login`, `register` and anything new, by message *and* by time taken. If one hides which
  usernames exist and another reveals it, the hiding is worth nothing. If revealing it is
  the chosen trade-off (a usable `register`), it is written down. (c005)
- **J2. Secrets are compared with `hmac.compare_digest` and created with `secrets`,** never
  `==` on a hash and never `random`. (c005)
- **J3. Password storage keeps its properties:** a random salt per user, the iteration
  count stored per record, and the password itself never stored, logged or sent back.
  (c005)
- **J4. Lockout cuts both ways.** Counting per username stops guessing but lets anyone lock
  out a victim. Is the trade-off written down, is the lockout temporary, and is its own
  state bounded (I1)? (c005)
- **J5. Permission is checked on the server, per command.** "Logged in" is not "allowed":
  does the command need a role? Leaving a command out of `help` is not access control.
  (9.2, c005)
- **J6. The session changes cleanly:** on logout, on a second login, on a failed login
  while logged in, and when the connection ends. No state from one connection reaches the
  next. (c005)

### K. Files the server trusts

- **K1. A file the program wrote is still input when it is read back.** What happens at
  start-up, and at first use, if the file is empty, not valid JSON, the wrong JSON type, or
  missing a field? The user gets a clear message that names the file, not a traceback or a
  `KeyError` in the middle of a login. (c005)
- **K2. Writes are atomic:** write a temporary file, then `os.replace`. A crash in the
  middle leaves the old file whole. (c005)
- **K3. Permissions are set when the file is created,** not afterwards, so there is no
  moment when others can read it. Say what that does on Windows. (step 11)
- **K4. Two writers.** Which processes open this file (`server.py`, `run.py`, the tests)?
  Can two write at once, do they share a temporary file name, and does one overwrite the
  other's change from a stale copy in memory? (c005)
- **K5. `open()` names its `encoding=`.** The default differs between Windows and Linux.
  (c005)

### L. Python traps (every change in a `.py` file)

- **L1. No bare `except:` and no `except Exception` that hides bugs.** A bare `except` also
  catches `KeyboardInterrupt` and `SystemExit`. If a broad catch is right (a last line of
  defence around one session), it logs the traceback. (c005)
- **L2. `assert` isn't used to validate input or state:** `python -O` removes it. Tests are
  the only place for it, and `unittest` has its own methods. (c005)
- **L3. No mutable default argument** (`def f(items=[])`, `={}`): every call shares the one
  object. Use `None` and create it inside, as `Server.__init__` does. (c005)
- **L4. Nothing from the peer reaches `pickle`, `eval`, `exec`, `subprocess` with
  `shell=True`, or a format string that is then executed.** Commands are argument lists.
  (c005)
- **L5. No `tempfile.mktemp`, no `random` for anything secret,** no `os.system`. (c005)
- **L6. A truthiness test isn't hiding a real value:** `if not x` is also true for `0`,
  `""` and `[]`. Use `is None` when `None` is what is meant. (4.1)

## Keeping this skill current

After each code review, add every finding the checklist didn't catch as a new item in the
right section, with the task or PR that taught it. Remove nothing just because it was
fixed: the item guards against the same mistake in new code. To check that the skill still
works, run it on the pre-fix code (`git show 154c71b:server.py` and the other files at that
commit): it must flag the findings of the 2026-10-21 review.
