"""Test cases for graph processing code in build.py."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Set as AbstractSet

import mypy.build as build_module
from mypy.build import (
    BuildManager,
    BuildSourceSet,
    State,
    SuppressionReason,
    order_ascc,
    sorted_components,
)
from mypy.errors import Errors
from mypy.fscache import FileSystemCache
from mypy.graph_utils import strongly_connected_components, topsort
from mypy.main import process_options
from mypy.modulefinder import SearchPaths
from mypy.options import Options
from mypy.plugin import Plugin
from mypy.report import Reports
from mypy.test.helpers import Suite, assert_equal
from mypy.version import __version__


class GraphSuite(Suite):
    def test_topsort_empty(self) -> None:
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {}
        assert_equal(list(topsort(data)), [])

    def test_topsort(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        c = frozenset({"C"})
        d = frozenset({"D"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {b, c}, b: {d}, c: {d}}
        res = list(topsort(data))
        assert_equal(res, [{d}, {b, c}, {a}])

    def test_topsort_orphan(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {b}}
        res = list(topsort(data))
        assert_equal(res, [{b}, {a}])

    def test_topsort_independent(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        c = frozenset({"C"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: set(), b: set(), c: set()}
        res = list(topsort(data))
        assert_equal(res, [{a, b, c}])

    def test_topsort_linear_chain(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        c = frozenset({"C"})
        d = frozenset({"D"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {b}, b: {c}, c: {d}, d: set()}
        res = list(topsort(data))
        assert_equal(res, [{d}, {c}, {b}, {a}])

    def test_topsort_self_dependency(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {a, b}, b: set()}
        res = list(topsort(data))
        assert_equal(res, [{b}, {a}])

    def test_topsort_orphan_diamond(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        c = frozenset({"C"})
        # B and C are orphans -- they appear only in values, not as keys.
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {b, c}}
        res = list(topsort(data))
        assert_equal(res, [{b, c}, {a}])

    def test_topsort_cycle(self) -> None:
        a = frozenset({"A"})
        b = frozenset({"B"})
        data: dict[AbstractSet[str], set[AbstractSet[str]]] = {a: {b}, b: {a}}
        with self.assertRaises(AssertionError):
            list(topsort(data))

    def test_scc(self) -> None:
        vertices = {"A", "B", "C", "D"}
        edges: dict[str, list[str]] = {"A": ["B", "C"], "B": ["C"], "C": ["B", "D"], "D": []}
        sccs = {frozenset(x) for x in strongly_connected_components(vertices, edges)}
        assert_equal(sccs, {frozenset({"A"}), frozenset({"B", "C"}), frozenset({"D"})})

    def _make_manager(self) -> BuildManager:
        options = Options()
        options.use_builtins_fixtures = True
        errors = Errors(options)
        fscache = FileSystemCache()
        search_paths = SearchPaths((), (), (), ())
        manager = BuildManager(
            data_dir="",
            search_paths=search_paths,
            ignore_prefix="",
            source_set=BuildSourceSet([]),
            reports=Reports("", {}),
            options=options,
            version_id=__version__,
            plugin=Plugin(options),
            plugins_snapshot={},
            errors=errors,
            flush_errors=lambda filename, msgs, serious: None,
            fscache=fscache,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return manager

    def test_fine_grained_cache_preserves_suppression_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "mypy.ini"), "w", encoding="utf-8") as f:
                f.write("[mypy]\ncache_fine_grained = True\nfollow_imports = skip\n")
            with open(os.path.join(tmp, "skipped.py"), "w", encoding="utf-8") as f:
                f.write("def ignored() -> int:\n    return 1\n")
            with open(os.path.join(tmp, "dep.py"), "w", encoding="utf-8") as f:
                f.write("import skipped\n\ndef value() -> int:\n    return 1\n")
            with open(os.path.join(tmp, "main.py"), "w", encoding="utf-8") as f:
                f.write("import dep\n\ndef value() -> int:\n    return dep.value()\n")
            with open(os.path.join(tmp, "seed.py"), "w", encoding="utf-8") as f:
                f.write("import skipped\n")

            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:

                def run_mypy(
                    args: list[str], *, server_options: bool = False
                ) -> build_module.BuildResult:
                    sources, options = process_options(args, server_options=server_options)
                    options.use_builtins_fixtures = True
                    result = build_module.build(sources=sources, options=options)
                    assert_equal(result.errors, [])
                    return result

                result = run_mypy(["dep.py", "main.py"])
                assert_equal(result.graph["dep"].suppressed, ["skipped"])
                assert_equal(result.manager.missing_modules["skipped"], SuppressionReason.SKIPPED)

                result = run_mypy(["seed.py", "skipped.py"])
                assert_equal(result.graph["seed"].dependencies, ["skipped", "builtins"])
                assert_equal(result.graph["seed"].suppressed, [])

                result = run_mypy(
                    ["--use-fine-grained-cache", "seed.py", "dep.py", "main.py"],
                    server_options=True,
                )
            finally:
                os.chdir(old_cwd)

            assert_equal(result.manager.missing_modules["skipped"], SuppressionReason.SKIPPED)
            assert result.graph["dep"].is_fresh()

    def test_sorted_components(self) -> None:
        manager = self._make_manager()
        graph = {
            "a": State.new_state("a", None, "import b, c", manager),
            "d": State.new_state("d", None, "pass", manager),
            "b": State.new_state("b", None, "import c", manager),
            "c": State.new_state("c", None, "import b, d", manager),
            "builtins": State.new_state("builtins", None, "", manager),
        }
        manager.parse_all(list(graph.values()))
        res = [scc.mod_ids for scc in sorted_components(graph)]
        assert_equal(res, [{"builtins"}, {"d"}, {"c", "b"}, {"a"}])

    def test_order_ascc(self) -> None:
        manager = self._make_manager()
        graph = {
            "a": State.new_state("a", None, "import b, c", manager),
            "d": State.new_state("d", None, "def f(): import a", manager),
            "b": State.new_state("b", None, "import c", manager),
            "c": State.new_state("c", None, "import b, d", manager),
            "builtins": State.new_state("builtins", None, "", manager),
        }
        manager.parse_all(list(graph.values()))
        res = [scc.mod_ids for scc in sorted_components(graph)]
        assert_equal(res, [{"builtins"}, {"a", "d", "c", "b"}])
        ascc = res[1]
        scc = order_ascc(graph, ascc)
        assert_equal(scc, ["d", "c", "b", "a"])
