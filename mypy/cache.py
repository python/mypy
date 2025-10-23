from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from librt.internal import (
    Buffer as Buffer,
    read_bool as read_bool,
    read_bytes as read_bytes,
    read_float as read_float,
    read_int as read_int,
    read_str as read_str,
    read_tag as read_tag,
    write_bool as write_bool,
    write_bytes as write_bytes,
    write_float as write_float,
    write_int as write_int,
    write_str as write_str,
    write_tag as write_tag,
)
from mypy_extensions import u8

from mypy.util import json_dumps, json_loads


class CacheMeta:
    """Class representing cache metadata for a module."""

    def __init__(
        self,
        *,
        id: str,
        path: str,
        mtime: int,
        size: int,
        hash: str,
        dependencies: list[str],
        data_mtime: int,
        data_file: str,
        suppressed: list[str],
        options: dict[str, object],
        dep_prios: list[int],
        dep_lines: list[int],
        dep_hashes: list[bytes],
        interface_hash: bytes,
        error_lines: list[str],
        version_id: str,
        ignore_all: bool,
        plugin_data: Any,
    ) -> None:
        self.id = id
        self.path = path
        self.mtime = mtime  # source file mtime
        self.size = size  # source file size
        self.hash = hash  # source file hash (as a hex string for historical reasons)
        self.dependencies = dependencies  # names of imported modules
        self.data_mtime = data_mtime  # mtime of data_file
        self.data_file = data_file  # path of <id>.data.json or <id>.data.ff
        self.suppressed = suppressed  # dependencies that weren't imported
        self.options = options  # build options snapshot
        # dep_prios and dep_lines are both aligned with dependencies + suppressed
        self.dep_prios = dep_prios
        self.dep_lines = dep_lines
        # dep_hashes list is aligned with dependencies only
        self.dep_hashes = dep_hashes  # list of interface_hash for dependencies
        self.interface_hash = interface_hash  # hash representing the public interface
        self.error_lines = error_lines
        self.version_id = version_id  # mypy version for cache invalidation
        self.ignore_all = ignore_all  # if errors were ignored
        self.plugin_data = plugin_data  # config data from plugins

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "mtime": self.mtime,
            "size": self.size,
            "hash": self.hash,
            "data_mtime": self.data_mtime,
            "dependencies": self.dependencies,
            "suppressed": self.suppressed,
            "options": self.options,
            "dep_prios": self.dep_prios,
            "dep_lines": self.dep_lines,
            "dep_hashes": [dep.hex() for dep in self.dep_hashes],
            "interface_hash": self.interface_hash.hex(),
            "error_lines": self.error_lines,
            "version_id": self.version_id,
            "ignore_all": self.ignore_all,
            "plugin_data": self.plugin_data,
        }

    @classmethod
    def deserialize(cls, meta: dict[str, Any], data_file: str) -> CacheMeta | None:
        try:
            return CacheMeta(
                id=meta["id"],
                path=meta["path"],
                mtime=meta["mtime"],
                size=meta["size"],
                hash=meta["hash"],
                dependencies=meta["dependencies"],
                data_mtime=meta["data_mtime"],
                data_file=data_file,
                suppressed=meta["suppressed"],
                options=meta["options"],
                dep_prios=meta["dep_prios"],
                dep_lines=meta["dep_lines"],
                dep_hashes=[bytes.fromhex(dep) for dep in meta["dep_hashes"]],
                interface_hash=bytes.fromhex(meta["interface_hash"]),
                error_lines=meta["error_lines"],
                version_id=meta["version_id"],
                ignore_all=meta["ignore_all"],
                plugin_data=meta["plugin_data"],
            )
        except (KeyError, ValueError):
            return None

    def write(self, data: Buffer) -> None:
        write_str(data, self.id)
        write_str(data, self.path)
        write_int(data, self.mtime)
        write_int(data, self.size)
        write_str(data, self.hash)
        write_str_list(data, self.dependencies)
        write_int(data, self.data_mtime)
        write_str_list(data, self.suppressed)
        write_bytes(data, json_dumps(self.options))
        write_int_list(data, self.dep_prios)
        write_int_list(data, self.dep_lines)
        write_bytes_list(data, self.dep_hashes)
        write_bytes(data, self.interface_hash)
        write_str_list(data, self.error_lines)
        write_str(data, self.version_id)
        write_bool(data, self.ignore_all)
        write_bytes(data, json_dumps(self.plugin_data))

    @classmethod
    def read(cls, data: Buffer, data_file: str) -> CacheMeta | None:
        try:
            return CacheMeta(
                id=read_str(data),
                path=read_str(data),
                mtime=read_int(data),
                size=read_int(data),
                hash=read_str(data),
                dependencies=read_str_list(data),
                data_mtime=read_int(data),
                data_file=data_file,
                suppressed=read_str_list(data),
                options=json_loads(read_bytes(data)),
                dep_prios=read_int_list(data),
                dep_lines=read_int_list(data),
                dep_hashes=read_bytes_list(data),
                interface_hash=read_bytes(data),
                error_lines=read_str_list(data),
                version_id=read_str(data),
                ignore_all=read_bool(data),
                plugin_data=json_loads(read_bytes(data)),
            )
        except ValueError:
            return None


