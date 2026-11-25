---
id: 033
title: Explain an unusable TLS certificate instead of a traceback
commit: "fix: explain an unusable TLS certificate instead of a traceback"
step: 16 — address the 2026-10-21 mentoring code review (pre-review fix 2 of 5 on batch 8)
date: 2026-11-24
tags: [python, ssl, tls, exceptions, exception-hierarchy, eafp, toctou, cli]
---

# Explain an unusable TLS certificate instead of a traceback

## What we did
The pre-review found that the launcher only checked that `server.crt` *exists*. A file
that exists but isn't a usable certificate made it crash with `ssl.SSLError`. Checking the
other two programs showed the same root cause three ways:
- **`client.py`:** it caught only `FileNotFoundError`, so a broken file gave a traceback.
- **`run.py`:** `os.path.exists` passed, then `make_client_context` raised.
- **`server.py`, the worst case:** it printed the **wrong** message: "Could not listen on
  127.0.0.1:65432 ([SSL] PEM lib …)". `ssl.SSLError` is a subclass of `OSError`, and the
  broad `except OSError` added in journal 027 for bind failures caught it and called it a
  bind failure.

Each program now catches `ssl.SSLError` where the certificate is loaded, names the file and
says how to fix it:
- **The server** (`server.py:351`, between `FileNotFoundError` and the bind clause) prints
  the `openssl` command again.
- **The client** (`client.py:117`) points to README "Setup" and returns `EXIT_FAILURE`.
- **The launcher** (`run.py:253`) now *loads* the certificate with
  `make_client_context(CERT_FILE)` instead of asking `os.path.exists`. That handles "missing"
  and "unusable" in one place, before anything is probed or started, and exits with
  `EXIT_LAUNCHER_FAILED`.

Three tests each write a real `not a certificate` file to a temp folder and let the real
loader fail on it, with no mocked exception. Before the fix they failed in the three ways
above: the bind message, a traceback, and exit 0 instead of 2. Then a real run of all three
programs in a copy of the repo with a broken `server.crt` gave a message each, with exit
codes 1, 1 and 2.

## How it fits
- **Plan:** Step 16, pre-review fix 2 of 5 on batch 8 (`PLAN.md` Step 10, "fail closed";
  README "Setup" and exit code 2). It also corrects journal 027's bind clause, which was too
  broad. Next is fix 3: Ctrl+C in the launcher's remaining waits.
- **Practice:**
  - *Try the real operation; don't check first (EAFP over LBYL).* `os.path.exists` answers
    "is there a file?", but the launcher needed "can I use it?". Only loading it answers
    that. A check also has a gap before the use: the file can change in between (TOCTOU,
    time of check to time of use). The `os.access` docs warn about exactly this, and
    recommend "EAFP techniques".
  - *A broad `except` catches more than you meant.* Journal 027 added `except OSError` for
    one purpose, bind failures, and `ssl.SSLError` quietly fell into it, because it is an
    `OSError` too. When adding a broad clause, ask "what else lands here?", and put each
    narrower class you know about before it: `FileNotFoundError`, then `ssl.SSLError`, then
    `OSError`.
  - *A wrong message is worse than a traceback.* The traceback at least showed `ssl`. "Could
    not listen" sends the user to look for another program on the port.
  - *When you'd choose differently:* a service with a deploy step validates its config there
    (`nginx -t`, `sshd -t`), before start-up. A library would let `ssl.SSLError` propagate
    and leave the message to the application.

## Commands used
- `python -c "import sys; from unittest import mock; import server; …; server.main()" "$S/bad.pem"`
  — show the server's misleading "Could not listen" message with a broken certificate,
  before writing the briefing
- `python -c "… import client; … sys.exit(client.main())" "$S/bad.pem" 2>&1 | tail -1` —
  the client's traceback with the same file
