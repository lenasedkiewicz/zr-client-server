---
id: 006
title: Create an admin account on first start
commit: "feat: create an admin account on first start"
step: 13 — create an admin account on first start
date: 2026-10-16
tags: [python, security, authorization, rbac, bootstrap, getpass, isatty, dependency-injection, unittest]
---

# Create an admin account on first start

## What we did
Accounts now have a role. `create_user` takes `role=ROLE_USER` and stores it in the record
(`users.py:58`, `users.py:72`), with the two roles defined in `config.py:19`. `has_admin()`
(`users.py:76`) reads the role with `record.get("role", ROLE_USER)`, so records written
before this step count as regular users and the existing `users.json` needs no migration.
`register` still creates plain users, because nothing in the network protocol can choose a
role.

The new `admin_setup.py` holds `ensure_admin` (`admin_setup.py:13`). If an admin exists it
returns at once. Otherwise it asks in the terminal for a username and the password twice,
and creates the account with `ROLE_ADMIN`, asking again after a mismatch or a validation
error. An existing username is rejected rather than promoted. Promotion will be its own
command. It's called from `server.py:210` after the certificate check and before
`serve_forever`, and from `run.py:106` *before* the server window opens, because a prompt
in the new window would outlast the launcher's 5-second startup wait. With no terminal
(`sys.stdin.isatty()` is false, `admin_setup.py:23`) it raises `RuntimeError`, and the
server exits instead of running without an admin. The prompts and the "is there a
terminal" flag are parameters, so `tests/test_admin_setup.py` scripts the answers. One
existing test (`test_register_stores_hash_not_password`) listed the record's exact keys
and now also expects `role == "user"`.

A surprise during the manual check: `python server.py < /dev/null` in Git Bash still
started the wizard. On Windows, `NUL` is a character device, and `isatty()` reports
character devices as terminals. The first `input()` then hit end of file, and the
`EOFError` branch exited cleanly ("Admin setup cancelled", exit code 1). Both ways out are
safe, but the tty check alone is not a reliable "am I interactive?" test on Windows.

## How it fits
- **Plan:** delivers Step 13. The stored role unblocks a `promote <username>` command and
  admin-only commands such as `stop`.
- **Practice:**
  - **Bootstrapping trust.** Every authorization system has a chicken-and-egg problem: who
    makes the first admin? The answer here is out-of-band: whoever can run the server in a
    terminal on its machine already controls it. The network can't create an admin.
    Django's `createsuperuser`, Jenkins' unlock key and Grafana's initial password work the
    same way. "First registered user becomes admin" is simpler but rejected, because anyone
    who reaches the port first wins.
  - **Least privilege / safe default.** The default role is `user`, and a missing role
    means `user`. A bug or an old record can only ever give *fewer* rights.
  - **Backward-compatible data.** Reading a new field with a default (`.get("role",
    ROLE_USER)`) avoids a migration step. With a real database you'd add a column with a
    default, which is the same idea.
  - **Inject the I/O.** `ask_username=input`, `ask_password=getpass.getpass` are default
    arguments, like `clock=` in `LoginThrottle`. Tests pass functions instead of patching
    `builtins.input`.
  - **When you'd differ:** in containers, CI or cloud deploys there's no terminal. There
    the first admin comes from environment variables or a secrets manager (Django:
    `createsuperuser --noinput` with `DJANGO_SUPERUSER_PASSWORD`), or from a one-time setup
    URL protected by a token printed in the server log.
  - **Known gap:** `users.json` is read once at startup. A second process editing it
    while the server runs is overwritten on the server's next save (a lost update). That's
    why the README says to create the admin with the server stopped, and why real systems
    keep users in a database with transactions.

