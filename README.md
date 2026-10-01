# zr-client-server

A simple client/server application communicating over raw TCP sockets, written in pure
Python (standard library only — no frameworks). The server answers every command with JSON.

> Status: work in progress — see [PLAN.md](PLAN.md) for the implementation plan.

## Requirements

- Python 3.10+
- No external dependencies (`socket`, `json`, `time`, `datetime` from the standard library)

## Usage

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

Response (success):

```json
{"status": "ok", "command": "uptime", "data": {"uptime_seconds": 12.34, "uptime": "0:00:12"}}
```

Response (error):

```json
{"status": "error", "message": "Unknown command: foo"}
```

## Project structure

```
zr-client-server/
├── server.py      # TCP server
├── client.py      # interactive TCP client
├── config.py      # shared configuration (host, port, version, ...)
├── protocol.py    # send/receive JSON message helpers
├── tests/
│   └── test_server.py
├── PLAN.md
└── README.md
```

## Tests

```bash
python -m unittest discover tests
```
