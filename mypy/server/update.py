"""Update build result by incrementally processing changed modules.

Use fine-grained dependencies to update targets in other modules that
may be affected by externally-visible changes in the changed modules.

Terms:

* A 'target' is a function definition or the top level of a module. We
  refer to targets using their fully qualified name (e.g. 'mod.Cls.attr').
  Targets are the smallest units of processing during fine-grained
  incremental checking.
* A 'trigger' represents the properties of a part of a program, and it
  gets triggered/activated when these properties change. For example,
  '<mod.func>' refers to a module-level function, and it gets triggered
  if the signature of the function changes, or if if the function is
  removed.

Some program state is maintained across multiple build increments:

* The full ASTs of all modules in memory all the time (+ type map).
* Maintain a fine-grained dependency map, which is from triggers to
  targets/triggers. The latter determine what other parts of a program
  need to be processed again due to an externally visible change to a
  module.

We perform a fine-grained incremental program update like this:

* Determine which modules have changes in their source code since the
  previous build.
* Fully process these modules, creating new ASTs and symbol tables
  for them. Retain the existing ASTs and symbol tables of modules that
  have no changes in their source code.
* Determine which parts of the changed modules have changed. The result
  is a set of triggered triggers.
* Using the dependency map, decide which other targets have become
  stale and need to be reprocessed.
* Replace old ASTs of the modules that we reprocessed earlier with
  the new ones, but try to retain the identities of original externally
  visible AST nodes so that we don't (always) need to patch references
  in the rest of the program.
* Semantically analyze and type check the stale targets.
* Repeat the previous steps until nothing externally visible has changed.

Major todo items:

- Support multiple type checking passes
"""

from typing import Dict, List, Set, Tuple, Iterable, Union, Optional

from mypy.build import (
    BuildManager, State, BuildSource, Graph, load_graph, SavedCache, PRI_HIGH, CacheMeta,
    cache_meta_from_dict
)
from mypy.checker import DeferredNode
from mypy.errors import Errors, CompileError
from mypy.nodes import (
    MypyFile, FuncDef, TypeInfo, Expression, SymbolNode, Var, FuncBase, ClassDef, Decorator,
    Import, ImportFrom
)
from mypy.options import Options
from mypy.types import Type
from mypy.server.astdiff import (
    snapshot_symbol_table, compare_symbol_table_snapshots, is_identical_type, SnapshotItem
)
from mypy.server.astmerge import merge_asts
from mypy.server.aststrip import strip_target
from mypy.server.deps import get_dependencies, get_dependencies_of_target
from mypy.server.target import module_prefix, split_target
from mypy.server.trigger import make_trigger


# If True, print out debug logging output.
DEBUG = False


class FineGrainedBuildManager:
    def __init__(self,
                 manager: BuildManager,
                 graph: Dict[str, State]) -> None:
        """Initialize fine-grained build based on a batch build.

        Args:
            manager: State of the build (mutated by this class)
            graph: Additional state of the build (mutated)
        """
        self.manager = manager
        self.options = manager.options
        self.graph = graph
        self.deps = get_all_dependencies(manager, graph, self.options)
        self.previous_targets_with_errors = manager.errors.targets()
        # Modules that had blocking errors in the previous run.
        # TODO: Handle blocking errors in the initial build
        self.blocking_errors = []  # type: List[str]
        manager.saved_cache = preserve_full_cache(graph, manager)

    def update(self, changed_modules: List[Tuple[str, str]]) -> List[str]:
        """Update previous build result by processing changed modules.

        Also propagate changes to other modules as needed, but only process
        those parts of other modules that are affected by the changes. Retain
        the existing ASTs and symbol tables of unaffected modules.

        Args:
            changed_modules: Modules changed since the previous update/build; each is
                a (module id, path) tuple. Includes modified, added and deleted modules.
                Assume this is correct; it's not validated here.

        Returns:
            A list of errors.
        """
        changed_ids = [id for id, _ in changed_modules]
        if DEBUG:
            print('==== update %s ====' % changed_ids)
        if self.blocking_errors:
            # TODO: Relax this requirement
            assert self.blocking_errors == changed_ids
        manager = self.manager
        graph = self.graph

        # Record symbol table snaphots of old versions of changed moduiles.
        old_snapshots = {}
        for id, _ in changed_modules:
            if id in manager.modules:
                snapshot = snapshot_symbol_table(id, manager.modules[id].names)
                old_snapshots[id] = snapshot
            else:
                old_snapshots[id] = {}

        manager.errors.reset()
        try:
            new_modules, self.graph = build_incremental_step(manager, changed_modules, graph)
        except CompileError as err:
            self.blocking_errors = changed_ids
            return err.messages
        self.blocking_errors = []
        graph = self.graph

        # TODO: What to do with stale dependencies?
        triggered = calculate_active_triggers(manager, old_snapshots, new_modules)
        if DEBUG:
            print('triggered:', sorted(triggered))
        update_dependencies(new_modules, self.deps, graph, self.options)
        propagate_changes_using_dependencies(manager, graph, self.deps, triggered,
                                             set(changed_ids),
                                             self.previous_targets_with_errors,
                                             graph)
        self.previous_targets_with_errors = manager.errors.targets()

        # Preserve current state.
        for id, _ in changed_modules:
            # Generate metadata so that we can reuse the AST in the next run.
            graph[id].write_cache()
        for id, state in graph.items():
            if state.tree is None and id in manager.saved_cache:
                meta, tree, type_map = manager.saved_cache[id]
                state.tree = tree
        manager.saved_cache = preserve_full_cache(graph, manager)

        return manager.errors.messages()


