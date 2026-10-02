"""Helpers for sending and receiving newline-delimited JSON messages over a socket.

Every message is a single JSON object serialized on one line and terminated with "\\n".
This solves TCP message framing: the receiver simply reads one line per message.
"""

import json

from config import ENCODING


def send_message(sock, message):
    """Serialize ``message`` (a dict) to JSON and send it as one line."""
    data = json.dumps(message) + "\n"
    sock.sendall(data.encode(ENCODING))


def receive_message(sock_file):
    """Read one message from a file object created with ``sock.makefile("r")``.

    Returns the decoded dict, or ``None`` if the connection was closed.
    Raises ``json.JSONDecodeError`` if the line is not valid JSON.
    """
    line = sock_file.readline()
    if not line:
        return None
    return json.loads(line)
