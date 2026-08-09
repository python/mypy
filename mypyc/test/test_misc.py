from __future__ import annotations

import os
import tempfile
import unittest

from mypyc.build import get_header_deps, resolve_cfile_deps
from mypyc.ir.ops import BasicBlock
from mypyc.ir.pprint import format_blocks, generate_names_for_ir
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.options import CompilerOptions


class TestMisc(unittest.TestCase):
    def test_debug_op(self) -> None:
        block = BasicBlock()
        builder = LowLevelIRBuilder(
            errors=None, options=CompilerOptions(strict_traceback_checks=True)
        )
        builder.activate_block(block)
        builder.debug_print("foo")

        names = generate_names_for_ir([], [block])
        code = format_blocks([block], names, {})
        assert code[:-1] == ["L0:", "    r0 = 'foo'", "    CPyDebug_PrintObject(r0)"]


class TestHeaderDeps(unittest.TestCase):
    """
    Tests for the header-dependency tracking used to build `Extension.depends`, which drives
    setuptools' `newer_group` decision about whether to recompile a .o file on incremental builds.
    """

    def test_get_header_deps_quoted_includes(self) -> None:
        # Quoted includes: the historical form. Used by the .c file to reach its own __native_<mod>.h /
        # __native_internal_<mod>.h. The `False` in each tuple marks the include as non-angled, which
        # `resolve_cfile_deps` uses to search the includer's directory.
        cfile = '#include "__native_caller.h"\n#include "__native_internal_caller.h"\n'
        assert get_header_deps([("caller.c", cfile)]) == [
            (False, "__native_caller.h"),
            (False, "__native_internal_caller.h"),
        ]

    def test_get_header_deps_angle_bracket_includes(self) -> None:
        # Angle-bracket includes are also matched, and reported with is_angled=True so that the resolver
        # skips the includer's dir for them (matching the C preprocessor). The cross-group export header
        # is reached via `#include <other_group/__native_other.h>` in __native_internal_<mod>.h. Before
        # this was matched the dep was missed entirely and the consumer's .o was never invalidated when
        # the other group's struct layout shifted.
        cfile = "#include <Python.h>\n#include <lib/__native_functions.h>\n"
        assert get_header_deps([("caller.c", cfile)]) == [
            (True, "Python.h"),
            (True, "lib/__native_functions.h"),
        ]

    def test_get_header_deps_mixed_and_whitespace(self) -> None:
        # The preprocessor tolerates whitespace and the leading-hash form. `get_header_deps` returns sorted
        # tuples — non-angled (False) sorts before angled (True), then alphabetical within each kind.
        cfile = '# include "a.h"\n#  include  <b.h>\n#include\t"c.h"\n'
        assert get_header_deps([("x.c", cfile)]) == [(False, "a.h"), (False, "c.h"), (True, "b.h")]

    def test_resolve_walks_transitively_through_headers(self) -> None:
        # Reproduces the bug scenario: caller's .c only directly includes caller's own headers, but
        # caller's __native_internal_caller.h includes the cross-group export header. The resolver
        # must follow that chain so setuptools sees the cross-group header as a dep.
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = tmp
            os.makedirs(os.path.join(build_dir, "lib"))
            os.makedirs(os.path.join(build_dir, "other_group"))

            # caller.c's directly-included headers, both live alongside
            # caller.c under build/ (resolved via target_dir).
            internal_h = os.path.join(build_dir, "__native_internal_caller.h")
            caller_h = os.path.join(build_dir, "__native_caller.h")
            cross_group_h = os.path.join(build_dir, "lib", "__native_functions.h")
            unrelated_h = os.path.join(build_dir, "other_group", "__native_other.h")

            with open(caller_h, "w") as f:
                # Headers outside build/ (CPython's <Python.h>, lib-rt's <CPy.h>) don't resolve under
                # target_dir, so they get dropped during resolution and aren't recursed into.
                f.write("#include <Python.h>\n#include <CPy.h>\n")
            with open(internal_h, "w") as f:
                # This header includes a header in another group via angle brackets. Pre-fix, this dep
                # was invisible to setuptools.
                f.write(
                    "#include <Python.h>\n"
                    '#include "__native_caller.h"\n'
                    "#include <lib/__native_functions.h>\n"
                )
            with open(cross_group_h, "w") as f:
                f.write("struct export_table_lib___functions { int x; };\n")
            with open(unrelated_h, "w") as f:
                # Sibling group not reached from caller's chain => must NOT appear in the resolved set.
                f.write("struct unrelated { int x; };\n")

            # caller.c is in build_dir, so its includer-dir is build_dir. Both directly-included headers
            # are quoted (`False`); the cross-group header that __native_internal_caller.h reaches via
            # `<lib/__native_functions.h>` is found by the recursive walk re-reading the on-disk header.
            deps = resolve_cfile_deps(
                cfile_dir=build_dir,
                direct_includes=[
                    (False, "__native_caller.h"),
                    (False, "__native_internal_caller.h"),
                ],
                target_dir=build_dir,
            )

            assert deps == {caller_h, internal_h, cross_group_h}, (
                f"expected the cross-group header to be reached transitively; "
                f"got {sorted(deps)!r}"
            )

    def test_resolve_drops_unresolvable_includes(self) -> None:
        # `<Python.h>`, `<CPy.h>`, etc. don't live under target_dir, so they're dropped from depends. They
        # never change between builds, so this is the right behavior. Crucially, it stops setuptools'
        # `missing="newer"` from treating them as always-newer and force-rebuilding every translation unit.
        with tempfile.TemporaryDirectory() as tmp:
            cfile_dir = tmp
            deps = resolve_cfile_deps(
                cfile_dir=cfile_dir,
                direct_includes=[(True, "Python.h"), (True, "CPy.h"), (False, "init.c")],
                target_dir=cfile_dir,
            )
            assert deps == set()

    def test_resolve_search_order_matches_preprocessor(self) -> None:
        # When the same header name exists both next to the includer and under target_dir, the C preprocessor
        # picks the includer-dir copy for `#include "shared.h"` and the target_dir copy for `#include <shared.h>`.
        # The resolver must record the same path the compiler will actually consume, otherwise mtimes of the
        # wrong file drive incremental rebuild decisions.
        with tempfile.TemporaryDirectory() as tmp:
            includer = os.path.join(tmp, "groupA")
            target = os.path.join(tmp, "build")
            os.makedirs(includer)
            os.makedirs(target)

            local_h = os.path.join(includer, "shared.h")
            global_h = os.path.join(target, "shared.h")
            with open(local_h, "w") as f:
                f.write("/* local */\n")
            with open(global_h, "w") as f:
                f.write("/* global */\n")

            # Quoted form: resolves to the includer-dir copy.
            assert resolve_cfile_deps(
                cfile_dir=includer, direct_includes=[(False, "shared.h")], target_dir=target
            ) == {local_h}

            # Angled form: skips the includer-dir copy, resolves under -I.
            assert resolve_cfile_deps(
                cfile_dir=includer, direct_includes=[(True, "shared.h")], target_dir=target
            ) == {global_h}
