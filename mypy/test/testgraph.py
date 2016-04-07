"""Test cases for graph processing code in build.py."""

from typing import AbstractSet, Dict, Set

from mypy.myunit import Suite, assert_equal
from mypy.build import BuildManager, State, TYPE_CHECK
from mypy.build import topsort, strongly_connected_components, sorted_components


class GraphSuite(Suite):

    def test_topsort(self) -> None:
        a = frozenset({'A'})
        b = frozenset({'B'})
        c = frozenset({'C'})
        d = frozenset({'D'})
        data = {a: {b, c}, b: {d}, c: {d}}  # type: Dict[AbstractSet[str], Set[AbstractSet[str]]]
        res = list(topsort(data))
        assert_equal(res, [{d}, {b, c}, {a}])

    def test_scc(self) -> None:
        vertices = {'A', 'B', 'C', 'D'}
        edges = {'A': ['B', 'C'],
                 'B': ['C'],
                 'C': ['B', 'D'],
                 'D': []}  # type: Dict[str, List[str]]
        sccs = set(frozenset(x) for x in strongly_connected_components(vertices, edges))
        assert_equal(sccs,
                     {frozenset({'A'}),
                      frozenset({'B', 'C'}),
                      frozenset({'D'})})

    def test_sorted_components(self) -> None:
        manager = BuildManager(
            data_dir='',
            lib_path=[],
            target=TYPE_CHECK,
            pyversion=(3, 5),
            flags=[],
            ignore_prefix='',
            custom_typing_module='',
            source_set=None,
            reports=None)
        graph = {'a': State('a', None, 'import b, c', manager),
                 'b': State('b', None, 'import c', manager),
                 'c': State('c', None, 'import b, d', manager),
                 'd': State('d', None, 'pass', manager)}
        res = sorted_components(graph)
        assert_equal(res, [frozenset({'d'}), frozenset({'c', 'b'}), frozenset({'a'})])
