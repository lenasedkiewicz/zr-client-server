---
id: 005
title: Lock out logins after repeated failures
commit: "feat: lock out logins after repeated failures"
step: 12 — lock out logins after repeated failures
date: 2026-10-15
tags: [python, security, brute-force, rate-limiting, account-lockout, time, monotonic-clock, dependency-injection, unittest]
---

# Lock out logins after repeated failures

## What we did
Before this change `login` accepted unlimited guesses. A short script could loop over a
password list against one account. PBKDF2 makes each guess cost the server a noticeable
fraction of a second of CPU, but that only slows the attacker down and adds load. Hashing protects a *stolen
file* (offline attack). Nothing protected the *protocol* (online attack).

The new `throttle.py` holds `LoginThrottle`, which keeps two in-memory dicts keyed by
username: consecutive failures and the time a lockout ends. `check` (`throttle.py:29`)
raises `ValueError("Too many failed logins, try again in N s")` while a name is locked
and clears an expired lockout. `record_failure` (`throttle.py:41`) locks the name once the
limit is reached, and `record_success` (`throttle.py:47`) resets it. The limits are
`MAX_FAILED_LOGINS = 5` and `LOGIN_LOCKOUT_SECONDS = 60` (`config.py:19`). In `cmd_login`
the server calls `check` **before** verifying the password (`server.py:98`), so a locked
name costs no PBKDF2 work. It then records the outcome (`server.py:100`, `server.py:103`).
A non-string username is rejected up front with the usual generic message, because it
can't be a dict key or a real account. That decision wasn't in the briefing.

Time comes from `time.monotonic()` (`throttle.py:20`), not `time.time()`. A wall clock
can jump when someone changes it or NTP corrects it, which would stretch or cancel a
lockout. The clock is a constructor parameter, and the server takes the throttle as
`Server(..., login_throttle=...)` (`server.py:46`), the same injection as `users=` and
`tls_context=`. That lets the tests (`tests/test_server.py:234`–`271`) use a fake clock
(`self.now += 59`) and check expiry without sleeping for a minute. Four of the six new
tests fail on the old `server.py`. The other two (`per_username`, `resets_failures`)
check that the lockout does not catch too much, so they pass without it, as expected.

## How it fits
- **Plan:** delivers Step 12, which closes the "next hardening" item from Steps 9 and 10.
  The only listed leftover is a stale `users.json.tmp` (Step 11 known gaps).
- **Practice:**
  - **Online vs offline attacks need different defences.** Slow hashing defends against
    offline attacks, and throttling defends against online ones. Together they are defence
    in depth.
  - **What you count by matters.** Per connection is useless, since a reconnect resets
    it. Per IP is meaningless on localhost and unfair behind NAT, and a botnet rotates IPs
    anyway. OWASP recommends counting per account, which is what we do.
  - **Lockouts must not leak or be weaponised.** Unknown usernames are counted the same
    way, so "locked" never means "this account exists" (Step 9's no-enumeration rule). The
    lock is temporary, because a permanent one lets anyone lock any user out (denial of
    service). The 60-second DoS window remains. Real systems add CAPTCHA after a few
    failures, MFA, a reset-by-email path, or an exponential delay instead of a hard lock.
  - **Inject what you can't control in tests** (clock, storage, TLS context). This is
    dependency injection without a framework: a default argument.
  - **When you'd differ:** with several server processes, the in-memory dicts don't
    synchronise and are lost on restart. Production uses a shared store with expiry (e.g.
    Redis with a TTL) or rate-limits at a reverse proxy or API gateway. An HTTP API would
    answer `429 Too Many Requests` with a `Retry-After` header. Here the "try again in N s"
    message plays that role. The dicts also grow with every guessed username, which is a
    known gap for a long-running public server.

## Commands used
- `ls`, `cat PLAN.md`, `tail -40 <file>`, `sed -n <from>,<to>p <file>`, `grep -n <pattern> <files>`: read the plan, the code and the previous journal entry before the briefing.
- `git log --oneline | head -15`: see recent commits.
- `git status --short --ignored`: confirm the tree is clean and see which files are ignored.
- `python - <<'EOF' … EOF`: insert the new tests and the `PLAN.md`/`README.md` sections.
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)"`: run the suite and show only the summary (31 tests, OK, 1 skipped).
- `cp server.py "$TEMP/server.py.new"`: back up the new server before testing the old one.
- `git show HEAD:server.py | sed 's/<old signature>/<new signature>/' > server.py`: put the old `cmd_login` back, accepting the new `login_throttle=` argument, to prove the new tests fail without the feature (4 failed). Then `cp "$TEMP/server.py.new" server.py` restored it.
- `git diff --stat`: check which files changed.
- `git add …`, `git commit -F -`: commit.