def get_all_dependencies(manager: BuildManager, graph: Dict[str, State],
                         options: Options) -> Dict[str, Set[str]]:
    """Return the fine-grained dependency map for an entire build."""
    deps = {}  # type: Dict[str, Set[str]]
    update_dependencies(manager.modules, deps, graph, options)
    return deps


def build_incremental_step(manager: BuildManager,
                           changed_modules: List[Tuple[str, str]],
                           graph: Dict[str, State]) -> Tuple[Dict[str, MypyFile], Graph]:
    """Build new versions of changed modules only.

    Raise CompleError on encountering a blocking error.

    Return the new ASTs for the changed modules.
    """
    assert len(changed_modules) == 1
    id, path = changed_modules[0]
    if id in manager.modules:
        assert path == manager.modules[id].path, '%s != %s' % (path, manager.modules[id].path)
    old_modules = dict(manager.modules)

    sources = get_sources(graph, changed_modules)
    changed_set = {id for id, _ in changed_modules}

    invalidate_stale_cache_entries(manager.saved_cache, changed_modules)

    old_graph = graph
    manager.missing_modules = set()
    graph = load_graph(sources, manager)

    # Find any other modules brought in by imports.
    for st in graph.values():
        if st.id not in old_graph and st.id not in changed_set:
            changed_set.add(st.id)
            assert st.path
            changed_modules.append((st.id, st.path))
    # TODO: Handle multiple changed modules per step
    assert len(changed_modules) == 1, changed_modules

    state = graph[id]

    # Parse file and run first pass of semantic analysis.
    state.parse_file()

    # TODO: state.fix_suppressed_dependencies()?

    # Run remaining passes of semantic analysis.
    try:
        state.semantic_analysis()
    except CompileError as err:
        # TODO: What if there are multiple changed modules?
        # There was a blocking error, so module AST is incomplete. Restore old modules.
        manager.modules.clear()
        manager.modules.update(old_modules)
        raise err
    state.semantic_analysis_pass_three()
    state.semantic_analysis_apply_patches()

    # Merge old and new ASTs.
    assert state.tree is not None, "file must be at least parsed"
    new_modules = {id: state.tree}
    replace_modules_with_new_variants(manager, graph, old_modules, new_modules)

    # Perform type checking.
    state.type_check_first_pass()
    # TODO: state.type_check_second_pass()?
    state.finish_passes()
    # TODO: state.write_cache()?
    # TODO: state.mark_as_rechecked()?
    # TODO: Store new State in graph, as it has updated dependencies etc.

    graph[id] = state

    return new_modules, graph


def get_sources(graph: Graph, changed_modules: List[Tuple[str, str]]) -> List[BuildSource]:
    sources = [BuildSource(st.path, st.id, None) for st in graph.values()]
    for id, path in changed_modules:
        if id not in graph:
            sources.append(BuildSource(path, id, None))
    return sources


