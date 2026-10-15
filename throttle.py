"""Temporary lockout after repeated failed logins (protection against online guessing).

Failures are counted per username, not per connection or IP address: reconnecting does not
reset the count, and unknown usernames are counted too, so a lockout never reveals which
accounts exist. The lockout is temporary, so an attacker cannot lock a user out for good.

State lives in memory: a server restart clears it.
"""

import time

from config import LOGIN_LOCKOUT_SECONDS, MAX_FAILED_LOGINS


class LoginThrottle:
    def __init__(
        self,
        max_failures=MAX_FAILED_LOGINS,
        lockout_seconds=LOGIN_LOCKOUT_SECONDS,
        clock=time.monotonic,
    ):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        # Monotonic: changing the system clock must not shorten or stretch a lockout.
        self.clock = clock
        self.failures = {}  # username -> consecutive failed attempts
        self.locked_until = {}  # username -> clock() value when the lockout ends

    def check(self, username):
        """Raise ``ValueError`` if ``username`` is locked out; clear an expired lockout."""
        locked_until = self.locked_until.get(username)
        if locked_until is None:
            return
        remaining = locked_until - self.clock()
        if remaining > 0:
            raise ValueError(f"Too many failed logins, try again in {int(remaining) + 1} s")
        # Lockout over: start counting from zero again.
        del self.locked_until[username]
        self.failures.pop(username, None)

    def record_failure(self, username):
        failures = self.failures.get(username, 0) + 1
        self.failures[username] = failures
        if failures >= self.max_failures:
            self.locked_until[username] = self.clock() + self.lockout_seconds

    def record_success(self, username):
        self.failures.pop(username, None)
        self.locked_until.pop(username, None)
