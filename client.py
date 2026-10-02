"""Interactive TCP client: sends commands to the server and prints the JSON replies."""

import json
import socket

from config import ENCODING, HOST, PORT
from protocol import receive_message, send_message


def main():
    try:
        sock = socket.create_connection((HOST, PORT))
    except ConnectionRefusedError:
        print(f"Cannot connect to {HOST}:{PORT} - is the server running?")
        return

    with sock, sock.makefile("r", encoding=ENCODING) as sock_file:
        print(f"Connected to {HOST}:{PORT}. Type 'help' for the list of commands.")
        while True:
            try:
                command = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nDisconnecting")
                return
            if not command:
                continue

            try:
                send_message(sock, {"command": command})
                response = receive_message(sock_file)
            except (ConnectionError, OSError):
                response = None
            if response is None:
                print("Connection closed by the server")
                return

            print(json.dumps(response, indent=2))
            if response.get("status") == "ok" and response.get("command") == "stop":
                print("Server stopped - exiting client")
                return


if __name__ == "__main__":
    main()
