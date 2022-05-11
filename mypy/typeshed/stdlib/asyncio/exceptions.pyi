__all__ = (
    "CancelledError",
    "InvalidStateError",
    "TimeoutError",
    "IncompleteReadError",
    "LimitOverrunError",
    "SendfileNotAvailableError",
)

class CancelledError(BaseException): ...
class TimeoutError(Exception): ...
class InvalidStateError(Exception): ...
class SendfileNotAvailableError(RuntimeError): ...

class IncompleteReadError(EOFError):
    expected: int | None
    partial: bytes
    def __init__(self, partial: bytes, expected: int | None) -> None: ...

class LimitOverrunError(Exception):
    consumed: int
    def __init__(self, message: str, consumed: int) -> None: ...
