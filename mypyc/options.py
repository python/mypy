from __future__ import annotations

import re
import sys
from typing import Final

from mypyc.common import EXT_SUFFIX, IS_FREE_THREADED


class TargetPython:
    """The Python build that generated code targets.

    This defaults to the running interpreter, but can be overridden so that
    the C code can be generated on a different Python than the one that will
    compile and run it.
    """

    def __init__(self, version: tuple[int, int], free_threaded: bool = False) -> None:
        # Python (C API) version, such as (3, 13)
        self.version: Final = version
        # Is this a free-threaded (GIL disabled) build?
        self.free_threaded: Final = free_threaded

    @classmethod
    def host(cls) -> TargetPython:
        """Target the running interpreter."""
        return cls(sys.version_info[:2], IS_FREE_THREADED)

    @classmethod
    def parse(cls, target: str) -> TargetPython:
        """Parse a target such as "3.13" or "3.14t" ("t" means free-threaded)."""
        m = re.fullmatch(r"3\.(\d+)(t?)", target.strip())
        if m is None:
            raise ValueError(f'Invalid target Python "{target}" (expected e.g. "3.13" or "3.14t")')
        result = cls((3, int(m.group(1))), m.group(2) == "t")
        if result.version < (3, 10):
            raise ValueError(f'Unsupported target Python "{target}" (3.10 or later is required)')
        if result.free_threaded and result.version < (3, 13):
            raise ValueError(f'Free-threaded builds require Python 3.13 or later (got "{target}")')
        return result

    @property
    def have_immortal(self) -> bool:
        """Does the target have immortal objects (introduced in 3.12, see PEP 683)?"""
        return self.version >= (3, 12)

    @property
    def ext_suffix(self) -> str:
        """File name suffix of extension modules, e.g. ".cpython-314t-x86_64-linux-gnu.so".

        This is the running interpreter's suffix with the version tag replaced, since
        only the Python version (not the platform) can differ from the host.
        """
        return replace_ext_suffix_version(EXT_SUFFIX, self)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TargetPython)
            and self.version == other.version
            and self.free_threaded == other.free_threaded
        )

    def __hash__(self) -> int:
        return hash((self.version, self.free_threaded))

    def __str__(self) -> str:
        return f"{self.version[0]}.{self.version[1]}{'t' if self.free_threaded else ''}"

    def __repr__(self) -> str:
        return f"TargetPython({str(self)!r})"


def replace_ext_suffix_version(suffix: str, target: TargetPython) -> str:
    """Replace the Python version tag in an extension suffix such as ".cp313-win_amd64.pyd"."""
    tag = f"{target.version[0]}{target.version[1]}{'t' if target.free_threaded else ''}"
    return re.sub(r"(\.cpython-|\.cp)\d+t?(?=-)", rf"\g<1>{tag}", suffix, count=1)


class CompilerOptions:
    def __init__(
        self,
        strip_asserts: bool = False,
        multi_file: bool = False,
        verbose: bool = False,
        separate: bool = False,
        target_dir: str | None = None,
        include_runtime_files: bool | None = None,
        capi_version: tuple[int, int] | None = None,
        python_version: tuple[int, int] | None = None,
        strict_dunder_typing: bool = False,
        group_name: str | None = None,
        log_trace: bool = False,
        depends_on_librt_internal: bool = False,
        experimental_features: bool = False,
        strict_traceback_checks: bool = False,
        target_python: TargetPython | None = None,
    ) -> None:
        self.strip_asserts = strip_asserts
        self.multi_file = multi_file
        self.verbose = verbose
        self.separate = separate
        self.global_opts = not separate
        self.target_dir = target_dir or "build"
        self.include_runtime_files = (
            include_runtime_files if include_runtime_files is not None else not multi_file
        )
        # The Python build to generate code for (see TargetPython). The generated
        # C must be compiled against the headers of this Python build.
        self.target_python = target_python or TargetPython.host()
        if capi_version is not None:
            self.capi_version = capi_version
        self.python_version = python_version
        # Make possible to inline dunder methods in the generated code.
        # Typically, the convention is the dunder methods can return `NotImplemented`
        # even when its return type is just `bool`.
        # By enabling this option, this convention is no longer valid and the dunder
        # will assume the return type of the method strictly, which can lead to
        # more optimization opportunities.
        self.strict_dunders_typing = strict_dunder_typing
        # Override the automatic group name derived from the hash of module names.
        # This affects the names of generated .c, .h and shared library files.
        # This is only supported when compiling exactly one group, and a shared
        # library is generated (with shims). This can be used to make the output
        # file names more predictable.
        self.group_name = group_name
        # If enabled, write a trace log of events based on executed operations to
        # mypyc_trace.txt when compiled module is executed. This is useful for
        # performance analysis.
        self.log_trace = log_trace
        # If enabled, add capsule imports of librt.internal API. This should be used
        # only for mypy itself, third-party code compiled with mypyc should not use
        # librt.internal.
        self.depends_on_librt_internal = depends_on_librt_internal
        # Some experimental features are only available when building librt in
        # experimental mode (e.g. use _experimental suffix in librt run test).
        # These can't be used with a librt wheel installed from PyPI.
        self.experimental_features = experimental_features
        # If enabled, mypyc will assert that every traceback it generates has a
        # positive line number.
        # Currently each AST node is assigned line number -1 by default to indicate
        # that it's unset. If the line number is never set and a traceback is
        # generated that points at such node, then the line number will be interpreted
        # as None instead of an integer by Python and potentially crash code that
        # expects an integer, such as pytest.
        # The goal is to prevent the incorrect tracebacks but it will require a lot
        # of changes across mypyc. In the meantime, this option should be enabled in
        # tests to make sure that no new code which leads to incorrect tracebacks is
        # added.
        self.strict_traceback_checks = strict_traceback_checks

    @property
    def capi_version(self) -> tuple[int, int]:
        """The target Python C API version.

        Overriding only this is mostly useful in IR tests, since there's no
        guarantee that binaries are backward compatible even if no recent API
        features are used.
        """
        return self.target_python.version

    @capi_version.setter
    def capi_version(self, version: tuple[int, int]) -> None:
        self.target_python = TargetPython(version, self.target_python.free_threaded)
