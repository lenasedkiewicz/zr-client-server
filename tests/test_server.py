"""End-to-end tests for the server."""

import socket
import threading
import time
import unittest

from config import ENCODING, SERVER_CREATED, SERVER_VERSION
from protocol import receive_message, send_message
from server import Server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = Server(port=0)  # 0 = let the OS pick a free port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.sock = socket.create_connection(self.server.address, timeout=5)
        self.sock_file = self.sock.makefile("r", encoding=ENCODING)

    def tearDown(self):
        if self.thread.is_alive():
            self.request("stop")
        self.sock_file.close()
        self.sock.close()
        self.thread.join(timeout=5)

    def request(self, command):
        send_message(self.sock, {"command": command})
        return receive_message(self.sock_file)

    def test_uptime(self):
        first = self.request("uptime")
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["command"], "uptime")
        self.assertIn("uptime", first["data"])
        time.sleep(0.05)
        second = self.request("uptime")
        self.assertGreater(second["data"]["uptime_seconds"], first["data"]["uptime_seconds"])

    def test_info(self):
        response = self.request("info")
        self.assertEqual(response["data"], {"version": SERVER_VERSION, "created": SERVER_CREATED})

    def test_help_lists_all_commands(self):
        response = self.request("help")
        self.assertEqual(set(response["data"]), {"uptime", "info", "help", "stop"})

    def test_unknown_command(self):
        response = self.request("foo")
        self.assertEqual(response["status"], "error")
        self.assertIn("foo", response["message"])
        # The connection stays usable after an error.
        self.assertEqual(self.request("info")["status"], "ok")

    def test_invalid_json(self):
        self.sock.sendall(b"not json\n")
        response = receive_message(self.sock_file)
        self.assertEqual(response["status"], "error")
        self.assertEqual(self.request("info")["status"], "ok")

    def test_stop(self):
        response = self.request("stop")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["command"], "stop")
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
