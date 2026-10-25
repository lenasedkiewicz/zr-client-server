---
id: 003
title: What an except clause catches (and why a sibling handler can't)
date: 2026-10-25
asked-during: 009 — fix: keep serving when sending a reply to a client fails
tags: [python, exceptions, try-except, exception-hierarchy, exception-chaining]
---

# What an except clause catches (and why a sibling handler can't)

## What it is
A `try` statement has one **`try` body** and a list of `except` clauses. Python handles an
exception from the body like this:

1. It checks the `except` clauses **in order** and picks the **first** one whose class
   matches. A class matches if the exception is an instance of it, so `except OSError`
   matches every subclass: `ConnectionError`, `BrokenPipeError`, `ConnectionResetError`,
   `ssl.SSLError`.
2. It runs that clause's block. Once a clause is chosen, the search is **over**.
3. If the handler block raises a new exception, the remaining `except` clauses of the same
   `try` are **not** searched. The new exception goes outward, as if the whole `try`
   statement had raised it.

So the `except` clauses only guard the `try` body. They don't guard each other, the
`else` block or the code after the `try`.

```python
try:
    int("x")                         # raises ValueError
except ValueError:
    print("handling ValueError")
    raise OSError("send failed")     # raised INSIDE a handler
except OSError:
    print("caught OSError")          # never runs
```

Output: `handling ValueError`, then the `ValueError` traceback, the line
**"During handling of the above exception, another exception occurred:"**, and the
`OSError` traceback. That line (implicit *exception chaining*) is the sign that an
exception escaped from a handler.

## Where it shows up in zr-client-server
Before journal 009, `handle_client` sent the "Invalid JSON" reply *inside*
`except json.JSONDecodeError`. Its neighbour, `except (ConnectionError, OSError)`, looked
as if it protected that send, but it couldn't. The normal reply was sent after the `try`
statement, so nothing covered it either. A client that reset the connection crashed the
whole server. The fix (`server.py:142`) only *builds* the reply in the handler and sends it
in its own `try ... except OSError` (`server.py:163`).

## Rules of thumb
- **Keep handler blocks trivial.** Set a variable or `return`. Do the risky work after the
  `try`, inside its own `try` if needed.
- **Use `else:`** for code that should run only when the body succeeded, and whose
  exceptions those handlers shouldn't catch (here: `handle_request`).
- **Catch the narrowest correct class.** `except (ConnectionError, OSError)` is the same as
  `except OSError`, because the first is a subclass of the second. With *separate* clauses,
  put the subclass first, or the parent clause catches everything.
- **`raise New(...) from err`** when you mean to translate an exception. The traceback
  then reads "direct cause" instead of "during handling".

## Interview answer
"An `except` clause only covers the `try` body it's attached to. Python picks the first
matching clause and runs it. If that handler raises, its siblings aren't checked, and the
new exception propagates out of the whole `try`, with the old one attached as context. In
my socket server this meant a send inside the `JSONDecodeError` handler wasn't protected by
the `except OSError` next to it. One client resetting the connection took the whole server
down. I fixed it by only building the reply in the handler and sending it in its own
narrow `try`."

## Read more
- [The try statement](https://docs.python.org/3/reference/compound_stmts.html#the-try-statement): Python Language Reference · the exact rules: clauses searched in turn, `else` exceptions not handled by the preceding clauses
- [Exception chaining](https://docs.python.org/3/tutorial/errors.html#exception-chaining): Python tutorial · "During handling of the above exception…" versus `raise … from`
- [Exception hierarchy](https://docs.python.org/3/library/exceptions.html#exception-hierarchy): Python docs · where `ConnectionError` and its subclasses sit under `OSError`
- [Python Try and Except Statements](https://www.freecodecamp.org/news/python-try-and-except-statements-how-to-handle-exceptions-in-python/): freeCodeCamp · beginner walk-through of `try`/`except`/`else`/`finally`
