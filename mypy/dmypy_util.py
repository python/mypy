"""Shared code between dmypy.py and dmypy_server.py.

This should be pretty lightweight and not depend on other mypy code.
"""

import json
import socket

from typing import Any

STATUS_FILE = 'dmypy.json'


def receive(sock: socket.socket) -> Any:
    """Receive JSON data from a socket until EOF."""
    bdata = bytearray()
    while True:
        more = sock.recv(100000)
        if not more:
            break
        bdata.extend(more)
    if not bdata:
        raise OSError("No data received")
    data = json.loads(bdata.decode('utf8'))
    if not isinstance(data, dict):
        raise OSError("Data received is not a dict (%s)" % str(type(data)))
    return data
