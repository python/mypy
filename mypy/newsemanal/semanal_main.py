"""Top-level logic for the new semantic analyzer."""

from typing import List

from mypy.nodes import Node, SymbolTable

MYPY = False
if MYPY:
    from mypy.build import Graph, State


def semantic_analysis_for_scc(graph: 'Graph', scc: List[str]) -> None:
    # Assume reachability analysis has already been performed.
    process_top_levels(graph, scc)
    process_functions(graph, scc)


def process_top_levels(graph: 'Graph', scc: List[str]) -> None:
    # Process top levels until everything has been bound.
    # TODO: Limit the number of iterations

    # Initialize ASTs and symbol tables.
    for id in scc:
        state = graph[id]
        assert state.tree is not None
        state.manager.new_semantic_analyzer.prepare_file(state.tree)

    # Initially all namespaces in the SCC are incomplete (well they are empty).
    state.manager.incomplete_namespaces.update(scc)

    worklist = scc[:]
    while worklist:
        deferred = []  # type: List[str]
        while worklist:
            next_id = worklist.pop()
            deferred += semantic_analyze_target(next_id, graph[next_id])
            # Assume this namespace is ready.
            # TODO: It could still be incomplete if some definitions couldn't be bound.
            state.manager.incomplete_namespaces.discard(next_id)
        worklist = deferred


def process_functions(graph: 'Graph', scc: List[str]) -> None:
    # TODO: This doesn't quite work yet
    # Process functions.
    deferred = []  # type: List[str]
    for id in scc:
        tree = graph[id].tree
        assert tree is not None
        symtable = tree.names
        targets = get_all_leaf_targets(symtable)
        for target in targets:
            deferred += semantic_analyze_target(target, graph[id])
    assert not deferred  # There can't be cross-function forward refs


def get_all_leaf_targets(symtable: SymbolTable) -> List[str]:
    # TODO: Implement
    return []


def semantic_analyze_target(target: str, state: 'State') -> List[str]:
    # TODO: Support refreshing function targets (currently only works for module top levels)
    tree = state.tree
    assert tree is not None
    analyzer = state.manager.new_semantic_analyzer
    # TODO: Move initialization to somewhere else
    analyzer.global_decls = [set()]
    analyzer.nonlocal_decls = [set()]
    analyzer.globals = tree.names
    with analyzer.file_context(file_node=tree,
                               fnam=tree.path,
                               options=state.options,
                               active_type=None):
        analyzer.refresh_partial(tree, [])
    if analyzer.deferred:
        return [target]
    else:
        return []
