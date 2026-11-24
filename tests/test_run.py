"""Launcher: it stops the background server it started, and exits with the right code.

``main()`` runs against mocks, patched on ``run``, the module that looks them up: no real
processes, and opening a real terminal window can't be tested here. ``probe_server`` is
tested against real sockets: a real ``Server`` in a thread, and listeners that aren't ours.
"""

import contextlib
import io
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

import run
from client import make_client_context
from config import HOST, MAX_MESSAGE_SIZE
from server import Server, make_server_context
from users import UserStore

CERTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
TEST_CERT = os.path.join(CERTS_DIR, "test-server.crt")
TEST_KEY = os.path.join(CERTS_DIR, "test-server.key")
OTHER_CERT = os.path.join(CERTS_DIR, "other.crt")  # a certificate our server doesn't have


class LauncherTestCase(unittest.TestCase):
    """Mocks for ``main()`` with no terminal window, so the server runs as its child process.

    No test methods here, so nothing runs twice in the classes that inherit the mocks.
    """

    def setUp(self):
        self.process = mock.Mock()  # the background server's Popen
        self.process.poll.return_value = None  # still running
        self.process.wait.return_value = 0
        self.patch("run.CERT_FILE", TEST_CERT)  # server.crt is git-ignored, so not in CI
        self.probe = self.patch("run.probe_server", return_value=run.ServerState.FREE)
        self.patch("run.ensure_admin")
        self.patch("run.UserStore")
        self.patch("run.start_server_in_window", return_value=False)
        self.start_background = self.patch("run.start_server_in_background", return_value=self.process)
        self.wait_for_server = self.patch("run.wait_for_server", return_value=run.ServerState.READY)
        # The client's Popen, used as `with Popen(...) as client`. Only run_client() calls
        # Popen here: the background server's start is patched above.
        self.client = mock.MagicMock()
        self.client.wait.return_value = 0
        self.client_popen = self.patch("run.subprocess.Popen")
        self.client_popen.return_value.__enter__.return_value = self.client

    def patch(self, target, *args, **kwargs):
        patcher = mock.patch(target, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_main(self):
        """Call ``main()``; return (exit code, printed text).

        The code is what ``main()`` returns, or what an early ``sys.exit()`` carried.
        """
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            try:
                code = run.main()
            except SystemExit as exit_:
                code = exit_.code
        return code, output.getvalue()

    def assert_stopped_gracefully(self):
        """terminate() first, then a wait with a time limit, and no kill()."""
        self.assertEqual(
            self.process.mock_calls[-2:],
            [mock.call.terminate(), mock.call.wait(timeout=run.STOP_TIMEOUT)],
        )
        self.process.kill.assert_not_called()


class BackgroundServerCleanupTest(LauncherTestCase):
    """The background server is stopped on every way out of ``main()`` (task 8.1)."""

    def test_ctrl_c_while_waiting_for_start_up_stops_the_server(self):
        self.wait_for_server.side_effect = KeyboardInterrupt
        code, output = self.run_main()
        self.assert_stopped_gracefully()
        self.assertEqual(code, run.EXIT_INTERRUPTED)  # the user gave up, like the client's 130
        self.assertIn("Start-up cancelled", output)
        self.client_popen.assert_not_called()

    def test_start_up_timeout_stops_the_server(self):
        self.wait_for_server.return_value = run.ServerState.FREE  # nobody answered in time
        code, output = self.run_main()
        self.assert_stopped_gracefully()  # before task 8.1: terminate() without wait()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("did not start", output)

    def test_normal_run_stops_the_server_once(self):
        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.client_popen.assert_called_once()
        self.process.terminate.assert_called_once()
        self.assert_stopped_gracefully()
        self.assertIn("Background server stopped", output)

    def test_server_that_ignores_terminate_is_killed(self):
        self.process.wait.side_effect = [subprocess.TimeoutExpired("server.py", run.STOP_TIMEOUT), 0]
        self.run_main()
        self.process.terminate.assert_called_once()
        self.process.kill.assert_called_once()
        self.assertEqual(self.process.wait.call_count, 2, "kill() must be followed by wait()")

    def test_server_that_already_exited_is_not_terminated(self):
        # e.g. the client sent `stop`: the server exited by itself before the launcher's turn.
        self.process.poll.return_value = 0
        self.run_main()
        self.process.terminate.assert_not_called()
        self.process.kill.assert_not_called()

    def test_server_already_running_is_left_alone(self):
        # Own only what you started: a server found on the port belongs to someone else.
        self.probe.return_value = run.ServerState.READY
        self.patch("run.wait_for_server_exit", return_value=True)
        self.run_main()
        self.start_background.assert_not_called()
        self.process.terminate.assert_not_called()
        # No start-up wait either: each probe is one more connection in its log.
        self.wait_for_server.assert_not_called()


class ExitCodeTest(LauncherTestCase):
    """``main()`` exits with the client's code, or with its own when it failed first (8.2)."""

    def test_client_exit_code_is_passed_on(self):
        self.client.wait.return_value = 3  # the review plan's test: any code goes through
        code, _ = self.run_main()
        self.assertEqual(code, 3)
        self.process.terminate.assert_called_once()  # and the server is still cleaned up

    def test_client_failure_is_passed_on_from_a_reused_server(self):
        self.probe.return_value = run.ServerState.READY
        self.patch("run.wait_for_server_exit", return_value=True)
        self.client.wait.return_value = 1  # EXIT_FAILURE
        code, _ = self.run_main()
        self.assertEqual(code, 1)  # EXIT_FAILURE, passed through unchanged

    def test_ctrl_c_while_the_client_runs_waits_for_its_code(self):
        # Ctrl+C reaches both processes (same terminal). The client handles it and exits;
        # the launcher must wait for that, not kill the client and lose its code.
        self.client.wait.side_effect = [KeyboardInterrupt, run.EXIT_INTERRUPTED]
        code, _ = self.run_main()
        self.assertEqual(code, run.EXIT_INTERRUPTED)
        self.assertEqual(self.client.wait.call_count, 2)
        self.client.kill.assert_not_called()
        self.client.terminate.assert_not_called()

    def test_client_killed_by_a_signal_gets_the_shell_code(self):
        # POSIX: Popen reports "killed by signal N" as -N; a shell shows 128 + N.
        self.client.wait.return_value = -2  # SIGINT
        code, _ = self.run_main()
        self.assertEqual(code, 130)

    def test_admin_setup_without_a_terminal_is_a_launcher_failure(self):
        run.ensure_admin.side_effect = RuntimeError("No terminal to ask for an admin account")
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("No terminal", output)
        self.start_background.assert_not_called()

    def test_end_of_input_at_the_admin_prompt_is_a_launcher_failure(self):
        run.ensure_admin.side_effect = EOFError
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("Admin setup cancelled", output)

    def test_ctrl_c_at_the_admin_prompt_is_an_interruption(self):
        run.ensure_admin.side_effect = KeyboardInterrupt
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_INTERRUPTED)
        self.assertIn("Admin setup cancelled", output)