def preserve_full_cache(graph: Graph, manager: BuildManager) -> SavedCache:
    saved_cache = {}
    for id, state in graph.items():
        assert state.id == id
        if state.tree is not None:
            meta = state.meta
            if meta is None:
                assert state.path
                # TODO: share the following with mypy.build
                dep_prios = [state.priorities.get(dep, PRI_HIGH) for dep in state.dependencies]
                meta = memory_only_cache_meta(
                    id,
                    state.path,
                    state.dependencies,
                    state.suppressed,
                    list(state.child_modules),
                    dep_prios,
                    state.source_hash,
                    state.ignore_all,
                    manager)
            saved_cache[id] = (meta, state.tree, state.type_map())
    return saved_cache


def memory_only_cache_meta(id: str,
                           path: str,
                           dependencies: List[str],
                           suppressed: List[str],
                           child_modules: List[str],
                           dep_prios: List[int],
                           source_hash: str,
                           ignore_all: bool,
                           manager: BuildManager) -> CacheMeta:
    options = manager.options.clone_for_module(id)
    meta = {'id': id,
            'path': path,
            'mtime': -1,
            'size': -1,
            'hash': source_hash,
            'data_mtime': -1,
            'dependencies': dependencies,
            'suppressed': suppressed,
            'child_modules': child_modules,
            'options': options.select_options_affecting_cache(),
            'dep_prios': dep_prios,
            'interface_hash': '',
            'version_id': manager.version_id,
            'ignore_all': ignore_all,
            }
    return cache_meta_from_dict(meta, '')


def invalidate_stale_cache_entries(cache: SavedCache,
                                   changed_modules: List[Tuple[str, str]]) -> None:
    for name, _ in changed_modules:
        if name in cache:
            del cache[name]


def verify_dependencies(state: State, manager: BuildManager) -> None:
    """Report errors for import targets in module that don't exist."""
    for dep in state.dependencies + state.suppressed: # TODO: ancestors?
        if dep not in manager.modules:
            assert state.tree
            line = find_import_line(state.tree, dep) or 1
            assert state.path
            manager.module_not_found(state.path, state.id, line, dep)


def find_import_line(node: MypyFile, target: str) -> Optional[int]:
    for imp in node.imports:
        if isinstance(imp, Import):
            for name, _ in imp.ids:
                if name == target:
                    return imp.line
        if isinstance(imp, ImportFrom):
            if imp.id == target:
                return imp.line
            # TODO: Relative imports
            for name, _ in imp.names:
                if '%s.%s' % (imp.id, name) == target:
                    return imp.line
        # TODO: ImportAll
    return None


def update_dependencies(new_modules: Dict[str, MypyFile],
                        deps: Dict[str, Set[str]],
                        graph: Dict[str, State],
                        options: Options) -> None:
    for id, node in new_modules.items():
        if '/typeshed/' in node.path:
            # We don't track changes to typeshed -- the assumption is that they are only changed
            # as part of mypy updates, which will invalidate everything anyway.
            #
            # TODO: Not a reliable test, as we could have a package named typeshed.
            # TODO: Consider relaxing this -- maybe allow some typeshed changes to be tracked.
            continue
        module_deps = get_dependencies(target=node,
                                       type_map=graph[id].type_map(),
                                       python_version=options.python_version)
        for trigger, targets in module_deps.items():
            deps.setdefault(trigger, set()).update(targets)


def calculate_active_triggers(manager: BuildManager,
                              old_snapshots: Dict[str, Dict[str, SnapshotItem]],
                              new_modules: Dict[str, MypyFile]) -> Set[str]:
    """Determine activated triggers by comparing old and new symbol tables.

    For example, if only the signature of function m.f is different in the new
    symbol table, return {'<m.f>'}.
    """
    names = set()  # type: Set[str]
    for id in new_modules:
        snapshot1 = old_snapshots[id]
        snapshot2 = snapshot_symbol_table(id, new_modules[id].names)
        names |= compare_symbol_table_snapshots(id, snapshot1, snapshot2)
    return {make_trigger(name) for name in names}


