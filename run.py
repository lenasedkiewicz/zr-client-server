"""Launcher: starts the server (in its own terminal window) and the client together."""

import enum
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time

from admin_setup import ensure_admin
from client import check_response, make_client_context
from config import EXIT_INTERRUPTED, EXIT_LAUNCHER_FAILED, HOST, PORT, TLS_CERT_FILE, USERS_FILE
from protocol import ConnectionClosed, MessageTooLong, receive_message, send_message
from users import UserStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
CLIENT_SCRIPT = os.path.join(BASE_DIR, "client.py")
SERVER_LOG = os.path.join(BASE_DIR, "server.log")
STARTUP_TIMEOUT = 5.0
STOP_TIMEOUT = 5.0
POLL_INTERVAL = 0.1
PROBE_TIMEOUT = 1.0
CERT_FILE = os.path.join(BASE_DIR, TLS_CERT_FILE)


class ServerState(enum.Enum):
    """Who is on HOST:PORT, as far as one probe can tell."""

    FREE = "nothing is listening"
    READY = "our server answered"
    BUSY = "a connection was accepted, but the TLS handshake didn't finish in time"
    NOT_OURS = "something else is listening"


def probe_server(timeout=PROBE_TIMEOUT):
    """Find out who is on HOST:PORT with a real exchange: a TLS handshake, then ``help``.

    A successful TCP connect only means the OS queued the connection, so it can't tell our
    server from another program. Our server serves one client at a time and accepts the next
    only when it's free, so a handshake that times out means it is busy. Every step is
    limited by ``timeout``. ``help`` works without a login.
    """
    context = make_client_context(CERT_FILE)  # pinned: trust only our own certificate
    try:
        raw_sock = socket.create_connection((HOST, PORT), timeout=timeout)
    except OSError:  # refused: nothing listens; or nothing reachable at all
        return ServerState.FREE
    with raw_sock:
        try:
            tls_sock = context.wrap_socket(raw_sock, server_hostname=HOST)
        except TimeoutError:  # before OSError, its parent: accepted by the OS, not by a server
            return ServerState.BUSY
        except OSError:  # ssl.SSLError (no TLS, another certificate) or a reset; both OSErrors
            return ServerState.NOT_OURS
        with tls_sock, tls_sock.makefile("rb") as sock_file:
            try:
                send_message(tls_sock, {"command": "help"})
                response = receive_message(sock_file)
                check_response(response)
            except (ConnectionClosed, MessageTooLong, OSError, ValueError, RecursionError):
                # A timeout lands here too: our server answers help at once once it has
                # accepted us. Bad JSON, bad UTF-8 or the wrong shape: not our protocol.
                return ServerState.NOT_OURS
    if response["status"] == "ok" and response.get("command") == "help":
        return ServerState.READY
    return ServerState.NOT_OURS


def wait_for_server(timeout=STARTUP_TIMEOUT):
    """Probe until our server answers; return the last state seen.

    ``READY``: it answered. ``NOT_OURS``: another program took the port, so waiting longer
    won't help. Anything else after ``timeout`` seconds: nobody answered in time.
    """
    deadline = time.monotonic() + timeout
    state = ServerState.FREE
    while time.monotonic() < deadline:
        state = probe_server()
        if state in (ServerState.READY, ServerState.NOT_OURS):
            return state
        time.sleep(POLL_INTERVAL)
    return state


