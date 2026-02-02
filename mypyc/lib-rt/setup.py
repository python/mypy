"""Build script for mypyc C runtime library and C API unit tests.

The tests are written in C++ and use the Google Test framework.
"""

from __future__ import annotations

import os
import subprocess
import sys
from distutils import ccompiler, sysconfig
from typing import Any

# we'll import stuff from the source tree, let's ensure is on the sys path
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import build_setup  # noqa: F401
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
        compile_args: list[str] = []
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
    compiler = ccompiler.new_compiler()
    sysconfig.customize_compiler(compiler)
    cflags: list[str] = []
    if compiler.compiler_type == "unix":  # type: ignore[attr-defined]
        cflags += ["-O3", "-Wno-unused-function"]
    elif compiler.compiler_type == "msvc":  # type: ignore[attr-defined]
        cflags += ["/O2"]

    setup(
        ext_modules=[
            Extension(
                "librt.internal",
                [
                    "internal/librt_internal.c",
                    "init.c",
                    "int_ops.c",
                    "exc_ops.c",
                    "pythonsupport.c",
                    "getargsfast.c",
                ],
                include_dirs=[".", "internal"],
                extra_compile_args=cflags,
            ),
            Extension(
                "librt.strings",
                [
                    "strings/librt_strings.c",
                    "init.c",
                    "int_ops.c",
                    "exc_ops.c",
                    "pythonsupport.c",
                    "getargsfast.c",
                ],
                include_dirs=[".", "strings"],
                extra_compile_args=cflags,
            ),
            Extension(
                "librt.base64",
                [
                    "base64/librt_base64.c",
                    "base64/lib.c",
                    "base64/codec_choose.c",
                    "base64/tables/tables.c",
                    "base64/arch/generic/codec.c",
                    "base64/arch/ssse3/codec.c",
                    "base64/arch/sse41/codec.c",
                    "base64/arch/sse42/codec.c",
                    "base64/arch/avx/codec.c",
                    "base64/arch/avx2/codec.c",
                    "base64/arch/avx512/codec.c",
                    "base64/arch/neon32/codec.c",
                    "base64/arch/neon64/codec.c",
                ],
                include_dirs=[".", "base64"],
                extra_compile_args=cflags,
            ),
            Extension(
                "librt.vecs",
                [
                    "vecs/librt_vecs.c",
                    "vecs/vec_i64.c",
                    "vecs/vec_i32.c",
                    "vecs/vec_i16.c",
                    "vecs/vec_u8.c",
                    "vecs/vec_float.c",
                    "vecs/vec_bool.c",
                    "vecs/vec_t.c",
                    "vecs/vec_nested.c",
                ],
                include_dirs=[".", "vecs"],
                extra_compile_args=cflags,
            ),
        ]
    )
