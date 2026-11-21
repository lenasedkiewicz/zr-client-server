"""Launcher clean-up: the background server ``run.py`` starts is stopped on every way out.

No real processes: everything ``main()`` would start or ask is a mock, patched on ``run``,
the module that looks it up. Opening a real terminal window can't be tested here.
"""

import contextlib
import io
import subprocess
import unittest
from unittest import mock

import run


class BackgroundServerCleanupTest(unittest.TestCase):
    """``main()`` with no terminal window, so the server runs as its child process."""

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
        self.client = self.patch("run.subprocess.run")

    def patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_main(self):
        """Call ``main()``; return (exit code or None, printed text)."""
        output = io.StringIO()
        code = None
        with contextlib.redirect_stdout(output):
            try:
                run.main()
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

    def test_ctrl_c_while_waiting_for_start_up_stops_the_server(self):
        self.wait_for_server.side_effect = KeyboardInterrupt
        code, output = self.run_main()
        self.assert_stopped_gracefully()
        self.assertEqual(code, 1)
        self.assertIn("Start-up cancelled", output)
        self.client.assert_not_called()

    def test_start_up_timeout_stops_the_server(self):
        self.wait_for_server.return_value = False
        code, output = self.run_main()
        self.assert_stopped_gracefully()  # before this fix: terminate() without wait()
        self.assertEqual(code, 1)
        self.assertIn("did not start", output)

    def test_normal_run_stops_the_server_once(self):
        code, output = self.run_main()
        self.assertIsNone(code)
        self.client.assert_called_once()
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