## Commands used
- `cat <files>`, `sed -n <from>,<to>p <file>`, `grep -n <pattern> <files>`, `wc -l <files>`: read the code before the briefing and find line numbers for this entry.
- `ls docs docs/*`, `git log --oneline | head -20`, `grep -rniE "todo|next|later|future" README.md docs`: check what was still planned.
- `python - <<'EOF' … EOF`: add the role constants, `has_admin` and the `ensure_admin` calls. The `\\n` gotcha from [python -](../commands.md#python--run-a-script-from-stdin) struck again and had to be fixed by hand.
- `python -c "import server, run, admin_setup"`: check that the edited modules still parse and import.
- `sed -i 's/…/…/' tests/test_server.py`: add `ROLE_USER` to the test imports.
- `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED|FAIL:|ERROR:)"`: run the suite (39 tests, OK, 1 skipped).
- `file <files>`: see the line endings (CRLF in the Windows checkout). It also showed that `docs/commands.md`, rewritten by a text-mode Python script, had turned from LF into CRLF.
- `python -c "…open(p,'rb')…replace(b'\r\n',b'\n')…open(p,'wb')…"`: convert `docs/commands.md` back to LF, so the diff shows only the new entries.
- `python "$TEMP/claude_cmds.py"`: add the new entries to `docs/commands.md` and the index line (see [python <file>](../commands.md#python-file-run-a-script-file)).
- `python -c "import json; …"`: print each account's role in the real `users.json` (none had an admin).
- `python server.py < /dev/null; echo "exit=$?"`: start the server with no keyboard input to check it refuses to run without an admin, and print its exit code.
- `git diff --stat`, `git add …`, `git commit -F -`: review and commit.

## Read more
- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) — OWASP · least privilege and deny by default. It also argues that bigger apps should prefer attribute- or relationship-based access over plain roles.
- [How to Create Role-Based Access Control (RBAC) with Custom Claims Using Firebase Rules](https://www.freecodecamp.org/news/firebase-rbac-custom-claims-rules/) — freeCodeCamp · beginner admin-versus-user example. Only the trusted backend may set a role, never the client.
- [`createsuperuser`](https://docs.djangoproject.com/en/stable/ref/django-admin/#createsuperuser) — Django docs · the same first-admin bootstrap in a big framework, including the non-interactive `--noinput` mode with environment variables.
- [`getpass`](https://docs.python.org/3/library/getpass.html) — Python docs · hidden password input, and the `GetPassWarning` fallback that may echo the password when there is no terminal.
- [`io.IOBase.isatty`](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Python docs · "connected to a terminal/tty device". Compare [`os.isatty`](https://docs.python.org/3/library/os.html#os.isatty), which says "tty(-like)", the reason `NUL` passes on Windows.

## Quiz

### Revise
1. Why can't the first admin be created with a network command such as `register --admin`?
   <details><summary>Answer</summary>

   Nobody has admin rights yet, so the server couldn't check who is allowed to do it. Anyone
   who reached the port could make themselves admin. The terminal on the server machine is
   trusted instead, because only someone who controls the server can use it.
   </details>
2. What does `has_admin()` return for `{"old": {"salt": "…", "hash": "…", "iterations": 1000}}`?
   a) `True` b) `False` c) raises `KeyError` d) `None`
   <details><summary>Answer</summary>

   b). `record.get("role", ROLE_USER)` gives `"user"` for a record without the field, so it
   isn't an admin. Indexing with `record["role"]` would have raised `KeyError` (c).
   </details>
3. Why does `run.py` call `ensure_admin` itself instead of leaving it to the server window?
   <details><summary>Answer</summary>

   `run.py` waits only 5 seconds for the server to accept connections. A server busy asking
   for an admin password in another window would miss that deadline, and `run.py` would
   report a failed start. Asking first, in the terminal the user is already looking at,
   avoids that.
   </details>
4. What does this test helper return, and why is it used instead of `mock.patch("builtins.input")`?
   ```python
   def answers(*values):
       replies = iter(values)
       return lambda prompt="": next(replies)
   ```
   <details><summary>Answer</summary>

   A function that returns the next scripted value on each call, and raises
   `StopIteration` once they run out (which also proves "no prompt was shown" when given no
   values). `ensure_admin` takes its prompt functions as parameters, so the test just passes
   this in. No global patching is needed.
   </details>
5. Spot the bug: `interactive = sys.stdin.isatty()` is used to decide whether to prompt, and
   the server is started on Windows with `python server.py < NUL`. What happens?
   <details><summary>Answer</summary>

   `NUL` is a character device, so `isatty()` returns `True`. The wizard prompts and
   `input()` raises `EOFError`. Our code catches it and exits with "Admin setup cancelled".
   Without that `except`, the server would crash with a traceback. The tty check is a hint,
   not a guarantee.
   </details>

### Defend the decision
1. "Why not make the first registered user the admin? It needs no extra code."
   <details><summary>Model answer</summary>

   It turns a race into a privilege escalation. Whoever connects first after a fresh install
   (or after `users.json` is deleted) owns the server. Bootstrapping on the server's terminal
   ties the first admin to control of the machine. The cost is a prompt at first start, and
   no unattended first start, which I'd handle with environment variables or a secret in a
   container deployment.
   </details>
2. "Why trigger on 'no admin exists' instead of 'users.json doesn't exist'?"
   <details><summary>Model answer</summary>

   The file already exists on installs from earlier steps, so a file check would never
   create an admin there. "No admin" describes the state we need to fix. It also recovers
   if the only admin record is removed by hand. The trade-off is that the check scans all
   records on each start, which is trivial for a JSON file.
   </details>
3. "Why default a missing role to `user` instead of migrating `users.json`?"
   <details><summary>Model answer</summary>

   A migration is a separate step that can be forgotten or fail halfway, and the old record
   is valid data with an obvious meaning. Reading with a safe default keeps old and new
   records working, and it fails safe: a missing field gives fewer rights, never more. With
   a database I'd add the column with `DEFAULT 'user'`, which has the same effect.
   </details>
4. "Two processes can now write `users.json`: the launcher and the server. Is that a problem?"
   <details><summary>Model answer</summary>

   Yes, a lost update. The server loads the file once and saves its in-memory copy, so a
   change written by another process while it runs is overwritten on the next `register`.
   We avoid it by order: `run.py` writes before it starts the server, and the README says
   to create the admin with the server stopped. A real fix is a single owner of the data:
   a database with transactions, or a file lock plus re-reading before each write.
   </details>
