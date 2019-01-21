"""Top-level logic for the new semantic analyzer."""

from typing import List

from mypy.nodes import Node, SymbolTable

MYPY = False
if MYPY:
    from mypy.build import Graph, State


def semantic_analysis_for_scc(graph: 'Graph', scc: List[str]) -> None:
    # Assume pass 1 has already been peformed.
    process_top_levels(graph, scc)
    process_functions(graph, scc)


def process_top_levels(graph: 'Graph', scc: List[str]) -> None:
    # Process top levels until everything has been bound.
    # TODO: Limit the number of iterations
    worklist = scc[:]
    while worklist:
        deferred = []  # type: List[str]
        while worklist:
            next_id = worklist.pop()
            deferred += graph[next_id].semantic_analyze_target(next_id)
        worklist = deferred


def process_functions(graph: 'Graph', scc: List[str]) -> None:
    # Process functions.
    deferred = []  # type: List[str]
    for id in scc:
        tree = graph[id].tree
        assert tree is not None
        symtable = tree.names
        targets = get_all_leaf_targets(symtable)
        for target in targets:
            deferred += graph[id].semantic_analyze_target(id)
    assert not deferred  # There can't be cross-function forward refs


def get_all_leaf_targets(symtable: SymbolTable) -> List[str]:
    assert False
    return []


def semanatic_analyze_target(id: str, state: 'State') -> List[str]:
    assert False
