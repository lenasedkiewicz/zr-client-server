"""Helpers for sending and receiving newline-delimited JSON messages over a socket.

Every message is a single JSON object serialized on one line and terminated with "\\n".
This solves TCP message framing: the receiver simply reads one line per message.

Requests look like ``{"command": "<name>"}``, with an optional ``"args"`` object for
commands that need input, e.g. ``{"command": "register", "args": {"username": ...}}``.
"""

import json

from config import ENCODING


def send_message(sock, message):
    """Serialize ``message`` (a dict) to JSON and send it as one line."""
    data = json.dumps(message) + "\n"
    sock.sendall(data.encode(ENCODING))


def receive_message(sock_file):
    """Read one message from a binary file object created with ``sock.makefile("rb")``.

    The line is read as bytes and decoded on its own, so a bad line can't corrupt the next
    one (a text-mode stream's decoder may already have swallowed the bytes that follow).

    Returns the decoded message, or ``None`` if the connection was closed.
    Raises ``ValueError`` for a malformed line: invalid UTF-8 (``UnicodeDecodeError``),
    invalid JSON (``json.JSONDecodeError``) or an integer too long to convert. Raises
    ``RecursionError`` if the JSON is nested too deeply.
    """
    line = sock_file.readline()
    if not line:
        return None
    return json.loads(line.decode(ENCODING))