- `python -m unittest -v -k unusable tests.test_server tests.test_client tests.test_run` —
  the three new tests: failing before the fix, passing after
  ([python -m unittest](../commands.md#python--m-unittest-run-the-test-suite) `-k`)
- `python -m unittest discover tests` — the full suite, OK with 1 skip
- `git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S"`, then
  `printf 'not a certificate\n' > "$S/server.crt"` and
  `for p in server.py client.py run.py; do python $p < /dev/null; echo "-> $p exit code $?"; done`
  — the three real programs with a broken certificate in a copy: exit codes 1, 1 and 2
- `sed -i 's/…no `server.crt`, /…a missing or unusable `server.crt`, /' README.md` — the
  exit-code table's row for 2
- `rm -rf "$S"` — delete the copy

## Read more
- [Glossary: EAFP](https://docs.python.org/3/glossary.html#term-EAFP) — Python docs · "Easier to ask for forgiveness than permission": assume it works and catch the exception if it doesn't, the style `run.py` switched to.
- [Glossary: LBYL](https://docs.python.org/3/glossary.html#term-LBYL) — Python docs · "the LBYL approach can risk introducing a race condition between 'the looking' and 'the leaping'".
- [os.access, the note](https://docs.python.org/3/library/os.html#os.access) — Python docs · checking before opening "creates a security hole, because the user might exploit the short time interval between checking and opening the file". "It's preferable to use EAFP techniques."
- [ssl.SSLError](https://docs.python.org/3/library/ssl.html#ssl.SSLError) — Python docs · "This error is a subtype of OSError": the reason the server's bind clause caught it.
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/) — freeCodeCamp · beginner-friendly: what `try`/`except` catches and in which order the clauses are tried.
- Related: [journal 027](027-explain-a-taken-port.md) (the bind clause this commit narrows), [concept 003](../concepts/003-except-clause-scope.md) (which handler catches what).

## Quiz

### Revise
1. What did `server.py` print for a corrupt `server.crt` before this commit, and why?
   <details><summary>Answer</summary>

   "Could not listen on 127.0.0.1:65432 ([SSL] PEM lib …)". Loading the certificate raised
   `ssl.SSLError`, a subclass of `OSError`. The only matching clause was journal 027's
   `except OSError` for bind failures, so the user was told about the port instead of the
   certificate.
   </details>

2. Multiple choice. In what order must these clauses come?
   a) `OSError`, `ssl.SSLError`, `FileNotFoundError`
   b) `FileNotFoundError`, `ssl.SSLError`, `OSError`
   c) `ssl.SSLError`, `OSError`, `FileNotFoundError`
   d) any order: Python picks the best match
   <details><summary>Answer</summary>

   b. Both `FileNotFoundError` and `ssl.SSLError` are subclasses of `OSError`, and Python
   takes the *first* clause that matches, not the best one. `OSError` must come last, or it
   catches everything. The two narrow ones don't overlap, so their order between themselves
   doesn't matter.
   </details>

3. Why is `os.path.exists(CERT_FILE)` the wrong check for the launcher, even when it's true?
   <details><summary>Answer</summary>

   It answers "is there a file?", but the launcher needs "can I build a TLS context from
   it?". A file can exist and be corrupt, empty or not PEM. Also, the answer can change
   between the check and the use (TOCTOU). Loading the file and handling the errors answers
   the real question.
   </details>

4. What does "TOCTOU" stand for, and how does EAFP avoid it?
   <details><summary>Answer</summary>

   Time of check to time of use: the state can change between checking a condition and
   acting on it, so the check proves nothing. EAFP has no separate check. It does the
   operation and handles its failure, so there's no gap between "looking" and "leaping".
   </details>

5. Spot the problem:
   ```python
   try:
       context = make_client_context()
   except OSError:
       print("TLS certificate not found")
   ```
   <details><summary>Answer</summary>

   `OSError` also catches `ssl.SSLError` (a broken file) and `PermissionError` (an
   unreadable one), so every one of those is reported as "not found". That's misleading in
   the same way journal 027's bind clause was. Catch the narrow classes, each with its own
   message, and let a broad clause come last, if at all.
   </details>

### Defend the decision
1. "Why does the launcher build a TLS context just to check a file? Isn't
   `os.path.exists` cheaper?"
   <details><summary>Model answer</summary>

   It is cheaper, and it answers the wrong question. The launcher needs a usable certificate
   for its probe and for the client. Building the context is the only check that proves
   that, and it takes a few milliseconds once at start-up. It also covers missing and
   broken files in one `try`, with the two messages side by side. Checking existence first
   and loading later is the LBYL pattern the Python docs warn about.
   </details>

2. "Journal 027 added `except OSError`. Why not narrow it to bind errors instead of adding
   an `SSLError` clause before it?"
   <details><summary>Model answer</summary>

   The bind errors aren't one class. A taken port, a reserved port (WinError 10013) and an
   address the machine doesn't have are all plain `OSError`s with different `errno`s, so
   `OSError` is the right catch for "bind failed". The mistake was that the `try` covers
   the whole `Server()` constructor, which also loads the certificate. Putting the known
   non-bind cases (`FileNotFoundError`, `ssl.SSLError`) first keeps each message accurate.
   Splitting the constructor so loading and binding are in separate `try`s would also work,
   at the cost of changing the `Server` API.
   </details>

3. "Why test with a real broken file and not `side_effect=ssl.SSLError(...)`?"
   <details><summary>Model answer</summary>

   A mocked exception tests my belief about what `ssl` raises. A real file tests what it
   *does* raise. Here that mattered: the server-side loader raised `[SSL] PEM lib`, and the
   client side raised `[X509: NO_CERTIFICATE_OR_CRL_FOUND]`, two different errors from two
   different calls. Both are `ssl.SSLError`, which the real file proves. Writing a temp file
   costs one line.
   </details>
