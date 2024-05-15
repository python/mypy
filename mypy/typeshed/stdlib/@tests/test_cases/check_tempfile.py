from __future__ import annotations

import io
import sys
from tempfile import TemporaryFile, _TemporaryFileWrapper
from typing_extensions import assert_type

if sys.platform == "win32":
    assert_type(TemporaryFile(), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile("w+"), _TemporaryFileWrapper[str])
    assert_type(TemporaryFile("w+b"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile("wb"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile("rb"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile("wb", 0), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile(mode="w+"), _TemporaryFileWrapper[str])
    assert_type(TemporaryFile(mode="w+b"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile(mode="wb"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile(mode="rb"), _TemporaryFileWrapper[bytes])
    assert_type(TemporaryFile(buffering=0), _TemporaryFileWrapper[bytes])
else:
    assert_type(TemporaryFile(), io.BufferedRandom)
    assert_type(TemporaryFile("w+"), io.TextIOWrapper)
    assert_type(TemporaryFile("w+b"), io.BufferedRandom)
    assert_type(TemporaryFile("wb"), io.BufferedWriter)
    assert_type(TemporaryFile("rb"), io.BufferedReader)
    assert_type(TemporaryFile("wb", 0), io.FileIO)
    assert_type(TemporaryFile(mode="w+"), io.TextIOWrapper)
    assert_type(TemporaryFile(mode="w+b"), io.BufferedRandom)
    assert_type(TemporaryFile(mode="wb"), io.BufferedWriter)
    assert_type(TemporaryFile(mode="rb"), io.BufferedReader)
    assert_type(TemporaryFile(buffering=0), io.FileIO)
