from typing import Final, Union


class Capsule:
    """Defines a C extension capsule that a primitive may require."""

    def __init__(self, name: str) -> None:
        self.name: Final = name

    def __repr__(self) -> str:
        return f"Capsule(name={self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Capsule) and self.name == other.name

    def __hash__(self) -> int:
        return hash(("Capsule", self.name))


class SourceDep:
    """Defines a C source file that a primitive may require."""

    def __init__(self, path: str) -> None:
        self.path: Final = path

    def __repr__(self) -> str:
        return f"SourceDep(path={self.path!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SourceDep) and self.path == other.path

    def __hash__(self) -> int:
        return hash(("SourceDep", self.path))


Dependency = Union[Capsule, SourceDep]


LIBRT_STRINGS: Final = Capsule("librt.strings")
LIBRT_BASE64: Final = Capsule("librt.base64")
