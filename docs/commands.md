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
- `-v`: verbose; print each test name with `ok`, `FAIL` or `skipped '<reason>'`.

Example: `python -m unittest discover tests`,
`python -m unittest -v tests.test_server.ServerTest.test_users_file_is_owner_only`

*First used in 001; single test and `-v` added in 004*

### python -c: run a one-line program

`python -c "<code>"`. Runs the code given as a string. Useful for a quick check of one
function without writing a file.

Example: `python -c "import client; print(client.build_request('info'))"`

PowerShell: the same command. Use double quotes outside and single quotes inside.

*First used in 001*

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

## Git

### git diff: show unstaged changes

`git diff [--stat] [<commit> [<commit>]] [-- <path>]`. With no commit, shows what changed in
the working tree since the last `git add`; with one, compares the working tree with that
commit; with two, compares the two commits.

- `--stat`: show only a per-file summary of added and removed lines.
- `-- <path>`: limit the diff to one file; `--` separates revisions from file names.

Example: `git diff --stat`, `git diff server.py`, `git diff feature/admin -- .gitignore` (no
output means the file is identical on both sides, so a merge will not conflict there)

Git Bash: a revision containing `/` followed by `:path` (e.g. `feature/admin:.gitignore`) can
be mangled by MSYS path conversion; the `<commit> -- <path>` form avoids it.

During a merge, `git diff` with no arguments shows only the conflicted files, in a
"combined" format with two `+`/`-` columns (one per parent).

*First used in 001; commit and `--` forms added in 007; merge view added in 008*

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
  (what the planning commit touched). `HEAD~1` is the commit before `HEAD`.

*First used in 004; `--stat` added in 010*

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

PowerShell: the same; use `| Select-Object -First 15` instead of `head`.

*First used in 005; `a..b` added in 008*

### git branch --show-current: print the current branch

`git branch --show-current`. Prints the name of the checked-out branch (nothing on a
detached HEAD). Without the flag, `git branch` lists local branches with `*` on the current
one, and `-a` adds the remote-tracking ones (`remotes/origin/...`).

Example: checking that a change goes onto `master` before editing; `git branch -a` after a
fetch to see `origin/feature/admin`.

*First used in 007; `-a` added in 008*

### git fetch: download new commits from the remote

`git fetch --all --prune`. Downloads commits and branches from the remote into the
remote-tracking branches (`origin/master`, ...) without touching your own branches or files.

- `--all`: fetch every configured remote, not just `origin`.
- `--prune`: delete remote-tracking branches whose branch was deleted on the remote.

Example: `git fetch --all --prune` before merging, so `origin/master` is current.

*First used in 008*

### git pull: fetch and update the current branch

`git pull [--ff-only]`. Runs `git fetch`, then joins the remote branch into the current
one. Plain `git pull` may create a merge commit (or rebase, depending on config) when
your branch and the remote have diverged.

- `--ff-only`: only fast-forward, i.e. move your branch pointer forward to the remote's
  commit. If the branches have diverged, git refuses and changes nothing, so a pull never
  creates a surprise merge commit.

Example: `git pull --ff-only` on `master` before branching for a new fix batch.

*First used in the step 16 plan commit (`docs:` commit, no journal entry)*

### git checkout: switch branches

`git checkout <branch>`. Switches the working tree to another branch. Git refuses if
uncommitted changes would be overwritten. Newer git also has `git switch <branch>`, which
does only this.

- `-b <new-branch>`: create the branch at the current commit and switch to it
  (`git switch -c <new-branch>` in newer git).

Example: `git checkout feature/admin`; `git checkout -b fix/server-survives-bad-client`

*First used in 008; `-b` added in the step 16 plan commit*

### git merge: join another branch into the current one

`git merge [--no-edit] <branch>`. Brings the other branch's commits into the current branch
and records a merge commit with two parents. On conflicts it stops: fix each file, `git add`
it, then `git commit` finishes the merge.

- `--no-edit`: accept git's default message instead of opening an editor.
- `--abort`: give up and return to the state before the merge. ⚠️ Discards the conflict
  resolutions you have made so far; safe when you want to start the merge over.

Conflict markers in a file: `<<<<<<< HEAD` (your branch), `=======`, `>>>>>>> <branch>`
(theirs). Remove all three and keep the right mix of both sides.

