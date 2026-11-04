"""TCP server with user accounts that answers commands with JSON.

A new connection starts logged out: only the commands marked ``requires_login=False``
(help, register, login) work until the client logs in.

Every connection is wrapped in TLS; the server refuses to start without a certificate.
"""

import datetime
import socket
import ssl
import sys
import threading
import time

from admin_setup import ensure_admin
from config import (
    HOST,
    PORT,
    SERVER_CREATED,
    SERVER_VERSION,
    TLS_CERT_FILE,
    TLS_HANDSHAKE_TIMEOUT,
    TLS_KEY_FILE,
)
from protocol import receive_message, send_message
from throttle import LoginThrottle
from users import UserStore

OPENSSL_COMMAND = (
    'MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes '
    f'-keyout {TLS_KEY_FILE} -out {TLS_CERT_FILE} -days 365 -subj "/CN=localhost" '
    '-addext "subjectAltName=IP:127.0.0.1,DNS:localhost"'
)


def make_server_context(cert_file=TLS_CERT_FILE, key_file=TLS_KEY_FILE):
    """Build the server-side TLS context; raises ``FileNotFoundError`` if a file is missing."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_file, key_file)
    return context


class Server:
    def __init__(self, host=HOST, port=PORT, users=None, tls_context=None, login_throttle=None):
        self.start_time = time.time()
        self.users = users if users is not None else UserStore()
        self.login_throttle = login_throttle if login_throttle is not None else LoginThrottle()
        # Built before binding, so a missing certificate never leaves a socket open.
        self.tls_context = tls_context if tls_context is not None else make_server_context()
        self.running = False
        # Set once listen() has run, so callers (the tests) know they can connect.
        self.listening = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        # Actual address - differs from the requested one when port=0 (used by tests).
        self.address = self.sock.getsockname()
        # name -> (handler, description, requires_login)
        self.commands = {
            "register": (self.cmd_register, "Creates a user account: register <username>", False),
            "login": (self.cmd_login, "Logs in to an account: login <username>", False),
            "logout": (self.cmd_logout, "Logs out of the current account", True),
            "uptime": (self.cmd_uptime, "Returns how long the server has been running", True),
            "info": (self.cmd_info, "Returns the server version and its creation date", True),
            "help": (self.cmd_help, "Returns the list of commands you can use now", False),
            "stop": (self.cmd_stop, "Stops both the server and the client", True),
        }

    def cmd_uptime(self, args, session):
        seconds = time.time() - self.start_time
        return {
            "uptime_seconds": round(seconds, 2),
            "uptime": str(datetime.timedelta(seconds=int(seconds))),
        }

    def cmd_info(self, args, session):
        return {"version": SERVER_VERSION, "created": SERVER_CREATED}

    def cmd_help(self, args, session):
        logged_in = session["user"] is not None
        return {
            name: description
            for name, (_, description, requires_login) in self.commands.items()
            if logged_in or not requires_login
        }

    def cmd_register(self, args, session):
        self.users.create_user(args.get("username"), args.get("password"))
        return {"message": f"User created: {args['username']}"}

    def cmd_login(self, args, session):
        if session["user"] is not None:
            raise ValueError(f"Already logged in as {session['user']}, logout first")
        username = args.get("username")
        if not isinstance(username, str):
            raise ValueError("Invalid username or password")
        # Checked before hashing: a locked-out username costs no PBKDF2 work.
        self.login_throttle.check(username)
        if not self.users.verify_password(username, args.get("password")):
            self.login_throttle.record_failure(username)
            # Same message for unknown user and wrong password: don't reveal which usernames exist.
            raise ValueError("Invalid username or password")
        self.login_throttle.record_success(username)
        session["user"] = username
        return {"message": f"Logged in as {username}", "username": username}

    def cmd_logout(self, args, session):
        username, session["user"] = session["user"], None
        return {"message": f"Logged out {username}"}

    def cmd_stop(self, args, session):
        self.running = False
        return {"message": "Server stopping"}

    def handle_request(self, request, session):
        """Build the response dict for a single decoded request.

        ``session`` holds per-connection state: ``{"user": <username or None>}``.
        """
        if not isinstance(request, dict) or not isinstance(request.get("command"), str):
            return {"status": "error", "message": 'Request must be {"command": "<name>"}'}
        args = request.get("args", {})
        if not isinstance(args, dict):
            return {"status": "error", "message": '"args" must be a JSON object'}
        name = request["command"].strip().lower()
        if name not in self.commands:
            return {"status": "error", "message": f"Unknown command: {name}"}
        handler, _, requires_login = self.commands[name]
        if requires_login and session["user"] is None:
            return {
                "status": "error",
                "command": name,
                "message": "Login required: use 'login <username>' or 'register <username>'",
            }
        try:
            data = handler(args, session)
        except ValueError as error:
            return {"status": "error", "command": name, "message": str(error)}
        return {"status": "ok", "command": name, "data": data}

    def handle_client(self, conn):
        """Serve one client until it disconnects or sends ``stop``.

        A network error (``OSError``, which includes ``ConnectionError`` and ``ssl.SSLError``)
        on a read *or* a send ends only this connection; it never reaches ``serve_forever``.
        """
        session = {"user": None}  # every connection starts logged out
        with conn, conn.makefile("rb") as conn_file:
            while self.running:
                try:
                    request = receive_message(conn_file)
                except (ValueError, RecursionError):
                    # A malformed line (bad UTF-8, bad JSON, too-long int, too-deep nesting)
                    # rejects only that message: the line is already consumed, so the session
                    # goes on. Only build the reply here: an error raised inside a handler
                    # would skip the sibling ``except OSError`` and escape.
                    response = {
                        "status": "error",
                        "message": "Invalid message: expected one line of UTF-8 JSON",
                    }
                except OSError:
                    return
                else:
                    if request is None:
                        return
                    response = self.handle_request(request, session)
                try:
                    send_message(conn, response)
                except OSError:
                    return

    def tls_handshake(self, conn, addr):
        """Wrap an accepted connection in TLS; return ``None`` if the handshake fails.

        Each accepted connection is wrapped, not the listening socket, so one bad client
        (plain TCP, wrong certificate, silence) only affects itself.
        """
        conn.settimeout(TLS_HANDSHAKE_TIMEOUT)
        try:
            tls_conn = self.tls_context.wrap_socket(conn, server_side=True)
        except (ssl.SSLError, OSError) as error:
            print(f"TLS handshake failed: {addr[0]}:{addr[1]} ({error})")
            conn.close()
            return None
        tls_conn.settimeout(None)  # back to blocking for the request loop
        return tls_conn

    def serve_forever(self):
        self.running = True
        self.sock.listen()
        self.listening.set()
        # Wake up periodically so Ctrl+C works on Windows, where a blocking accept()
        # is not interrupted by KeyboardInterrupt. Accepted sockets stay blocking.
        self.sock.settimeout(1.0)
        print(f"Server listening on {self.address[0]}:{self.address[1]}")
        try:
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                except socket.timeout:
                    continue
                tls_conn = self.tls_handshake(conn, addr)
                if tls_conn is None:
                    continue
                print(f"Client connected: {addr[0]}:{addr[1]}")
                self.handle_client(tls_conn)
                print(f"Client disconnected: {addr[0]}:{addr[1]}")
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            self.listening.clear()
            self.sock.close()
            print("Server stopped")


if __name__ == "__main__":
    try:
        server = Server()
    except FileNotFoundError:
        # Fail closed: never fall back to plain text.
        print(f"TLS certificate or key not found ({TLS_CERT_FILE}, {TLS_KEY_FILE}).")
        print("Create them once (Git Bash) in the project folder:")
        print(f"  {OPENSSL_COMMAND}")
        sys.exit(1)
    try:
        ensure_admin(server.users)
    except RuntimeError as error:  # no terminal to ask in (e.g. started in the background)
        server.sock.close()
        print(error)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        server.sock.close()
        print("\nAdmin setup cancelled - server not started")
        sys.exit(1)
    server.serve_forever()