def wait_for_server_exit(timeout=1.0):
    """Give a server that received ``stop`` a moment to close its socket."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_server() is not ServerState.READY:
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
    except RuntimeError as error:  # no terminal to ask in
        print(error)
        sys.exit(EXIT_LAUNCHER_FAILED)
    except EOFError:  # end of input at the prompt: no admin, so no server
        print("\nAdmin setup cancelled - server not started")
        sys.exit(EXIT_LAUNCHER_FAILED)
    except KeyboardInterrupt:  # the user gave up: the same code as an interrupted client
        print("\nAdmin setup cancelled - server not started")
        sys.exit(EXIT_INTERRUPTED)
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
    """Wait for the new server to accept connections; exit if it doesn't.

    Exits with ``EXIT_LAUNCHER_FAILED`` after the start-up timeout, and with
    ``EXIT_INTERRUPTED`` on Ctrl+C.
    """
    try:
        state = wait_for_server()
    except KeyboardInterrupt:
        print("\nStart-up cancelled")
        sys.exit(EXIT_INTERRUPTED)
    if state is ServerState.READY:
        return
    if state is ServerState.NOT_OURS:
        # Our server lost the race for the port and will exit with "already in use".
        print(f"Port {HOST}:{PORT} is used by another program - the server could not start")
        sys.exit(EXIT_LAUNCHER_FAILED)
    print(f"Server did not start on {HOST}:{PORT} within {STARTUP_TIMEOUT:.0f} s")
    if background_server is not None:
        print(f"See {SERVER_LOG} for details")
    else:
        # A console window closes when its program exits, taking the error with it. Don't
        # start a second server: the first may just be slow, and both would want the port.
        print("The server window may have closed with an error. To see it, run "
              "`python server.py` in a terminal in the project folder.")
    sys.exit(EXIT_LAUNCHER_FAILED)


def shell_exit_code(returncode):
    """Turn a ``Popen.returncode`` into the code a shell would show.

    On POSIX a child killed by signal N has ``returncode`` -N, but a shell reports 128 + N
    (and ``sys.exit(-2)`` would show up as 254). Windows never gives a negative code.
    """
    return 128 - returncode if returncode < 0 else returncode


def run_client():
    """Run the client in this terminal until it exits; return its exit code."""
    with subprocess.Popen([sys.executable, CLIENT_SCRIPT], cwd=BASE_DIR) as client:
        while True:
            try:
                returncode = client.wait()
                break
            except KeyboardInterrupt:
                # Ctrl+C reaches the client too (same terminal), and it handles it itself:
                # wait for it to exit. subprocess.run would wait only 0.25 s, then kill it
                # and lose its exit code (CPython's subprocess.py, bpo-25942).
                continue
    return shell_exit_code(returncode)


def main():
    """Start a server if needed, run the client; return the client's exit code."""
    # The probe and the client both need the certificate. Load it once now, so a missing or
    # broken file is reported at once, not as a traceback or after a 5 s start-up timeout.
    # Loading it, not os.path.exists(): a file can exist and still be unusable.
    try:
        make_client_context(CERT_FILE)
    except FileNotFoundError:
        print(f"TLS certificate not found ({CERT_FILE}) - see README 'Setup'")
        return EXIT_LAUNCHER_FAILED
    except OSError as error:  # ssl.SSLError (corrupt, not PEM) or PermissionError (unreadable)
        print(f"TLS certificate {CERT_FILE} can't be used: {error} - see README 'Setup'")
        return EXIT_LAUNCHER_FAILED
    state = probe_server()
    if state is ServerState.NOT_OURS:
        print(f"Port {HOST}:{PORT} is used by another program, not this server. "
              "Stop it, or change PORT in config.py.")
        return EXIT_LAUNCHER_FAILED
    if state is ServerState.BUSY:
        # The same as a program that listens but never accepts; no probe can tell them apart.
        print(f"Something on {HOST}:{PORT} accepted the connection but did not answer within "
              f"{PROBE_TIMEOUT:g} s. If it is this server, it is busy with another client - "
              "try again later.")
        return EXIT_LAUNCHER_FAILED

    background_server = None
    # The try starts before the server does: a background server is ours to stop on every
    # way out (a normal end, sys.exit() and Ctrl+C alike). A server in a window, or one that
    # was already running, belongs to the user and is never touched.
    try:
        if state is ServerState.READY:
            print(f"Server already running on {HOST}:{PORT} - reusing it")
        else:
            background_server = start_server()
            wait_until_started(background_server)
        exit_code = run_client()
    finally:
        if background_server is not None:
            stop_background_server(background_server)

    if background_server is None and not wait_for_server_exit():
        print("Server is still running - type 'stop' in a client or press Ctrl+C "
              "in the server window to stop it")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