# Always use this type alias to refer to type tags.
Tag = u8

LITERAL_INT: Final[Tag] = 1
LITERAL_STR: Final[Tag] = 2
LITERAL_BOOL: Final[Tag] = 3
LITERAL_FLOAT: Final[Tag] = 4
LITERAL_COMPLEX: Final[Tag] = 5
LITERAL_NONE: Final[Tag] = 6


def read_literal(data: Buffer, tag: Tag) -> int | str | bool | float:
    if tag == LITERAL_INT:
        return read_int(data)
    elif tag == LITERAL_STR:
        return read_str(data)
    elif tag == LITERAL_BOOL:
        return read_bool(data)
    elif tag == LITERAL_FLOAT:
        return read_float(data)
    assert False, f"Unknown literal tag {tag}"


def write_literal(data: Buffer, value: int | str | bool | float | complex | None) -> None:
    if isinstance(value, bool):
        write_tag(data, LITERAL_BOOL)
        write_bool(data, value)
    elif isinstance(value, int):
        write_tag(data, LITERAL_INT)
        write_int(data, value)
    elif isinstance(value, str):
        write_tag(data, LITERAL_STR)
        write_str(data, value)
    elif isinstance(value, float):
        write_tag(data, LITERAL_FLOAT)
        write_float(data, value)
    elif isinstance(value, complex):
        write_tag(data, LITERAL_COMPLEX)
        write_float(data, value.real)
        write_float(data, value.imag)
    else:
        write_tag(data, LITERAL_NONE)


def read_int_opt(data: Buffer) -> int | None:
    if read_bool(data):
        return read_int(data)
    return None


def write_int_opt(data: Buffer, value: int | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_int(data, value)
    else:
        write_bool(data, False)


def read_str_opt(data: Buffer) -> str | None:
    if read_bool(data):
        return read_str(data)
    return None


def write_str_opt(data: Buffer, value: str | None) -> None:
    if value is not None:
        write_bool(data, True)
        write_str(data, value)
    else:
        write_bool(data, False)


def read_int_list(data: Buffer) -> list[int]:
    size = read_int(data)
    return [read_int(data) for _ in range(size)]


def write_int_list(data: Buffer, value: list[int]) -> None:
    write_int(data, len(value))
    for item in value:
        write_int(data, item)


def read_str_list(data: Buffer) -> list[str]:
    size = read_int(data)
    return [read_str(data) for _ in range(size)]


def write_str_list(data: Buffer, value: Sequence[str]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str(data, item)


def read_bytes_list(data: Buffer) -> list[bytes]:
    size = read_int(data)
    return [read_bytes(data) for _ in range(size)]


def write_bytes_list(data: Buffer, value: Sequence[bytes]) -> None:
    write_int(data, len(value))
    for item in value:
        write_bytes(data, item)


def read_str_opt_list(data: Buffer) -> list[str | None]:
    size = read_int(data)
    return [read_str_opt(data) for _ in range(size)]


def write_str_opt_list(data: Buffer, value: list[str | None]) -> None:
    write_int(data, len(value))
    for item in value:
        write_str_opt(data, item)
