---
id: 036
title: Document the server's trust assumptions
commit: "docs: document the server's trust assumptions"
step: 16 — address the 2026-10-21 mentoring code review (task 9.2)
date: 2026-11-27
tags: [security, threat-modeling, trust-boundary, denial-of-service, account-lockout, tls, pbkdf2, windows, acl, documentation]
---

# Document the server's trust assumptions

## What we did
The review noted that any local process that can log in can `stop` the server. This
commit adds a "Security assumptions" section to `README.md`, between "User accounts" and
"Project structure". It has three parts: **who can reach it**, **what is protected** (a
table of each asset, its defence and the file that implements it) and **what isn't** (the
known gaps). Nothing in the code changed. The section writes down what the code already does.

Writing it from the code, not from the plan's summary, turned up three things worth saying
out loud:
- **The trust boundary is the machine, not the account.** `register` is public
  (`requires_login=False`, `server.py:101`), so anyone who can connect can create an
  account. `stop` checks only for a login (`server.py:107`), so in practice any program on
  the machine can stop the server. The plan's "local users with an account" sounded
  narrower than it is.
- **The lockout can be used as a weapon.** `throttle.py` counts failures per username, so
  anyone who knows the admin's name can keep that account locked by failing 5 logins a
  minute. That is the price of two good decisions: don't reveal which accounts exist, and
  don't trust the source address, which is `127.0.0.1` for every client.
