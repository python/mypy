"""Top-level logic for the new semantic analyzer.

The semantic analyzer binds names, resolves imports, detects various
special constructs that don't have dedicated AST nodes after parse
(such as 'cast' which looks like a call), and performs various simple
consistency checks.

Semantic analysis of each SCC (strongly connected component; import
cycle) is performed in one unit. Each module is analyzed as multiple
separate *targets*; the module top level is one target and each function
is a target. Nested functions are not separate targets, however. This is
mostly identical to targets used by mypy daemon (but classes aren't
targets in semantic analysis).

We first analyze each module top level in an SCC. If we encounter some
names that we can't bind because the target of the name may not have
been processed yet, we *defer* the current target for further
processing. Deferred targets will be analyzed additional times until
everything can be bound, or we reach a maximum number of iterations.

We keep track of a set of incomplete namespaces, i.e. namespaces that we
haven't finished populating yet. References to these namespaces cause a
deferral if they can't be satisfied. Initially every module in the SCC
will be incomplete.
"""

import contextlib
from typing import List, Tuple, Optional, Union, Callable, Iterator

from mypy.nodes import (
    MypyFile, TypeInfo, FuncDef, Decorator, OverloadedFuncDef
)
from mypy.newsemanal.semanal_typeargs import TypeArgumentAnalyzer
from mypy.state import strict_optional_set
from mypy.newsemanal.semanal import (
    NewSemanticAnalyzer, apply_semantic_analyzer_patches, remove_imported_names_from_symtable
)
from mypy.newsemanal.semanal_classprop import (
    calculate_class_abstract_status, calculate_class_vars, check_protocol_status
)
from mypy.errors import Errors
from mypy.newsemanal.semanal_infer import infer_decorator_signature_if_simple
from mypy.checker import FineGrainedDeferredNode

MYPY = False
if MYPY:
    from mypy.build import Graph, State


Patches = List[Tuple[int, Callable[[], None]]]


# If we perform this many iterations, raise an exception since we are likely stuck.
MAX_ITERATIONS = 20


# Number of passes over core modules before going on to the rest of the builtin SCC.
CORE_WARMUP = 2
core_modules = ['typing', 'builtins', 'abc', 'collections']


def semantic_analysis_for_scc(graph: 'Graph', scc: List[str], errors: Errors) -> None:
    """Perform semantic analysis for all modules in a SCC (import cycle).

    Assume that reachability analysis has already been performed.
    """
    patches = []  # type: Patches
    # Note that functions can't define new module-level attributes
    # using 'global x', since module top levels are fully processed
    # before functions. This limitation is unlikely to go away soon.
    process_top_levels(graph, scc, patches)
    process_functions(graph, scc, patches)
    # We use patch callbacks to fix up things when we expect relatively few
    # callbacks to be required.
    apply_semantic_analyzer_patches(patches)
    # This pass might need fallbacks calculated above.
    check_type_arguments(graph, scc, errors)
    calculate_class_properties(graph, scc, errors)
    check_blockers(graph, scc)
    # Clean-up builtins, so that TypeVar etc. are not accessible without importing.
    if 'builtins' in scc:
        cleanup_builtin_scc(graph['builtins'])


def cleanup_builtin_scc(state: 'State') -> None:
    """Remove imported names from builtins namespace.

    This way names imported from typing in builtins.pyi aren't available
    by default (without importing them). We can only do this after processing
    the whole SCC is finished, when the imported names aren't needed for
    processing builtins.pyi itself.
    """
    assert state.tree is not None
    remove_imported_names_from_symtable(state.tree.names, 'builtins')


