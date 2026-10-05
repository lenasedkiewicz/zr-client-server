"""TCP server that answers the register, uptime, info, help and stop commands with JSON."""

import datetime
import json
import socket
import time

from config import ENCODING, HOST, PORT, SERVER_CREATED, SERVER_VERSION
from protocol import receive_message, send_message
from users import UserStore


class Server:
    def __init__(self, host=HOST, port=PORT, users=None):
        self.start_time = time.time()
        self.users = users if users is not None else UserStore()
        self.running = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        # Actual address - differs from the requested one when port=0 (used by tests).
        self.address = self.sock.getsockname()
        self.commands = {
            "register": (self.cmd_register, "Creates a user account: register <username>"),
            "uptime": (self.cmd_uptime, "Returns how long the server has been running"),
            "info": (self.cmd_info, "Returns the server version and its creation date"),
            "help": (self.cmd_help, "Returns the list of available commands"),
            "stop": (self.cmd_stop, "Stops both the server and the client"),
        }

    def cmd_uptime(self, args):
        seconds = time.time() - self.start_time
        return {
            "uptime_seconds": round(seconds, 2),
            "uptime": str(datetime.timedelta(seconds=int(seconds))),
        }

    def cmd_info(self, args):
        return {"version": SERVER_VERSION, "created": SERVER_CREATED}

    def cmd_help(self, args):
        return {name: description for name, (_, description) in self.commands.items()}

    def cmd_register(self, args):
        self.users.create_user(args.get("username"), args.get("password"))
        return {"message": f"User created: {args['username']}"}

    def cmd_stop(self, args):
        self.running = False
        return {"message": "Server stopping"}

    def handle_request(self, request):
        """Build the response dict for a single decoded request."""
        if not isinstance(request, dict) or not isinstance(request.get("command"), str):
            return {"status": "error", "message": 'Request must be {"command": "<name>"}'}
        args = request.get("args", {})
        if not isinstance(args, dict):
            return {"status": "error", "message": '"args" must be a JSON object'}
        name = request["command"].strip().lower()
        if name not in self.commands:
            return {"status": "error", "message": f"Unknown command: {name}"}
        handler, _ = self.commands[name]
        try:
            data = handler(args)
        except ValueError as error:
            return {"status": "error", "command": name, "message": str(error)}
        return {"status": "ok", "command": name, "data": data}

    def handle_client(self, conn):
        """Serve one client until it disconnects or sends ``stop``."""
        with conn, conn.makefile("r", encoding=ENCODING) as conn_file:
            while self.running:
                try:
                    request = receive_message(conn_file)
                except json.JSONDecodeError:
                    send_message(conn, {"status": "error", "message": "Invalid JSON"})
                    continue
                except (ConnectionError, OSError):
                    return
                if request is None:
                    return
                send_message(conn, self.handle_request(request))

    def serve_forever(self):
        self.running = True
        self.sock.listen()
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
                print(f"Client connected: {addr[0]}:{addr[1]}")
                self.handle_client(conn)
                print(f"Client disconnected: {addr[0]}:{addr[1]}")
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            self.sock.close()
            print("Server stopped")


if __name__ == "__main__":
    Server().serve_forever()
