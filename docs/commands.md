# Commands reference

Every shell command used in this project, explained once. Dev-journal entries list the
commands they ran and link here. Primary shell: PowerShell on Windows (Git Bash also available).

## Entry format

Use a heading in the form `### <command>: <what it does>`, so it can be linked as
`commands.md#<command>-<what-it-does>`:

```markdown
### mkdir: make a directory

`mkdir [-p] <path>`. Creates a directory.

- `-p`: create missing parent directories; no error if it already exists.

Example: `mkdir -p docs/dev-journal`

PowerShell: `New-Item -ItemType Directory -Force docs/dev-journal`

*First used in NNN*
```

Mark destructive commands with ⚠️ and say when they are safe to run.

## Python

### python --version: show the Python version

`python --version`. Prints the interpreter version (this project needs 3.10+).

On Windows the command is `python` (or the launcher `py`). On macOS and Linux it is often
`python3`.

*First used in 001*

### python -m unittest: run the test suite

`python -m unittest discover tests`. `-m` runs a module as a script, and `unittest discover`
finds every `test*.py` in the `tests` folder and runs it.

- `discover <dir>`: the folder to search for tests.
- `<module>.<Class>.<test>`: run a single test instead, e.g.
  `tests.test_server.ServerTest.test_users_file_is_owner_only`.
- Several targets in one run: list modules and/or classes separated by spaces, e.g.
  `tests.test_protocol tests.test_server.HandleRequestTest`. Handy for running only the fast
  unit tests without the end-to-end class.
- `-v`: verbose; print each test name with `ok`, `FAIL` or `skipped '<reason>'`.
- `-k <pattern>`: run only the tests whose full name contains `<pattern>` (or matches it, if
  it has `*`). Repeat `-k` to select several. In 025 this ran every new client test except
  the Ctrl+C ones against the old code: there, a mocked `KeyboardInterrupt` escaped and
  aborted the whole run.

Example: `python -m unittest discover tests`,
`python -m unittest -v tests.test_server.ServerTest.test_users_file_is_owner_only`,
`python -m unittest -v tests.test_protocol tests.test_server.HandleRequestTest tests.test_server.VersionTest`,
`python -m unittest -k malformed -k too_long tests.test_client`

*First used in 001; single test and `-v` added in 004; several modules/classes added in 013;
`-k` added in 025*

### python -c: run a one-line program

`python -c "<code>"`. Runs the code given as a string. Useful for a quick check of one
function without writing a file.

Example: `python -c "import client; print(client.build_request('info'))"`

PowerShell: the same command. Use double quotes outside and single quotes inside.

Gotcha (Windows): the console encoding is a legacy code page (e.g. `cp1250`), so
`print('١')` fails with `UnicodeEncodeError: 'charmap' codec can't encode`. That is
the *printing* failing, not your code. Print `bool(...)`, `ascii(...)` or `repr(...)`
instead, or set `PYTHONIOENCODING=utf-8` (PowerShell: `$env:PYTHONIOENCODING = 'utf-8'`).
Example from 014:
`python -c "import re; print(bool(re.match(r'^\d$', '١')), bool(re.match(r'^1$', '1\n')))"`
→ `True True` (`\d` matches an Arabic-Indic digit; `$` accepts a trailing newline).

Example from 022, asking Python which OS clock sits behind each `time` function:
`python -c "import time;print(time.get_clock_info('monotonic'), time.get_clock_info('time'))"`
→ on Windows with Python 3.13, `monotonic` is `QueryPerformanceCounter()` (`adjustable=False`)
and `time` is `GetSystemTimePreciseAsFileTime()` (`adjustable=True`).

*First used in 001; console-encoding gotcha added in 014; clock example added in 022*

### python <file>: run a script file

