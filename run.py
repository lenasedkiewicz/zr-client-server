"""Launcher: starts the server (in its own terminal window) and the client together."""

import os
import shlex
import shutil
import socket
import subprocess
import sys
import time

from config import HOST, PORT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
CLIENT_SCRIPT = os.path.join(BASE_DIR, "client.py")
SERVER_LOG = os.path.join(BASE_DIR, "server.log")
STARTUP_TIMEOUT = 5.0
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
    log = open(SERVER_LOG, "w", encoding="utf-8")
    process = subprocess.Popen(
        server_command(), cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT
    )
    log.close()  # The child process keeps its own handle.
    return process


def main():
    background_server = None

    if server_is_running():
        print(f"Server already running on {HOST}:{PORT} - reusing it")
    else:
        try:
            opened_window = start_server_in_window()
        except OSError as error:
            print(f"Could not open a terminal window ({error})")
            opened_window = False
        if opened_window:
            print("Server started in a new terminal window")
        else:
            background_server = start_server_in_background()
            print(f"Server started in the background (log: {SERVER_LOG})")

        if not wait_for_server():
            print(f"Server did not start on {HOST}:{PORT} within {STARTUP_TIMEOUT:.0f} s")
            if background_server is not None:
                background_server.terminate()
                print(f"See {SERVER_LOG} for details")
            sys.exit(1)

    try:
        subprocess.run([sys.executable, CLIENT_SCRIPT], cwd=BASE_DIR)
    except KeyboardInterrupt:
        pass  # The client handles Ctrl+C itself; just don't print a traceback here.

    if background_server is not None:
        if background_server.poll() is None:
            background_server.terminate()
            background_server.wait()
            print("Background server stopped")
    elif not wait_for_server_exit():
        print("Server is still running - type 'stop' in a client or press Ctrl+C "
              "in the server window to stop it")


if __name__ == "__main__":
    main()