## Read more
- [Authentication Cheat Sheet: Protect Against Automated Attacks](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — OWASP · count failures per account, not per IP; lockout threshold, observation window and duration; exponential lockout; lockout as DoS.
- [Rate limit (glossary)](https://developer.mozilla.org/en-US/docs/Glossary/Rate_limit) — MDN · beginner definition of rate limiting / throttling and why servers do it.
- [429 Too Many Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/429) — MDN · how HTTP signals a rate limit, and `Retry-After` (our "try again in N s").
- [`time.monotonic()`](https://docs.python.org/3/library/time.html#time.monotonic) — Python docs · a clock that never goes backwards; only differences between values mean anything.
- [PEP 418 – Add monotonic time, performance counter, and process time functions](https://peps.python.org/pep-0418/) — Python PEPs · why timeouts based on the system clock fire too early or too late when the time is changed or adjusted by NTP.

## Quiz

### Revise
1. Which attack does `LoginThrottle` defend against, and which one does PBKDF2 defend against?
   <details><summary>Answer</summary>

   The throttle limits **online** guessing through the `login` command. PBKDF2 slows down
   **offline** guessing by someone who has copied `users.json`. Each covers a gap the other
   leaves.
   </details>
2. Why does `throttle.py` use `time.monotonic()` instead of `time.time()`?
   a) it's faster b) it can't go backwards and ignores system clock changes c) it returns a
   date d) it's timezone-aware
   <details><summary>Answer</summary>

   b). `time.time()` follows the wall clock, which can jump when someone changes it or NTP
   corrects it, so a lockout could last hours or end at once. Only differences between
   `monotonic()` values mean anything.
   </details>
3. What does this print, and why?
   ```python
   t = LoginThrottle(max_failures=2, lockout_seconds=60, clock=lambda: 100.0)
   t.record_failure("bob"); t.record_failure("bob")
   t.check("alice"); print("ok")
   ```
   <details><summary>Answer</summary>

   It prints `ok`. The lock is per username: `bob` is locked until 160.0, but `alice` has no
   entry, so `check` returns at once.
   </details>
4. Spot the bug: a teammate moves `self.login_throttle.check(username)` to *after*
   `verify_password`. What changes?
   <details><summary>Answer</summary>

   A locked name still costs a full PBKDF2 hash on every attempt, so the server keeps doing
   expensive work for an attacker. Worse, if the code returns success when the password
   matches before checking, the lockout stops nothing. The check must come first.
   </details>
5. Why is a username that is not a string (e.g. `["alice"]`) rejected before the throttle?
   <details><summary>Answer</summary>

   A list can't be a dict key (it's unhashable, so it raises `TypeError`), and it can't be a
   real account. Rejecting it early with the same generic message keeps the throttle's keys
   simple and the response uninformative.
   </details>
6. How do the tests check "lockout ends after 60 s" without waiting 60 s?
   <details><summary>Answer</summary>

   The server gets `LoginThrottle(..., clock=lambda: self.now)`, and the test advances
   `self.now` by hand (`self.now += 59`, then `+= 1`). Time is an injected dependency.
   </details>

### Defend the decision
1. "Why count failures per username and not per IP address or per connection?"
   <details><summary>Model answer</summary>

   Per connection resets on every reconnect, so it stops nothing. Per IP is meaningless
   here (everything is 127.0.0.1) and in general it's unfair behind NAT and bypassed by
   attackers with many IPs. Per account, as OWASP recommends, protects the thing under
   attack. The trade-off is that an attacker can deliberately lock a known user out. We
   limit that with a short, temporary lock. A real service would combine per-account and
   per-IP limits and add CAPTCHA or MFA.
   </details>
2. "Locking accounts lets anyone lock out a user. Why not just slow responses down?"
   <details><summary>Model answer</summary>

   Delays alone still let an attacker run guesses in parallel connections (here the server
   is single-client, but that won't last). A temporary lock gives a hard cap of 5 guesses
   per minute per account, about 7,200 per day, which defeats a password list but not a
   very common password. The DoS risk is bounded to 60 s at a time. An exponential lockout,
   which OWASP mentions, is the natural next step if 60 s proves too weak.
   </details>
3. "Why keep the state in memory? It's gone after a restart."
   <details><summary>Model answer</summary>

   It fits the project: one process, stdlib only, and no database. Persisting it to
   `users.json` would add a file write on every failed login, which an attacker could
   use to cause disk I/O. The cost is that a restart clears all locks and the dicts grow
   with guessed names. With several servers I'd move it to a shared store with TTLs (e.g.
   Redis), or to a reverse proxy rate limit.
   </details>
4. "Why does `Server` take `login_throttle=` as a parameter?"
   <details><summary>Model answer</summary>

   It's dependency injection without a framework, consistent with `users=` and
   `tls_context=`. Production uses the default, while tests pass a throttle with a lower
   limit and a fake clock, so they are fast and deterministic. The alternative,
   `mock.patch("time.monotonic")`, couples tests to how the module imports `time` and is
   easier to get wrong.
   </details>
