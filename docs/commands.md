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

### python -m unittest discover: run the test suite

`python -m unittest discover [<start_dir>]`. Finds `test*.py` files under the directory
and runs every `TestCase` in them.

- `-m unittest`: run the stdlib `unittest` module as a script.
- `discover tests`: start the search in `tests/` (it needs an `__init__.py`).

Example: `python -m unittest discover tests`

Windows: the command is `python` (or the `py` launcher); `python3` usually doesn't exist.

*First used in 001*

### python -c: run a one-line program

`python -c "<code>"`. Runs the code passed as a string. Useful for quick checks without
creating a file.

Example: `python -c "from tests.test_server import SEMVER; print(bool(SEMVER.match('0.1-alpha')))"`

PowerShell: wrap the code in single quotes (`'...'`) so PowerShell doesn't expand `$`.

*First used in 001*

### python - with a heredoc: run a multi-line script from stdin

`python - <<'EOF' ... EOF`. `-` tells Python to read the program from standard input, and the
heredoc supplies it. This is a one-off script that leaves no file behind.

Example: inserting `test_version_is_semver` and Step 8 into their files.

PowerShell: there are no heredocs. Pipe a here-string instead:
`@'` (newline) code (newline) `'@ | python -`

*First used in 001*

## Git

### git branch --show-current: print the current branch

`git branch --show-current`. Prints the name of the checked-out branch (nothing on a detached HEAD).

Example: checking that the change goes onto `master` before editing.

*First used in 001*

### git status: show what changed in the working tree

`git status [--short]`. Lists modified, staged and untracked files.

- `--short`: one line per file with a two-letter code (`M ` staged, ` M` modified,
  `??` untracked).

Example: `git status --short` (checks that `server.key` no longer shows as `??` once ignored)

*First used in commit "chore: ignore TLS key, certificate and users file"*

### git diff: show differences between versions

`git diff [<commit>] [<commit>] [-- <path>]`. With no commit, compares the working tree with
the index; with one, the working tree with that commit; with two, the two commits.

- `-- <path>`: limit the diff to that path; `--` separates revisions from file names.
- `--stat`: show only a per-file summary (lines added/removed) instead of the full diff.
  *First used in 001*

Example: `git diff feature/admin -- .gitignore` (no output means the file is identical on
both sides, so a later merge will not conflict there)

Git Bash: a revision containing `/` followed by `:path` (e.g. `feature/admin:.gitignore`) can
be mangled by MSYS path conversion; the `<commit> -- <path>` form avoids it.

*First used in commit "chore: ignore TLS key, certificate and users file"*

### git add: stage changes for the next commit

`git add <path>...`. Copies the current content of the files into the index (staging area).

Example: `git add .gitignore docs/commands.md`

*First used in commit "chore: ignore TLS key, certificate and users file"*

### git commit: record staged changes

`git commit -m <message>`. Creates a commit from the index.

- `-m <message>`: the message; give it several times for separate paragraphs (subject, body,
  trailers such as `Co-Authored-By:`).

Example: `git commit -m "chore: ignore TLS key, certificate and users file" -m "Co-Authored-By: ..."`

*First used in commit "chore: ignore TLS key, certificate and users file"*

## Shell and files

### cat >> with a heredoc: append lines to a file

`cat >> <file> <<'EOF' ... EOF`. Appends the lines between the markers to the file
(`>>` appends, `>` would overwrite ⚠️). Quoting `'EOF'` stops the shell from expanding `$` or
backticks inside.

Example: appending the ignore rules to `.gitignore`

PowerShell: `Add-Content -Encoding utf8 .gitignore "users.json"` (one call per line, or pass
an array of lines)

*First used in commit "chore: ignore TLS key, certificate and users file"*

### sed -i: edit a file in place

`sed -i 's/<old>/<new>/' <file>`. Replaces the first match of `<old>` on each line and writes
the result back to the file. ⚠️ No backup is kept, so run it on files under git, where
`git diff` shows the change and `git restore <file>` undoes it.

- `-i`: in place (GNU sed, as in Git Bash). macOS/BSD sed needs `-i ''`.
- `s/.../.../`: substitute. Any delimiter works, e.g. `s|a|b|` when the text contains `/`.

Example: `sed -i 's/^SERVER_VERSION = "1.0.0"/SERVER_VERSION = "0.1.0-alpha"/' config.py`

PowerShell: `(Get-Content config.py) -replace '"1\.0\.0"', '"0.1.0-alpha"' | Set-Content -Encoding utf8 config.py`

*First used in 001*

### grep: search text for a pattern

`grep [-n] [-E] <pattern> [<file>...]`. Prints the lines that match.

- `-n`: prefix each line with its line number.
- `-E`: extended regex, so `|` and `( )` work without backslashes.

Example: `grep -n "test_version_is_semver" tests/test_server.py`;
`python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"` keeps only the test
summary (`2>&1` sends stderr, where unittest writes, into the pipe).

PowerShell: `Select-String -Pattern "test_version_is_semver" tests/test_server.py`

*First used in 001*

### cat / head / tail: print files

`cat <file>...` prints whole files. `head -n N` / `tail -n N` print the first or last N lines;
piping into `| head -70` trims long output.

Example: `cat docs/concepts/README.md`, `tail -n 2 docs/dev-journal/README.md`

PowerShell: `Get-Content <file>`, `Get-Content <file> -TotalCount N`, `Get-Content <file> -Tail N`

*First used in 001*