- **Windows file permissions were wider than assumed.** Step 11 says that on Windows "the
  user profile is owner-only by default". This repo isn't in the profile. `icacls` showed
  that `users.json` and `server.key` inherit `Authenticated Users:(M)` from `D:\`, so every
  local account can read and even overwrite the password hashes and the TLS private key.
  The README now says this and how to check it. Fixing it is a separate chunk.

`pre-review` on the branch found two drift problems in this chunk, and both were fixed
before the commit. Step 11 of `PLAN.md` still implied that `users.json` is owner-only on
Windows, so its "Known gaps" now records the ACL finding (H1/H3). The protection table
first copied eight values from `config.py`, making a third copy next to "User accounts"
and "Protocol". It now names the constants (`MAX_FAILED_LOGINS`, `MAX_MESSAGE_SIZE`, …),
so changing a value can't leave the table wrong (H2).

## How it fits
- **Plan:** task 9.2, the last task of batch 9 and of Step 16 (`PLAN.md`,
  `docs/plans/001-code-review-2026-10-21.md`). Each gap links to its planned fix:
  admin-only `stop` (Step 13, "Next") and a deadline per message for slowloris (Step 4).
  Next: `pre-review` on the branch, then the batch 9 PR.
- **Practice:** this is a small **threat model**. It answers OWASP's four questions in a
  few lines: what we work on, what can go wrong, what we do about it, and what we
  deliberately don't do. Three habits make it useful:
  - **State the trust boundary in terms of who can act**, not what the UI suggests. A login
    that anyone can create isn't a boundary.
  - **Link each protection to the code** that provides it (the "Where" column), so a
    reviewer can check the claim and the doc goes stale visibly when the file changes.
  - **Write down the known gaps.** An undocumented gap gets relied on by the next person.
    A documented one is a decision someone can revisit.

  When you'd do more: a real service models threats with STRIDE per data flow and keeps
  the model next to the architecture diagram. A single-user script with no socket needs
  none of this.

## Commands used
- `grep -n "^#" README.md`: list the README's headings to choose where the section goes
- `grep -n -E "HOST|PORT|ITERATIONS|…" config.py`, `grep -n -E "pbkdf2|…" users.py`,
  `grep -n -E "requires_login|…" server.py`: collect the facts the section states, from the
  code rather than from memory
- `sed -n 96,112p server.py`: read the dispatch dict to see which commands need a login
- `git diff master fix/launcher-cleanup -- README.md | grep -E "^@@"`: see where PR #12
  edits the README, so the new section goes somewhere that can't conflict
- `git ls-files server.key server.crt users.json`: confirm none of the secrets is tracked
  (no output)
- `icacls users.json; icacls server.key` (PowerShell): show who may open both files. This
  is how the `Authenticated Users:(M)` finding came up
  ([icacls](../commands.md#icacls-show-who-may-open-a-file-windows))
- `snap=$(git stash create); base=$(git merge-base "$snap" fix/launcher-cleanup); git merge-tree "$base" "$snap" fix/launcher-cleanup | grep -c -E "^\+<<<<<<<"`:
  check that the uncommitted change merges cleanly with PR #12, without committing anything
  ([git stash create](../commands.md#git-stash-put-changes-aside-for-a-moment))
- `git diff --stat master...HEAD` and `git status --short`: the scope for `pre-review`, the
  branch's commits plus the uncommitted work
- `git grep -n -i -E "owner-only by default|profile is owner|ACL" -- '*.md' '*.py'`: H1,
  find every sentence about Windows file protection that the `icacls` finding could have
  made untrue. It found `PLAN.md` Step 11
- `git grep -n "Security assumptions" -- '*.md'`: check what already refers to the new
  section (the `pre-review` skill does)
- `grep -n "minimum_version\|TLSv1_2" server.py client.py config.py`: find where the TLS
  minimum is set, so the table can name it instead of copying "1.2"
- `python -m unittest discover tests`: 118 tests, OK (1 skipped). The change is docs only,
  so this just confirms nothing else moved

## Read more
- [Threat Modeling Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html):
  OWASP · the four questions, trust boundaries in the system model, and STRIDE. Its DoS
  example is our lockout gap: "locks a legitimate user out of their account by performing
  many failed authentication attempts".
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html):
  OWASP · account lockout. Count failures "associated with the account itself, rather than
  the source IP address" (what `throttle.py` does), and take care that it isn't used "to
  cause a denial of service by locking out other users' accounts".
- [Denial of Service](https://community.owasp.org/attacks/Denial_of_Service): OWASP ·
  resource-exhaustion DoS (unreleased resources, growing state) and the "DoS locking
  customer accounts" section.
- [Denial of Service (DoS)](https://developer.mozilla.org/en-US/docs/Glossary/Denial_of_Service):
  MDN Glossary · the beginner definition: an attack that consumes server resources, "more
  of a category than a particular kind of attack".
- [ssl: TLS/SSL wrapper for socket objects](https://docs.python.org/3/library/ssl.html#security-considerations):
  Python docs · `create_default_context` and its `cafile`: the client trusts only the CA
  certificates you give it, which is how `client.py` pins `server.crt`.
- [icacls](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls):
  Microsoft Learn · reading an ACL: `(I)` is inherited, `F`/`M`/`RX` are full, modify,
  and read and execute.
- Related concepts: [concept 005, reviewing a Python server](../concepts/005-reviewing-a-python-server.md).

## Quiz

### Revise
1. The server listens on `127.0.0.1` and `stop` requires a login. Who can stop it?
   a) only the admin, b) only users the admin created, c) any program on the same machine,
   d) anyone on the local network.
   <details><summary>Answer</summary>

   c). `register` needs no login, so any program that can connect to `127.0.0.1` can create
   an account, log in and send `stop`. d) would become true if `HOST` were `0.0.0.0`.
   </details>
2. What is a *trust boundary*, and where is it in zr-client-server?
   <details><summary>Answer</summary>

   It's the line where data or requests move from something you don't control to something
   you do, so they must be checked there. Here it's the socket: everything that arrives from
   a client is untrusted. Since anyone local can be a client, the boundary is effectively
   "can run a program on this machine".
   </details>
3. Why does a per-username lockout make a DoS possible, and why didn't we count failures
   per IP address instead?
   <details><summary>Answer</summary>

   Anyone who knows a username can fail 5 logins on purpose and lock the real owner out for
   60 s, again and again. Counting per IP wouldn't help here: every client comes from
   `127.0.0.1`, so one counter would cover all clients. And on a network, an attacker can
   spread guesses over many addresses. OWASP recommends counting per account.
   </details>
4. `icacls users.json` prints `NT AUTHORITY\Authenticated Users:(I)(M)`. What does it mean?
   <details><summary>Answer</summary>

   Every signed-in account on the machine may modify the file (read, write, delete), and
   the right is **inherited** (`I`) from the parent folder, not set on the file. Python's
   `0o600` didn't prevent it, because on Windows the mode only sets the read-only flag.
   </details>
5. Spot the gap: "Passwords are safe because they're hashed with PBKDF2 and sent over TLS."
   <details><summary>Answer</summary>

   Those protect a password in transit and at rest in `users.json`. They don't stop someone
   who can read `users.json` from guessing offline (slowly, at 600,000 iterations per guess),
   or someone who can read `server.key` from posing as the server. On this machine, both
   files were readable by every local account.
   </details>

### Defend the decision
1. "Why write down security gaps instead of fixing them first?"
   <details><summary>Model answer</summary>

   Some gaps are trade-offs, not bugs. One client at a time is the chosen concurrency model,
   and the lockout DoS is the cost of not revealing accounts. Others need a design decision
   first, like admin-only `stop`. Documenting them stops anyone from relying on a protection
   that doesn't exist, and each one points to its planned fix. The alternative, saying
   nothing until everything is fixed, leaves users with a false sense of safety in the
   meantime.
   </details>
2. "Your server is localhost-only. Why does it need TLS at all?"
   <details><summary>Model answer</summary>

   It's defence in depth, and it's practice for when it isn't localhost-only. Loopback
   traffic can be captured locally (Wireshark on the loopback adapter), and the client
   pins `server.crt`, so another program that grabs the port can't collect passwords by
   posing as the server. The cost is a certificate to create and renew, which the README
   covers. The documented gap is that `server.key` is only as safe as its file permissions.
   </details>
3. "Why is the threat model in the README and not in a separate security document?"
   <details><summary>Model answer</summary>

   The README is where a person deciding to run the server looks. The section is short and
   sits next to "User accounts", whose details it relies on, and it links to the
   implementing file for each claim. A separate `SECURITY.md` makes sense when there's a
   vulnerability-reporting process or a longer model (STRIDE per data flow). Neither exists
   yet, so one more file would just be one more place to go stale.
   </details>
