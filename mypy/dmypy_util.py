"""Shared code between dmypy.py and dmypy_server.py.

This should be pretty lightweight and not depend on other mypy code (other than ipc).
"""

from __future__ import annotations

import json
from typing import Any, Final

from mypy.ipc import IPCBase

DEFAULT_STATUS_FILE: Final = ".dmypy.json"


def receive(connection: IPCBase) -> Any:
    """Receive single JSON data frame from a connection.

    Raise OSError if the data received is not valid JSON or if it is
    not a dict.
    """
    bdata = connection.read()
    if not bdata:
        raise OSError("No data received")
    try:
        data = json.loads(bdata)
    except Exception as e:
        raise OSError("Data received is not valid JSON") from e
    if not isinstance(data, dict):
        raise OSError(f"Data received is not a dict ({type(data)})")
    return data

def send(connection: IPCBase, data: Any) -> None:
    """Send data to a connection encoded and framed.

    The data must be JSON-serializable. We assume that a single send call is a
    single frame to be sent on the connect.
    As an easy way to separate frames, we urlencode them and separate by space.
    Last frame also has a trailing space.
    """
    connection.write(json.dumps(data))
