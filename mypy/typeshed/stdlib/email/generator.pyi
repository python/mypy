from _typeshed import SupportsWrite
from email.message import Message
from email.policy import Policy

__all__ = ["Generator", "DecodedGenerator", "BytesGenerator"]

class Generator:
    def clone(self, fp: SupportsWrite[str]) -> Generator: ...
    def write(self, s: str) -> None: ...
    def __init__(
        self,
        outfp: SupportsWrite[str],
        mangle_from_: bool | None = ...,
        maxheaderlen: int | None = ...,
        *,
        policy: Policy | None = ...,
    ) -> None: ...
    def flatten(self, msg: Message, unixfrom: bool = ..., linesep: str | None = ...) -> None: ...

class BytesGenerator:
    def clone(self, fp: SupportsWrite[bytes]) -> BytesGenerator: ...
    def write(self, s: str) -> None: ...
    def __init__(
        self,
        outfp: SupportsWrite[bytes],
        mangle_from_: bool | None = ...,
        maxheaderlen: int | None = ...,
        *,
        policy: Policy | None = ...,
    ) -> None: ...
    def flatten(self, msg: Message, unixfrom: bool = ..., linesep: str | None = ...) -> None: ...

class DecodedGenerator(Generator):
    def __init__(
        self,
        outfp: SupportsWrite[str],
        mangle_from_: bool | None = ...,
        maxheaderlen: int | None = ...,
        fmt: str | None = ...,
        *,
        policy: Policy | None = ...,
    ) -> None: ...
