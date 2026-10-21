---
id: 004
title: Create the users file with owner-only permissions
commit: "feat: create users file with owner-only permissions"
step: 11 — restrict users file permissions
date: 2026-10-14
tags: [python, os, file-permissions, posix, umask, least-privilege, defence-in-depth, toctou, unittest, wsl]
---

# Create the users file with owner-only permissions

## What we did
`users.json` holds every account's salt and PBKDF2 hash. Before this change `_save()` created
its temporary file with plain `open(tmp_path, "w")`, so on Linux/macOS the file got the
default mode `0o666` minus the umask: usually `0o644` (`rw-r--r--`). Any local user could
copy the hashes and guess passwords offline, at their own pace, with no rate limit.

Now `_save()` creates the temporary file with `os.open(..., O_WRONLY | O_CREAT | O_TRUNC,
USERS_FILE_MODE)` (`users.py:47`) and wraps the descriptor in a normal text file with
`os.fdopen` (`users.py:48`). `USERS_FILE_MODE = 0o600` lives in `config.py:13`. `os.replace`
(`users.py:50`) renames the file, so the final `users.json` keeps the `0o600` inode. The mode is
set **when the file is created**, not with a later `os.chmod`, so there is no moment when the
hashes are readable by others. The new test `tests/test_server.py:172` registers a user and
checks `stat.S_IMODE(...) == 0o600`.

On Windows the `mode` argument only sets the read-only flag, and access is governed by ACLs
(the profile folder is already owner-only by default), so the test is skipped there. It was
run under WSL Ubuntu instead: it passes with the new code and fails on the old one with
`420 != 384` (`0o644` vs `0o600`), so it really guards the change.

Known gaps, left out on purpose: an existing `users.json` with `0o644` is fixed only on its
next save (the next `register`); and if a stale `users.json.tmp` survives a crash, `O_CREAT`
reuses it and keeps its old mode. Removing a stale temp file first, or `O_EXCL` with a
random name as `tempfile.mkstemp` does, would close that.

## How it fits
- **Plan:** delivers Step 11, the first "later chunk" from Step 10. The remaining hardening
  item is rate limiting / lockout after failed logins.
- **Practice:**
  - *Least privilege:* a file gets only the access its one user (the server process)
    needs. The opposite is CWE-732, "Incorrect Permission Assignment for Critical Resource".
  - *Defence in depth:* salted, slow hashes protect passwords *if* the file leaks; tight
    permissions make the leak harder in the first place. TLS (Step 10) covers transit.
  - *Secure by construction / avoid TOCTOU:* create-then-`chmod` leaves a window between the
    two calls. Passing the mode to the call that creates the file is atomic.
  - *When you'd differ:* real services keep accounts in a database, run as a dedicated
    system user and lock down the data *directory* (`0o700`); on Windows you'd set ACLs
    (`icacls`) or rely on the service account's profile.

## Commands used
- `python -m unittest discover tests`: run the whole suite on Windows (25 tests, 1 skipped).
- `python -m unittest -v tests.test_server.ServerTest.test_users_file_is_owner_only`: run
  just the new test and see why it was skipped.
- `wsl.exe -l -q`: check which WSL distributions are installed.
- `wsl.exe -d Ubuntu -- bash -c '...'`: run the suite inside Ubuntu on a copy of the repo.
- `cp -r /mnt/d/Programming/zr-client-server /tmp/zr`: copy the repo into the Linux file
  system, where POSIX permissions are real (the `/mnt/d` drive does not keep them).
- `umask`: print the default permission mask (`0022` in WSL Ubuntu).
- `git show HEAD:users.py > users.py`: put the old `users.py` in the copy, to prove the new
  test fails without the fix.
- `rm -rf /tmp/zr`: delete the throwaway copy.
- `sed -i`, `sed -n`, `grep -n`, `cat`: edit imports and look up line numbers.

