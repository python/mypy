# Stubs for socketserver

# NOTE: These are incomplete!

from typing import Tuple

class BaseRequestHandler(): ...

class TCPServer():
    def __init__(
        self,
        server_address: Tuple[str, int],
        request_handler: BaseRequestHandler,
        bind_and_activate: bool = True,
    ) -> None: ...
