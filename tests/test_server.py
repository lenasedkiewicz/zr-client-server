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
        self.connect()

    def tearDown(self):
        if self.thread.is_alive():
            # stop requires a login; if already logged in, login just errors and stop still works.
            self.login_as("teardown")
            self.request("stop")
        self.sock_file.close()
        self.sock.close()
        self.thread.join(timeout=5)
        self.tmp_dir.cleanup()

    def connect(self):
        self.sock = socket.create_connection(self.server.address, timeout=5)
        self.sock_file = self.sock.makefile("r", encoding=ENCODING)

    def request(self, command, args=None):
        message = {"command": command}
        if args is not None:
            message["args"] = args
        send_message(self.sock, message)
        return receive_message(self.sock_file)

    def register(self, username="alice", password="secret123"):
        return self.request("register", {"username": username, "password": password})

    def login(self, username="alice", password="secret123"):
        return self.request("login", {"username": username, "password": password})

    def login_as(self, username="alice", password="secret123"):
        """Register (if needed) and log in, so protected commands can be used."""
        self.register(username, password)
        return self.login(username, password)

    def test_uptime(self):
        self.login_as()
        first = self.request("uptime")
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["command"], "uptime")
        self.assertIn("uptime", first["data"])
        time.sleep(0.05)
        second = self.request("uptime")
        self.assertGreater(second["data"]["uptime_seconds"], first["data"]["uptime_seconds"])

    def test_info(self):
        self.login_as()
        response = self.request("info")
        self.assertEqual(response["data"], {"version": SERVER_VERSION, "created": SERVER_CREATED})

    def test_help_logged_in_lists_all_commands(self):
        self.login_as()
        response = self.request("help")
        self.assertEqual(
            set(response["data"]),
            {"register", "login", "logout", "uptime", "info", "help", "stop"},
        )

    def test_help_logged_out_lists_only_auth_commands(self):
        response = self.request("help")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(set(response["data"]), {"register", "login", "help"})

    def test_unknown_command(self):
        self.login_as()
        response = self.request("foo")
        self.assertEqual(response["status"], "error")
        self.assertIn("foo", response["message"])
        # The connection stays usable after an error.
        self.assertEqual(self.request("info")["status"], "ok")

    def test_invalid_json(self):
        self.login_as()
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

    def test_commands_require_login(self):
        for command in ("uptime", "info", "stop", "logout"):
            with self.subTest(command=command):
                response = self.request(command)
                self.assertEqual(response["status"], "error")
                self.assertIn("Login required", response["message"])
        self.assertTrue(self.thread.is_alive())  # stop was rejected

    def test_login(self):
        self.register()
        response = self.login()
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["username"], "alice")
        self.assertEqual(self.request("uptime")["status"], "ok")

    def test_login_wrong_password_and_unknown_user_look_the_same(self):
        self.register()
        wrong_password = self.login("alice", "wrong-pass")
        unknown_user = self.login("nobody", "secret123")
        self.assertEqual(wrong_password["status"], "error")
        self.assertEqual(wrong_password["message"], unknown_user["message"])
        self.assertEqual(self.request("uptime")["status"], "error")

    def test_login_invalid_args(self):
        for args in ({}, {"username": ["alice"], "password": "secret123"}):
            with self.subTest(args=args):
                self.assertEqual(self.request("login", args)["status"], "error")

    def test_login_twice(self):
        self.login_as()
        response = self.login()
        self.assertEqual(response["status"], "error")
        self.assertIn("Already logged in", response["message"])

    def test_logout(self):
        self.login_as()
        self.assertEqual(self.request("logout")["status"], "ok")
        self.assertIn("Login required", self.request("uptime")["message"])
        self.assertEqual(set(self.request("help")["data"]), {"register", "login", "help"})

    def test_new_connection_starts_logged_out(self):
        self.login_as()
        self.sock_file.close()
        self.sock.close()
        self.connect()  # the server takes the next client after the first disconnects
        self.assertIn("Login required", self.request("uptime")["message"])

    def test_stop(self):
        self.login_as()
        response = self.request("stop")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["command"], "stop")
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
