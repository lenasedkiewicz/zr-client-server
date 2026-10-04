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

## Shell and files
