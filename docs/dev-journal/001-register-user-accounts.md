---
id: 001
title: Register user accounts with salted PBKDF2 hashes
commit: "feat: add register command with salted PBKDF2 password storage"
step: 8 — User accounts: register
date: 2026-10-05
tags: [python, security, password-hashing, pbkdf2, hashlib, secrets, getpass, json, protocol, unittest]
---

# Register user accounts with salted PBKDF2 hashes

## What we did
Before this change a request could only name a command (`{"command": "uptime"}`), so it had
no way to carry a username or password. Requests now take an optional `"args"` object, and
every handler receives it (`server.py:56`). A handler that raises `ValueError` turns into an
error response, so validation code doesn't need to know what the protocol looks like. The
new `register` command (`server.py:44`) hands the work to `UserStore.create_user`
(`users.py:45`).

`users.py` keeps accounts in `users.json`, which is git-ignored. The password is never
written to the file. Each user gets a random 16-byte salt from `secrets.token_bytes`. The
stored value is `hashlib.pbkdf2_hmac("sha256", password, salt, 600_000)`, and the
iteration count is saved with each user. Checking a password hashes it again with the same
salt and compares the two with `hmac.compare_digest` (`users.py:62`). Saving writes to a
temp file first and then swaps it in with `os.replace`. On the client, `register <username>`
asks for the password twice with `getpass`, so it never shows on screen (`client.py:11`).
`Server` now accepts a `users=` store, which lets tests pass a temp file and only 1,000
iterations.

## How it fits
- **Plan:** this adds Step 8 to `PLAN.md`. It unblocks Step 9 (login, logout and requiring
  authentication for commands), which needs accounts and `verify_password` to exist.
- **Practice:**
  - *Store hashes, never passwords.* A **salt** makes identical passwords hash to different
    values, which makes precomputed rainbow tables useless. A **slow** hash (many
    iterations) makes each guess expensive. Plain `sha256(password)` gets neither benefit.
    For new systems OWASP prefers Argon2id or bcrypt, but those are third-party.
    PBKDF2-HMAC-SHA256 is the best option in the standard library, and it is the
    FIPS-approved choice.
  - *Constant-time comparison.* `==` on bytes stops at the first byte that differs, so in
    theory the response time leaks information. `hmac.compare_digest` always takes the same
    time.
  - *Separation of concerns and dependency injection.* `UserStore` knows nothing about
    sockets, and `Server` receives the store from outside. That makes tests fast and
    isolated, and the JSON file could later be replaced with `sqlite3` without touching
    `server.py`.
  - *Atomic write.* Writing to a temp file and calling `os.replace` means a crash leaves
    either the old file or the new one, never half of one.
  - *When you'd do it differently:* in production you'd use a vetted library (argon2-cffi or
    bcrypt), a real database, and TLS (`ssl.SSLContext.wrap_socket`), because right now the
    password crosses the socket as plain text. That is fine on `127.0.0.1` and not
    acceptable on a network.

## Commands used
- `ls -R`, `cat`, `head -60`, `grep -n "^##\|^###"`, `grep -v __pycache__`: read the
  project files and the structure of `docs/commands.md` before planning.
- `python --version`: confirmed Python 3.13.1.
- `cat >> config.py <<'EOF' … EOF`: appended the new settings with a heredoc.
- `python - <<'EOF' … EOF`: ran a short Python script from stdin to make several exact
  text replacements in `server.py`, `client.py`, `tests/test_server.py`, `PLAN.md` and
  `README.md`.
