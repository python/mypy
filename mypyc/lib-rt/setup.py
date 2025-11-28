"""Build script for mypyc C runtime library and C API unit tests.

The tests are written in C++ and use the Google Test framework.
"""

from __future__ import annotations

import os
import platform
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

EXTRA_FLAGS_PER_COMPILER_TYPE_PER_PATH_COMPONENT = {
    "unix": {
        "base64/arch/ssse3": ["-mssse3"],
        "base64/arch/sse41": ["-msse4.1"],
        "base64/arch/sse42": ["-msse4.2"],
        "base64/arch/avx2": ["-mavx2"],
        "base64/arch/avx": ["-mavx"],
    },
    "msvc": {
        "base64/arch/sse42": ["/arch:SSE4.2"],
        "base64/arch/avx2": ["/arch:AVX2"],
        "base64/arch/avx": ["/arch:AVX"],
    },
}

ccompiler.CCompiler.__spawn = ccompiler.CCompiler.spawn  # type: ignore[attr-defined]
X86_64 = platform.machine() in ("x86_64", "AMD64", "amd64")


def spawn(self, cmd, **kwargs) -> None:  # type: ignore[no-untyped-def]
    compiler_type: str = self.compiler_type
    extra_options = EXTRA_FLAGS_PER_COMPILER_TYPE_PER_PATH_COMPONENT[compiler_type]
    new_cmd = list(cmd)
    if X86_64 and extra_options is not None:
        # filenames are closer to the end of command line
        for argument in reversed(new_cmd):
            # Check if the matching argument contains a source filename.
            if not str(argument).endswith(".c"):
                continue

            for path in extra_options.keys():
                if path in str(argument):
                    if compiler_type == "bcpp":
                        compiler = new_cmd.pop()
                        # Borland accepts a source file name at the end,
                        # insert the options before it
                        new_cmd.extend(extra_options[path])
                        new_cmd.append(compiler)
                    else:
                        new_cmd.extend(extra_options[path])

                    # path component is found, no need to search any further
                    break
    self.__spawn(new_cmd, **kwargs)


ccompiler.CCompiler.spawn = spawn  # type: ignore[method-assign]


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
    # TODO: we need a way to share our preferred C flags and get_extension() logic with
    # mypyc/build.py without code duplication.
    compiler = ccompiler.new_compiler()
    sysconfig.customize_compiler(compiler)
    cflags: list[str] = []
    if compiler.compiler_type == "unix":  # type: ignore[attr-defined]
        cflags += ["-O3"]
    elif compiler.compiler_type == "msvc":  # type: ignore[attr-defined]
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
            ),
            Extension(
                "librt.strings",
                [
                    "librt_strings.c",
                    "init.c",
                    "int_ops.c",
                    "exc_ops.c",
                    "pythonsupport.c",
                    "getargsfast.c",
                ],
                include_dirs=["."],
                extra_compile_args=cflags,
            ),
            Extension(
                "librt.base64",
                [
                    "librt_base64.c",
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
        ]
    )
