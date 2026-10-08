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

### cat: print or append to files

`cat <files>` prints files one after another. `cat >> <file> <<'EOF'` appends the heredoc
text to a file. `cat > <file> <<'EOF'` ⚠️ **overwrites** the file (single `>`), which is
safe for a new scratch file like `"$TEMP/edit.py"`.

- `-A`: show hidden characters: `$` at each line end, `^M` for a Windows `\r`. Useful
  when a text match fails and you suspect line endings or tabs.

PowerShell: `Get-Content <file>`. To append, use `Add-Content -Encoding utf8 <file> <text>`.
To overwrite, use `Set-Content -Encoding utf8 <file> <text>`.

*First used in 001; `>` added in 002; `-A` added in 003*

### rm: delete files

`rm <file>`. Deletes a file permanently, with no recycle bin. ⚠️ Safe for temporary files
you just created. Never combine `-rf` with a variable that might be empty.

Example: `rm "$TEMP/claude_edit2.py"`

PowerShell: `Remove-Item <file>`.

*First used in 002*

### $TEMP: the temp directory

`"$TEMP/<name>"`. In Git Bash on Windows, `$TEMP` points to the user's temp folder, a good
place for throwaway scripts that must not end up in the repo.

PowerShell: `$env:TEMP`.

*First used in 002*

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

Example: `python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"`.
`2>&1` sends stderr, where unittest prints its summary, into the pipe.

PowerShell: `Select-String -Pattern <p>` (`-NotMatch` for `-v`, `-Context 0,N` for `-A N`,
`(… | Measure-Object).Count` for `-c`).

*First used in 001; `-c` added in 003*

### sed -n: print selected lines

`sed -n '<from>,<to>p' <file>`. Prints only lines `from` to `to`. `-n` turns off the
default "print every line", and `p` prints the selected range.

Example: `sed -n 1,80p tests/test_server.py`

PowerShell: `Get-Content tests/test_server.py | Select-Object -First 80`
(or `-Skip 9 -First 11` for lines 10–20).

*First used in 003*

### cut: keep part of each line

`cut -c<from>-<to>`. Keeps only the given character columns of each line; here, to shorten
long output.

Example: `grep -n "TCP on" README.md | cat -A | cut -c1-140`

PowerShell: `… | ForEach-Object { $_.Substring(0, [Math]::Min(140, $_.Length)) }`.

*First used in 003*

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

PowerShell: `foreach ($i in 1..10) { python -c "…" 2>$null; if ($?) { break } }`,
`Start-Sleep -Seconds 1`.

*First used in 003*

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
