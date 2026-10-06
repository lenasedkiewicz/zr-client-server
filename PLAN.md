# Plan: Python socket client/server (no frameworks)

## Context
`D:\Programming\zr-client-server` is empty (not a git repo; Python 3.13.1 available).
The task (Polish requirements): build a client/server app over raw sockets, **no frameworks**
(standard library only: `socket`, `json`, `time`, `datetime`). The server handles commands and
answers in JSON:

| Command  | Response |
|----------|----------|
| `uptime` | server lifetime (time since start) |
| `info`   | server version + server creation date |
| `help`   | list of available commands with short descriptions |
| `stop`   | stops **both** server and client |

The user asked for this plan to be saved in the project folder, plus an initial `README.md`
and `.gitignore`.

## Step 1 — files to create right after approval
- `PLAN.md` — copy of this plan in the project folder.
- `README.md` — project description, requirements (Python 3.10+, stdlib only), how to run
  server and client, command table, protocol description, project structure.
- `.gitignore` — standard Python: `__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `env/`,
  `.pytest_cache/`, `.coverage`, `htmlcov/`, `*.log`, `.idea/`, `.vscode/`, `.DS_Store`, `Thumbs.db`.

## Step 2 — project structure
```
zr-client-server/
├── server.py      # TCP server
├── client.py      # interactive TCP client
├── run.py         # launcher: starts server + client together (step 7)
├── config.py      # HOST, PORT, BUFFER_SIZE, ENCODING, SERVER_VERSION, SERVER_CREATED
├── protocol.py    # send_message / receive_message helpers (shared by both sides)
├── users.py       # UserStore: accounts with salted PBKDF2 hashes in users.json (steps 8–9)
├── tests/
│   └── test_server.py   # unittest (stdlib) end-to-end tests
├── PLAN.md
├── README.md
└── .gitignore
```

## Step 3 — protocol (`protocol.py`)
- TCP, `127.0.0.1:65432` (in `config.py`), UTF-8.
- Every message is one JSON object terminated with `\n` (newline-delimited JSON) — solves
  TCP message framing without any library.
- Request: `{"command": "uptime"}`
- Response: `{"status": "ok", "command": "uptime", "data": {...}}` or
  `{"status": "error", "message": "Unknown command: foo"}`.
- Helpers: `send_message(sock, dict)` and `receive_message(sock_file) -> dict | None`
  (reads one line via `sock.makefile("r")`, returns `None` on closed connection).

## Step 4 — server (`server.py`)
- Class `Server` storing `start_time = time.time()` at startup.
- `socket.socket(AF_INET, SOCK_STREAM)`, `SO_REUSEADDR`, `bind`, `listen`, accept loop
  (one client at a time — simple and sufficient for the spec).
- Command dispatch via a dict `{name: (handler, description)}` — `help` is generated from
  this same dict, so it always lists exactly the implemented commands.
- Handlers:
  - `uptime` → `{"uptime_seconds": 12.34, "uptime": "0:00:12"}`
  - `info` → `{"version": "1.0.0", "created": "2026-10-01"}`
  - `help` → `{"uptime": "...", "info": "...", "help": "...", "stop": "..."}`
  - `stop` → sends `{"status":"ok","command":"stop","data":{"message":"Server stopping"}}`,
    then closes the connection and the listening socket and exits the loop.
- Invalid JSON / unknown command → error response, connection stays open.
- Client disconnect → server goes back to `accept()`.
- `Ctrl+C` handled gracefully (close socket).

## Step 5 — client (`client.py`)
- Connects to the server, input loop: `> ` prompt, sends the typed command, pretty-prints the
  JSON reply (`json.dumps(..., indent=2)`).
- On `stop` response (or when server closes the connection) the client prints a message and
  exits → satisfies "stops server and client simultaneously".
- Handles `ConnectionRefusedError` (server not running) and `Ctrl+C` / EOF.

## Step 6 — tests (`tests/test_server.py`, stdlib `unittest`)
- Start server in a background thread on a free port; connect a raw socket;
  assert JSON for `uptime`, `info`, `help` (keys == set of commands), unknown command → error,
  `stop` → server thread terminates.

## Step 7 — launcher (`run.py`)
Starts the server and then the client with a single command: `python run.py`.
Written in Python (stdlib `subprocess`, `socket`, `sys`, `time`, `shutil`) so it works the
same on every OS, unlike separate `.bat` / `.sh` scripts.

- **Server already running?** Try to connect to `HOST:PORT` first. If it succeeds, skip
  starting a new server (avoids "address already in use") and go straight to the client.
- **Start the server in its own terminal window**, so its log stays separate from the
  client prompt:
  - Windows: `subprocess.Popen([sys.executable, "server.py"], creationflags=CREATE_NEW_CONSOLE)`.
  - macOS: `osascript` telling Terminal to run `python server.py` in the project folder.
  - Linux: the first available of `x-terminal-emulator`, `gnome-terminal`, `konsole`,
    `xterm` (found with `shutil.which`).
  - No terminal available (e.g. SSH session): start the server as a background process in
    the same terminal, with its output going to `server.log`.
- **Wait until the server is ready**: try to connect every 0.1 s, give up after ~5 s with a
  clear error. This is better than a fixed `sleep`.
- **Run the client in the current terminal** (`subprocess.run([sys.executable, "client.py"])`),
  so the user types commands where they ran `run.py`.
- **Shutdown**: `stop` already ends both processes, and the server window closes with them.
  If the user leaves the client in another way (Ctrl+C / EOF), the launcher leaves the
  server running and prints how to stop it. Only a server started in the background is
  stopped by the launcher, because it has no window of its own.
- Use `sys.executable` and paths relative to `run.py`, so it works from any working
  directory and inside a virtualenv.
- README: add a "Quick start" section with `python run.py`; keep the two-terminal
  instructions as the manual alternative.
- Tests: none automated (opening windows can't be tested reliably); check by hand on
  Windows (see Verification).

## Step 8 — user accounts: register
Lets a user create an account with a password, as groundwork for login (step 9).

- **Protocol:** requests may carry an optional `"args"` object, e.g.
  `{"command": "register", "args": {"username": "alice", "password": "..."}}`.
  Every handler receives `args`; a handler raising `ValueError` becomes an error response.
- **`users.py` — `UserStore`:** keeps accounts in `users.json` (path in `config.py`,
  git-ignored). Passwords are never stored: each user gets a random 16-byte salt
  (`secrets`) and the file keeps `hashlib.pbkdf2_hmac("sha256", ...)` with 600,000
  iterations (OWASP), stored per user so the default can be raised later. Checks use
  `hmac.compare_digest`. Writes go to a temp file swapped in with `os.replace`.
- **Validation:** username 3–32 characters `[A-Za-z0-9_]`, password at least 8 characters,
  usernames must be unique.
- **Client:** `register <username>` asks for the password twice with `getpass` (not echoed).
- **Server:** `Server(users=...)` accepts a `UserStore`, so tests use a temp file and fewer
  iterations.
- **Known limitation:** passwords cross the socket in plain text (no TLS) — acceptable for
  localhost; production would wrap the socket with `ssl`.

## Step 9 — login and access control
Every command except `help`, `register` and `login` requires a logged-in user.

- **Commands:** `login <username>` (client asks for the password with `getpass`) and
  `logout`. `login` while logged in → error "Already logged in as …, logout first".
- **Dispatch dict:** entries become `(handler, description, requires_login)`. The check
  lives in one place, `handle_request`, so a new command cannot forget it; a protected
  command without a login → `{"status": "error", "message": "Login required: ..."}`.
- **`help`** is generated from the same dict, filtered: logged out → only `help`,
  `register`, `login`; logged in → every command.
- **Session per connection:** `handle_client` creates `session = {"user": None}` and passes
  it to every handler, so closing the connection logs the user out. No tokens are needed
  because TCP keeps the connection open (unlike stateless HTTP).
- **No username enumeration:** unknown user and wrong password give the same message, and
  `verify_password` runs a dummy hash for unknown users so response times match.
- **Client:** the prompt shows the logged-in user (`alice> `).
- **Next hardening (not built):** rate limiting / lockout after failed logins, TLS.

## Verification
1. `python server.py` in terminal 1, `python client.py` in terminal 2.
2. Type `help`, `info`, `uptime` (twice — value grows), `foo` (error) → check JSON output.
3. Type `stop` → both processes exit cleanly.
4. `python -m unittest discover tests` → all pass.
5. `python run.py` → a server window opens and the client prompt appears in the current
   terminal; `stop` closes both. Run `python run.py` again while a server is already
   running → it reuses that server instead of starting a second one.
6. In the client: `register alice` → password prompts do not echo what you type; a
   mismatch is rejected locally; `register alice` again → "User already exists";
   `users.json` contains a salt and hash, not the password.
7. Logged out: `help` lists only `help`, `register`, `login`; `uptime` → "Login required".
   `login alice` with a wrong password → "Invalid username or password"; with the right
   one → prompt becomes `alice> ` and `help` lists every command. `logout` → back to `> `.

## Assumptions (adjustable)
- Code, comments, README and messages in English.
- Single client at a time (spec does not require concurrency).
- `git init` is not run unless requested.