class WhoIsOnThePortTest(LauncherTestCase):
    """``main()`` reuses only our server, and never starts a second one (task 8.3)."""

    def assert_nothing_started(self):
        self.start_background.assert_not_called()
        run.start_server_in_window.assert_not_called()
        self.client_popen.assert_not_called()

    def test_another_program_on_the_port_is_not_reused(self):
        # The review's acceptance test: no client is started against a stranger.
        self.probe.return_value = run.ServerState.NOT_OURS
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn(f"Port {HOST}:{run.PORT} is used by another program", output)
        self.assert_nothing_started()
        run.ensure_admin.assert_not_called()

    def test_a_busy_server_is_reported_not_reused(self):
        self.probe.return_value = run.ServerState.BUSY
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("busy with another client", output)
        self.assert_nothing_started()

    def test_port_taken_by_another_program_during_start_up(self):
        self.wait_for_server.return_value = run.ServerState.NOT_OURS
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("used by another program", output)
        self.client_popen.assert_not_called()
        self.assert_stopped_gracefully()  # our background server is still cleaned up

    def test_window_that_never_answers_gets_a_hint_and_no_second_server(self):
        run.start_server_in_window.return_value = True
        self.wait_for_server.return_value = run.ServerState.FREE
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("python server.py", output)  # how to see the window's error
        # The first server may just be slow: a second one would fight it for the port.
        self.start_background.assert_not_called()
        self.client_popen.assert_not_called()

    def test_missing_certificate_stops_before_anything(self):
        self.patch("run.CERT_FILE", os.path.join(CERTS_DIR, "missing.crt"))
        code, output = self.run_main()
        self.assertEqual(code, run.EXIT_LAUNCHER_FAILED)
        self.assertIn("TLS certificate not found", output)
        self.probe.assert_not_called()
        self.assert_nothing_started()