`python <path/to/script.py>`. Runs a Python file. Used for one-off edit scripts kept in
`$TEMP` (see [$TEMP](#temp-the-temp-directory)) when the script itself contains `'''`
strings that would clash with quoting in [python -](#python--run-a-script-from-stdin).

Example: `python "$TEMP/claude_edit2.py"`

*First used in 002*

### python -: run a script from stdin

`python - <<'EOF' … EOF`. `-` tells Python to read the program from standard input, and
the [heredoc](#heredoc-multi-line-input-to-a-command) supplies it. Handy for a throwaway
script that edits files.

Gotcha: inside a normal (non-raw) Python string, `\n` is a real line break. To write the
two characters `\n` into a target file, write `\\n` in the script. Text containing many
backslashes (Windows paths like `C:\Users`, where `\U` is an invalid escape, or regexes) is
easier as a raw string (`r'…'`) in a script file written with an editor, run with
[python <file>](#python-file-run-a-script-file). *(Raw-string tip added in 003.)*

The same trap with `\u`: `"\\u0662"` in the script is the 6 characters `٢` in Python,
and if that text then lands inside *another* normal string literal it becomes the real
character `٢`. In 014 this wrote a non-ASCII digit into the test file instead of an escape.
Use `chr(92) + 'u0662'` (92 is the backslash), or skip the script and use an editor.
Check the result with [file](#file-show-a-files-type-and-line-endings) (`ASCII text` vs
`UTF-8 text`) or [od -c](#od--c-show-the-exact-characters-in-a-file). *(Added in 014.)*

PowerShell: pipe a here-string instead: `@'<code>'@ | python -`.

*First used in 001*

### python -u: unbuffered output

`python -u <script>`. Turns off output buffering, so `print` lines reach a redirected file
or pipe immediately rather than when the buffer fills or the program exits.

Example: `python -u server.py > "$TEMP/srv.log" 2>&1` (server log readable while it runs)

*First used in 003*

### python -I: isolated mode

`python -I <script>`. Runs Python in isolated mode: the script's own folder and the current
folder are **not** added to `sys.path`, and `PYTHON*` environment variables and the user
site-packages are ignored. A stray `json.py` next to a probe script can't then shadow the
real `json` module. Combine with `-u` as `python -I -u probe.py`.

Example: `python -I -u probe.py` (a throwaway experiment in the scratchpad: which exception
each malformed input raises, and whether a text stream survives a decode error)

*First used in 010*

### PYTHONPATH: extra folders to import from

`PYTHONPATH=<dir> python <script>`. Adds `<dir>` to the front of `sys.path` for that one
run. Python adds a script's *own* folder, not the current one, so a probe in the scratchpad
can't `import config` from the repo without it. `.` means the current folder.

Example: `PYTHONPATH=. python "$S/hold_port.py"`: a scratchpad script that imports `config`
from the repo, holds the server's port, and runs `python server.py` to see what it prints.

PowerShell: `$env:PYTHONPATH = '.'; python $S\hold_port.py`. This stays set for the rest of
the session, so clear it afterwards: `Remove-Item Env:PYTHONPATH`. Don't combine it with
[python -I](#python--i-isolated-mode), which ignores `PYTHONPATH`.

*First used in 027*

### py: the Windows Python launcher

`py [-<version>] <python arguments>`. Installed with Python on Windows. It starts a chosen
installed Python version, so you can run the same command on several versions without
changing `PATH`. Everything after the version flag goes to Python unchanged.

- `-0`: list the installed versions; `*` marks the default.
- `-3.10`, `-3.12`, …: run that version.

Example: `py -0`; `py -3.10 -m unittest discover tests` (the CI runs 3.10 and 3.14, so check
the oldest supported version locally); `py -3.12 -c "import sys; print(sys.version)"`

PowerShell: the same command. On Linux and macOS there is no `py`; use `python3.10` etc.

*First used in 020*

## TLS / OpenSSL

### openssl req: create a self-signed certificate

`openssl req -x509 -newkey rsa:2048 -nodes -keyout <key> -out <crt> -days N -subj "/CN=…" -addext "subjectAltName=…"`.
Creates a new private key and a self-signed certificate in one step. Python's `ssl` can use
certificates but cannot create them, so this is done once from the command line.

- `req`: the certificate-request tool; with `-x509` it outputs a self-signed certificate
  instead of a request for a CA to sign.
- `-newkey rsa:2048`: generate a new 2048-bit RSA key pair.
- `-nodes`: "no DES", i.e. do not encrypt the private key with a passphrase, so the
  server can start without a prompt. The key file must then be protected (git-ignored).
- `-keyout <file>` / `-out <file>`: where to write the private key and the certificate.
- `-days N`: validity period (365 for the real pair, 36500 for the test pair so tests
  never expire).
- `-subj "/CN=localhost"`: the subject, given inline to skip the interactive questions.
- `-addext "subjectAltName=IP:127.0.0.1,DNS:localhost"`: the names the certificate is
  valid for. Clients check the hostname against the SAN, not the CN, so it must contain
  the `127.0.0.1` the client connects to.

Example: `MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -keyout server.key -out server.crt -days 365 -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"`

PowerShell: `openssl` ships with Git for Windows but is not on the PowerShell PATH. Run it
from Git Bash, or call `& "C:\Program Files\Git\usr\bin\openssl.exe" req …` (no
`MSYS_NO_PATHCONV` needed there).

*First used in 003*

### MSYS_NO_PATHCONV: stop Git Bash rewriting paths

`MSYS_NO_PATHCONV=1 <command>`. Git Bash converts arguments that look like Unix paths into
Windows paths before running a native program, so `-subj "/CN=localhost"` would arrive as
`C:/Program Files/Git/CN=localhost`. Setting this variable for one command turns that off.
`VAR=value cmd` sets the variable only for that command.

PowerShell: not needed (no path conversion). To set a variable for one command:
`$env:VAR = 'x'; cmd`.

*First used in 003*

### openssl x509: print a certificate's details

`openssl x509 -in <crt> -noout [-subject -issuer -dates -fingerprint] [-ext <names>]`. Reads
a certificate and prints the parts you ask for.

- `-noout`: don't print the encoded certificate itself.
- `-subject` / `-issuer`: who the certificate is for, and who signed it. Self-signed means
  both are the same.
- `-dates`: `notBefore` / `notAfter`; `-fingerprint`: a hash that identifies the exact
  certificate.
- `-ext basicConstraints,keyUsage,...`: print only these X.509 extensions (OpenSSL 1.1.1+).

Example: `openssl x509 -in "$TEMP/sent.pem" -noout -subject -issuer -dates -fingerprint`
(the issuer of the certificate the server "sent" was Avast, not us)

PowerShell: see the `openssl` PATH note under [openssl req](#openssl-req-create-a-self-signed-certificate).

*First used in 015*

### openssl verify: check a certificate against trusted ones

`openssl verify [-x509_strict] -CAfile <trusted.crt> <crt>`. Builds and checks the chain of
`<crt>` against the certificates in `-CAfile`; prints `OK` or the reason it fails.

- `-x509_strict`: apply the stricter RFC 5280 checks (Python turns these on by default).

Example: `openssl verify -x509_strict -CAfile tests/certs/test-server.crt tests/certs/test-server.crt`

Note: Git Bash's `openssl` (1.1.1 here) is not the OpenSSL inside Python (3.5 in Python
3.14). Check `python -c "import ssl; print(ssl.OPENSSL_VERSION)"` before blaming a version.

*First used in 015*

## Network

### curl: make an HTTP request

`curl [-s] [-S] [-m N] [-o <file>] [-w <format>] <url>`. Downloads a URL and prints the body.

- `-s`: silent, no progress bar; `-S` with `-s`: still show errors.
- `-m N`: give up after N seconds.
- `-o /dev/null -w "%{http_code}
"`: throw the body away and print only the status code.

Example: `curl -sS -m 20 -o /dev/null -w "%{http_code}
" https://api.github.com/repos/actions/checkout/releases/latest`

`curl: (60) SSL certificate problem: unable to get local issuer certificate` means curl
doesn't trust the certificate it received. Here Avast's HTTPS scanning had replaced it.

PowerShell: `curl.exe` (plain `curl` is an alias for `Invoke-WebRequest` in Windows
PowerShell 5.1).

*First used in 015*

### netstat -ano: which process uses a port

`netstat -ano`. Lists every TCP and UDP connection and listening port with its state and
the ID of the process that owns it.

- `-a`: all connections and listening ports. `-n`: numbers, not names, which is faster and
  exact. `-o`: add the owning process ID (Windows; on Linux use `ss -ltnp`).

Example (029: which process is the test server listening on 65432?):
`netstat -ano | grep "127.0.0.1:65432" | grep LISTENING | awk '{print $NF}'`. `$NF` is
awk's last field, the PID. Then check it with
[tasklist /FI](#tasklist-list-running-processes) before
[taskkill](#taskkill-stop-a-windows-process).

PowerShell: `(Get-NetTCPConnection -LocalPort 65432 -State Listen).OwningProcess`.

*First used in 029*

## Git

### git diff: show unstaged changes

`git diff [--stat] [<commit> [<commit>]] [-- <path>]`. With no commit, shows what changed in
the working tree since the last `git add`; with one, compares the working tree with that
commit; with two, compares the two commits.

- `--stat`: show only a per-file summary of added and removed lines.
- `-- <path>`: limit the diff to one file; `--` separates revisions from file names.
- `-U<n>`: show n lines of context around each change. `git diff -U0` shows only the
  changed lines, which suits a quick review of a small edit.

Example: `git diff --stat`, `git diff server.py`, `git diff feature/admin -- .gitignore` (no
output means the file is identical on both sides, so a merge will not conflict there)

Git Bash: a revision containing `/` followed by `:path` (e.g. `feature/admin:.gitignore`) can
be mangled by MSYS path conversion; the `<commit> -- <path>` form avoids it.

During a merge, `git diff` with no arguments shows only the conflicted files, in a
"combined" format with two `+`/`-` columns (one per parent).

- `<a>...<b>` (three dots): what `<b>` changed since it branched off `<a>`, i.e. the diff
  from their [merge base](#git-merge-base-find-the-common-ancestor) to `<b>`. This is what a
  pull request shows. Two dots (or two commits with a space) compare the two tips, so
  changes made on `<a>` in the meantime show up too. Example: `git diff master...HEAD`.
- `-- . ':!<path>'`: everything except `<path>` (an "exclude pathspec"). Example:
  `git diff 8bc6362 HEAD --stat -- . ':!docs'` (what the review fixes changed, without the
  journal). PowerShell: the same, single quotes work there too.
- `--quiet`: print nothing, and exit 0 if there are no differences, 1 if there are. Made
  for scripts: `git diff --quiet -- run.py && echo "run.py clean"` (032: check that a file
  has no uncommitted changes before mutating it, and that it's back to HEAD afterwards).

*First used in 001; commit and `--` forms added in 007; merge view added in 008; `-U<n>` added in 017; `...` and `':!'` added with the pre-review skill; `--quiet` added in 032*

### git add: stage changes

`git add <paths>`. Marks files to be included in the next commit.

Example: `git add users.py server.py docs/dev-journal/001-register-user-accounts.md`

*First used in 001*

### git commit: record a commit

`git commit -F <file>`. Creates a commit from the staged changes.

- `-F -`: read the commit message from stdin (used with a heredoc for multi-line messages).
- `-m "<msg>"`: give the message inline (one paragraph per `-m`).

PowerShell: `git commit -m @'<multi-line message>'@`, with the closing `'@` at column 0.

*First used in 001*

### git show: print a file from a commit

`git show <rev>:<path>`. Prints the file as it was in that commit, without touching the
working tree. Redirect it to a file to get an old copy.

Example: `git show HEAD:users.py > users.py` (in a throwaway copy, to run the new test
against the old code)

PowerShell: the same, but `>` writes UTF-16 in Windows PowerShell 5.1; use
`git show HEAD:users.py | Out-File -Encoding utf8 old_users.py`.

- `--stat <rev>`: show a commit's message and the list of files it changed, with
  added/removed line counts, instead of the full diff. Example: `git show --stat HEAD~1`
- `--format='<fmt>'`: the header line(s), with the same placeholders as
  [git log](#git-log-list-commits). Example: `git show --stat --format='%h %s' e872f44`
  (024: one line, then the changed files).
  (what the planning commit touched). `HEAD~1` is the commit before `HEAD`.
- `<rev> -- <path>`: show that commit's message and its diff, but only for `<path>`.
  Example: `git show ab438a5 -- README.md` (what the previous task added to the README, to
  match its wording).

*First used in 004; `--stat` added in 010; `<rev> -- <path>` added in 021; `--format` added in 024*

### git archive: export a commit's files

`git archive <rev> | tar -x -C <dir>`. Writes the files of a commit as a tar archive to
stdout, and `tar -x -C <dir>` unpacks them into `<dir>`. The result is a plain copy with no
`.git` and no untracked files, so you can change and test it without touching your
working tree.

- `tar -x`: extract. `-C <dir>`: change to `<dir>` first (it must exist).
- Files that git ignores (`server.crt`, `users.json`) are not in the copy.

Example (the "does the new test fail without the fix?" check in 027, on a copy):
`git archive HEAD | tar -x -C "$S/c1"`, then
`git show 65d08cd:server.py > "$S/c1/server.py"` and run the tests in `$S/c1`. `>` is
safe here because it writes into the copy, not the repo.

PowerShell: don't pipe it. Windows PowerShell 5.1 turns output piped between two programs
into text, which corrupts a binary stream like a tar archive (PowerShell 7.4+ passes the
bytes through). Write a file instead: `git archive -o $S\c1.tar HEAD; tar -x -f $S\c1.tar -C $S\c1`.
`tar` ships with Windows 10+, and `-o` (output file) and `tar -f` (archive file) replace
the pipe.
⚠️ Clean up the copy afterwards (`rm -rf "$S/c1"`, PowerShell
`Remove-Item -Recurse -Force $S\c1`), and check the path first: it's the scratchpad, not the
repo.

*First used in 027*

### git grep: search tracked files

`git grep [-n] <pattern> [<path>]`. Like [grep](#grep-search-text) `-r`, but searches only
files git tracks, so it skips `.git/`, ignored files and virtualenvs.

Example: `git grep -n "skip" tests`

PowerShell: the same command.

*First used in 010*

### git log: list commits

`git log --oneline [<a>..<b>]`. Lists commits, newest first.

- `--oneline`: one line per commit, with the short hash and the subject.
- `<a>..<b>`: only commits reachable from `<b>` but not from `<a>`, i.e. what `<b>` has that
  `<a>` lacks.

Example: `git log --oneline | head -15`; `git log --oneline origin/master..origin/feature/admin`
(the PR's own commits)

- `-S'<text>' -- <path>`: only commits that added or removed `<text>` in that file (the
  "pickaxe"). Used to find when test passwords first appeared, for a GitGuardian triage.
- `-<n> [<branch>]`: only the newest `n` commits, of `<branch>` instead of the current one.
  Works the same in PowerShell, with no `head` needed. Example: `git log --oneline -3 master`
  (is the merged PR on `master` yet?).
- `--graph --all`: draw the branch and merge lines, for every branch and not only the
  current one. Example: `git log --all --oneline --graph`.
- `--no-merges`: leave out merge commits, so only the commits that changed code remain.
- `--format='<fmt>'`: choose what is printed per commit: `%h` short hash, `%s` subject,
  `%b` body, `%n` a newline. Example: `git log --format='%h %s%n%b' 8bc6362..HEAD --no-merges`
  (every fix since the review plan, with its full message).

PowerShell: the same; use `| Select-Object -First 15` instead of `head`.

*First used in 005; `a..b` added in 008; `-S` added in 018; `-<n> <branch>` added in 021;
`--graph`, `--all`, `--no-merges` and `--format` added with the pre-review skill*

### git branch --show-current: print the current branch

`git branch --show-current`. Prints the name of the checked-out branch (nothing on a
detached HEAD). Without the flag, `git branch` lists local branches with `*` on the current
one, and `-a` adds the remote-tracking ones (`remotes/origin/...`).

Example: checking that a change goes onto `master` before editing; `git branch -a` after a
fetch to see `origin/feature/admin`.

- `-vv`: also show each branch's last commit and the remote branch it tracks.
- `-d <branch>…`: delete local branches. Safe: git refuses if a branch has commits that
  aren't merged. ⚠️ `-D` deletes anyway and can lose commits; use it only when you mean it.

Example: `git branch -d feature/admin test/test-foundations` after their PRs were merged.

`[gone]` in `git branch -vv` (after `git fetch --prune`) means the remote branch was
deleted, usually because its PR was merged. Those local branches are the ones to clean up.
`-D` example (028): `git branch -D fix/server-lifecycle`. Its one commit was an older copy
of a change merged under another hash, so `-d` refused. That was checked first with
[diff <(…) <(…)](#diff---compare-two-commands-output).

*First used in 007; `-a` added in 008; `-vv`, `-d` added in 018; `[gone]`, `-D` added in 028*

### git fetch: download new commits from the remote

`git fetch --all --prune`. Downloads commits and branches from the remote into the
remote-tracking branches (`origin/master`, ...) without touching your own branches or files.

- `--all`: fetch every configured remote, not just `origin`.
- `--prune`: delete remote-tracking branches whose branch was deleted on the remote.

- `--quiet` (short: `-q`): no progress output.

Example: `git fetch --all --prune` before merging, so `origin/master` is current;
`git fetch -q` after a PR merge.

*First used in 008; `--quiet` added in 015; `-q` added in 024*

### git pull: fetch and update the current branch

`git pull [--ff-only]`. Runs `git fetch`, then joins the remote branch into the current
one. Plain `git pull` may create a merge commit (or rebase, depending on config) when
your branch and the remote have diverged.

- `--ff-only`: only fast-forward, i.e. move your branch pointer forward to the remote's
  commit. If the branches have diverged, git refuses and changes nothing, so a pull never
  creates a surprise merge commit.
- `-q`: quiet, no progress or summary output.

Example: `git pull --ff-only` on `master` before branching for a new fix batch;
`git pull -q --ff-only` right after a PR merge.

*First used in the step 16 plan commit (`docs:` commit, no journal entry); `-q` added in 020*

### git checkout: switch branches

`git checkout <branch>`. Switches the working tree to another branch. Git refuses if
uncommitted changes would be overwritten. Newer git also has `git switch <branch>`, which
does only this.

- `-b <new-branch>`: create the branch at the current commit and switch to it
  (`git switch -c <new-branch>` in newer git).
- `-b <new-branch> <start>`: create the branch at `<start>` instead of the current commit.
  Example: `git checkout -b chore/pre-review-skill master` (start from `master` while
  standing on an unmerged fix branch).
- `-q`: quiet, no "Switched to branch" message.
- ⚠️ `-- <path>…`: restore the files from the index, which **throws away** their uncommitted
  changes, with no undo. Safe only for changes you made a moment ago on purpose, or ones
  stashed first. In 026, after `git stash push -- client.py config.py` and a temporary edit
  to the old code, `git checkout -q client.py config.py && git stash pop -q` dropped the
  temporary edit and brought the fix back. The `--` may be left out when no branch has the
  same name as the file, but with it git never mistakes a path for a branch. Newer git:
  `git restore <path>`.

Example: `git checkout feature/admin`; `git checkout -b fix/server-survives-bad-client`;
`git checkout -q master`; `git switch fix/server-limits` (back to batch 5's branch from an
already-merged one)

*First used in 008; `-b` added in the step 16 plan commit; `-q` added in 020; `git switch`
first used in 021; start point added with the pre-review skill; `-- <path>` added in 026*

### git merge: join another branch into the current one

`git merge [--no-edit] <branch>`. Brings the other branch's commits into the current branch
and records a merge commit with two parents. On conflicts it stops: fix each file, `git add`
it, then `git commit` finishes the merge.

- `--no-edit`: accept git's default message instead of opening an editor.
- `--no-commit`: stop before recording the merge, so you can check the result first.
- `--no-ff`: always create a merge commit, even if git could just move the branch forward.
- `--abort`: give up and return to the state before the merge. ⚠️ Discards the conflict
  resolutions you have made so far; safe when you want to start the merge over.

Conflict markers in a file: `<<<<<<< HEAD` (your branch), `=======`, `>>>>>>> <branch>`
(theirs). Remove all three and keep the right mix of both sides.

Example: `git merge origin/master --no-edit` (on `feature/admin`, to update PR #1)

*First used in 008; `--no-commit`, `--no-ff` added in the PR #5 merge*

### git clone: copy a repository

`git clone [-q] <source> <folder>`. Creates a new folder with a full copy of the repository.
The source can be a URL or a local path, so a throwaway local clone is a safe place to try a
merge when your git is too old for `git merge-tree --write-tree`.

- `-q`: quiet, no progress output.

Example: `git clone -q . ../mergetest`

*First used in the PR #5 merge*

### git merge-base: find the common ancestor

`git merge-base <a> <b>`. Prints the commit where two branches split. A merge compares both
sides against this commit.

Example: `git merge-base origin/master origin/feature/admin` → `3eafafb…`

- `--is-ancestor <a> <b>`: print nothing, exit with 0 if `<a>` is already in `<b>`'s history
  (fully merged), 1 if not. Made for scripts: `git merge-base --is-ancestor feature/admin
  master && echo merged`.

*First used in 008; `--is-ancestor` added in 018*

### git cherry: find commits not yet upstream

`git cherry <upstream> <branch>`. Lists the branch's commits, marked `+` if no commit with the
same changes is in `<upstream>`, `-` if one is. Unlike `git log a..b` it compares the changes,
so a commit that reached `master` by a squash or cherry-pick shows as `-`.

Example: `git cherry master feature/admin | grep -c '^+'` → `0` (nothing left to merge)

*First used in 018*

### git cherry-pick: copy a commit onto the current branch

`git cherry-pick <commit>…`. Applies the changes of each given commit on top of the current
branch as a new commit, with the same message and author but a new hash. The original
commit stays where it was.

Example: `git cherry-pick e872f44` (task 6.2 was committed after the batch 6 branch was
pushed for its PR, so it never reached `master`; it was copied onto a new branch started
from `master`).

If it conflicts, git stops: fix the files, `git add` them, then `git cherry-pick --continue`,
or `git cherry-pick --abort` to go back. Use it for a commit or two that are on the wrong
branch. To move a whole branch, rebase or merge instead. Afterwards `git cherry` shows the
original as `-`, already upstream.

PowerShell: the same command.

*First used in 024*

### git mv: rename a tracked file

`git mv <old> <new>`. Renames the file and stages the rename in one step.

Example: `git mv docs/dev-journal/001-alpha-version-in-info.md docs/dev-journal/007-alpha-version-in-info.md`

PowerShell: the same command.

*First used in 008*

### git push: upload commits to the remote

`git push [<remote> <branch>]`. Sends your new commits to the remote branch. With no
arguments it pushes the current branch to its upstream. A plain push only adds commits;
⚠️ `--force` overwrites the remote branch and is only safe on a branch nobody else uses
(it is what a rebase of a pushed branch would need).

- `-u`: also set the remote branch as the upstream of the local one, so later plain
  `git push` / `git pull` know where to go. Use it on a branch's first push.

- ⚠️ `--delete <branch>…`: delete branches on the remote, for everyone. Safe for a branch
  whose PR is merged; GitHub's "Restore branch" button on the PR can bring it back.

Example: `git push origin feature/admin` (updates PR #1); `git push -u origin ci/github-actions`
(first push of a new branch); `git push origin --delete ci/github-actions`

*First used in 008; `-u` added in 015; `--delete` added in 018*

### git ls-remote: list a remote's branches and tags

`git ls-remote [--tags] <url> [<pattern>]`. Lists refs and the commit each points to, without
cloning. Useful to find the commit SHA behind a tag.

Example: `git ls-remote --tags https://github.com/actions/checkout.git 'v*'`

It goes over HTTPS, so here it failed the same way as `curl` (Avast); the GitHub API via a
browser gave the SHA instead.

- `--heads origin`: list the branches that really exist on GitHub now. Your
  `origin/...` refs are only a copy from the last fetch.

*First used in 015; `--heads` added in 018*

### gh pr view: show a pull request

`gh pr view <number> [--json <fields>]`. GitHub CLI: prints a pull request's details.

- `--json headRefName,baseRefName,mergeable,title`: print only those fields as JSON;
  `mergeable` is `CONFLICTING` when GitHub cannot merge it automatically.

- `--jq <filter>`: keep only part of the JSON, as in [gh api](#gh-api-call-the-github-api).
  `statusCheckRollup` lists the PR's checks (CI jobs, GitGuardian) with their result, and
  `mergeStateStatus` is `UNSTABLE` while a check fails or is still running.

Example: `gh pr view 1 --json headRefName,baseRefName,mergeable,title`;
`gh pr view 5 --json mergeable,mergeStateStatus,statusCheckRollup`

*First used in 008; `--jq`, `statusCheckRollup` added in 018*

### gh pr create: open a pull request

`gh pr create --base <branch> --title <title> --body-file <file>`. GitHub CLI: opens a pull
request from the current branch. Push the branch first (`git push -u`), otherwise gh asks
whether to push it for you.

- `--base <branch>`: the branch to merge into (here `master`).
- `--title <title>`: the PR title.
- `--body-file <file>`: read the PR description from a file. This is easier than `--body`
  for a multi-line Markdown body, because you avoid quoting problems in PowerShell and Bash.

Example: `gh pr create --base master --title "Batch 4: protocol contract" --body-file pr-body.md`

PowerShell: the same command.

*First used with `chore: bump version to 0.1.1-alpha` (no journal entry)*

### gh pr list: list pull requests

`gh pr list [--head <branch>] [--state open|closed|merged|all]`. GitHub CLI: lists pull
requests; by default only open ones.

- `--head <branch>`: only PRs opened from this branch. Empty output means it has no open PR.
- `--limit <n>`: at most n PRs (default 30).
- `--json <fields> --jq <filter>`: pick fields and format them, e.g. each PR's state and
  head commit, to check that every branch's PR is merged.

Example: `gh pr list --head fix/server-survives-bad-client`;
`gh pr list --state all --limit 10 --json number,headRefName,state --jq '.[]|"\(.number) \(.state) \(.headRefName)"'`

*First used in 011; `--limit`, `--json`, `--jq` added in 018*

### gh run list: list GitHub Actions runs

`gh run list [--branch <b>] [--limit N] [--json <fields> --jq <expr>]`. GitHub CLI: shows
recent CI runs with their status (`completed`, `in_progress`), conclusion (`success`,
`failure`), event (`push`, `pull_request`) and commit.

- `--branch <b>`: only runs for that branch.
- `--json` / `--jq`: pick fields and format them, as for
  [gh pr list](#gh-pr-list-list-pull-requests).

Example (028: did CI pass on the merged PR #11?): `gh run list --branch master --limit 3`;
`gh run list --limit 3 --json headSha,status,conclusion,event,headBranch -q '.[] | "\(.headBranch) \(.event) \(.headSha[0:7]) \(.status) \(.conclusion)"'`.
`-q` is short for `--jq`.

PowerShell: the same command. Quote the `--jq` expression with single quotes there too.

*First used in 028*

### git ls-tree: list files in a commit

`git ls-tree [--name-only] <rev> [<path>]`. Lists the files and folders stored in a commit or
branch, without checking it out.

- `--name-only`: print just the paths, not the mode, type and hash.

Example: `git ls-tree --name-only origin/feature/admin docs/concepts/`

*First used in 008*

### git merge-tree: preview a merge without touching files

`git merge-tree --write-tree --name-only <branch1> <branch2>`. Performs the merge in memory
and prints the resulting tree plus the conflicted files, leaving the working tree alone.
Needs git 2.38+. Older versions only know the deprecated `git merge-tree <base> <b1> <b2>`
form and fail with `usage:` (exit 129), as here; then just merge and `git merge --abort` if
needed.

The old form still works as a preview. It prints a diff per file, with `changed in both` for
files both sides touched and `<<<<<<<` markers where they really conflict. Search it instead
of reading it:
`git merge-tree $(git merge-base origin/master fix/server-lifecycle-2) origin/master fix/server-lifecycle-2 | grep -n -B3 -A25 "<<<<<<<"`.
`$( … )` runs the inner command and puts its output in place, here the base commit's hash.
PowerShell runs the same `git` line, since `$( … )` works there too.
"Changed in both" with no markers merged cleanly as text, but still read the result: git
merges lines, not meaning.

*First used in 008; old form as a preview added in the lifecycle-2 merge*

### git ls-files: list tracked files

`git ls-files [<path>]`. Prints every file git tracks, one per line. Ignored and untracked
files are left out, so it shows what a reviewer will actually get.

Example: `git ls-files`; `git ls-files tests`

- `-z`: end each name with a NUL byte instead of a newline, so a name with spaces or a
  newline can't be split in two. Pair it with [xargs -0](#xargs-turn-input-lines-into-arguments).

Example (028: a scratch copy of the repo with only tracked files, plus the working tree's
uncommitted `run.py`):
`git ls-files -z | xargs -0 tar -cf - | tar -x -C "$S/e2e"`.
`tar -c` creates an archive, `-f -` writes it to stdout, and the second `tar -x -C` unpacks
it in the copy. Unlike [git archive](#git-archive-export-a-commits-files), this copies the
files as they are on disk, uncommitted changes included. ⚠️ In PowerShell 5.1 don't pipe
binary data between programs (see git archive); run it in Git Bash.

- `--eol`: show each file's line endings, in the index (`i/`) and in the working tree
  (`w/`): `lf`, `crlf`, `mixed`, or `-text` for a binary file. With `core.autocrlf=true`
  (the usual Windows setup) a text file is `i/lf w/crlf`: LF in the repo, CRLF on disk.
  Use it after an edit by a POSIX tool such as [sed -i](#sed--i-edit-a-file-in-place), along
  with `git diff --stat`. If the stat shows every line changed, the line endings changed.
  Git's "LF will be replaced by CRLF" warning is only this conversion, not a change.

Example (034): `git ls-files --eol run.py client.py`

PowerShell: the same command.

*First used with the pre-review skill; `-z` added in 028; `--eol` added in 034*

### git status: show the working tree state

`git status --short [--ignored]`. Shows changed, staged and untracked files.

- `--short`: two-letter codes per file (`M` modified, `??` untracked).
- `--ignored`: also list ignored files (`!!`), e.g. to check that `server.key` and
  `users.json` really are git-ignored.
- `-sb`: short format plus a first line with the branch and how far it is ahead of or
  behind its upstream (`## feature/admin...origin/feature/admin`).

During a merge, `UU` marks a file with unresolved conflicts, `A ` a file added by the
other branch.

Example: `git status --short --ignored`

Gotcha (030): `git status --short users.json` prints nothing whether or not the file
changed, because `users.json` is git-ignored and git doesn't watch it. Empty output
doesn't prove "unchanged" there. Look at the file itself (`ls -l`, or read it).

*First used in 005; `-sb` and merge codes added in 008; ignored-file gotcha added in 030*

### git check-ignore: why is a file ignored?

`git check-ignore -v <path>`. Prints the `.gitignore` rule that ignores `<path>`, as
`file:line:pattern<TAB>path`, and nothing (exit code 1) if the file isn't ignored.

- `-v`: verbose, show the matching rule, not only the path.

Example (030): `git check-ignore -v users.json` → `.gitignore:27:users.json	users.json`.

PowerShell: the same command.

*First used in 030*

### git stash: put changes aside for a moment

`git stash [push] [-q] [-u] [-m <message>] [-- <path>…]` / `git stash pop [-q]`. Saves uncommitted changes on a
stack and resets the files to the last commit; `pop` puts them back and drops the entry.

- `-- <path>`: stash only these files and leave the others changed. Used here to undo just
  the fix in `server.py` while keeping the new tests, to prove the tests fail without it.
- `-q`: quiet, no summary output.
- `-u`: also stash untracked files, which are left in place by default.
- `-m "<message>"`: label the entry, so `git stash list` shows what it is. Worth it when the
  stash will wait longer than a minute (e.g. unfinished work parked while another branch
  goes in).

A stash exists only in this clone and is never pushed. To move work to another machine,
commit it on a branch and push that.

Example: `git stash push -m "task 3.1 logging WIP"`;
`git stash -q -- server.py && python -m unittest tests.test_server; git stash pop -q`

If `pop` hits a conflict, the entry stays on the stack (`git stash list`) and nothing is
lost. Resolve the conflict, then `git stash drop`.

*First used in 011; `-m` added in 015, `-u` added in 016*

### git for-each-ref: list branches and tags with a format

`git for-each-ref [--sort=<key>] [--format=<format>] [<pattern>…]`. Lists refs (branches,
tags), and unlike `git branch` lets you choose the fields and the order.

- `--sort=-committerdate`: newest commit first (`-` reverses the order).
- `--format='%(committerdate:short) %(refname:short) %(subject)'`: what to print for each ref.
- `refs/heads refs/remotes`: only local and remote-tracking branches.

Example: `git for-each-ref --sort=-committerdate --format='%(committerdate:short) %(refname:short)' refs/heads refs/remotes`

*First used in 016*

### git rev-list --count: count commits

`git rev-list --count <a>..<b>`. Prints how many commits are in `<b>` but not in `<a>`.

Example: `git rev-list --count master..origin/ci/github-actions`

*First used in 016*

### git rev-parse: turn a name into a commit hash

`git rev-parse <rev>…`. Prints the full commit hash for each branch, tag or other name.
Two names that print the same hash point at the same commit.

Example: `git rev-parse fix/server-limits origin/fix/server-limits`. Two identical lines
mean the local branch and the remote copy are in sync, so it's safe to keep working on it.

*First used in 021*

### git reflog: show where HEAD has been

`git reflog [-<n>] [--date=short]`. Lists every commit, checkout and pull that moved `HEAD` in
**this clone**. It's local and is never pushed, so it can show which machine did the work.

- `-<n>`: only the last n entries.
- `--date=short`: show dates instead of `HEAD@{0}` positions.

Example: `git reflog -15 --date=short`

*First used in 016*

### git worktree list: list working folders

`git worktree list`. Shows every folder checked out from this repository and its branch.

*First used in 016*

### git fsck: check the repository and find lost commits

`git fsck [--unreachable] [--no-reflogs]`. Checks the object database. It only reports, and
changes nothing.

- `--unreachable`: list objects that no branch or tag points to, such as a dropped stash.
- `--no-reflogs`: don't count reflog entries as references, so more lost commits show up.

Example: `git fsck --unreachable --no-reflogs`. Stash commits are named `WIP on <branch>`.

*First used in 016*

### git config: read a setting

`git config [--get] <key>`. Prints a setting's value. With a second argument it would change
the setting instead.

Example: `git config user.email`, `git config --get core.autocrlf`

*First used in 016*

### gh api: call the GitHub API

`gh api <endpoint> [--jq <filter>]`. Makes an authenticated GET request to the GitHub REST
API. `gh` fills in the login for you.

- `--jq <filter>`: keep only part of the JSON reply.

Example: `gh api repos/lenasedkiewicz/zr-client-server/branches --jq '.[].name'`

*First used in 016*

## WSL (Linux on Windows)

### wsl.exe: run a command in a Linux distribution

`wsl.exe [-l -q] [-d <distro> -- <command>]`. Runs Linux commands from Windows. Used here
to test POSIX file permissions, which Windows does not have.

- `-l -q`: list installed distributions, names only. `-l -v` adds state and WSL version;
  "has no installed distributions" means WSL itself works but no Linux is installed.
- `-d <distro>`: pick the distribution (e.g. `Ubuntu`).
- `-- <command>`: everything after `--` runs inside Linux; `bash -c '<script>'` runs several
  commands at once.

Windows drives appear under `/mnt/<letter>` (e.g. `/mnt/d/Programming/zr-client-server`),
but they don't keep Linux permissions, so copy the project into the Linux file system
(`/tmp`) before testing modes. Inside WSL Python is `python3`.

Example: `wsl.exe -d Ubuntu -- bash -c 'cd /tmp/zr && python3 -m unittest discover tests'`

PowerShell: the same command (`wsl` without `.exe` also works).

*First used in 004; `-l -v` added in 015*

### umask: show the default permission mask

`umask`. Prints the bits removed from every new file's mode (POSIX shells only). `0022`
means group and others lose write, so `open()` (`0o666`) creates `0o644` files.

PowerShell: no equivalent; Windows uses ACLs.

*First used in 004*

## Shell and files

### mkdir: make a directory

`mkdir [-p] <path>`. Creates a directory.

- `-p`: create missing parent directories; no error if it already exists.

Example: `mkdir -p tests/certs`

PowerShell: `New-Item -ItemType Directory -Force tests/certs`

*First used in 003*

### which: find a command

`which <name>`. Prints where the program that runs as `<name>` lives, or nothing if it is
not on the PATH.

Example: `which openssl` → `/mingw64/bin/openssl` (Git Bash's copy)

PowerShell: `(Get-Command openssl).Source` (errors if not found).

*First used in 003*

### tasklist: list running processes

`tasklist`. Windows command that prints the running processes. It works in PowerShell and in
Git Bash.

Example: `tasklist | grep -i avast`. PowerShell: `Get-Process | Where-Object Name -Match avast`

- `/FI "PID eq <n>"`: only the process with that ID, to check what it is before stopping
  it. In Git Bash write `//FI`: a single `/FI` looks like a path to Git Bash, which rewrites
  it ([MSYS_NO_PATHCONV](#msys_no_pathconv-stop-git-bash-rewriting-paths)). PowerShell and
  cmd take `/FI` as is.

Example (029): `tasklist //FI "PID eq 44316"` → `python.exe 44316 Console …`, the test
server found with [netstat](#netstat--ano-which-process-uses-a-port).

*First used in 016; `/FI` added in 029*

### taskkill: stop a Windows process

`taskkill /PID <n> [/F]`. Stops the process with that ID. ⚠️ `/F` forces it, like
`kill -9`: the process gets no chance to clean up. That's safe for a throwaway process you
started yourself and checked with `tasklist /FI` first; never use it on a PID you haven't
checked.

Example (029, the test server started in a scratch copy): `taskkill //PID 44316 //F`
(Git Bash; `//` for the same reason as `tasklist //FI`).

PowerShell: `Stop-Process -Id 44316 -Force`.

*First used in 029*

### ls: list files

`ls [-R] [-l] <path>`. Lists the files in a directory, or shows one file.

- `-R`: recurse into subdirectories.
- `-l`: long format: permissions, owner, size in bytes and modification time.
- `--time-style=full-iso` (GNU `ls`, as in Git Bash): the full date and time, to the
  fraction of a second, instead of a short date.

Example (030: did a test run write to `users.json`?):
`ls -l --time-style=full-iso users.json` → size 2 (`{}`), last changed 2026-10-08, so no.

PowerShell: `Get-ChildItem` (`-Recurse` for `-R`). For one file's size and time:
`Get-Item users.json | Select-Object Length, LastWriteTime`.

*First used in 001; `-l`, `--time-style` added in 030*

### cd / VAR=value: change directory, set a shell variable

`cd <dir>` makes `<dir>` the current directory for the commands after it. `cmd1 && cmd2`
runs `cmd2` only if `cmd1` succeeded, so `cd <dir> && python …` never runs in the wrong
folder. In Git Bash, Windows drives are `/c/`, `/d/`, …, so `D:\Programming` becomes
`/d/Programming`.

`NAME=value` (no spaces around `=`) stores a value in a shell variable. Read it back with
`"$NAME"`, in quotes so that a path with spaces stays one argument. It lasts only for that
shell session.

Example: `SP="…/scratchpad"` then `cd /d/Programming/zr-client-server && python "$SP/check_cleanup.py"`

PowerShell: `Set-Location D:\Programming\zr-client-server` (alias `cd`). Variables are
`$SP = "…"` and `$SP`. Windows PowerShell 5.1 has no `&&`; use `cmd1; if ($?) { cmd2 }`.

*First used in 012*

### cat: print or append to files

`cat <files>` prints files one after another. `cat >> <file> <<'EOF'` appends the heredoc
text to a file. `cat > <file> <<'EOF'` ⚠️ **overwrites** the file (single `>`), which is
safe for a new scratch file like `"$TEMP/edit.py"`.

- `-A`: show hidden characters: `$` at each line end, `^M` for a Windows `\r`. Useful
  when a text match fails and you suspect line endings or tabs.
- `-n`: number every line, like the editor's gutter, so you can refer to `client.py:84`.
  PowerShell: `Get-Content client.py | ForEach-Object { "{0,4}  {1}" -f $_.ReadCount, $_ }`.

PowerShell: `Get-Content <file>`. To append, use `Add-Content -Encoding utf8 <file> <text>`.
To overwrite, use `Set-Content -Encoding utf8 <file> <text>`.

*First used in 001; `>` added in 002; `-A` added in 003; `-n` added in 025*

### cp: copy files

`cp [-r] <source> <dest>`. Copies a file, or a directory with `-r`.

- `-r`: recurse, copying the directory and everything inside it.

Example: `cp -r /mnt/d/Programming/zr-client-server /tmp/zr` (inside WSL)

PowerShell: `Copy-Item -Recurse <source> <dest>`.

*First used in 004*

### rm: delete files

`rm <file>`. Deletes a file permanently, with no recycle bin. ⚠️ Safe for temporary files
you just created. Never combine `-rf` with a variable that might be empty.

- `-r`: recurse into directories; `-f`: no prompts, no error if missing. ⚠️ `rm -rf`
  deletes a whole tree with no confirmation. Safe only on a fixed, known path you just
  created, like `rm -rf /tmp/zr` in WSL.

Example: `rm "$TEMP/claude_edit2.py"`, `rm -rf /tmp/zr`

PowerShell: `Remove-Item <file>`; ⚠️ `Remove-Item -Recurse -Force <dir>` for `rm -rf`.

*First used in 002; `-rf` added in 004*

### $TEMP: the temp directory

`"$TEMP/<name>"`. In Git Bash on Windows, `$TEMP` points to the user's temp folder, a good
place for throwaway scripts that must not end up in the repo.

PowerShell: `$env:TEMP`.

*First used in 002*

### wc -l: count lines

`wc -l <files>`. Prints the number of lines in each file and a total. Used to see how long
a file is before reading it.

Example: `wc -l client.py tests/test_server.py`

PowerShell: `(Get-Content client.py | Measure-Object -Line).Lines`

*First used in 006*

### file: show a file's type and line endings

`file <files>`. Guesses what a file contains. For text it also reports the line endings:
`with CRLF line terminators` means Windows-style `\r\n`. With `core.autocrlf` git stores
LF and checks out CRLF, so `git diff` stays clean either way.

Example: `file server.py run.py`. In 006 it also caught a Python edit script that had
rewritten a whole LF file as CRLF: on Windows, `open(p, "w")` in text mode writes every
`\n` as `\r\n`, and `git diff --stat` then shows every line changed. Fix: write bytes
(`open(p, "wb")`) or pass `newline="\n"`.

PowerShell: no built-in equivalent. `(Get-Content -Raw server.py) -match "\r\n"` returns
`True` for CRLF.

`file -` reads stdin instead of a file, so you can check an old version without writing it
to disk: `git show HEAD:tests/test_server.py | file -`. `ASCII text` vs `UTF-8 text` tells
you whether a non-ASCII character slipped into the file.

*First used in 006; `-` (stdin) added in 014*

### od -c: show the exact characters in a file

`od -c <file>` ("octal dump", `-c` = as characters). Prints every byte, with escapes for
the invisible ones (`\n`, `\r`, `\t`) and octal codes for non-ASCII bytes. Use it when an
editor or terminal hides what is really in a line.

Example: `sed -n 58p tests/test_server.py | od -c`. In 014 it checked whether a line held
the escape `٢` (six ASCII characters) or the real UTF-8 bytes of `٢`.

PowerShell: `Format-Hex tests/test_server.py` (hex instead of octal; on Windows PowerShell
5.1 it reads the file's bytes, so pass a path rather than piped text).

*First used in 014*

### < file / $?: redirect stdin, read the exit code

`cmd < file` feeds a file to the command's standard input instead of the keyboard.
`< /dev/null` gives it empty input, which simulates "no user at the keyboard". `$?` holds
the exit code of the last command (`0` = success).

Example: `python server.py < /dev/null; echo "exit=$?"`. The server must not wait for an
admin password nobody can type. Gotcha: on Windows `/dev/null` maps to `NUL`, a character
device that `isatty()` reports as a terminal, so the program still prompts and then gets
end of file.

PowerShell: `$null | python server.py; "exit=$LASTEXITCODE"` (`$LASTEXITCODE` holds a
native program's exit code; `$?` is only `True`/`False`).

After a pipe, `$?` is the exit code of the *last* command, so in
`printf 'stop\n' | python client.py | tail -1` it would be `tail`'s. Bash keeps every
stage's code in the array `PIPESTATUS`, counting from 0: `${PIPESTATUS[1]}` is
`python client.py`'s. Read it in the very next command, because the next pipeline
overwrites it. PowerShell: `$LASTEXITCODE` is the last *native* program's code, here also
`tail`'s, so run the client without the pipe to see its code.

`2>/dev/null` goes the other way: it throws away the command's error output (stream 2,
stderr) and keeps normal output. Example: `ls docs/concepts 2>/dev/null` prints nothing
instead of an error if the folder doesn't exist. PowerShell: `2>$null`.

*First used in 006; `2>/dev/null` added in 021; `PIPESTATUS` added in 029*

### head / tail: first or last lines

`head -N` / `tail -N`. Shows the first or last N lines of a file or of piped output.

PowerShell: `Get-Content <file> -TotalCount N` / `-Tail N`. For piped output, use
`Select-Object -First N` / `-Last N`.

*First used in 001*

### grep: search text

`grep [-n] [-v] [-E] [-A N] <pattern> [files]`. Prints lines that match a pattern.

- `-n`: show line numbers.
- `-v`: invert, i.e. print lines that do **not** match.
- `-E`: extended regex, so `(a|b)` works without backslashes.
- `-A N`: also print N lines after each match.
- `-B N`: also print N lines before each match. `-B3 -A25 "<<<<<<<"` shows a conflict block
  with some context.
- `-c`: print only the number of matching lines.
- `-r`: search every file under a directory (recursive).
- `-i`: ignore case.
- `-a`: treat binary input as text. Without it, grep prints only `Binary file (standard input)
  matches` when the input has non-UTF-8 bytes (e.g. Windows error messages in a local
  code page).
- `-o`: print only the part of each line that matched, not the whole line. Combined with
  `-E`, it cuts one field out of noisy output: `grep -a -oE "^ERROR: [a-z_]+"` keeps
  `ERROR: test_name` from unittest's longer failure headers (032).

Example: `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`.
`2>&1` sends stderr, where unittest prints its summary, into the pipe.

PowerShell: `Select-String -Pattern <p>` (`-NotMatch` for `-v`, `-Context 0,N` for `-A N`,
`-Context N,0` for `-B N`, `(… | Measure-Object).Count` for `-c`, and
`(… ).Matches.Value` for `-o`).

In a basic (non `-E`) pattern, `\|` means "or" and `\b` is a word boundary:
`grep -n "\bENCODING\b\|\bjson\b" server.py` finds `json` but not `json_file`. Useful to check
whether an import is still used.

*First used in 001; `-c` added in 003; `-r`, `-i` added in 006 (`grep -rniE "todo|next" README.md docs`); `-a` added in 009; `\|`, `\b` added in 010; `-B N` added in the lifecycle-2 merge; `-o` added in 032*

### cmp -s: are two files identical?

`cmp -s <file1> <file2>`. Compares two files byte by byte. `-s` (silent) prints nothing;
the exit code says it: 0 when identical, 1 when they differ. Faster than `diff` when you
only need yes or no.

Example (032: did the `sed` mutation really change the file?):
`if cmp -s run.py "$S/run.py.orig"; then echo "mutation did not change the file"; fi`.
A `sed` pattern that doesn't match changes nothing and reports no error, so without this
check a "mutation" could run the tests on unchanged code and look like a pass.

PowerShell: `(Get-FileHash run.py).Hash -eq (Get-FileHash $S\run.py.orig).Hash`.

*First used in 032*

### shell function: name a repeated sequence

`name() { command1; command2 "$1"; }`. Defines a function for the rest of this shell
session. Inside it, `$1`, `$2`, … are its arguments, and `return` leaves it early.

Example (032, one mutation per call: restore the original, apply one `sed` edit, check that
it changed something, run the tests):
`mutate() { cp "$S/run.py.orig" run.py; sed -i "$1" run.py; …; python -m unittest …; }`,
then `mutate 's/…ValueError, //' "no ValueError"`. ⚠️ It overwrites `run.py`, so keep the
backup, restore it after the last call, and check with `git diff --quiet -- run.py`.

PowerShell: `function Invoke-Mutation($Edit, $Name) { … }`, using a verb-noun name, so it
can't collide with a built-in alias.

*First used in 032*

### tr: translate characters

`tr <set1> <set2>`. Replaces each character of `set1` in stdin with the matching one in
`set2`.

Example: `… | tr '
' ' '` joins all output lines into one, so each run of a loop prints a
single summary line.

PowerShell: `(… ) -join ' '`.

*First used in 009*

### sed -n: print selected lines

`sed -n '<from>,<to>p' <file>`. Prints only lines `from` to `to`. `-n` turns off the
default "print every line", and `p` prints the selected range.

Example: `sed -n 1,80p tests/test_server.py`

PowerShell: `Get-Content tests/test_server.py | Select-Object -First 80`
(or `-Skip 9 -First 11` for lines 10–20).

*First used in 003*

### awk: print lines between two patterns

`awk '/<start>/{p=1} p{print NR": "$0} /<end>/{p=0}' <file>`. Prints every line from one
that matches `<start>` to one that matches `<end>`. `p` is a flag variable, `NR` is the line
number and `$0` the whole line.

Example: `awk '/^<<<<<<< /{p=1} p{print NR": "$0} /^>>>>>>> /{p=0}' tests/test_server.py`
(show only the conflict regions of a file)

PowerShell: `Select-String -Pattern '^<<<<<<<' -Context 0,20 <file>` shows each match plus
the next 20 lines (no exact range).

*First used in 008*

### cut: keep part of each line

`cut -c<from>-<to>`. Keeps only the given character columns of each line; here, to shorten
long output.

Example: `grep -n "TCP on" README.md | cat -A | cut -c1-140`

PowerShell: `… | ForEach-Object { $_.Substring(0, [Math]::Min(140, $_.Length)) }`.

*First used in 003*

### xargs: turn input lines into arguments

`<list> | xargs [-0] <command>`. Reads names from stdin and runs `<command>` with them as
arguments, for a command that takes arguments rather than reading stdin (here `tar -c`).

- `-0`: names are separated by NUL bytes, from `git ls-files -z` or `find -print0`, so
  spaces in a name are safe.

Example: `git ls-files -z | xargs -0 tar -cf -` (see
[git ls-files](#git-ls-files-list-tracked-files)).

PowerShell: pass the list as an argument instead: `tar -cf $S\copy.tar (git ls-files)`.

*First used in 028*

### diff <(…) <(…): compare two commands' output

`diff <(cmd1) <(cmd2)`. Bash *process substitution*: each `<(…)` runs a command and gives
its output to `diff` as if it were a file. `diff` prints the lines that differ and exits 0
when there are none, so `&& echo yes || echo NO` turns it into a yes/no check.

Example (028, before force-deleting a stale branch): is the old 6.2 commit the same change
as the merged one?
`diff <(git diff e872f44^ e872f44 -- server.py tests/test_server.py) <(git diff 65d08cd^ 65d08cd -- server.py tests/test_server.py) >/dev/null && echo yes || echo NO`.
`<commit>^` is that commit's parent, so `git diff c^ c` is the commit's own change.
`git range-diff` does the same for whole series of commits.

PowerShell has no process substitution: `Compare-Object (git diff e872f44^ e872f44) (git diff 65d08cd^ 65d08cd)`
prints nothing when they match. (`^` needs no quoting in PowerShell; it is special only in
cmd.exe.)

*First used in 028*

### sort / uniq -c: count repeated lines

`… | sort | uniq -c`. `sort` puts identical lines next to each other; `uniq -c` collapses
each run of identical lines into one, prefixed with how many there were. `uniq` alone only
merges *adjacent* duplicates, which is why `sort` comes first.

Example: `python -m unittest tests.test_server 2>&1 | grep -E "^(Ran|OK|FAILED)|AttributeError" | sort | uniq -c`
(36 identical `AttributeError` lines become one line with the count 36)

PowerShell: `… | Group-Object | Select-Object Count, Name`.

*First used in 011*

### printf: print text with escapes

`printf '<format>'`. Like `echo`, but `\n` reliably means a line break on every shell.
Piping it into a program types those lines into its stdin.

Example: `printf 'help\n' | python client.py`. The client reads `help`, then EOF, and
exits.

PowerShell: `"help" | python client.py`.

*First used in 003*

### background process: run without waiting

`(cmd &)`. `&` starts the command in the background, and the subshell `( … )` detaches it
from the current shell. Used to start a server, then talk to it from the same terminal. Stop
it with a command it understands (here `stop`), or `kill <pid>`.

Example: `(python -u server.py > "$TEMP/srv.log" 2>&1 &)`

PowerShell: `Start-Process python -ArgumentList '-u','server.py' -NoNewWindow -RedirectStandardOutput "$env:TEMP\srv.log"`.

*First used in 003*

### for loop / sleep: retry and wait

`for i in 1 2 3; do <cmd> && break; done` runs `<cmd>` up to three times and stops at the
first success (`&&` runs `break` only if `<cmd>` succeeded). `sleep N` pauses for N
seconds.

Example: `for i in 1 2 3 4 5 6 7 8 9 10; do python -c "import socket;socket.create_connection(('127.0.0.1',65432)).close()" 2>/dev/null && break; done`
(wait until the server accepts connections). `2>/dev/null` discards the error messages
from failed attempts.

`seq N` prints the numbers 1 to N, one per line, so `for i in $(seq 10); do <cmd>; done` runs
`<cmd>` ten times. `$(…)` substitutes a command's output. Useful to check whether a test is
flaky: run it many times and compare the results.

Example: `for i in $(seq 10); do python -m unittest tests.test_server.ServerTest.test_client_reset_does_not_stop_server 2>&1 | grep -a -E "^(OK|FAILED)"; done`

PowerShell: `foreach ($i in 1..10) { python -c "…" 2>$null; if ($?) { break } }`,
`Start-Sleep -Seconds 1`.

*First used in 003; `seq` and `$(…)` added in 009*

### timeout: stop a command that runs too long

`timeout <seconds> <command>`. Runs the command and kills it if it hasn't finished after
that many seconds (exit code 124). A guard for anything that might hang, such as a probe
that blocks on `readline()` or a test against a server that just crashed.

Example: `timeout 300 python -m unittest discover tests`

Windows: this is the GNU coreutils `timeout` in Git Bash. `timeout.exe` in cmd/PowerShell
is a different program that only *waits*. In PowerShell use
`$p = Start-Process python -ArgumentList '-m','unittest' -PassThru -NoNewWindow; if (-not $p.WaitForExit(300000)) { $p.Kill() }`.

*First used in 010*

### sed -i: edit a file in place

`sed -i 's/old/new/' <file>`. Replaces text in a file. ⚠️ It overwrites the file with no
backup. It's safe on files tracked by git, because `git diff` shows the change and git can
undo it.

- `-i`: in place (GNU sed, as in Git Bash). macOS/BSD sed needs `-i ''`.
- `s/.../.../`: substitute. Any delimiter works, e.g. `s|a|b|` when the text contains `/`.
  Add `g` (`s/a/b/g`) to replace every match on a line, not just the first.
- `;` joins several commands: `sed -i 's/^id: 001$/id: 007/; s/Step 8/Step 14/g' <file>`.
- `/pattern/d`: delete every line that matches. Anchor it with `^` and `$` so it can't hit
  other lines. Example: `sed -i '/^BUFFER_SIZE = 1024$/d' config.py`.
- `-e <cmd>`: one command per `-e`, the same as joining them with `;`. Example, dropping the
  three conflict-marker lines and keeping both sides:
  `sed -i -e '/^<<<<<<< HEAD$/d' -e '/^=======$/d' -e '/^>>>>>>> origin\/master$/d' docs/dev-journal/README.md`
  (`\/` is a `/` inside a `/…/` pattern). Then `grep -c` for the markers to check that none
  are left.
- `-E`: extended regex, as in [grep -E](#grep-search-text): `( )`, `+`, `?` and `|` work
  without backslashes. Example (032, as a filter): `… | sed -E 's/ \(tests[^)]*\)//'`
  deletes unittest's ` (tests.module.Class.test)` suffix, where `\(` is a literal
  parenthesis.
- ⚠️ In GNU sed's basic regex, `\|` means "or", so `s/a\|b/…/` matches `a` *or* `b`. It is not
  a literal `|`, which needs no backslash. Mixing them up can match an empty string and
  scramble the line, so check the result with `sed -n '<N>p'` and fix it with `git diff`.
  For a long literal line, an exact edit in an editor is safer than a regex.

PowerShell: `(Get-Content f) -replace 'old','new' | Set-Content -Encoding utf8 f`. For `d`:
`(Get-Content f) | Where-Object { $_ -notmatch '^BUFFER_SIZE' } | Set-Content -Encoding utf8 f`.

Without `-i`, `sed 's/old/new/'` is a filter: it edits text flowing through a pipe and
leaves files alone. Example: `git show HEAD:server.py | sed 's/old/new/' > server.py`
(an old version with one line patched, to run new tests against it). ⚠️ `>` overwrites
`server.py`, so back it up first (`cp server.py "$TEMP/server.py.new"`) and restore it
afterwards. PowerShell: `(git show HEAD:server.py) -replace 'old','new' | Set-Content
-Encoding utf8 server.py`.

*First used in 001; filter form added in 005; `g` and `;` added in 008; `/pattern/d` added in 017; `-e` added in the lifecycle-2 merge; `-E` added in 032*

### heredoc: multi-line input to a command

`cmd <<'EOF' … EOF`. Feeds the lines up to `EOF` to the command's stdin. Quoting `'EOF'`
stops the shell from expanding `$vars` inside.

PowerShell: pipe a here-string `@' … '@` into the command.

*First used in 001*
