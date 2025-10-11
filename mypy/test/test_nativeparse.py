import contextlib
import os
import tempfile
import unittest
from collections.abc import Iterator

from mypy import nodes
from mypy.nativeparse import native_parse, parse_to_binary_ast
from mypy.nodes import MypyFile


class TestNativeParse(unittest.TestCase):
    def test_trivial_binary_data(self) -> None:
        with temp_source("print('hello')") as fnam:
            b = parse_to_binary_ast(fnam)
            assert list(b) == [nodes.EXPR_STMT, nodes.CALL_EXPR, nodes.NAME_EXPR, 10] + list(
                b"print"
            ) + [22, nodes.STR_EXPR, 10] + list(b"hello")

    def test_deserialize_hello(self) -> None:
        with temp_source("print('hello')") as fnam:
            node = native_parse(fnam)
            assert isinstance(node, MypyFile)


@contextlib.contextmanager
def temp_source(text: str) -> Iterator[str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, "t.py")
        with open(temp_path, "w") as f:
            f.write(text)
        yield temp_path