def process_selected_targets(state: 'State', nodes: List[FineGrainedDeferredNode],
                             graph: 'Graph', strip_patches: List[Callable[[], None]]) -> None:
    """Semantically analyze only selected nodes in a given module.

    This essentially mirrors the logic of semantic_analysis_for_scc()
    except that we process only some targets. This is used in fine grained
    incremental mode, when propagating an update.

    The strip_patches are additional patches that may be produced by aststrip.py to
    re-introduce implicitly declared instance variables (attributes defined on self).
    """
    patches = []  # type: Patches
    if any(isinstance(n.node, MypyFile) for n in nodes):
        # Process module top level first (if needed).
        process_top_levels(graph, [state.id], patches)
    analyzer = state.manager.new_semantic_analyzer
    for n in nodes:
        if isinstance(n.node, MypyFile):
            # Already done above.
            continue
        process_top_level_function(analyzer, state, state.id,
                                   n.node.fullname(), n.node, n.active_typeinfo, patches)
    apply_semantic_analyzer_patches(patches)
    for patch in strip_patches:
        patch()

    check_type_arguments_in_targets(nodes, state, state.manager.errors)
    calculate_class_properties(graph, [state.id], state.manager.errors)


def process_top_levels(graph: 'Graph', scc: List[str], patches: Patches) -> None:
    # Process top levels until everything has been bound.

    # Initialize ASTs and symbol tables.
    for id in scc:
        state = graph[id]
        assert state.tree is not None
        state.manager.new_semantic_analyzer.prepare_file(state.tree)

    # Initially all namespaces in the SCC are incomplete (well they are empty).
    state.manager.incomplete_namespaces.update(scc)

    worklist = scc[:]
    # HACK: process core stuff first. This is mostly needed to support defining
    # named tuples in builtin SCC.
    if all(m in worklist for m in core_modules):
        worklist += list(reversed(core_modules)) * CORE_WARMUP
    final_iteration = False
    iteration = 0
    while worklist:
        iteration += 1
        if iteration > MAX_ITERATIONS:
            state.manager.new_semantic_analyzer.report_hang()
            break
        if final_iteration:
            # Give up. It's impossible to bind all names.
            state.manager.incomplete_namespaces.clear()
        all_deferred = []  # type: List[str]
        any_progress = False
        while worklist:
            next_id = worklist.pop()
            state = graph[next_id]
            assert state.tree is not None
            deferred, incomplete, progress = semantic_analyze_target(next_id, state,
                                                                     state.tree,
                                                                     None,
                                                                     final_iteration,
                                                                     patches)
            all_deferred += deferred
            any_progress = any_progress or progress
            if not incomplete:
                state.manager.incomplete_namespaces.discard(next_id)
        if final_iteration:
            assert not all_deferred, 'Must not defer during final iteration'
        # Reverse to process the targets in the same order on every iteration. This avoids
        # processing the same target twice in a row, which is inefficient.
        worklist = list(reversed(all_deferred))
        final_iteration = not any_progress


def process_functions(graph: 'Graph', scc: List[str], patches: Patches) -> None:
    # Process functions.
    for module in scc:
        tree = graph[module].tree
        assert tree is not None
        analyzer = graph[module].manager.new_semantic_analyzer
        targets = get_all_leaf_targets(tree)
        for target, node, active_type in targets:
            assert isinstance(node, (FuncDef, OverloadedFuncDef, Decorator))
            process_top_level_function(analyzer,
                                       graph[module],
                                       module,
                                       target,
                                       node,
                                       active_type,
                                       patches)


def process_top_level_function(analyzer: 'NewSemanticAnalyzer',
                               state: 'State',
                               module: str,
                               target: str,
                               node: Union[FuncDef, OverloadedFuncDef, Decorator],
                               active_type: Optional[TypeInfo],
                               patches: Patches) -> None:
    """Analyze single top-level function or method.

    Process the body of the function (including nested functions) again and again,
    until all names have been resolved (ot iteration limit reached).
    """
    # We need one more iteration after incomplete is False (e.g. to report errors, if any).
    final_iteration = False
    incomplete = True
    # Start in the incomplete state (no missing names will be reported on first pass).
    # Note that we use module name, since functions don't create qualified names.
    deferred = [module]
    analyzer.incomplete_namespaces.add(module)
    iteration = 0
    while deferred:
        iteration += 1
        if iteration == MAX_ITERATIONS:
            analyzer.report_hang()
            break
        if not (deferred or incomplete) or final_iteration:
            # OK, this is one last pass, now missing names will be reported.
            analyzer.incomplete_namespaces.discard(module)
        deferred, incomplete, progress = semantic_analyze_target(target, state, node, active_type,
                                                                 final_iteration, patches)
        if final_iteration:
            assert not deferred, 'Must not defer during final iteration'
        if not progress:
            final_iteration = True

    analyzer.incomplete_namespaces.discard(module)
    # After semantic analysis is done, discard local namespaces
    # to avoid memory hoarding.
    analyzer.saved_locals.clear()


