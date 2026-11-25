"""Client error handling: every failure ends with a message and an exit code, never a traceback.

No real server: the TLS context, the socket, ``input`` and ``receive_message`` are mocks,
patched on ``client``, the module that looks them up.
"""

import contextlib
import errno
import io
import json
import os
import socket
import tempfile
import unittest
from unittest import mock

import client
from config import HOST, PORT
from protocol import ConnectionClosed, MessageTooLong


class CheckResponseTest(unittest.TestCase):
    def test_valid_replies_pass(self):
        for response in (
            {"status": "ok", "command": "help", "data": {"commands": {}}},
            {"status": "error", "message": "Unknown command: foo"},
            {"status": "error", "command": "login", "message": "Invalid username or password"},
            {"status": "ok", "command": "login", "data": {"username": "alice"}},
        ):
            with self.subTest(response=response):
                client.check_response(response)  # must not raise

    def test_invalid_replies_raise_value_error(self):
        for response in (
            None,
            ["status", "ok"],
            "ok",
            42,
            {},
            {"status": "maybe"},
            {"status": "ok", "command": "login"},
            {"status": "ok", "command": "login", "data": ["alice"]},
            {"status": "ok", "command": "login", "data": {"username": 7}},
        ):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    client.check_response(response)


class ClientMainTest(unittest.TestCase):
    """Run ``client.main()`` against mocks; a traceback would fail the test with the error."""

    def setUp(self):
        self.sock = mock.MagicMock()  # MagicMock: supports `with sock`
        self.context = mock.Mock()
        self.context.wrap_socket.return_value = self.sock
        self.real_make_client_context = client.make_client_context  # before it's patched
        self.patch("client.make_client_context", return_value=self.context)
        self.create_connection = self.patch("client.socket.create_connection")
        self.send = self.patch("client.send_message")
        self.receive = self.patch("client.receive_message")
        # One command, then end of input (Ctrl+D / Ctrl+Z) if the client asks again.
        self.input = self.patch("builtins.input", side_effect=["help", EOFError])

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_client(self):
        """Run ``client.main()``; keep its exit code in ``self.exit_code``, return the output."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.exit_code = client.main()
        return output.getvalue()

    def assert_exit_code(self, expected):
        self.assertEqual(self.exit_code, expected, "wrong exit code")

    def assert_disconnected_after_one_command(self):
        self.assertEqual(self.input.call_count, 1, "client asked for another command")
        self.sock.__exit__.assert_called_once()  # the `with` closed the socket

    def test_valid_reply_is_printed_and_the_prompt_comes_back(self):
        self.receive.return_value = {"status": "ok", "command": "help", "data": {}}
        output = self.run_client()
        self.assertIn('"status": "ok"', output)
        self.assertEqual(self.input.call_count, 2)
        self.assertIn("Disconnecting", output)
        self.assert_exit_code(client.EXIT_OK)  # the user ended it (end of input)

    def test_stop_ends_the_client_with_success(self):
        self.receive.return_value = {"status": "ok", "command": "stop", "data": {}}
        output = self.run_client()
        self.assertIn("Server stopped - exiting client", output)
        self.assert_exit_code(client.EXIT_OK)

    def test_ctrl_c_at_the_prompt_is_a_normal_end(self):
        self.input.side_effect = KeyboardInterrupt
        self.assertIn("Disconnecting", self.run_client())
        self.assert_exit_code(client.EXIT_OK)

    def test_missing_certificate(self):
        self.patch("client.make_client_context", side_effect=FileNotFoundError(2, "No such file"))
        self.assertIn("TLS certificate not found", self.run_client())
        self.assert_exit_code(client.EXIT_FAILURE)
        self.create_connection.assert_not_called()

    def test_unusable_certificate(self):
        # The file exists but isn't a certificate: the real loader raises ssl.SSLError.
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        broken = os.path.join(tmp_dir.name, "server.crt")
        with open(broken, "w", encoding="ascii") as f:
            f.write("not a certificate\n")
        real_make_context = self.real_make_client_context
        self.patch("client.make_client_context", new=lambda: real_make_context(broken))
        output = self.run_client()
        self.assertIn("can't be used", output)
        self.assertIn("see README 'Setup'", output)
        self.assert_exit_code(client.EXIT_FAILURE)
        self.create_connection.assert_not_called()

    def test_unreadable_certificate(self):
        # No read permission, or server.crt is a directory (on Windows both give errno 13).
        # Mocked: what a directory raises differs between systems, this doesn't.
        error = PermissionError(errno.EACCES, "Permission denied", "server.crt")
        self.patch("client.make_client_context", side_effect=error)
        output = self.run_client()
        self.assertIn("can't be used", output)
        self.assertIn("Permission denied", output)
        self.assert_exit_code(client.EXIT_FAILURE)
        self.create_connection.assert_not_called()

    def test_connection_refused(self):
        self.create_connection.side_effect = ConnectionRefusedError
        self.assertIn("is the server running?", self.run_client())
        self.assert_exit_code(client.EXIT_FAILURE)

    def test_other_connect_failures_name_the_reason(self):
        for error in (
            TimeoutError("timed out"),
            socket.gaierror(11001, "getaddrinfo failed"),
            OSError(10065, "No route to host"),
        ):
            with self.subTest(error=error):
                self.create_connection.side_effect = error
                output = self.run_client()
                self.assertIn(f"Cannot connect to {HOST}:{PORT}: ", output)
                self.assertIn(str(error), output)
                self.context.wrap_socket.assert_not_called()
                self.assert_exit_code(client.EXIT_FAILURE)

    def test_each_wait_has_its_own_limit(self):
        raw_sock = self.create_connection.return_value

        def wrap_socket(sock, server_hostname):
            # The handshake limit must be in place before the handshake starts.
            sock.settimeout.assert_called_once_with(client.HANDSHAKE_WAIT_TIMEOUT)
            return self.sock

        self.context.wrap_socket.side_effect = wrap_socket
        self.receive.return_value = {"status": "ok", "command": "help", "data": {}}
        self.run_client()
        self.create_connection.assert_called_once_with((HOST, PORT), timeout=client.CONNECT_TIMEOUT)
        self.context.wrap_socket.assert_called_once_with(raw_sock, server_hostname=HOST)
        self.sock.settimeout.assert_called_once_with(client.REPLY_TIMEOUT)

    def test_handshake_timeout_says_the_server_may_be_busy(self):
        self.context.wrap_socket.side_effect = TimeoutError("The handshake operation timed out")
        output = self.run_client()
        self.assertIn(
            f"No answer from the server within {client.HANDSHAKE_WAIT_TIMEOUT:g} s - it may be busy",
            output,
        )
        self.create_connection.return_value.close.assert_called_once()
        self.input.assert_not_called()
        self.assert_exit_code(client.EXIT_FAILURE)

    def test_send_or_reply_timeout_disconnects(self):
        for name, step in (("send", self.send), ("reply", self.receive)):
            with self.subTest(step=name):
                self.reset_session()
                self.send.reset_mock(side_effect=True)
                step.side_effect = TimeoutError("timed out")
                output = self.run_client()
                self.assertIn(
                    f"No reply from the server within {client.REPLY_TIMEOUT:g} s - disconnecting",
                    output,
                )
                self.assertNotIn("Connection closed by the server", output)
                self.assert_disconnected_after_one_command()
                self.assert_exit_code(client.EXIT_FAILURE)

    def test_ctrl_c_during_the_handshake(self):
        self.context.wrap_socket.side_effect = KeyboardInterrupt
        self.assertIn("Interrupted", self.run_client())
        self.assert_exit_code(client.EXIT_INTERRUPTED)

    def test_ctrl_c_while_waiting_for_a_reply(self):
        self.receive.side_effect = KeyboardInterrupt
        self.assertIn("Interrupted", self.run_client())
        self.assert_disconnected_after_one_command()
        self.assert_exit_code(client.EXIT_INTERRUPTED)

    def test_connection_closed_by_the_server(self):
        self.receive.side_effect = ConnectionClosed()
        self.assertIn("Connection closed by the server", self.run_client())
        self.assert_disconnected_after_one_command()
        self.assert_exit_code(client.EXIT_FAILURE)

    def test_too_long_reply(self):
        self.receive.side_effect = MessageTooLong(65536)
        self.assertIn("Reply from the server is too long - disconnecting", self.run_client())
        self.assert_disconnected_after_one_command()
        self.assert_exit_code(client.EXIT_FAILURE)

    def test_malformed_reply(self):
        for error in (
            json.JSONDecodeError("Expecting value", "nonsense", 0),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
            ValueError("Exceeds the limit (4300 digits) for integer string conversion"),
            RecursionError("maximum recursion depth exceeded"),
        ):
            with self.subTest(error=error):
                self.reset_session()
                self.receive.side_effect = error
                output = self.run_client()
                self.assertIn("Unexpected reply from the server: ", output)
                self.assertIn("- disconnecting", output)
                self.assert_disconnected_after_one_command()
                self.assert_exit_code(client.EXIT_FAILURE)

    def test_reply_with_the_wrong_shape(self):
        for response in (["status", "ok"], "ok", None, {"status": "ok", "command": "login"}):
            with self.subTest(response=response):
                self.reset_session()
                self.receive.return_value = response
                output = self.run_client()
                self.assertIn("Unexpected reply from the server: ", output)
                self.assert_disconnected_after_one_command()
                self.assert_exit_code(client.EXIT_FAILURE)

    def reset_session(self):
        """Fresh prompt answers and call counts for the next subTest."""
        self.input.reset_mock()
        self.input.side_effect = ["help", EOFError]
        self.sock.reset_mock()
        self.receive.reset_mock(return_value=True, side_effect=True)


if __name__ == "__main__":
    unittest.main()
