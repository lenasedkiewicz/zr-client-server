"""Unit tests for the NDJSON helpers in protocol.py, with no sockets.

``receive_message`` only calls ``readline()`` on a binary file, so ``io.BytesIO`` stands in
for ``sock.makefile("rb")``. ``send_message`` only calls ``sendall()``, so a ``Mock`` stands in
for the socket.
"""

import io
import json
import unittest
from unittest import mock

from config import ENCODING
from protocol import receive_message, send_message


class SendMessageTest(unittest.TestCase):
    def test_sends_one_json_line_in_one_call(self):
        sock = mock.Mock()
        send_message(sock, {"command": "info", "args": {"name": "zażółć"}})
        sock.sendall.assert_called_once()
        (data,), _ = sock.sendall.call_args
        self.assertIsInstance(data, bytes)
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(data.count(b"\n"), 1)  # one message = exactly one line
        self.assertEqual(json.loads(data.decode(ENCODING)), {"command": "info", "args": {"name": "zażółć"}})

    def test_newline_inside_a_string_is_escaped(self):
        # A raw "\n" in a value would split the message into two frames.
        sock = mock.Mock()
        send_message(sock, {"message": "line one\nline two"})
        (data,), _ = sock.sendall.call_args
        self.assertEqual(data.count(b"\n"), 1)

    def test_round_trip(self):
        sock = mock.Mock()
        message = {"status": "ok", "command": "uptime", "data": {"uptime_seconds": 1.5}}
        send_message(sock, message)
        (data,), _ = sock.sendall.call_args
        self.assertEqual(receive_message(io.BytesIO(data)), message)


class ReceiveMessageTest(unittest.TestCase):
    def test_reads_one_message(self):
        self.assertEqual(receive_message(io.BytesIO(b'{"command": "help"}\n')), {"command": "help"})

    def test_reads_messages_one_line_at_a_time(self):
        stream = io.BytesIO(b'{"command": "login"}\n{"command": "info"}\n')
        self.assertEqual(receive_message(stream), {"command": "login"})
        self.assertEqual(receive_message(stream), {"command": "info"})
        self.assertIsNone(receive_message(stream))

    def test_end_of_stream_returns_none(self):
        self.assertIsNone(receive_message(io.BytesIO(b"")))

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):  # json.JSONDecodeError is a ValueError
            receive_message(io.BytesIO(b"not json\n"))

    def test_invalid_utf8_raises_value_error(self):
        with self.assertRaises(ValueError):  # UnicodeDecodeError is a ValueError
            receive_message(io.BytesIO(b"\xff\xfe not utf-8\n"))

    def test_bad_line_does_not_corrupt_the_next_one(self):
        stream = io.BytesIO(b'\xff{"broken"\n{"command": "info"}\n')
        with self.assertRaises(ValueError):
            receive_message(stream)
        self.assertEqual(receive_message(stream), {"command": "info"})


if __name__ == "__main__":
    unittest.main()
