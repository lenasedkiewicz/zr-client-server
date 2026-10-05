"""Shared configuration for the server and the client."""

HOST = "127.0.0.1"
PORT = 65432
BUFFER_SIZE = 1024
ENCODING = "utf-8"

SERVER_VERSION = "1.0.0"
SERVER_CREATED = "2026-10-01"

# User accounts
USERS_FILE = "users.json"
# OWASP (2023) recommends at least 600,000 iterations for PBKDF2-HMAC-SHA256.
PBKDF2_ITERATIONS = 600_000
USERNAME_PATTERN = r"[A-Za-z0-9_]{3,32}"
MIN_PASSWORD_LENGTH = 8
