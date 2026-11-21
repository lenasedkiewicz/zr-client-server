"""Launcher: starts the server (in its own terminal window) and the client together."""

import os
import shlex
import shutil
import socket
import subprocess
import sys
import time

from admin_setup import ensure_admin
from config import HOST, PORT, USERS_FILE
from users import UserStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
CLIENT_SCRIPT = os.path.join(BASE_DIR, "client.py")
SERVER_LOG = os.path.join(BASE_DIR, "server.log")
STARTUP_TIMEOUT = 5.0
STOP_TIMEOUT = 5.0
POLL_INTERVAL = 0.1


def server_is_running():
    """Return True if something is accepting connections on HOST:PORT."""
    try:
        with socket.create_connection((HOST, PORT), timeout=POLL_INTERVAL):
            return True
    except OSError:
        return False


def wait_for_server(timeout=STARTUP_TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server_is_running():
            return True
        time.sleep(POLL_INTERVAL)
    return False


def wait_for_server_exit(timeout=1.0):
    """Give a server that received ``stop`` a moment to close its socket."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not server_is_running():
            return True
        time.sleep(POLL_INTERVAL)
    return False


def server_command():
    # -u: unbuffered output, so the server log shows up immediately.
    return [sys.executable, "-u", SERVER_SCRIPT]


def start_server_in_window():
    """Start the server in a new terminal window. Return False if no terminal is available."""
    command = server_command()
    if sys.platform == "win32":
        subprocess.Popen(command, cwd=BASE_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True

    if sys.platform == "darwin":
        shell_command = f"cd {shlex.quote(BASE_DIR)} && {shlex.join(command)}; exit"
        # Escape for an AppleScript string literal.
        script_arg = shell_command.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "{script_arg}"'],
            stdout=subprocess.DEVNULL,
        )
        return True

    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False  # No graphical session (e.g. SSH) - no window can be opened.
    for terminal, flag in (
        ("x-terminal-emulator", "-e"),
        ("gnome-terminal", "--"),
        ("konsole", "-e"),
        ("xterm", "-e"),
    ):
        if shutil.which(terminal):
            subprocess.Popen([terminal, flag, *command], cwd=BASE_DIR)
            return True
    return False


def start_server_in_background():
    """Start the server in this terminal's background, logging to server.log."""
    # The child gets its own copy of the handle, so ours can close as soon as Popen returns,
    # and the with block closes it even if Popen raises.
    with open(SERVER_LOG, "w", encoding="utf-8") as log:
        return subprocess.Popen(
            server_command(), cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT
        )


def stop_background_server(process):
    """Stop the server this launcher started: ask, wait with a limit, then force.

    ``terminate()`` sends SIGTERM on POSIX (on Windows it already kills at once);
    ``kill()`` (SIGKILL) is the last resort for a process that doesn't exit in time.
    A server that already exited (the client sent ``stop``) is left alone.
    """
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()  # collect the exit status, so no zombie stays behind on POSIX
    print("Background server stopped")


def start_server():
    """Start a server; return its process if it runs in the background, else ``None``."""
    # Ask here, in the user's terminal: a prompt in the new server window would
    # outlast the startup timeout below.
    try:
        ensure_admin(UserStore(os.path.join(BASE_DIR, USERS_FILE)))
    except RuntimeError as error:
        print(error)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\nAdmin setup cancelled - server not started")
        sys.exit(1)
    try:
        opened_window = start_server_in_window()
    except OSError as error:
        print(f"Could not open a terminal window ({error})")
        opened_window = False
    if opened_window:
        print("Server started in a new terminal window")
        return None
    process = start_server_in_background()
    print(f"Server started in the background (log: {SERVER_LOG})")
    return process


def wait_until_started(background_server):
    """Wait for the new server to accept connections; exit with code 1 if it doesn't."""
    try:
        started = wait_for_server()
    except KeyboardInterrupt:
        print("\nStart-up cancelled")
        sys.exit(1)
    if not started:
        print(f"Server did not start on {HOST}:{PORT} within {STARTUP_TIMEOUT:.0f} s")
        if background_server is not None:
            print(f"See {SERVER_LOG} for details")
        sys.exit(1)


def run_client():
    try:
        subprocess.run([sys.executable, CLIENT_SCRIPT], cwd=BASE_DIR)
    except KeyboardInterrupt:
        pass  # The client handles Ctrl+C itself; just don't print a traceback here.


def main():
    background_server = None
    # The try starts before the server does: a background server is ours to stop on every
    # way out (a normal end, sys.exit() and Ctrl+C alike). A server in a window, or one that
    # was already running, belongs to the user and is never touched.
    try:
        if server_is_running():
            print(f"Server already running on {HOST}:{PORT} - reusing it")
        else:
            background_server = start_server()
            wait_until_started(background_server)
        run_client()
    finally:
        if background_server is not None:
            stop_background_server(background_server)

    if background_server is None and not wait_for_server_exit():
        print("Server is still running - type 'stop' in a client or press Ctrl+C "
              "in the server window to stop it")


if __name__ == "__main__":
    main()