Example: `git merge origin/master --no-edit` (on `feature/admin`, to update PR #1)

*First used in 008*

### git merge-base: find the common ancestor

`git merge-base <a> <b>`. Prints the commit where two branches split. A merge compares both
sides against this commit.

Example: `git merge-base origin/master origin/feature/admin` → `3eafafb…`

*First used in 008*

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

Example: `git push origin feature/admin` (updates PR #1)

*First used in 008*

### gh pr view: show a pull request

`gh pr view <number> [--json <fields>]`. GitHub CLI: prints a pull request's details.

- `--json headRefName,baseRefName,mergeable,title`: print only those fields as JSON;
  `mergeable` is `CONFLICTING` when GitHub cannot merge it automatically.

Example: `gh pr view 1 --json headRefName,baseRefName,mergeable,title`

*First used in 008*

### gh pr list: list pull requests

`gh pr list [--head <branch>] [--state open|closed|merged|all]`. GitHub CLI: lists pull
requests; by default only open ones.

- `--head <branch>`: only PRs opened from this branch. Empty output means it has no open PR.

Example: `gh pr list --head fix/server-survives-bad-client`

*First used in 011*

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

*First used in 008*

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

*First used in 005; `-sb` and merge codes added in 008*

### git stash: put changes aside for a moment

`git stash [push] [-q] [-- <path>…]` / `git stash pop [-q]`. Saves uncommitted changes on a
stack and resets the files to the last commit; `pop` puts them back and drops the entry.

- `-- <path>`: stash only these files and leave the others changed. Used here to undo just
  the fix in `server.py` while keeping the new tests, to prove the tests fail without it.
- `-q`: quiet, no summary output.

Example: `git stash -q -- server.py && python -m unittest tests.test_server; git stash pop -q`

If `pop` hits a conflict, the entry stays on the stack (`git stash list`) and nothing is
lost. Resolve the conflict, then `git stash drop`.

*First used in 011*

## WSL (Linux on Windows)

### wsl.exe: run a command in a Linux distribution

`wsl.exe [-l -q] [-d <distro> -- <command>]`. Runs Linux commands from Windows. Used here
to test POSIX file permissions, which Windows does not have.

- `-l -q`: list installed distributions, names only.
- `-d <distro>`: pick the distribution (e.g. `Ubuntu`).
- `-- <command>`: everything after `--` runs inside Linux; `bash -c '<script>'` runs several
  commands at once.

Windows drives appear under `/mnt/<letter>` (e.g. `/mnt/d/Programming/zr-client-server`),
but they don't keep Linux permissions, so copy the project into the Linux file system
(`/tmp`) before testing modes. Inside WSL Python is `python3`.

Example: `wsl.exe -d Ubuntu -- bash -c 'cd /tmp/zr && python3 -m unittest discover tests'`

PowerShell: the same command (`wsl` without `.exe` also works).

*First used in 004*

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

### ls: list files

`ls [-R]`. Lists the files in a directory.

- `-R`: recurse into subdirectories.

PowerShell: `Get-ChildItem` (`-Recurse` for `-R`).

*First used in 001*

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

PowerShell: `Get-Content <file>`. To append, use `Add-Content -Encoding utf8 <file> <text>`.
To overwrite, use `Set-Content -Encoding utf8 <file> <text>`.

*First used in 001; `>` added in 002; `-A` added in 003*

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

*First used in 006*

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

*First used in 006*

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
- `-c`: print only the number of matching lines.
- `-r`: search every file under a directory (recursive).
- `-i`: ignore case.
- `-a`: treat binary input as text. Without it, grep prints only `Binary file (standard input)
  matches` when the input has non-UTF-8 bytes (e.g. Windows error messages in a local
  code page).

Example: `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`.
`2>&1` sends stderr, where unittest prints its summary, into the pipe.

PowerShell: `Select-String -Pattern <p>` (`-NotMatch` for `-v`, `-Context 0,N` for `-A N`,
`(… | Measure-Object).Count` for `-c`).

In a basic (non `-E`) pattern, `\|` means "or" and `\b` is a word boundary:
`grep -n "\bENCODING\b\|\bjson\b" server.py` finds `json` but not `json_file`. Useful to check
whether an import is still used.

*First used in 001; `-c` added in 003; `-r`, `-i` added in 006 (`grep -rniE "todo|next" README.md docs`); `-a` added in 009; `\|`, `\b` added in 010*

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

PowerShell: `(Get-Content f) -replace 'old','new' | Set-Content -Encoding utf8 f`.

Without `-i`, `sed 's/old/new/'` is a filter: it edits text flowing through a pipe and
leaves files alone. Example: `git show HEAD:server.py | sed 's/old/new/' > server.py`
(an old version with one line patched, to run new tests against it). ⚠️ `>` overwrites
`server.py`, so back it up first (`cp server.py "$TEMP/server.py.new"`) and restore it
afterwards. PowerShell: `(git show HEAD:server.py) -replace 'old','new' | Set-Content
-Encoding utf8 server.py`.

*First used in 001; filter form added in 005; `g` and `;` added in 008*

### heredoc: multi-line input to a command

`cmd <<'EOF' … EOF`. Feeds the lines up to `EOF` to the command's stdin. Quoting `'EOF'`
stops the shell from expanding `$vars` inside.

PowerShell: pipe a here-string `@' … '@` into the command.

*First used in 001*
