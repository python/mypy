"""Test cases for IR generation."""

from __future__ import annotations

import os.path
import sys
import unittest

from mypy.errors import CompileError
from mypy.nodes import FuncDef
from mypy.test.config import test_temp_dir
from mypy.test.data import DataDrivenTestCase
from mypyc.common import TOP_LEVEL_NAME
from mypyc.ir.pprint import format_func
from mypyc.test.testutil import (
    ICODE_GEN_BUILTINS,
    MypycDataSuite,
    assert_test_output,
    build_ir_for_single_file,
    build_ir_for_single_file2,
    infer_ir_build_options_from_test_name,
    remove_comment_lines,
    replace_word_size,
    use_custom_builtins,
)

files = [
    "irbuild-basic.test",
    "irbuild-int.test",
    "irbuild-bool.test",
    "irbuild-lists.test",
    "irbuild-tuple.test",
    "irbuild-dict.test",
    "irbuild-set.test",
    "irbuild-str.test",
    "irbuild-bytes.test",
    "irbuild-float.test",
    "irbuild-frozenset.test",
    "irbuild-statements.test",
    "irbuild-nested.test",
    "irbuild-classes.test",
    "irbuild-final.test",
    "irbuild-optional.test",
    "irbuild-any.test",
    "irbuild-generics.test",
    "irbuild-try.test",
    "irbuild-strip-asserts.test",
    "irbuild-i64.test",
    "irbuild-i32.test",
    "irbuild-i16.test",
    "irbuild-u8.test",
    "irbuild-vec-i64.test",
    "irbuild-vec-misc.test",
    "irbuild-vec-t.test",
    "irbuild-vec-nested.test",
    "irbuild-vectorcall.test",
    "irbuild-unreachable.test",
    "irbuild-isinstance.test",
    "irbuild-dunders.test",
    "irbuild-singledispatch.test",
    "irbuild-constant-fold.test",
    "irbuild-glue-methods.test",
    "irbuild-math.test",
    "irbuild-weakref.test",
    "irbuild-librt-strings.test",
    "irbuild-librt-random.test",
    "irbuild-base64.test",
    "irbuild-threading.test",
    "irbuild-time.test",
    "irbuild-match.test",
]

if sys.version_info >= (3, 12):
    files.append("irbuild-python312.test")

if sys.version_info >= (3, 14):
    files.append("irbuild-python314.test")

if sys.version_info >= (3, 15):
    files.append("irbuild-python315.test")


class TestGenOps(MypycDataSuite):
    files = files
    base_path = test_temp_dir
    optional_out = True

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        """Perform a runtime checking transformation test case."""
        options = infer_ir_build_options_from_test_name(testcase.name)
        if options is None:
            # Skipped test case
            return
        with use_custom_builtins(os.path.join(self.data_prefix, ICODE_GEN_BUILTINS), testcase):
            expected_output = remove_comment_lines(testcase.output)
            expected_output = replace_word_size(expected_output)
            name = testcase.name
            try:
                ir = build_ir_for_single_file(testcase.input, options)
            except CompileError as e:
                actual = e.messages
            else:
                actual = []
                for fn in ir:
                    if fn.name == TOP_LEVEL_NAME and not name.endswith("_toplevel"):
                        continue
                    actual.extend(format_func(fn))

            assert_test_output(testcase, actual, "Invalid source code output", expected_output)


class TestRedefinedParamSignature(unittest.TestCase):
    def test_widens_native_signature(self) -> None:
        """The native signature must use the (possibly widened) parameter variable type.

        Under --allow-redefinition the variable's type is the join of the
        declaration and every redefinition. The local argument register and any
        closure environment attribute use that wider type, so a narrower
        signature derived from the declared Callable type generates invalid C
        when the argument is stored (https://github.com/python/mypy/issues/22221).
        """
        source = [
            "# flags: --allow-redefinition",
            "def f(n: int):",
            "    def inner():",
            "        nonlocal n",
            "        n = n - 1",
            "        return n",
            "    return inner()",
        ]
        module, tree, _, mapper = build_ir_for_single_file2(source)
        fdef = tree.defs[0]
        assert isinstance(fdef, FuncDef)
        sig = mapper.func_to_decl[fdef].sig
        assert sig.args[0].name == "n"
        assert str(sig.args[0].type) == "union[int, object]"
