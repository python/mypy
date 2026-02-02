from typing import Final


class Capsule:
    """Defines a C extension capsule that a primitive may require."""

    def __init__(self, name: str) -> None:
        # Module fullname, e.g. 'librt.base64'
        self.name: Final = name

    def __repr__(self) -> str:
        return f"Capsule(name={self.name!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Capsule) and self.name == other.name

    def __hash__(self) -> int:
        return hash(("Capsule", self.name))


class SourceDep:
    """Defines a C source file that a primitive may require.

    Each source file must also have a corresponding .h file (replace .c with .h)
    that gets implicitly #included if the source is used.
    """

    def __init__(self, path: str) -> None:
        # Relative path from mypyc/lib-rt, e.g. 'bytes_extra_ops.c'
        self.path: Final = path

    def __repr__(self) -> str:
        return f"SourceDep(path={self.path!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SourceDep) and self.path == other.path

    def __hash__(self) -> int:
        return hash(("SourceDep", self.path))

    def get_header(self) -> str:
        """Get the header file path by replacing .c with .h"""
        return self.path.replace(".c", ".h")


Dependency = Capsule | SourceDep


LIBRT_STRINGS: Final = Capsule("librt.strings")
LIBRT_BASE64: Final = Capsule("librt.base64")
LIBRT_VECS: Final = Capsule("librt.vecs")

BYTES_EXTRA_OPS: Final = SourceDep("bytes_extra_ops.c")
BYTES_WRITER_EXTRA_OPS: Final = SourceDep("byteswriter_extra_ops.c")
STRING_WRITER_EXTRA_OPS: Final = SourceDep("stringwriter_extra_ops.c")
BYTEARRAY_EXTRA_OPS: Final = SourceDep("bytearray_extra_ops.c")
STR_EXTRA_OPS: Final = SourceDep("str_extra_ops.c")
