"""User account storage: salted PBKDF2 password hashes kept in a JSON file.

Passwords are never stored. Each user gets a random salt, and the file keeps
``pbkdf2_hmac("sha256", password, salt, iterations)``. Checking a password means
hashing it again with the same salt and comparing the results in constant time.
"""

import hashlib
import hmac
import json
import os
import re
import secrets

from config import ENCODING, MIN_PASSWORD_LENGTH, PBKDF2_ITERATIONS, USERNAME_PATTERN, USERS_FILE

SALT_BYTES = 16


class UserStore:
    def __init__(self, path=USERS_FILE, iterations=PBKDF2_ITERATIONS):
        self.path = path
        self.iterations = iterations
        self.users = self._load()

    def _load(self):
        try:
            with open(self.path, encoding=ENCODING) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save(self):
        # Write to a temporary file and swap it in, so a crash mid-write
        # never leaves a half-written users file behind.
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding=ENCODING) as f:
            json.dump(self.users, f, indent=2)
        os.replace(tmp_path, self.path)

    @staticmethod
    def _hash(password, salt, iterations):
        return hashlib.pbkdf2_hmac("sha256", password.encode(ENCODING), salt, iterations)

    def create_user(self, username, password):
        """Add a new user. Raises ``ValueError`` with a user-facing message on bad input."""
        if not isinstance(username, str) or not re.fullmatch(USERNAME_PATTERN, username):
            raise ValueError("Username must be 3-32 characters: letters, digits or _")
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        if username in self.users:
            raise ValueError(f"User already exists: {username}")
        salt = secrets.token_bytes(SALT_BYTES)
        self.users[username] = {
            "salt": salt.hex(),
            "hash": self._hash(password, salt, self.iterations).hex(),
            # Stored per user, so the default can be raised later without breaking old accounts.
            "iterations": self.iterations,
        }
        self._save()

    def verify_password(self, username, password):
        """Return True if ``username`` exists and ``password`` matches its stored hash."""
        record = self.users.get(username) if isinstance(username, str) else None
        if record is None or not isinstance(password, str):
            # Hash anyway, so an unknown username takes as long as a wrong password
            # and response times don't reveal which usernames exist.
            self._hash(str(password), bytes(SALT_BYTES), self.iterations)
            return False
        expected = bytes.fromhex(record["hash"])
        actual = self._hash(password, bytes.fromhex(record["salt"]), record["iterations"])
        return hmac.compare_digest(expected, actual)
