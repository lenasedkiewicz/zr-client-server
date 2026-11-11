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
from protocol import ConnectionClosed, receive_message, send_message


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
        with self.assertRaises(ConnectionClosed):
            receive_message(stream)

    def test_end_of_stream_raises_connection_closed(self):
        with self.assertRaises(ConnectionClosed):
            receive_message(io.BytesIO(b""))

    def test_clean_close_discards_nothing(self):
        with self.assertRaises(ConnectionClosed) as caught:
            receive_message(io.BytesIO(b""))
        self.assertEqual(caught.exception.discarded, 0)

    def test_unterminated_final_line_is_not_a_message(self):
        # Valid JSON, but no "\n": the peer closed mid-message, so it must not run.
        with self.assertRaises(ConnectionClosed) as caught:
            receive_message(io.BytesIO(b'{"command": "stop"}'))
        self.assertEqual(caught.exception.discarded, len(b'{"command": "stop"}'))

    def test_complete_line_before_an_unterminated_one_is_read(self):
        stream = io.BytesIO(b'{"command": "info"}\n{"command": "stop"}')
        self.assertEqual(receive_message(stream), {"command": "info"})
        with self.assertRaises(ConnectionClosed) as caught:
            receive_message(stream)
        self.assertEqual(caught.exception.discarded, len(b'{"command": "stop"}'))

    def test_null_is_a_message_not_end_of_stream(self):
        stream = io.BytesIO(b'null\n{"command": "info"}\n')
        self.assertIsNone(receive_message(stream))
        self.assertEqual(receive_message(stream), {"command": "info"})

    def test_any_json_value_is_returned_as_is(self):
        # protocol.py frames messages; deciding what a valid *request* is belongs to the server.
        for line, value in ((b"[]\n", []), (b'"x"\n', "x"), (b"1\n", 1), (b"false\n", False)):
            with self.subTest(line=line):
                self.assertEqual(receive_message(io.BytesIO(line)), value)

    def test_connection_closed_is_not_caught_as_malformed_or_network_error(self):
        # The server catches ValueError (malformed line) and OSError (network) separately.
        self.assertFalse(issubclass(ConnectionClosed, (ValueError, OSError)))

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
