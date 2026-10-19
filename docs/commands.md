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

## Git

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
