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

Example: `python -m unittest discover tests`

*First used in 001*

### python -c: run a one-line program

`python -c "<code>"`. Runs the code given as a string. Useful for a quick check of one
function without writing a file.

Example: `python -c "import client; print(client.build_request('info'))"`

PowerShell: the same command. Use double quotes outside and single quotes inside.

*First used in 001*

### python -: run a script from stdin

`python - <<'EOF' … EOF`. `-` tells Python to read the program from standard input, and
the [heredoc](#heredoc-multi-line-input-to-a-command) supplies it. Handy for a throwaway
script that edits files.

Gotcha: inside a normal (non-raw) Python string, `\n` is a real line break. To write the
two characters `\n` into a target file, write `\\n` in the script.

PowerShell: pipe a here-string instead: `@'<code>'@ | python -`.

*First used in 001*

## Git

### git diff: show unstaged changes

`git diff [--stat] [<path>]`. Shows what changed in the working tree since the last
commit or `git add`.

- `--stat`: show only a per-file summary of added and removed lines.
- `<path>`: limit the diff to one file.

Example: `git diff --stat`, `git diff server.py`

*First used in 001*

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

## Shell and files

### ls: list files

`ls [-R]`. Lists the files in a directory.

- `-R`: recurse into subdirectories.

PowerShell: `Get-ChildItem` (`-Recurse` for `-R`).

*First used in 001*

### cat: print or append to files

`cat <files>` prints files one after another. `cat >> <file> <<'EOF'` appends the heredoc
text to a file.

PowerShell: `Get-Content <file>`. To append, use `Add-Content -Encoding utf8 <file> <text>`.

*First used in 001*

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

Example: `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`.
`2>&1` sends stderr, where unittest prints its summary, into the pipe.

PowerShell: `Select-String -Pattern <p>` (`-NotMatch` for `-v`, `-Context 0,N` for `-A N`).

*First used in 001*

### sed -i: edit a file in place

`sed -i 's/old/new/' <file>`. Replaces text in a file. ⚠️ It overwrites the file with no
backup. It's safe on files tracked by git, because `git diff` shows the change and git can
undo it.

PowerShell: `(Get-Content f) -replace 'old','new' | Set-Content -Encoding utf8 f`.

*First used in 001*

### heredoc: multi-line input to a command

`cmd <<'EOF' … EOF`. Feeds the lines up to `EOF` to the command's stdin. Quoting `'EOF'`
stops the shell from expanding `$vars` inside.

PowerShell: pipe a here-string `@' … '@` into the command.

*First used in 001*
