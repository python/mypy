from __future__ import annotations

import re
import sys
import sysconfig
from typing import Final, final

from mypy.defaults import PYTHON3_VERSION_MIN
from mypyc.common import EXT_SUFFIX

# Is the running interpreter a free-threaded build (GIL disabled)? Use
# TargetPython.host().free_threaded instead of this.
_HOST_FREE_THREADED: Final = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


@final
class TargetPython:
    """The Python build that generated code targets.

    This defaults to the running interpreter, but can be overridden so that
    the C code can be generated on a different Python than the one that will
    compile and run it.

    This is currently mostly meant for users that bring their own monolithic
    build system (e.g. Bazel or Buck2), which call mypyc_build() to only generate
    C and then compile it themselves against the headers of the target Python.
    It's not exposed through the mypyc command line or mypycify().

    WARNING: Never compile the generated C for a different Python than the
    target. setuptools-based builds always compile using the running interpreter,
    so a different target there produces extension modules that fail to compile
    or, worse, compile but don't work (e.g. code for a GIL build has data races
    on a free-threaded build).
    """

    def __init__(self, version: tuple[int, int], free_threaded: bool = False) -> None:
        if version[0] != 3 or version < PYTHON3_VERSION_MIN:
            min_version = ".".join(str(v) for v in PYTHON3_VERSION_MIN)
            raise ValueError(
                f"Unsupported target Python {version[0]}.{version[1]} "
                f"({min_version} or later is required)"
            )
        if free_threaded and version < (3, 13):
            raise ValueError(
                f"Free-threaded builds require Python 3.13 or later "
                f"(got {version[0]}.{version[1]})"
            )
        # Python (C API) version, such as (3, 13)
        self.version: Final = version
        # Is this a free-threaded (GIL disabled) build?
        self.free_threaded: Final = free_threaded
        # Python 3.12 introduced immortal objects, specified via a special reference
        # count value. The reference counts of immortal objects are normally not
        # modified, but it's not strictly wrong to modify them. See PEP 683 for more
        # information, but note that some details in the PEP are out of date.
        self.have_immortal: Final = version >= (3, 12)
        # File name suffix of extension modules, e.g. ".cpython-314t-x86_64-linux-gnu.so".
        # Only the Python version (not the platform) can differ from the host.
        is_host = version == sys.version_info[:2] and free_threaded == _HOST_FREE_THREADED
        self.ext_suffix: Final = (
            EXT_SUFFIX
            if is_host
            else replace_ext_suffix_version(EXT_SUFFIX, version, free_threaded)
        )

    @staticmethod
    def host() -> TargetPython:
        """Target the running interpreter."""
        return TargetPython(sys.version_info[:2], _HOST_FREE_THREADED)

    @staticmethod
    def parse(target: str) -> TargetPython:
        """Parse a target such as "3.13" or "3.14t" ("t" means free-threaded)."""
        m = re.fullmatch(r"(\d+)\.(\d+)(t?)", target.strip())
        if m is None:
            raise ValueError(f'Invalid target Python "{target}" (expected e.g. "3.13" or "3.14t")')
        return TargetPython((int(m.group(1)), int(m.group(2))), m.group(3) == "t")

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


def replace_ext_suffix_version(suffix: str, version: tuple[int, int], free_threaded: bool) -> str:
    """Replace the Python version tag in an extension suffix such as ".cp313-win_amd64.pyd"."""
    tag = f"{version[0]}{version[1]}{'t' if free_threaded else ''}"
    result, n = re.subn(r"(\.cpython-|\.cp)\d+t?(?=-)", rf"\g<1>{tag}", suffix, count=1)
    if n == 0:
        raise ValueError(
            f'Can\'t target Python {version[0]}.{version[1]}{"t" if free_threaded else ""}: '
            f'unrecognized extension module suffix "{suffix}"'
        )
    return result


class CompilerOptions:
    def __init__(
        self,
        strip_asserts: bool = False,
        multi_file: bool = False,
        verbose: bool = False,
        separate: bool = False,
        target_dir: str | None = None,
        include_runtime_files: bool | None = None,
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
        # The Python build to generate code for (see TargetPython, including the
        # warning there). This determines both the C API version and the Python
        # version used for type checking.
        self.target_python = target_python or TargetPython.host()
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
