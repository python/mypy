# Very simplified datetime stubs for use in tests

class datetime:
    def __new__(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int = ...,
        minute: int = ...,
        second: int = ...,
        microsecond: int = ...,
        *,
        fold: int = ...,
    ) -> datetime: ...
    def __format__(self, __fmt: str) -> str: ...