TargetInfo = Tuple[str, Union[MypyFile, FuncDef, OverloadedFuncDef, Decorator], Optional[TypeInfo]]


def get_all_leaf_targets(file: MypyFile) -> List[TargetInfo]:
    """Return all leaf targets in a symbol table (module-level and methods)."""
    result = []  # type: List[TargetInfo]
    for fullname, node, active_type in file.local_definitions():
        if isinstance(node.node, (FuncDef, OverloadedFuncDef, Decorator)):
            result.append((fullname, node.node, active_type))
    return result


def semantic_analyze_target(target: str,
                            state: 'State',
                            node: Union[MypyFile, FuncDef, OverloadedFuncDef, Decorator],
                            active_type: Optional[TypeInfo],
                            final_iteration: bool,
                            patches: Patches) -> Tuple[List[str], bool, bool]:
    """Semantically analyze a single target.

    Return tuple with these items:
    - list of deferred targets
    - was some definition incomplete
    - were any new names were defined (or placeholders replaced)
    """
    tree = state.tree
    assert tree is not None
    analyzer = state.manager.new_semantic_analyzer
    # TODO: Move initialization to somewhere else
    analyzer.global_decls = [set()]
    analyzer.nonlocal_decls = [set()]
    analyzer.globals = tree.names
    analyzer.progress = False
    with state.wrap_context(check_blockers=False):
        with analyzer.file_context(file_node=tree,
                                   fnam=tree.path,
                                   options=state.options,
                                   active_type=active_type):
            refresh_node = node
            if isinstance(refresh_node, Decorator):
                # Decorator expressions will be processed as part of the module top level.
                refresh_node = refresh_node.func
            analyzer.refresh_partial(refresh_node, patches, final_iteration)
            if isinstance(node, Decorator):
                infer_decorator_signature_if_simple(node, analyzer)
    if analyzer.deferred:
        return [target], analyzer.incomplete, analyzer.progress
    else:
        return [], analyzer.incomplete, analyzer.progress


def check_type_arguments(graph: 'Graph', scc: List[str], errors: Errors) -> None:
    for module in scc:
        state = graph[module]
        assert state.tree
        analyzer = TypeArgumentAnalyzer(errors)
        with state.wrap_context():
            with strict_optional_set(state.options.strict_optional):
                state.tree.accept(analyzer)


def check_type_arguments_in_targets(targets: List[FineGrainedDeferredNode], state: 'State',
                                    errors: Errors) -> None:
    """Check type arguments against type variable bounds and restrictions.

    This mirrors the logic in check_type_arguments() except that we process only
    some targets. This is used in fine grained incremental mode.
    """
    analyzer = TypeArgumentAnalyzer(errors)
    with state.wrap_context():
        with strict_optional_set(state.options.strict_optional):
            for target in targets:
                analyzer.recurse_into_functions = not isinstance(target.node, MypyFile)
                target.node.accept(analyzer)


def calculate_class_properties(graph: 'Graph', scc: List[str], errors: Errors) -> None:
    for module in scc:
        tree = graph[module].tree
        assert tree
        # TODO: calculate properties also for classes nested in functions.
        for _, node, _ in tree.local_definitions():
            if isinstance(node.node, TypeInfo):
                saved = (module, node.node, None)  # module, class, function
                with errors.scope.saved_scope(saved) if errors.scope else nothing():
                    calculate_class_abstract_status(node.node, tree.is_stub, errors)
                    check_protocol_status(node.node, errors)
                    calculate_class_vars(node.node)


def check_blockers(graph: 'Graph', scc: List[str]) -> None:
    for module in scc:
        graph[module].check_blockers()


@contextlib.contextmanager
def nothing() -> Iterator[None]:
    yield
