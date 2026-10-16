"""Tests for the first-start admin setup and account roles."""

import contextlib
import io
import json
import os
import tempfile
import unittest

from admin_setup import ensure_admin
from config import ROLE_ADMIN, ROLE_USER
from users import UserStore


def answers(*values):
    """Return a fake prompt function that replies with ``values`` in order."""
    replies = iter(values)
    return lambda prompt="": next(replies)


class EnsureAdminTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp_dir.name, "users.json")
        self.store = UserStore(self.path, iterations=1_000)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def run_setup(self, usernames, passwords, interactive=True):
        """Run ``ensure_admin`` with scripted answers and its output hidden."""
        with contextlib.redirect_stdout(io.StringIO()):
            return ensure_admin(
                self.store,
                ask_username=answers(*usernames),
                ask_password=answers(*passwords),
                interactive=interactive,
            )

    def saved_role(self, username):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)[username]["role"]

    def test_creates_admin_when_none_exists(self):
        created = self.run_setup(["root"], ["secret123", "secret123"])
        self.assertEqual(created, "root")
        self.assertTrue(self.store.has_admin())
        self.assertEqual(self.saved_role("root"), ROLE_ADMIN)
        self.assertTrue(self.store.verify_password("root", "secret123"))

    def test_does_nothing_when_admin_exists(self):
        self.store.create_user("root", "secret123", role=ROLE_ADMIN)
        # No answers: any prompt would raise StopIteration.
        self.assertIsNone(self.run_setup([], [], interactive=False))

    def test_asks_again_after_password_mismatch(self):
        created = self.run_setup(["root", "root"], ["secret123", "other1234", "secret123", "secret123"])
        self.assertEqual(created, "root")

    def test_asks_again_after_invalid_username(self):
        created = self.run_setup(["x", "root"], ["secret123"] * 4)
        self.assertEqual(created, "root")

    def test_existing_user_name_is_not_promoted(self):
        self.store.create_user("alice", "secret123")
        created = self.run_setup(["alice", "root"], ["secret123"] * 4)
        self.assertEqual(created, "root")
        self.assertEqual(self.saved_role("alice"), ROLE_USER)

    def test_refuses_without_terminal(self):
        with self.assertRaises(RuntimeError):
            self.run_setup([], [], interactive=False)
        self.assertFalse(self.store.has_admin())

    def test_register_creates_regular_user(self):
        self.store.create_user("alice", "secret123")
        self.assertEqual(self.saved_role("alice"), ROLE_USER)
        self.assertFalse(self.store.has_admin())

    def test_record_without_role_is_not_admin(self):
        # users.json written before step 13 has no "role" field.
        self.store.create_user("old", "secret123")
        del self.store.users["old"]["role"]
        self.assertFalse(self.store.has_admin())


if __name__ == "__main__":
    unittest.main()
