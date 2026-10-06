---
id: 002
title: Login, logout and access control
commit: "feat: add login/logout and require authentication for commands"
step: 9 — Login and access control
date: 2026-10-05
tags: [python, security, authentication, authorization, session, user-enumeration, dispatch, unittest]
---

# Login, logout and access control

## What we did
Each entry in the dispatch dict is now `(handler, description, requires_login)`
(`server.py:28`). `handle_request` checks that flag in one place (`server.py:92`): a
protected command sent before login gets `"Login required: ..."` and never reaches its
handler. `help` is still generated from the same dict but now filtered (`server.py:48`).
Logged out, it lists only `help`, `register` and `login`. Logged in, it lists everything.
The new commands are `login` (`server.py:60`) and `logout` (`server.py:70`).

The logged-in user is stored on the **connection**. `handle_client` creates
`session = {"user": None}` (`server.py:106`) and passes it to every handler, so
disconnecting logs the user out and the next client starts fresh. A wrong password and an
unknown username return the same message. For an unknown username, `verify_password` also
runs a throwaway hash (`users.py:66`), so both failures take about the same time. The client
asks for the password with `getpass` and shows the user in the prompt (`alice> `). It updates
the prompt only on a successful `login`/`logout` response (`client.py:73`), so the server
stays the source of truth.

## How it fits
- **Plan:** this adds Step 9 to `PLAN.md` and finishes the accounts feature started in
  [001](001-register-user-accounts.md). Natural next steps: rate limiting or lockout after
  failed logins, TLS via `ssl`, and re-hashing old accounts on login when the iteration
  count goes up.
- **Practice:**
  - *Authentication vs authorisation.* `login` answers "who are you?". The
    `requires_login` check answers "what may you do?". Putting the check in the dispatcher
    is the same idea as middleware or a `@login_required` decorator in a web framework:
    a new command is protected by changing a flag, not by remembering to add an `if`.
  - *Secure by default?* Here the flag must be set for every command. A stricter design
    makes `requires_login=True` the default and lists the public commands explicitly. With
    three public commands, being explicit in the table is clear enough.
  - *Stateful connection vs stateless requests.* TCP keeps one long-lived connection, so a
    session dict tied to it is enough, with no token. HTTP is stateless: every request
    carries a session ID (cookie) or a token that the server looks up. With several servers
    or reconnecting clients you'd issue a random `secrets.token_urlsafe()` token and keep
    sessions server-side.
  - *Don't help attackers enumerate users.* Same message, similar timing. The remaining
    gap is unlimited guessing: OWASP recommends lockout or throttling per account, which
    isn't built yet.

## Commands used
- `cat > "$TEMP/claude_edit2.py" <<'PYEOF' … PYEOF` then `python "$TEMP/claude_edit2.py"`:
  wrote the edit script to a temp file first. This avoids the quoting problems of piping a
  script containing `'''` strings through a heredoc into `python -`.
- `rm "$TEMP/claude_edit2.py"`: deleted the temporary script afterwards.
- `git diff client.py users.py` and `git diff --stat`: reviewed the changes.
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR|AssertionError|Traceback)"`:
  21 tests, OK.
- `grep -n "…" server.py`: found line numbers for this entry.
- `git add …` / `git commit -F -`: made the commit.

## Read more
- [Authentication vs Authorization](https://www.freecodecamp.org/news/whats-the-difference-between-authentication-and-authorisation/) — freeCodeCamp · the difference between the two words, which this commit implements as `login` vs `requires_login`.
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) — OWASP · generic login errors, timing differences, and account lockout (the next step we didn't build).
- [Session management](https://developer.mozilla.org/en-US/docs/Web/Security/Authentication/Session_management) — MDN · how stateless HTTP needs session IDs in cookies, compared with our per-connection session.
- [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — OWASP · background for `verify_password`, carried over from [001](001-register-user-accounts.md).

## Quiz

### Revise
1. Which of these is *authorisation*? (a) checking the password in `login`, (b) rejecting
   `uptime` because `session["user"]` is `None`, (c) hashing the password with PBKDF2,
   (d) asking for the password with `getpass`.
   <details><summary>Answer</summary>

   (b). It decides what an (un)identified user may do. (a) is authentication; (c) and (d)
   are about protecting the credential.
   </details>
2. Why do "unknown user" and "wrong password" return the same message?
   <details><summary>Answer</summary>

   Different messages tell an attacker which usernames exist (user enumeration). They
   could then focus password guessing or phishing on real accounts.
   </details>
3. The error messages are identical. Why does `verify_password` still hash something for an
   unknown username?
   <details><summary>Answer</summary>

   Without it, an unknown username would return almost instantly, while a real one takes
   the full PBKDF2 time. The response time would reveal which accounts exist even though
   the message doesn't.
   </details>
4. What happens to the login when the client disconnects, and why?
   <details><summary>Answer</summary>

   It's gone. `session` is a local variable created in `handle_client` for each
   connection, so it disappears when `handle_client` returns. The next connection gets a
   fresh `{"user": None}`.
   </details>
5. Spot the risk: a new command `"reset": (self.cmd_reset, "Deletes all users", False)`.
   <details><summary>Answer</summary>

   `requires_login` is `False`, so anyone can call it without logging in. Because each
   command opts in to protection, a wrong flag silently exposes it. Making protection the
   default, or adding a test that lists the public commands, guards against this.
   </details>

### Defend the decision
1. "Why keep the session on the connection instead of issuing a token?"
   <details><summary>Model answer</summary>

   Our protocol uses one long-lived TCP connection per client, so the connection already
   identifies the client. A dict per connection is the simplest correct design, and it
   logs the user out automatically on disconnect. Tokens solve a problem we don't have
   (stateless HTTP, several servers, reconnects). If we needed those, I'd issue
   `secrets.token_urlsafe()` tokens and store sessions server-side with an expiry.
   </details>
2. "Why put the login check in the dispatcher rather than in each handler?"
   <details><summary>Model answer</summary>

   It's one place to read, test and audit, and handlers stay focused on their own work.
   The same dict drives `help`, so what the user sees always matches what they're allowed
   to do. The trade-off is that the flag is per command. For roles (admin vs user) I'd
   replace the boolean with a required role or permission.
   </details>
3. "Is this login secure enough for production?"
   <details><summary>Model answer</summary>

   No. Passwords cross the socket without TLS, there's no rate limiting or lockout, so
   unlimited online guessing is possible, and there's no MFA. What it does get right:
   salted slow hashes, constant-time comparison, generic errors with matched timing, and
   per-connection sessions. I'd add `ssl`, per-account throttling and logging of failed
   attempts next.
   </details>
