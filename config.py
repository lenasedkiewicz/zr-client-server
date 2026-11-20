"""Shared configuration for the server and the client."""

HOST = "127.0.0.1"
PORT = 65432
ENCODING = "utf-8"
# Longest message the server reads, in bytes of the decrypted line, not counting its "\n".
# Far above any real request (register is a few hundred bytes). A longer line closes the
# connection, so a client can't make the server buffer without bound.
MAX_MESSAGE_SIZE = 64 * 1024

SERVER_VERSION = "0.1.1-alpha"
SERVER_CREATED = "2026-10-01"

# User accounts
USERS_FILE = "users.json"
USERS_FILE_MODE = 0o600  # owner read/write only: the file holds password hashes
# OWASP (2023) recommends at least 600,000 iterations for PBKDF2-HMAC-SHA256.
PBKDF2_ITERATIONS = 600_000
USERNAME_PATTERN = r"[A-Za-z0-9_]{3,32}"
MIN_PASSWORD_LENGTH = 8
# Account roles; a record without "role" (created before step 13) is a regular user.
ROLE_USER = "user"
ROLE_ADMIN = "admin"
# Failed logins per username before a temporary lockout, and how long it lasts.
MAX_FAILED_LOGINS = 5
LOGIN_LOCKOUT_SECONDS = 60

# TLS (create the pair once with openssl - see README "Setup")
TLS_CERT_FILE = "server.crt"
TLS_KEY_FILE = "server.key"
# A client that connects but never finishes the handshake must not block the accept loop.
TLS_HANDSHAKE_TIMEOUT = 5.0
# Seconds a client may stay silent after the handshake before the server drops it. The
# server serves one client at a time, so an idle one blocks everyone else. Generous, because
# a person at the prompt reads and types slowly. It limits each read, not a whole message:
# a client trickling one byte at a time is not stopped (known gap, see PLAN.md step 16).
CLIENT_IDLE_TIMEOUT = 120.0

# Client: how long it waits for the server (CLIENT_IDLE_TIMEOUT above is the other way
# round: how long the server waits for a client). Each wait has its own likely cause.
# Connect: a refused connect fails at once, so this only matters for an unreachable host.
CONNECT_TIMEOUT = 5.0
# Handshake: the OS completes the TCP connect from the listen() backlog, but the handshake
# waits until the server calls accept(), i.e. until it has finished with another client.
HANDSHAKE_WAIT_TIMEOUT = 10.0
# Each send or reply; the slowest command is login/register (PBKDF2, about 0.5 s).
REPLY_TIMEOUT = 10.0

# Server logging, applied only when server.py runs as a script
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