def replace_modules_with_new_variants(
        manager: BuildManager,
        graph: Dict[str, State],
        old_modules: Dict[str, MypyFile],
        new_modules: Dict[str, MypyFile]) -> None:
    """Replace modules with newly builds versions.

    Retain the identities of externally visible AST nodes in the
    old ASTs so that references to the affected modules from other
    modules will still be valid (unless something was deleted or
    replaced with an incompatible definition, in which case there
    will be dangling references that will be handled by
    propagate_changes_using_dependencies).
    """
    for id in new_modules:
        if id in old_modules:
            merge_asts(old_modules[id], old_modules[id].names,
                       new_modules[id], new_modules[id].names)
            manager.modules[id] = old_modules[id]


def propagate_changes_using_dependencies(
        manager: BuildManager,
        graph: Dict[str, State],
        deps: Dict[str, Set[str]],
        triggered: Set[str],
        up_to_date_modules: Set[str],
        targets_with_errors: Set[str],
        modules: Iterable[str]) -> None:
    # TODO: Multiple type checking passes
    # TODO: Restrict the number of iterations to some maximum to avoid infinite loops

    # Propagate changes until nothing visible has changed during the last
    # iteration.
    while triggered or targets_with_errors:
        todo = find_targets_recursive(triggered, deps, manager.modules, up_to_date_modules)
        # Also process targets that used to have errors, as otherwise some
        # errors might be lost.
        for target in targets_with_errors:
            id = module_prefix(modules, target)
            if id not in up_to_date_modules:
                if id not in todo:
                    todo[id] = set()
                if DEBUG:
                    print('process', target)
                todo[id].update(lookup_target(manager.modules, target))
        triggered = set()
        # TODO: Preserve order (set is not optimal)
        for id, nodes in sorted(todo.items(), key=lambda x: x[0]):
            assert id not in up_to_date_modules
            triggered |= reprocess_nodes(manager, graph, id, nodes, deps)
        # Changes elsewhere may require us to reprocess modules that were
        # previously considered up to date. For example, there may be a
        # dependency loop that loops back to an originally processed module.
        up_to_date_modules = set()
        targets_with_errors = set()
        if DEBUG:
            print('triggered:', list(triggered))


def find_targets_recursive(
        triggers: Set[str],
        deps: Dict[str, Set[str]],
        modules: Dict[str, MypyFile],
        up_to_date_modules: Set[str]) -> Dict[str, Set[DeferredNode]]:
    """Find names of all targets that need to reprocessed, given some triggers.

    Returns: Dictionary from module id to a set of stale targets.
    """
    result = {}  # type: Dict[str, Set[DeferredNode]]
    worklist = triggers
    processed = set()  # type: Set[str]

    # Find AST nodes corresponding to each target.
    #
    # TODO: Don't rely on a set, since the items are in an unpredictable order.
    while worklist:
        processed |= worklist
        current = worklist
        worklist = set()
        for target in current:
            if target.startswith('<'):
                worklist |= deps.get(target, set()) - processed
            else:
                module_id = module_prefix(modules, target)
                if module_id in up_to_date_modules:
                    # Already processed.
                    continue
                if module_id not in result:
                    result[module_id] = set()
                if DEBUG:
                    print('process', target)
                deferred = lookup_target(modules, target)
                result[module_id].update(deferred)

    return result


def reprocess_nodes(manager: BuildManager,
                    graph: Dict[str, State],
                    module_id: str,
                    nodeset: Set[DeferredNode],
                    deps: Dict[str, Set[str]]) -> Set[str]:
    """Reprocess a set of nodes within a single module.

    Return fired triggers.
    """
    file_node = manager.modules[module_id]

    def key(node: DeferredNode) -> str:
        fullname = node.node.fullname()
        if isinstance(node.node, FuncDef) and fullname is None:
            assert node.node.info is not None
            fullname = '%s.%s' % (node.node.info.fullname(), node.node.name())
        return fullname

    # Some nodes by full name so that the order of processing is deterministic.
    nodes = sorted(nodeset, key=key)

    # Strip semantic analysis information.
    for deferred in nodes:
        strip_target(deferred.node)
    semantic_analyzer = manager.semantic_analyzer

    # Second pass of semantic analysis. We don't redo the first pass, because it only
    # does local things that won't go stale.
    for deferred in nodes:
        with semantic_analyzer.file_context(
                file_node=file_node,
                fnam=file_node.path,
                options=manager.options,
                active_type=deferred.active_typeinfo):
            manager.semantic_analyzer.refresh_partial(deferred.node)

    # Third pass of semantic analysis.
    for deferred in nodes:
        with semantic_analyzer.file_context(
                file_node=file_node,
                fnam=file_node.path,
                options=manager.options,
                active_type=deferred.active_typeinfo):
            manager.semantic_analyzer_pass3.refresh_partial(deferred.node)

    # Keep track of potentially affected attribute types before type checking.
    old_types_map = get_enclosing_namespace_types(nodes)

    # Type check.
    meta, file_node, type_map = manager.saved_cache[module_id]
    graph[module_id].tree = file_node
    graph[module_id].type_checker().type_map = type_map
    graph[module_id].type_checker().check_second_pass(nodes)  # TODO: check return value

    # Check if any attribute types were changed and need to be propagated further.
    new_triggered = get_triggered_namespace_items(old_types_map)

    # Dependencies may have changed.
    update_deps(module_id, nodes, graph, deps, manager.options)

    # Report missing imports.
    verify_dependencies(graph[module_id], manager)

    return new_triggered


