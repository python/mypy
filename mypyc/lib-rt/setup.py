"""Build script for mypyc C runtime library and C API unit tests.

The tests are written in C++ and use the Google Test framework.
"""

from __future__ import annotations

import os
import subprocess
import sys
from distutils import ccompiler, sysconfig
from typing import Any

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

C_APIS_TO_TEST = [
    "init.c",
    "int_ops.c",
    "float_ops.c",
    "list_ops.c",
    "exc_ops.c",
    "generic_ops.c",
    "pythonsupport.c",
]


class BuildExtGtest(build_ext):
    def get_library_names(self) -> list[str]:
        return ["gtest"]

    def run(self) -> None:
        # Build Google Test, the C++ framework we use for testing C code.
        # The source code for Google Test is copied to this repository.
        gtest_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "external", "googletest")
        )
        os.makedirs(self.build_temp, exist_ok=True)
        subprocess.check_call(
            ["make", "-f", os.path.join(gtest_dir, "make", "Makefile"), f"GTEST_DIR={gtest_dir}"],
            cwd=self.build_temp,
        )
        self.library_dirs = [self.build_temp]
        return build_ext.run(self)


if "--run-capi-tests" in sys.argv:
    sys.argv.pop()

    kwargs: dict[str, Any]
    if sys.platform == "darwin":
        kwargs = {"language": "c++"}
        compile_args = []
    else:
        kwargs = {}
        compile_args = ["--std=c++11"]

    setup(
        name="test_capi",
        version="0.1",
        ext_modules=[
            Extension(
                "test_capi",
                ["test_capi.cc"] + C_APIS_TO_TEST,
                depends=["CPy.h", "mypyc_util.h", "pythonsupport.h"],
                extra_compile_args=["-Wno-unused-function", "-Wno-sign-compare"] + compile_args,
                libraries=["gtest"],
                include_dirs=["../external/googletest", "../external/googletest/include"],
                **kwargs,
            )
        ],
        cmdclass={"build_ext": BuildExtGtest},
    )
else:
    # TODO: we need a way to share our preferred C flags and get_extension() logic with
    # mypyc/build.py without code duplication.
    compiler = ccompiler.new_compiler()
    sysconfig.customize_compiler(compiler)
    cflags: list[str] = []
    if compiler.compiler_type == "unix":
        cflags += ["-O3"]
    elif compiler.compiler_type == "msvc":
        cflags += ["/O2"]

    setup(
        ext_modules=[
            Extension(
                "librt.internal",
                [
                    "librt_internal.c",
                    "init.c",
                    "int_ops.c",
                    "exc_ops.c",
                    "pythonsupport.c",
                    "getargsfast.c",
                ],
                include_dirs=["."],
                extra_compile_args=cflags,
            )
        ]
    )
