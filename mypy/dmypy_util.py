"""Shared code between dmypy.py and dmypy_server.py.

This should be pretty lightweight and not depend on other mypy code.
"""

import json
import socket

from typing import Any

MYPY = False
if MYPY:
    from typing_extensions import Final

STATUS_FILE = '.dmypy.json'  # type: Final


def receive(sock: socket.socket) -> Any:
    """Receive JSON data from a socket until EOF.

    Raise a subclass of OSError if there's a socket exception.

    Raise OSError if the data received is not valid JSON or if it is
    not a dict.
    """
    bdata = bytearray()
    while True:
        more = sock.recv(100000)
        if not more:
            break
        bdata.extend(more)
    if not bdata:
        raise OSError("No data received")
    try:
        data = json.loads(bdata.decode('utf8'))
    except Exception:
        raise OSError("Data received is not valid JSON")
    if not isinstance(data, dict):
        raise OSError("Data received is not a dict (%s)" % str(type(data)))
    return data
