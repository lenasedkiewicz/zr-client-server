"""End-to-end tests for the server."""

import json
import os
import socket
import tempfile
import threading
import time
import unittest

from config import ENCODING, SERVER_CREATED, SERVER_VERSION
from protocol import receive_message, send_message
from server import Server
from users import UserStore


class ServerTest(unittest.TestCase):
    def setUp(self):
        # Each test gets its own users file; few iterations keep the tests fast.
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.users_path = os.path.join(self.tmp_dir.name, "users.json")
        users = UserStore(self.users_path, iterations=1_000)
        self.server = Server(port=0, users=users)  # 0 = let the OS pick a free port
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
        self.tmp_dir.cleanup()

    def request(self, command, args=None):
        message = {"command": command}
        if args is not None:
            message["args"] = args
        send_message(self.sock, message)
        return receive_message(self.sock_file)

    def register(self, username="alice", password="secret123"):
        return self.request("register", {"username": username, "password": password})

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
        self.assertEqual(set(response["data"]), {"register", "uptime", "info", "help", "stop"})

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

    def test_register(self):
        response = self.register()
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["command"], "register")

    def test_register_stores_hash_not_password(self):
        self.register(password="secret123")
        with open(self.users_path, encoding=ENCODING) as f:
            content = f.read()
        self.assertNotIn("secret123", content)
        record = json.loads(content)["alice"]
        self.assertEqual(set(record), {"salt", "hash", "iterations"})
        self.assertTrue(self.server.users.verify_password("alice", "secret123"))
        self.assertFalse(self.server.users.verify_password("alice", "wrong-pass"))

    def test_register_same_password_gives_different_hashes(self):
        self.register("alice", "secret123")
        self.register("bob", "secret123")
        users = self.server.users.users
        self.assertNotEqual(users["alice"]["hash"], users["bob"]["hash"])

    def test_register_duplicate_username(self):
        self.register()
        response = self.register()
        self.assertEqual(response["status"], "error")
        self.assertIn("already exists", response["message"])

    def test_register_invalid_input(self):
        for args in (
            {"username": "al", "password": "secret123"},  # username too short
            {"username": "bad name", "password": "secret123"},  # space not allowed
            {"username": "alice", "password": "short"},  # password too short
            {},  # nothing given
        ):
            with self.subTest(args=args):
                self.assertEqual(self.request("register", args)["status"], "error")

    def test_args_must_be_object(self):
        response = self.request("info", args=["not", "an", "object"])
        self.assertEqual(response["status"], "error")

    def test_users_persist_across_restarts(self):
        self.register()
        reloaded = UserStore(self.users_path, iterations=1_000)
        self.assertTrue(reloaded.verify_password("alice", "secret123"))

    def test_stop(self):
        response = self.request("stop")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["command"], "stop")
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
