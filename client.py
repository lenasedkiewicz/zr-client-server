"""Interactive TLS client: sends commands to the server and prints the JSON replies."""

import getpass
import json
import socket
import ssl

from config import (
    CONNECT_TIMEOUT,
    HANDSHAKE_WAIT_TIMEOUT,
    HOST,
    PORT,
    REPLY_TIMEOUT,
    TLS_CERT_FILE,
)
from protocol import ConnectionClosed, MessageTooLong, receive_message, send_message


def build_request(line):
    """Turn a typed line into a request dict, or return None if it is incomplete.

    Commands that need a password ask for it with ``getpass``, so it is not echoed.
    """
    name, *params = line.split()
    if name.lower() == "register":
        if len(params) != 1:
            print("Usage: register <username>")
            return None
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords do not match")
            return None
        return {"command": "register", "args": {"username": params[0], "password": password}}
    if name.lower() == "login":
        if len(params) != 1:
            print("Usage: login <username>")
            return None
        password = getpass.getpass("Password: ")
        return {"command": "login", "args": {"username": params[0], "password": password}}
    return {"command": line}


def make_client_context(cafile=TLS_CERT_FILE):
    """Trust only our own certificate (pinning); certificate and hostname checks stay on."""
    return ssl.create_default_context(cafile=cafile)


def check_response(response):
    """Raise ``ValueError`` unless ``response`` has the shape this client reads.

    The server is a peer on the network, so its replies are checked the way the server checks
    requests. Only the fields the client uses are checked: an object whose ``status`` is
    ``"ok"`` or ``"error"``, and for a successful login a string ``data.username``.
    """
    if not isinstance(response, dict):
        raise ValueError(f"expected a JSON object, got {json.dumps(response)[:40]}")
    if response.get("status") not in ("ok", "error"):
        raise ValueError('"status" must be "ok" or "error"')
    if response["status"] == "ok" and response.get("command") == "login":
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("username"), str):
            raise ValueError('a login reply must have a string "data.username"')


def connect(context):
    """Open the TLS connection to the server, or print why not and return None.

    Every wait has a limit: the connect, the handshake, and then each send and reply.
    """
    try:
        raw_sock = socket.create_connection((HOST, PORT), timeout=CONNECT_TIMEOUT)
    except ConnectionRefusedError:
        print(f"Cannot connect to {HOST}:{PORT} - is the server running?")
        return None
    except OSError as error:
        # Timed out, host or network unreachable, unknown host name (socket.gaierror), ...
        print(f"Cannot connect to {HOST}:{PORT}: {error}")
        return None
    # The TLS socket inherits the raw socket's timeout, so it limits the handshake.
    raw_sock.settimeout(HANDSHAKE_WAIT_TIMEOUT)
    try:
        sock = context.wrap_socket(raw_sock, server_hostname=HOST)
    except ssl.SSLCertVerificationError as error:
        raw_sock.close()
        print(f"Server certificate rejected: {error.verify_message}")
        return None
    except TimeoutError:
        # Before OSError, its parent. A connect that worked only means we are in the
        # server's listen() backlog; it serves one client at a time.
        raw_sock.close()
        print(
            f"No answer from the server within {HANDSHAKE_WAIT_TIMEOUT:g} s - it may be busy "
            "with another client. Try again later."
        )
        return None
    except OSError as error:
        raw_sock.close()
        print(f"TLS handshake failed: {error}")
        return None
    # From now on the limit is per send and per reply. input() doesn't touch the socket, so
    # a person thinking at the prompt is never timed out.
    sock.settimeout(REPLY_TIMEOUT)
    return sock


def main():
    try:
        context = make_client_context()
    except FileNotFoundError:
        print(f"TLS certificate not found ({TLS_CERT_FILE}) - see README 'Setup'")
        return
    try:
        sock = connect(context)
        if sock is not None:
            run_session(sock)
    except KeyboardInterrupt:
        # Ctrl+C away from the prompt: while connecting, during the handshake (which waits
        # while the server is busy with another client) or while waiting for a reply.
        # run_session's `with` has already closed the socket.
        print("\nInterrupted")


def run_session(sock):
    """Read commands, send them and print the replies until the user or the server ends it."""
    with sock, sock.makefile("rb") as sock_file:
        print(f"Connected to {HOST}:{PORT} over TLS. Type 'help' for the list of commands.")
        user = None  # shown in the prompt; mirrors the server-side session
        while True:
            try:
                command = input(f"{user}> " if user else "> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nDisconnecting")
                return
            if not command:
                continue
            try:
                request = build_request(command)
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled")
                continue
            if request is None:
                continue

            try:
                send_message(sock, request)
                response = receive_message(sock_file)
                check_response(response)
            except TimeoutError:
                # Before OSError, its parent. After a timeout the makefile() stream may be
                # inconsistent, and a late reply would be read as the next one: disconnect.
                print(f"No reply from the server within {REPLY_TIMEOUT:g} s - disconnecting")
                return
            except (ConnectionClosed, OSError):
                print("Connection closed by the server")
                return
            except MessageTooLong:
                # The rest of the line is still unread; reading on would parse it as a reply.
                print("Reply from the server is too long - disconnecting")
                return
            except (ValueError, RecursionError) as error:
                # Bad UTF-8 or JSON, a huge int, deep nesting, or the wrong shape. The server
                # is broken or not ours, so the session's state can't be trusted any more.
                print(f"Unexpected reply from the server: {error} - disconnecting")
                return

            print(json.dumps(response, indent=2))
            if response.get("status") != "ok":
                continue
            if response.get("command") == "login":
                user = response["data"]["username"]
            elif response.get("command") == "logout":
                user = None
            elif response.get("command") == "stop":
                print("Server stopped - exiting client")
                return


if __name__ == "__main__":
    main()
