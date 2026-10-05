# zr-client-server

A simple client/server application communicating over raw TCP sockets, written in pure
Python (standard library only — no frameworks). The server answers every command with JSON.

## Requirements

- Python 3.10+
- No external dependencies (only the standard library: `socket`, `json`, `time`, `datetime`,
  `hashlib`, `hmac`, `secrets`, `getpass`, ...)

## Quick start

Start the server and the client with a single command:

```bash
python run.py
```

The launcher:

- opens the server in a new terminal window (Windows console, macOS Terminal, or the first
  available Linux terminal: `x-terminal-emulator`, `gnome-terminal`, `konsole`, `xterm`),
- waits until the server accepts connections, then runs the client in the current terminal,
- reuses a server that is already running instead of starting a second one,
- falls back to running the server in the background (log in `server.log`) when no terminal
  window can be opened, e.g. over SSH; such a server is stopped when the client exits.

Typing `stop` ends both the server and the client. Leaving the client with Ctrl+C / Ctrl+D
keeps a windowed server running.

## Manual start

Start the server (terminal 1):

```bash
python server.py
```

Start the client (terminal 2):

```bash
python client.py
```

Then type commands at the `>` prompt.

## Commands

| Command  | Description |
|----------|-------------|
| `register <username>` | Creates a user account; the client asks for the password (hidden) |
| `uptime` | Returns how long the server has been running |
| `info`   | Returns the server version and its creation date |
| `help`   | Returns the list of available commands with short descriptions |
| `stop`   | Stops both the server and the client |

## Protocol

- TCP on `127.0.0.1:65432` (configurable in `config.py`), UTF-8 encoding.
- Each message is a single JSON object terminated with a newline (`\n`).

Request:

```json
{"command": "uptime"}
```

Commands that need input send it in an optional `args` object:

```json
{"command": "register", "args": {"username": "alice", "password": "secret123"}}
```

Response (success):

```json
{"status": "ok", "command": "uptime", "data": {"uptime_seconds": 12.34, "uptime": "0:00:12"}}
```

Response (error):

```json
{"status": "error", "message": "Unknown command: foo"}
```

## User accounts

Accounts are stored in `users.json` (git-ignored) next to the server. Passwords are never
saved: each user gets a random salt and the file keeps a PBKDF2-HMAC-SHA256 hash
(600,000 iterations). Usernames are 3–32 letters, digits or `_`; passwords need at least
8 characters.

Note: there is no TLS, so passwords travel over the socket unencrypted. That is fine on
`127.0.0.1`, but not on a real network.

## Project structure

```
zr-client-server/
├── server.py      # TCP server
├── client.py      # interactive TCP client
├── run.py         # launcher: starts server + client together
├── config.py      # shared configuration (host, port, version, ...)
├── protocol.py    # send/receive JSON message helpers
├── users.py       # user accounts with salted password hashes
├── tests/
│   └── test_server.py
├── docs/
│   ├── dev-journal/   # one learning entry per commit
│   ├── concepts/      # concept notes from questions asked while building
│   └── commands.md    # every shell command used, explained once
├── PLAN.md
└── README.md
```

## Tests

```bash
python -m unittest discover tests
```
