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
    """Tests for the header-dependency tracking used to build
    `Extension.depends`, which drives setuptools' `newer_group` decision
    about whether to recompile a .o file on incremental builds.

    The critical case is cross-group export-table headers: each module's
    `__native_internal_<mod>.h` does `#include <other_group/__native_other.h>`,
    and the consumer's compiled .o file bakes in byte offsets into that
    header's `export_table_<group>` struct. If we miss this header in the
    deps list, struct-layout changes in `other_group` won't trigger a
    rebuild of the consumer, and its baked-in offsets will silently resolve
    to whatever now occupies those slots.
    """

    def test_get_header_deps_quoted_includes(self) -> None:
        # Quoted includes — the historical form. Used by the .c file to
        # reach its own __native_<mod>.h / __native_internal_<mod>.h.
        cfile = '#include "__native_caller.h"\n#include "__native_internal_caller.h"\n'
        assert get_header_deps([("caller.c", cfile)]) == [
            "__native_caller.h",
            "__native_internal_caller.h",
        ]

    def test_get_header_deps_angle_bracket_includes(self) -> None:
        # Angle-bracket includes are also matched. The cross-group export
        # header is reached via `#include <other_group/__native_other.h>`
        # in __native_internal_<mod>.h. Before this was matched the dep
        # was missed entirely and the consumer's .o was never invalidated
        # when the other group's struct layout shifted.
        cfile = "#include <Python.h>\n#include <lib/__native_functions.h>\n"
        assert get_header_deps([("caller.c", cfile)]) == [
            "Python.h",
            "lib/__native_functions.h",
        ]

    def test_get_header_deps_mixed_and_whitespace(self) -> None:
        # The preprocessor tolerates whitespace and the leading-hash form.
        cfile = (
            '# include "a.h"\n'
            '#  include  <b.h>\n'
            '#include\t"c.h"\n'
        )
        assert get_header_deps([("x.c", cfile)]) == ["a.h", "b.h", "c.h"]

    def test_resolve_walks_transitively_through_headers(self) -> None:
        # Reproduces the bug2 scenario: caller's .c only directly includes
        # caller's own headers, but caller's __native_internal_caller.h
        # includes the cross-group export header. The resolver must follow
        # that chain so setuptools sees the cross-group header as a dep.
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = tmp
            os.makedirs(os.path.join(build_dir, "lib"))
            os.makedirs(os.path.join(build_dir, "other_group"))

            # caller.c's directly-included headers — both live alongside
            # caller.c under build/ (resolved via target_dir).
            internal_h = os.path.join(build_dir, "__native_internal_caller.h")
            caller_h = os.path.join(build_dir, "__native_caller.h")
            cross_group_h = os.path.join(build_dir, "lib", "__native_functions.h")
            unrelated_h = os.path.join(build_dir, "other_group", "__native_other.h")

            with open(caller_h, "w") as f:
                # lib-rt headers don't exist on disk under build/, so they
                # get dropped during resolution and aren't recursed into.
                f.write("#include <Python.h>\n#include <CPy.h>\n")
            with open(internal_h, "w") as f:
                # The smoking gun: this header includes a header in another
                # group via angle brackets. Pre-fix, this dep was invisible
                # to setuptools.
                f.write(
                    "#include <Python.h>\n"
                    '#include "__native_caller.h"\n'
                    "#include <lib/__native_functions.h>\n"
                )
            with open(cross_group_h, "w") as f:
                f.write("struct export_table_lib___functions { int x; };\n")
            with open(unrelated_h, "w") as f:
                # Sibling group not reached from caller's chain — must
                # NOT appear in the resolved set.
                f.write("struct unrelated { int x; };\n")

            # caller.c is in build_dir, so its includer-dir is build_dir.
            deps = resolve_cfile_deps(
                cfile_dir=build_dir,
                direct_includes=["__native_caller.h", "__native_internal_caller.h"],
                target_dir=build_dir,
            )

            assert deps == {caller_h, internal_h, cross_group_h}, (
                f"expected the cross-group header to be reached transitively; "
                f"got {sorted(deps)!r}"
            )

    def test_resolve_drops_unresolvable_includes(self) -> None:
        # `<Python.h>`, `<CPy.h>`, etc. don't live under target_dir, so
        # they're dropped from depends. They never change between builds,
        # so this is the right behavior — and crucially it stops
        # setuptools' `missing="newer"` from treating them as always-newer
        # and force-rebuilding every translation unit.
        with tempfile.TemporaryDirectory() as tmp:
            cfile_dir = tmp
            deps = resolve_cfile_deps(
                cfile_dir=cfile_dir,
                direct_includes=["Python.h", "CPy.h", "init.c"],
                target_dir=cfile_dir,
            )
            assert deps == set()

    def test_resolve_prefers_includer_dir_for_quoted_like_paths(self) -> None:
        # When the same name resolves in both the includer's directory and
        # target_dir, the includer-relative one wins — that's the
        # preprocessor's behavior for `#include "..."`. Approximated here
        # by checking the includer's dir first.
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

            deps = resolve_cfile_deps(
                cfile_dir=includer, direct_includes=["shared.h"], target_dir=target
            )
            assert deps == {local_h}
