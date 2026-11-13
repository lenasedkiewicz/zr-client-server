"""Helpers for sending and receiving newline-delimited JSON messages over a socket.

Every message is one JSON value serialized on one line and terminated with "\\n".
This solves TCP message framing: the receiver simply reads one line per message.

This module only frames messages; it doesn't decide what a valid request is. Requests look
like ``{"command": "<name>"}``, with an optional ``"args"`` object for commands that need
input, e.g. ``{"command": "register", "args": {"username": ...}}``, and ``server.py``
rejects anything else.
"""

import json
import socket
from typing import Any, BinaryIO

from config import ENCODING


class ConnectionClosed(Exception):
    """The peer closed the connection: there are no more messages to read.

    A plain ``Exception`` on purpose: as a ``ValueError`` it would be caught as a malformed
    message, as an ``OSError`` as a network failure.

    ``discarded`` is the size in bytes of an unterminated final message: the peer closed
    before sending its ``\\n``, so those bytes were dropped unread. It is 0 for a clean close
    between messages.
    """

    def __init__(self, discarded: int = 0) -> None:
        detail = f": {discarded} bytes without a final newline discarded" if discarded else ""
        super().__init__(f"connection closed{detail}")
        self.discarded = discarded


def send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    """Serialize ``message`` to JSON and send it as one line."""
    data = json.dumps(message) + "\n"
    sock.sendall(data.encode(ENCODING))


def receive_message(sock_file: BinaryIO) -> Any:
    """Read one message from a binary file object created with ``sock.makefile("rb")``.

    The line is read as bytes and decoded on its own, so a bad line can't corrupt the next
    one (a text-mode stream's decoder may already have swallowed the bytes that follow).

    Returns the decoded JSON value, which may be any JSON type, including ``None`` for
    ``null``; the caller checks its shape. Raises ``ConnectionClosed`` at end of stream, a
    signal no message can be mistaken for. A message is complete only with its ``\\n``, so a
    final line cut off by the close also raises ``ConnectionClosed`` (with ``discarded`` set),
    even if its bytes would parse. Raises ``ValueError`` for a malformed line:
    invalid UTF-8 (``UnicodeDecodeError``), invalid JSON (``json.JSONDecodeError``) or an
    integer too long to convert; ``RecursionError`` if the JSON is nested too deeply; and
    ``OSError`` if the read itself fails.
    """
    line = sock_file.readline()
    if not line.endswith(b"\n"):
        # readline() without a size stops only at "\n" or at end of stream, so this is either
        # a clean close (b"") or a close in the middle of a message. No "\n", no message.
        raise ConnectionClosed(discarded=len(line))
    return json.loads(line.decode(ENCODING))