- `git diff --stat` and `git diff server.py`: reviewed the changes.
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`: ran the
  suite (13 tests, OK) and filtered out the server's log lines.
- `python -c "import client; print(client.build_request('info'))"`: did a quick check of
  the client's request building without opening a socket.
- `git add …` / `git commit -F -`: made the commit.

## Read more
- [What Your Auth Library Isn't Telling You About Passwords: Hashing and Salting Explained](https://www.freecodecamp.org/news/passwords-hashing-and-salting-explained/) — freeCodeCamp · why a salt doesn't need to be secret, and why a slow hash beats brute force.
- [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — OWASP · the source of the 600,000 iterations figure, and why Argon2id or bcrypt come first.
- [hashlib — Key derivation](https://docs.python.org/3/library/hashlib.html#key-derivation) — Python docs · the `pbkdf2_hmac` signature and the advice on salt size and iteration count.
- [secrets — Generate secure random numbers](https://docs.python.org/3/library/secrets.html) — Python docs · why `secrets` and not `random`, and what `compare_digest` protects against.
- [getpass — Portable password input](https://docs.python.org/3/library/getpass.html) — Python docs · hidden input, and the `GetPassWarning` fallback when echo can't be turned off.

## Quiz

### Revise
1. What is a salt, and does it need to be kept secret?
   <details><summary>Answer</summary>

   A salt is random data generated for each user and mixed into the password before
   hashing. It doesn't need to be secret: it is stored next to the hash. Its job is to make
   every hash unique, so identical passwords look different and precomputed (rainbow)
   tables don't work.
   </details>
2. Why is `hashlib.sha256(password).hexdigest()` a poor way to store passwords? (a) SHA-256
   is broken, (b) it is fast and unsalted, (c) it is too long to store, (d) it isn't
   deterministic.
   <details><summary>Answer</summary>

   (b). SHA-256 isn't broken, but it is designed to be fast, so an attacker can try
   billions of guesses a second. Without a salt, the same password always gives the same
   hash.
   </details>
3. Why does `users.py` use `secrets.token_bytes` and not `random.randbytes`?
   <details><summary>Answer</summary>

   `random` is a deterministic pseudo-random generator built for simulations, and its
   output can be predicted once its state is known. `secrets` uses the operating system's
   cryptographically secure source.
   </details>
4. Spot the bug: `return stored_hash == pbkdf2_hmac("sha256", pw, salt, n)`.
   <details><summary>Answer</summary>

   `==` stops at the first byte that differs, so the time it takes depends on how many
   leading bytes match, which is a timing side channel. Use
   `hmac.compare_digest(stored_hash, ...)`.
   </details>
5. Why is the iteration count saved inside each user's record and not only in `config.py`?
   <details><summary>Answer</summary>

   So the default can be raised later. Old accounts are still checked with the count they
   were created with, and can be re-hashed with the new count on their next successful
   login.
   </details>
6. What does writing to `users.json.tmp` and then calling `os.replace` protect against?
   <details><summary>Answer</summary>

   A crash or power cut during the write. The rename swaps the file in one step, so readers
   see either the complete old file or the complete new one, never a truncated JSON file
   that would lock everyone out.
   </details>

### Defend the decision
1. "Why PBKDF2 and not bcrypt or Argon2?"
   <details><summary>Model answer</summary>

   The project is standard library only, and PBKDF2-HMAC-SHA256 is the strongest password
   hash in `hashlib`. It is also the FIPS-approved choice. Argon2id is memory-hard, which
   makes GPU and ASIC attacks more expensive, and OWASP prefers it for new systems. Without
   the stdlib-only rule I'd use argon2-cffi. To make up for this I followed OWASP's 600,000
   iterations and stored the count per user so it can be raised.
   </details>
2. "Why add an `args` object instead of sending `register alice secret` as a string?"
   <details><summary>Model answer</summary>

   A structured field means the server doesn't parse free text, so passwords with spaces
   just work and each argument has a name. Older requests without `args` still work
   because the field is optional. The trade-off is that the client now has to know each
   command's arguments, which is why `client.py` has `build_request`.
   </details>
3. "Why does `Server` take a `users=` parameter?"
   <details><summary>Model answer</summary>

   It is dependency injection. In production the server uses the default `UserStore()`.
   Tests pass a store backed by a temp file with 1,000 iterations, so they never touch the
   real `users.json` and run in milliseconds instead of about 0.3 s per hash. It also
   leaves room to swap in a SQLite-backed store with the same interface.
   </details>
4. "Is it safe that the password is sent to the server in plain text?"
   <details><summary>Model answer</summary>

   Only on localhost. Anyone who can sniff the network would see it, so on a real network
   I'd wrap the socket with the stdlib `ssl` module (TLS). Hashing on the client instead
   doesn't help: the hash simply becomes the password an attacker replays.
   </details>
