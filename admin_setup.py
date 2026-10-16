"""First-start setup: create the first admin account if there is none yet.

The first admin cannot be created over the network, because nobody has admin rights yet.
Access to a terminal on the server machine is the proof of authority instead.
"""

import getpass
import sys

from config import ROLE_ADMIN


def ensure_admin(store, ask_username=input, ask_password=getpass.getpass, interactive=None):
    """Create an admin in ``store`` if none exists; return the new username, or ``None``.

    Asks again after invalid input. Raises ``RuntimeError`` when an admin is needed but
    there is no terminal to ask in. ``KeyboardInterrupt``/``EOFError`` from the prompts
    propagate, so the caller can abort the start.
    """
    if store.has_admin():
        return None
    if interactive is None:
        interactive = sys.stdin is not None and sys.stdin.isatty()
    if not interactive:
        raise RuntimeError(
            "No admin account yet: run 'python server.py' in a terminal once to create it"
        )
    print("No admin account yet - create one now.")
    while True:
        username = ask_username("Admin username: ").strip()
        password = ask_password("Password: ")
        if ask_password("Repeat password: ") != password:
            print("Passwords do not match")
            continue
        try:
            store.create_user(username, password, role=ROLE_ADMIN)
        except ValueError as error:
            print(error)
            continue
        print(f"Admin created: {username}")
        return username