## Read more
- [How to Change File Permissions with the chmod Command on Linux](https://www.freecodecamp.org/news/how-to-change-file-permissions-with-the-chmod-command-on-linux/) — freeCodeCamp · owner / group / others and read / write / execute, the model behind `0o600`.
- [os.open](https://docs.python.org/3/library/os.html#os.open) — Python docs · the `mode` is masked by the umask; `os.chmod` on Windows sets only the read-only flag.
- [tempfile.mkstemp](https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp) — Python docs · the stdlib's own secure temp file: no creation race (`O_EXCL`), readable only by its creator.
- [stat.S_IMODE](https://docs.python.org/3/library/stat.html) — Python docs · getting just the permission bits out of `st_mode`, as the test does.
- [CWE-732: Incorrect Permission Assignment for Critical Resource](https://cwe.mitre.org/data/definitions/732.html) — MITRE · the weakness this commit fixes; Example 4 shows the create-then-chmod pattern.

## Quiz

### Revise
1. What access does mode `0o600` give, and to whom?
   <details><summary>Answer</summary>

   Read and write (4 + 2 = 6) for the owner, nothing (0) for the group and nothing for
   others. In `ls -l` it shows as `rw-------`.
   </details>
2. With umask `0o022`, what mode does `open(path, "w")` give a new file on Linux?
   a) `0o600` b) `0o644` c) `0o666` d) `0o755`
   <details><summary>Answer</summary>

   b) `open` asks for `0o666`; the umask removes the write bit from group and others, giving
   `0o644`.
   </details>
3. Spot the problem:
   ```python
   with open(path, "w") as f:
       json.dump(users, f)
   os.chmod(path, 0o600)
   ```
   <details><summary>Answer</summary>

   Between creating the file and `chmod`, the hashes sit in a `0o644` file that another user
   can open, and an open handle keeps working after the `chmod`. Pass the mode to `os.open`
   when creating the file instead.
   </details>
4. Why does `users.json` end up `0o600` although the code only sets the mode on
   `users.json.tmp`?
   <details><summary>Answer</summary>

   `os.replace` renames the file: the same inode, with its permissions, gets the new name.
   </details>
5. Why is `test_users_file_is_owner_only` skipped on Windows, and how was it still checked?
   <details><summary>Answer</summary>

   On Windows the mode only toggles the read-only flag, so `S_IMODE` would not report
   `0o600`. It was run under WSL Ubuntu, on a copy in the Linux file system, and failed on
   the old code as expected.
   </details>
6. Can a umask *add* permissions to `os.open(path, flags, 0o600)`?
   <details><summary>Answer</summary>

   No. The umask is masked out (`mode & ~umask`), so it can only remove bits; `0o600` stays
   `0o600` or becomes stricter.
   </details>

### Defend the decision
1. "The passwords are already hashed with PBKDF2. Why care who can read the file?"
   <details><summary>Model answer</summary>

   Hashing slows an attacker down; it doesn't stop them. With the file they can run an
   offline guessing attack with no rate limit, and weak passwords fall quickly. Restricting
   the file is a cheap second layer (defence in depth), the same reason we added TLS
   for transit.
   </details>
2. "Why `os.open` with a mode instead of `os.chmod` after writing?"
   <details><summary>Model answer</summary>

   `chmod` after the fact is check-then-act: the file exists with default permissions for a
   moment, and anyone who opens it then keeps the handle. Setting the mode in the creating
   call is atomic. The cost is slightly less familiar code (`os.open` + `os.fdopen`), which a
   comment explains. `tempfile.mkstemp` would also work, at the cost of a random file name.
   </details>
3. "This does nothing on Windows. Why ship it?"
   <details><summary>Model answer</summary>

   The server is plain Python and may run on Linux, where it matters most (shared hosts,
   containers). On Windows the user profile's ACLs already restrict access. Proper Windows
   hardening would need ACL changes (`icacls` or the Win32 API), which the stdlib doesn't
   wrap, so it's out of scope; the test is skipped there with a stated reason rather than
   passing falsely.
   </details>