class WaitLoopTest(unittest.TestCase):
    """The start-up and exit waits, with a fake clock instead of sleeping."""

    def setUp(self):
        now = [0.0]

        def fake_sleep(seconds):
            now[0] += seconds

        for name, fake in (("monotonic", lambda: now[0]), ("sleep", fake_sleep)):
            patcher = mock.patch(f"run.time.{name}", side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def probe_answers(self, *states):
        patcher = mock.patch("run.probe_server", side_effect=list(states))
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_start_up_wait_returns_once_our_server_answers(self):
        probe = self.probe_answers(run.ServerState.FREE, run.ServerState.FREE, run.ServerState.READY)
        self.assertEqual(run.wait_for_server(timeout=5), run.ServerState.READY)
        self.assertEqual(probe.call_count, 3)

    def test_start_up_wait_stops_at_once_for_another_program(self):
        probe = self.probe_answers(run.ServerState.FREE, run.ServerState.NOT_OURS)
        self.assertEqual(run.wait_for_server(timeout=5), run.ServerState.NOT_OURS)
        self.assertEqual(probe.call_count, 2)

    def test_start_up_wait_gives_up_after_the_timeout(self):
        self.probe_answers(*[run.ServerState.FREE] * 100)
        self.assertEqual(run.wait_for_server(timeout=0.5), run.ServerState.FREE)

    def test_exit_wait_ends_when_our_server_is_gone(self):
        self.probe_answers(run.ServerState.READY, run.ServerState.FREE)
        self.assertTrue(run.wait_for_server_exit(timeout=1))


class ProbeServerTest(unittest.TestCase):
    """``probe_server`` against real sockets on a free port."""

    TIMEOUT = 0.5  # the probe's limit in these tests; a real run uses PROBE_TIMEOUT

    def setUp(self):
        patcher = mock.patch("run.CERT_FILE", TEST_CERT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_port(self, port):
        patcher = mock.patch("run.PORT", port)
        patcher.start()
        self.addCleanup(patcher.stop)

    def probe(self):
        return run.probe_server(timeout=self.TIMEOUT)

    def start_our_server(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        users = UserStore(os.path.join(tmp_dir.name, "users.json"), iterations=1_000)
        server = Server(port=0, users=users, tls_context=make_server_context(TEST_CERT, TEST_KEY))
        self.addCleanup(server.close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, timeout=5)
        self.addCleanup(setattr, server, "running", False)  # runs first: the loop exits
        self.assertTrue(server.listening.wait(timeout=5), "server did not start listening")
        self.use_port(server.address[1])
        return server

    def plain_listener(self, reply=None):
        """A TCP listener that isn't ours: it accepts, sends ``reply`` and closes.

        With ``reply=None`` it never calls accept(): connections wait in its backlog.
        """
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind((HOST, 0))
        listener.listen()
        self.use_port(listener.getsockname()[1])
        if reply is not None:
            def answer_once():
                conn, _ = listener.accept()
                with conn:
                    conn.sendall(reply)

            thread = threading.Thread(target=answer_once, daemon=True)
            thread.start()
            self.addCleanup(thread.join, timeout=5)

    def test_free_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((HOST, 0))
        port = sock.getsockname()[1]
        sock.close()  # nothing listens there now: a connect is refused
        self.use_port(port)
        self.assertEqual(self.probe(), run.ServerState.FREE)

    def test_our_server_is_ready_and_still_serves_afterwards(self):
        server = self.start_our_server()
        self.assertEqual(self.probe(), run.ServerState.READY)
        # The control question: after the probe, does the server still answer a new client?
        self.assertEqual(self.probe(), run.ServerState.READY)
        self.assertTrue(server.running)

    def test_plain_tcp_listener_is_not_ours(self):
        # The review's test: a listener that accepts but speaks no TLS.
        self.plain_listener(reply=b"HTTP/1.1 400 Bad Request\r\n\r\n")
        self.assertEqual(self.probe(), run.ServerState.NOT_OURS)

    def test_listener_that_never_accepts_is_busy(self):
        self.plain_listener(reply=None)
        self.assertEqual(self.probe(), run.ServerState.BUSY)

    def test_our_server_busy_with_another_client_is_busy(self):
        self.start_our_server()
        # Hold the only slot: a connected, idle TLS client. The server waits in its read.
        raw = socket.create_connection((HOST, run.PORT), timeout=5)
        holder = make_client_context(TEST_CERT).wrap_socket(raw, server_hostname=HOST)
        self.addCleanup(holder.close)
        self.assertEqual(self.probe(), run.ServerState.BUSY)

    def test_tls_server_with_another_certificate_is_not_ours(self):
        self.start_our_server()
        with mock.patch("run.CERT_FILE", OTHER_CERT):  # we'd trust only "other"
            self.assertEqual(self.probe(), run.ServerState.NOT_OURS)

    def fake_tls_peer(self, reply):
        """A TLS server holding *our* test certificate and key that answers with ``reply``.

        It passes the pinned handshake, so only the reply decides what the probe sees. It
        reads one request line, sends ``reply`` (``b""``: nothing) and closes. With
        ``reply=None`` it stays silent until the test ends.
        """
        context = make_server_context(TEST_CERT, TEST_KEY)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind((HOST, 0))
        listener.listen()
        self.use_port(listener.getsockname()[1])
        test_over = threading.Event()

        def serve_once():
            try:
                conn, _ = listener.accept()
                with context.wrap_socket(conn, server_side=True) as tls, tls.makefile("rb") as f:
                    f.readline()  # the probe's help request
                    if reply is None:
                        test_over.wait(timeout=5)
                    else:
                        tls.sendall(reply)
            except OSError:
                pass  # the probe gave up first (e.g. after a too-long line): expected here

        thread = threading.Thread(target=serve_once, daemon=True)
        thread.start()
        self.addCleanup(thread.join, timeout=5)
        self.addCleanup(test_over.set)  # runs before the join: a silent peer lets go

    def test_fake_peer_with_a_real_help_reply_is_ready(self):
        # The control for the cases below: the fake peer is faithful enough to pass.
        self.fake_tls_peer(b'{"status": "ok", "command": "help", "data": {}}\n')
        self.assertEqual(self.probe(), run.ServerState.READY)

    def test_tls_peer_with_our_certificate_but_another_protocol_is_not_ours(self):
        # The rows of the pre-review's hostile-input table that apply to a peer we read from.
        too_long = b'"' + b"x" * MAX_MESSAGE_SIZE + b'"\n'
        deep = b"[" * 20_000 + b"]" * 20_000 + b"\n"  # under the size limit, over the recursion limit
        for name, reply in (
            ("bytes that aren't UTF-8", b"\xff\xfe\n"),
            ("invalid JSON", b"not json\n"),
            ("null", b"null\n"),
            ("a list", b"[]\n"),
            ("a number", b"5\n"),
            ("a string", b'"x"\n'),
            ("an integer over 4300 digits", b"1" * 5000 + b"\n"),
            ("nesting deeper than the recursion limit", deep),
            ("a line over MAX_MESSAGE_SIZE", too_long),
            ("a reply without the final newline", b'{"status": "ok", "command": "help", "data": {}}'),
            ("closed right after the handshake", b""),
            ("an answer to another command", b'{"status": "ok", "command": "info", "data": {}}\n'),
            ("no command at all", b'{"status": "ok"}\n'),
            ("silence", None),
        ):
            with self.subTest(name):
                self.fake_tls_peer(reply)
                self.assertEqual(self.probe(), run.ServerState.NOT_OURS)


class StartServerInBackgroundTest(unittest.TestCase):
    def test_log_file_is_closed_when_popen_fails(self):
        opener = mock.mock_open()
        with mock.patch("builtins.open", opener), \
                mock.patch("run.subprocess.Popen", side_effect=OSError("no python")):
            with self.assertRaises(OSError):
                run.start_server_in_background()
        opener.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
