import os
import tempfile
import unittest

from mypy import nodes
from mypy.nativeparse import parse_to_binary_ast


class TestNativeParse(unittest.TestCase):
    def test_hello_world_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, "t.py")
            with open(temp_path, "w") as f:
                f.write("print('hello')")

            b = parse_to_binary_ast(temp_path)
            assert list(b) == [nodes.EXPR_STMT, nodes.CALL_EXPR, nodes.NAME_EXPR, 5] + list(
                b"print"
            ) + [1, nodes.STR_EXPR, 5] + list(b"hello")
