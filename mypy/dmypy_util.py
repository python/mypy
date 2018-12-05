"""Shared code between dmypy.py and dmypy_server.py.

This should be pretty lightweight and not depend on other mypy code (other than ipc).
"""

import json
import sys

from typing import Any

if sys.platform == 'win32':
    from multiprocessing.connection import PipeConnection as Connection
else:
    from multiprocessing.connection import Connection

MYPY = False
if MYPY:
    from typing_extensions import Final

STATUS_FILE = '.dmypy.json'  # type: Final


def receive(connection: Connection) -> Any:
    """Receive JSON data from a connection until EOF.

    Raise OSError if the data received is not valid JSON or if it is
    not a dict.
    """
    try:
        bdata = connection.recv_bytes()
    except EOFError:
        pass
    if not bdata:
        raise OSError("No data received")
    try:
        data = json.loads(bdata.decode('utf8'))
    except Exception:
        raise OSError("Data received is not valid JSON")
    if not isinstance(data, dict):
        raise OSError("Data received is not a dict (%s)" % str(type(data)))
    return data
