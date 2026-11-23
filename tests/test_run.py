"""Launcher: it stops the background server it started, and exits with the right code.

No real processes: everything ``main()`` would start or ask is a mock, patched on ``run``,
the module that looks it up. Opening a real terminal window can't be tested here.
"""

import contextlib
import io
import subprocess
import unittest
from unittest import mock

import run


class LauncherTestCase(unittest.TestCase):
    """Mocks for ``main()`` with no terminal window, so the server runs as its child process.

    No test methods here, so nothing runs twice in the classes that inherit the mocks.
    """

    def setUp(self):
        self.process = mock.Mock()  # the background server's Popen
        self.process.poll.return_value = None  # still running
        self.process.wait.return_value = 0
        self.patch("run.server_is_running", return_value=False)
        self.patch("run.ensure_admin")
        self.patch("run.UserStore")
        self.patch("run.start_server_in_window", return_value=False)
        self.start_background = self.patch("run.start_server_in_background", return_value=self.process)
        self.wait_for_server = self.patch("run.wait_for_server", return_value=True)
        # The client's Popen, used as `with Popen(...) as client`. Only run_client() calls
        # Popen here: the background server's start is patched above.
        self.client = mock.MagicMock()
        self.client.wait.return_value = 0
        self.client_popen = self.patch("run.subprocess.Popen")
        self.client_popen.return_value.__enter__.return_value = self.client

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
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
        self.wait_for_server.return_value = False
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
        run.server_is_running.return_value = True
        self.patch("run.wait_for_server_exit", return_value=True)
        self.run_main()
        self.start_background.assert_not_called()
        self.process.terminate.assert_not_called()
        # No start-up wait either: each probe is one more "TLS handshake failed" in its log.
        self.wait_for_server.assert_not_called()


class ExitCodeTest(LauncherTestCase):
    """``main()`` exits with the client's code, or with its own when it failed first (8.2)."""

    def test_client_exit_code_is_passed_on(self):
        self.client.wait.return_value = 3  # the review plan's test: any code goes through
        code, _ = self.run_main()
        self.assertEqual(code, 3)
        self.process.terminate.assert_called_once()  # and the server is still cleaned up

    def test_client_failure_is_passed_on_from_a_reused_server(self):
        run.server_is_running.return_value = True
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