NamespaceNode = Union[TypeInfo, MypyFile]


def get_enclosing_namespace_types(nodes: List[DeferredNode]) -> Dict[NamespaceNode,
                                                                     Dict[str, Type]]:
    types = {}  # type: Dict[NamespaceNode, Dict[str, Type]]
    for deferred in nodes:
        info = deferred.active_typeinfo
        if info:
            target = info  # type: Optional[NamespaceNode]
        elif isinstance(deferred.node, MypyFile):
            target = deferred.node
        else:
            target = None
        if target and target not in types:
            local_types = {name: node.node.type
                         for name, node in target.names.items()
                         if isinstance(node.node, Var) and node.node.type}
            types[target] = local_types
    return types


def get_triggered_namespace_items(old_types_map: Dict[NamespaceNode, Dict[str, Type]]) -> Set[str]:
    new_triggered = set()
    for namespace_node, old_types in old_types_map.items():
        for name, node in namespace_node.names.items():
            if (name in old_types and
                    (not isinstance(node.node, Var) or
                     node.node.type and not is_identical_type(node.node.type, old_types[name]))):
                # Type checking a method changed an attribute type.
                new_triggered.add(make_trigger('{}.{}'.format(namespace_node.fullname(), name)))
    return new_triggered


def update_deps(module_id: str,
                nodes: List[DeferredNode],
                graph: Dict[str, State],
                deps: Dict[str, Set[str]],
                options: Options) -> None:
    for deferred in nodes:
        node = deferred.node
        type_map = graph[module_id].type_map()
        new_deps = get_dependencies_of_target(module_id, node, type_map, options.python_version)
        for trigger, targets in new_deps.items():
            deps.setdefault(trigger, set()).update(targets)


def lookup_target(modules: Dict[str, MypyFile], target: str) -> List[DeferredNode]:
    """Look up a target by fully-qualified name."""
    module, rest = split_target(modules, target)
    if rest:
        components = rest.split('.')
    else:
        components = []
    node = modules[module]  # type: Optional[SymbolNode]
    file = None  # type: Optional[MypyFile]
    active_class = None
    active_class_name = None
    for c in components:
        if isinstance(node, TypeInfo):
            active_class = node
            active_class_name = node.name()
        # TODO: Is it possible for the assertion to fail?
        if isinstance(node, MypyFile):
            file = node
        assert isinstance(node, (MypyFile, TypeInfo))
        node = node.names[c].node
    if isinstance(node, TypeInfo):
        # A ClassDef target covers the body of the class and everything defined
        # within it.  To get the body we include the entire surrounding target,
        # typically a module top-level, since we don't support processing class
        # bodies as separate entitites for simplicity.
        assert file is not None
        result = [DeferredNode(file, None, None)]
        for name, symnode in node.names.items():
            node = symnode.node
            if isinstance(node, FuncDef):
                result.extend(lookup_target(modules, target + '.' + name))
        return result
    if isinstance(node, Decorator):
        # Decorator targets actually refer to the function definition only.
        node = node.func
    assert isinstance(node, (FuncDef, MypyFile)), 'unexpected type: %s' % type(node)
    return [DeferredNode(node, active_class_name, active_class)]
