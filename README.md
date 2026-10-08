# zr-client-server

A simple client/server application communicating over raw TCP sockets encrypted with TLS,
written in pure Python (standard library only — no frameworks). The server answers every
command with JSON.

## Requirements

- Python 3.10+
- No external dependencies (only the standard library: `socket`, `ssl`, `json`, `time`,
  `datetime`, `hashlib`, `hmac`, `secrets`, `getpass`, ...)
- The OpenSSL command-line tool, used once to create the TLS certificate (bundled with Git
  for Windows; preinstalled on most macOS and Linux systems)

## Setup

Create a self-signed certificate and private key once, in the project folder. In Git Bash
(on Windows `openssl` is not on the PowerShell PATH):

```bash
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -keyout server.key -out server.crt -days 365 -subj "/CN=localhost" -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
```

`server.key` is secret and git-ignored. The server refuses to start without the pair, and
the client refuses to connect without `server.crt`. It trusts only that certificate. Run
the command again when it expires after 365 days.

## Quick start

After the one-time [Setup](#setup), start the server and the client with a single command:

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

## First use

A new connection is logged out. Create an account once, then log in:

```
> register alice
Password:
Repeat password:
> login alice
Password:
alice> uptime
```

Passwords are typed without being shown. Until you log in, only `help`, `register` and
`login` work, and `help` lists just those. Closing the client logs you out.

## Commands

| Command  | Login required | Description |
|----------|----------------|-------------|
| `register <username>` | no | Creates a user account; the client asks for the password (hidden) |
| `login <username>` | no | Logs in; the client asks for the password (hidden) |
| `help`   | no  | Lists the commands you can use now (only the three above when logged out) |
| `logout` | yes | Logs out of the current account |
| `uptime` | yes | Returns how long the server has been running |
| `info`   | yes | Returns the server version and its creation date |
| `stop`   | yes | Stops both the server and the client |

## Protocol

- TLS (1.2 or newer) over TCP on `127.0.0.1:65432` (configurable in `config.py`), UTF-8
  encoding. A client that does not finish the TLS handshake within 5 seconds is dropped.
- Inside TLS, each message is a single JSON object terminated with a newline (`\n`).

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

Response (protected command while logged out):

```json
{"status": "error", "command": "uptime", "message": "Login required: use 'login <username>' or 'register <username>'"}
```

## User accounts

Accounts are stored in `users.json` (git-ignored) next to the server. Passwords are never
saved: each user gets a random salt and the file keeps a PBKDF2-HMAC-SHA256 hash
(600,000 iterations). Usernames are 3–32 letters, digits or `_`; passwords need at least
8 characters.

The login belongs to the connection: the server keeps `{"user": ...}` for each connected
client and forgets it when the client disconnects. A wrong password and an unknown username
get the same error, so the server does not reveal which accounts exist.

Passwords travel inside the TLS connection, so a packet capture sees only ciphertext.

## Project structure

```
zr-client-server/
├── server.py      # TLS server
├── client.py      # interactive TLS client
├── run.py         # launcher: starts server + client together
├── config.py      # shared configuration (host, port, version, ...)
├── protocol.py    # send/receive JSON message helpers
├── users.py       # user accounts with salted password hashes
├── tests/
│   ├── certs/         # test-only certificates (never use them elsewhere)
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
