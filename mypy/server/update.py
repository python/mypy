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

import os.path
from typing import Dict, List, Set, Tuple, Iterable, Union, Optional, Mapping, NamedTuple

from mypy.build import (
    BuildManager, State, BuildSource, Graph, load_graph, SavedCache, CacheMeta,
    cache_meta_from_dict, find_module_clear_caches
)
from mypy.checker import DeferredNode
from mypy.errors import Errors, CompileError
from mypy.nodes import (
    MypyFile, FuncDef, TypeInfo, Expression, SymbolNode, Var, FuncBase, ClassDef, Decorator,
    Import, ImportFrom, OverloadedFuncDef, SymbolTable
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


MAX_ITER = 1000


class FineGrainedBuildManager:
    def __init__(self,
                 manager: BuildManager,
                 graph: Graph) -> None:
        """Initialize fine-grained build based on a batch build.

        Args:
            manager: State of the build (mutated by this class)
            graph: Additional state of the build (only read to initialize state)
        """
        self.manager = manager
        self.options = manager.options
        self.previous_modules = get_module_to_path_map(manager)
        self.deps = get_all_dependencies(manager, graph, self.options)
        self.previous_targets_with_errors = manager.errors.targets()
        # Module, if any, that had blocking errors in the last run as (id, path) tuple.
        # TODO: Handle blocking errors in the initial build
        self.blocking_error = None  # type: Optional[Tuple[str, str]]
        # Module that we haven't processed yet but that are known to be stale.
        self.stale = []  # type: List[Tuple[str, str]]
        mark_all_meta_as_memory_only(graph, manager)
        manager.saved_cache = preserve_full_cache(graph, manager)
        self.type_maps = extract_type_maps(graph)
        # Active triggers during the last update
        self.triggered = []  # type: List[str]

    def update(self, changed_modules: List[Tuple[str, str]]) -> List[str]:
        """Update previous build result by processing changed modules.

        Also propagate changes to other modules as needed, but only process
        those parts of other modules that are affected by the changes. Retain
        the existing ASTs and symbol tables of unaffected modules.

        Create new graph with new State objects, but reuse original BuildManager.

        Args:
            changed_modules: Modules changed since the previous update/build; each is
                a (module id, path) tuple. Includes modified, added and deleted modules.
                Assume this is correct; it's not validated here.

        Returns:
            A list of errors.
        """
        assert changed_modules, 'No changed modules'

        # Reset global caches for the new build.
        find_module_clear_caches()

        self.triggered = []
        changed_modules = dedupe_modules(changed_modules + self.stale)
        initial_set = {id for id, _ in changed_modules}
        if DEBUG:
            print('==== update %s ====' % ', '.join(repr(id)
                                                    for id, _ in changed_modules))
            if self.previous_targets_with_errors:
                print('previous targets with errors: %s' %
                      sorted(self.previous_targets_with_errors))

        if self.blocking_error:
            # Handle blocking errors first. We'll exit as soon as we find a
            # module that still has blocking errors.
            if DEBUG:
                print('existing blocker: %s' % self.blocking_error[0])
            changed_modules = dedupe_modules([self.blocking_error] + changed_modules)
            self.blocking_error = None

        while changed_modules:
            next_id, next_path = changed_modules.pop(0)
            if next_id not in self.previous_modules and next_id not in initial_set:
                print('skip %r (module not in import graph)' % next_id)
                continue
            result = self.update_single(next_id, next_path)
            messages, remaining, (next_id, next_path), blocker = result
            changed_modules = [(id, path) for id, path in changed_modules
                               if id != next_id]
            changed_modules = dedupe_modules(changed_modules + remaining)
            if blocker:
                self.blocking_error = (next_id, next_path)
                self.stale = changed_modules
                return messages

        return messages

    def update_single(self, module: str, path: str) -> Tuple[List[str],
                                                             List[Tuple[str, str]],
                                                             Tuple[str, str],
                                                             bool]:
        """Update a single modified module.

        If the module contains imports of previously unseen modules, only process one of
        the new modules and return the remaining work to be done.

        Returns:
            Tuple with these items:

            - Error messages
            - Remaining modules to process as (module id, path) tuples
            - Module which was actually processed as (id, path) tuple
            - Whether there was a blocking error in the module
        """
        if DEBUG:
            print('--- update single %r ---' % module)

        # TODO: If new module brings in other modules, we parse some files multiple times.
        manager = self.manager
        previous_modules = self.previous_modules

        # Record symbol table snaphot of old version the changed module.
        old_snapshots = {}  # type: Dict[str, Dict[str, SnapshotItem]]
        if module in manager.modules:
            snapshot = snapshot_symbol_table(module, manager.modules[module].names)
            old_snapshots[module] = snapshot

        manager.errors.reset()
        result = update_single_isolated(module, path, manager, previous_modules)
        if isinstance(result, BlockedUpdate):
            # Blocking error -- just give up
            module, path, remaining = result
            self.previous_modules = get_module_to_path_map(manager)
            return manager.errors.messages(), remaining, (module, path), True
        assert isinstance(result, NormalUpdate)  # Work around #4124
        module, path, remaining, tree, graph = result

        # TODO: What to do with stale dependencies?
        triggered = calculate_active_triggers(manager, old_snapshots, {module: tree})
        if DEBUG:
            filtered = [trigger for trigger in triggered
                        if not trigger.endswith('__>')]
            print('triggered:', sorted(filtered))
        self.triggered.extend(triggered)
        update_dependencies({module: tree}, self.deps, graph, self.options)
        propagate_changes_using_dependencies(manager, graph, self.deps, triggered,
                                             {module},
                                             self.previous_targets_with_errors,
                                             graph)

        # Preserve state needed for the next update.
        self.previous_targets_with_errors = manager.errors.targets()
        # If deleted, module won't be in the graph.
        if module in graph:
            # Generate metadata so that we can reuse the AST in the next run.
            graph[module].write_cache()
        for id, state in graph.items():
            # Look up missing ASTs from saved cache.
            if state.tree is None and id in manager.saved_cache:
                meta, tree, type_map = manager.saved_cache[id]
                state.tree = tree
        mark_all_meta_as_memory_only(graph, manager)
        manager.saved_cache = preserve_full_cache(graph, manager)
        self.previous_modules = get_module_to_path_map(manager)
        self.type_maps = extract_type_maps(graph)

        return manager.errors.messages(), remaining, (module, path), False


def mark_all_meta_as_memory_only(graph: Dict[str, State],
                                 manager: BuildManager) -> None:
    for id, state in graph.items():
        if id in manager.saved_cache:
            # Don't look at disk.
            old = manager.saved_cache[id]
            manager.saved_cache[id] = (old[0]._replace(memory_only=True),
                                       old[1],
                                       old[2])


def get_all_dependencies(manager: BuildManager, graph: Dict[str, State],
                         options: Options) -> Dict[str, Set[str]]:
    """Return the fine-grained dependency map for an entire build."""
    deps = {}  # type: Dict[str, Set[str]]
    update_dependencies(manager.modules, deps, graph, options)
    return deps


# The result of update_single_isolated when no blockers, with these items:
#
# - Id of the changed module (can be different from the module argument)
# - Path of the changed module
# - New AST for the changed module (None if module was deleted)
# - The entire updated build graph
# - Remaining changed modules that are not processed yet as (module id, path)
#   tuples (non-empty if the original changed module imported other new
#   modules)
NormalUpdate = NamedTuple('NormalUpdate', [('module', str),
                                           ('path', str),
                                           ('remaining', List[Tuple[str, str]]),
                                           ('tree', Optional[MypyFile]),
                                           ('graph', Graph)])

# The result of update_single_isolated when there is a blocking error. Items
# are similar to NormalUpdate (but there are fewer).
BlockedUpdate = NamedTuple('BlockedUpdate', [('module', str),
                                             ('path', str),
                                             ('remaining', List[Tuple[str, str]])])

UpdateResult = Union[NormalUpdate, BlockedUpdate]


def update_single_isolated(module: str,
                           path: str,
                           manager: BuildManager,
                           previous_modules: Dict[str, str]) -> UpdateResult:
    """Build a new version of one changed module only.

    Don't propagate changes to elsewhere in the program. Raise CompleError on
    encountering a blocking error.

    Args:
        module: Changed module (modified, created or deleted)
        path: Path of the changed module
        manager: Build manager
        graph: Build graph

    Returns a named tuple describing the result (see above for details).
    """
    if module in manager.modules:
        assert_equivalent_paths(path, manager.modules[module].path)
    elif DEBUG:
        print('new module %r' % module)

    old_modules = dict(manager.modules)
    sources = get_sources(previous_modules, [(module, path)])
    invalidate_stale_cache_entries(manager.saved_cache, [(module, path)])

    manager.missing_modules = set()
    try:
        graph = load_graph(sources, manager)
    except CompileError as err:
        # Parse error somewhere in the program -- a blocker
        assert err.module_with_blocker
        if err.module_with_blocker != module:
            # Blocker is in a fresh module. Delete the state of the original target module
            # since it will be stale.
            #
            # TODO: It would be more efficient to store the original target module
            path = manager.modules[module].path
            del manager.modules[module]
            remaining_modules = [(module, path)]
        else:
            remaining_modules = []
        return BlockedUpdate(err.module_with_blocker, path, remaining_modules)

    if not os.path.isfile(path):
        graph = delete_module(module, graph, manager)
        return NormalUpdate(module, path, [], None, graph)

    # Find any other modules brought in by imports.
    changed_modules = get_all_changed_modules(module, path, previous_modules, graph)
    # If there are multiple modules to process, only process the last one of them and return
    # the remaining ones to the caller. Often the last one is going to be imported by
    # one of the prior modules, making it more efficient to process it first.
    if len(changed_modules) > 1:
        module, path = changed_modules.pop()
        remaining_modules = changed_modules
        # The remaining modules haven't been processed yet so drop them.
        for id, _ in remaining_modules:
            del manager.modules[id]
            del graph[id]
        if DEBUG:
            print('--> %r (newly imported)' % module)
    else:
        remaining_modules = []

    state = graph[module]

    # Process the changed file.
    state.parse_file()
    # TODO: state.fix_suppressed_dependencies()?
    try:
        state.semantic_analysis()
    except CompileError as err:
        # There was a blocking error, so module AST is incomplete. Restore old modules.
        manager.modules.clear()
        manager.modules.update(old_modules)
        del graph[module]
        return BlockedUpdate(module, path, remaining_modules)
    state.semantic_analysis_pass_three()
    state.semantic_analysis_apply_patches()

    # Merge old and new ASTs.
    assert state.tree is not None, "file must be at least parsed"
    new_modules = {module: state.tree}  # type: Dict[str, Optional[MypyFile]]
    replace_modules_with_new_variants(manager, graph, old_modules, new_modules)

    # Perform type checking.
    state.type_check_first_pass()
    state.type_check_second_pass()
    state.finish_passes()
    # TODO: state.write_cache()?
    # TODO: state.mark_as_rechecked()?

    graph[module] = state

    return NormalUpdate(module, path, remaining_modules, state.tree, graph)


def assert_equivalent_paths(path1: str, path2: str) -> None:
    path1 = os.path.normpath(path1)
    path2 = os.path.normpath(path2)
    assert path1 == path2, '%s != %s' % (path1, path2)


def delete_module(module_id: str,
                  graph: Dict[str, State],
                  manager: BuildManager) -> Dict[str, State]:
    if DEBUG:
        print('delete module %r' % module_id)
    # TODO: Deletion of a package
    # TODO: Remove deps for the module (this only affects memory use, not correctness)
    assert module_id not in graph
    new_graph = graph.copy()
    del manager.modules[module_id]
    if module_id in manager.saved_cache:
        del manager.saved_cache[module_id]
    components = module_id.split('.')
    if len(components) > 1:
        parent = manager.modules['.'.join(components[:-1])]
        if components[-1] in parent.names:
            del parent.names[components[-1]]
    return new_graph


def dedupe_modules(modules: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()  # type: Set[str]
    result = []
    for id, path in modules:
        if id not in seen:
            seen.add(id)
            result.append((id, path))
    return result


def get_module_to_path_map(manager: BuildManager) -> Dict[str, str]:
    return {module: node.path
            for module, node in manager.modules.items()}


def get_sources(modules: Dict[str, str],
                changed_modules: List[Tuple[str, str]]) -> List[BuildSource]:
    # TODO: Race condition when reading from the file system; we should only read each
    #       bit of external state once during a build to have a consistent view of the world
    items = sorted(modules.items(), key=lambda x: x[0])
    sources = [BuildSource(path, id, None)
               for id, path in items
               if os.path.isfile(path)]
    for id, path in changed_modules:
        if os.path.isfile(path) and id not in modules:
            sources.append(BuildSource(path, id, None))
    return sources


def get_all_changed_modules(root_module: str,
                            root_path: str,
                            old_modules: Dict[str, str],
                            new_graph: Dict[str, State]) -> List[Tuple[str, str]]:
    changed_set = {root_module}
    changed_modules = [(root_module, root_path)]
    for st in new_graph.values():
        if st.id not in old_modules and st.id not in changed_set:
            assert st.path
            changed_set.add(st.id)
            changed_modules.append((st.id, st.path))
    return changed_modules


def preserve_full_cache(graph: Graph, manager: BuildManager) -> SavedCache:
    """Preserve every module with an AST in the graph, including modules with errors."""
    saved_cache = {}
    for id, state in graph.items():
        assert state.id == id
        if state.tree is not None:
            meta = state.meta
            if meta is None:
                # No metadata, likely because of an error. We still want to retain the AST.
                # There is no corresponding JSON so create partial "memory-only" metadata.
                assert state.path
                dep_prios = state.dependency_priorities()
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
            else:
                meta = meta._replace(memory_only=True)
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
    """Create cache metadata for module that doesn't have a JSON cache files.

    JSON cache files aren't written for modules with errors, but we want to still
    cache them in fine-grained incremental mode.
    """
    options = manager.options.clone_for_module(id)
    # Note that we omit attributes related to the JSON files.
    meta = {'id': id,
            'path': path,
            'memory_only': True,  # Important bit: don't expect JSON files to exist
            'hash': source_hash,
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
    for dep in state.dependencies + state.suppressed:  # TODO: ancestors?
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


def update_dependencies(new_modules: Mapping[str, Optional[MypyFile]],
                        deps: Dict[str, Set[str]],
                        graph: Dict[str, State],
                        options: Options) -> None:
    for id, node in new_modules.items():
        if node is None:
            continue
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
                              new_modules: Dict[str, Optional[MypyFile]]) -> Set[str]:
    """Determine activated triggers by comparing old and new symbol tables.

    For example, if only the signature of function m.f is different in the new
    symbol table, return {'<m.f>'}.
    """
    names = set()  # type: Set[str]
    for id in new_modules:
        snapshot1 = old_snapshots.get(id)
        if snapshot1 is None:
            names.add(id)
            snapshot1 = {}
        new = new_modules[id]
        if new is None:
            snapshot2 = snapshot_symbol_table(id, SymbolTable())
            names.add(id)
        else:
            snapshot2 = snapshot_symbol_table(id, new.names)
        names |= compare_symbol_table_snapshots(id, snapshot1, snapshot2)
    return {make_trigger(name) for name in names}


def replace_modules_with_new_variants(
        manager: BuildManager,
        graph: Dict[str, State],
        old_modules: Dict[str, MypyFile],
        new_modules: Dict[str, Optional[MypyFile]]) -> None:
    """Replace modules with newly builds versions.

    Retain the identities of externally visible AST nodes in the
    old ASTs so that references to the affected modules from other
    modules will still be valid (unless something was deleted or
    replaced with an incompatible definition, in which case there
    will be dangling references that will be handled by
    propagate_changes_using_dependencies).
    """
    for id in new_modules:
        new_module = new_modules[id]
        if id in old_modules and new_module is not None:
            merge_asts(old_modules[id], old_modules[id].names,
                       new_module, new_module.names)
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
    num_iter = 0

    # Propagate changes until nothing visible has changed during the last
    # iteration.
    while triggered or targets_with_errors:
        num_iter += 1
        if num_iter > MAX_ITER:
            raise RuntimeError('Max number of iterations (%d) reached (endless loop?)' % MAX_ITER)

        todo = find_targets_recursive(triggered, deps, manager.modules, up_to_date_modules)
        # Also process targets that used to have errors, as otherwise some
        # errors might be lost.
        for target in targets_with_errors:
            id = module_prefix(modules, target)
            if id is not None and id not in up_to_date_modules:
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
                if module_id is None:
                    # Deleted module.
                    continue
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
    if module_id not in manager.saved_cache or module_id not in graph:
        if DEBUG:
            print('%s not in saved cache or graph (blocking errors or deleted?)' % module_id)
        return set()

    file_node = manager.modules[module_id]
    old_symbols = find_symbol_tables_recursive(file_node.fullname(), file_node.names)
    old_symbols = {name: names.copy() for name, names in old_symbols.items()}

    def key(node: DeferredNode) -> str:
        fullname = node.node.fullname()
        if fullname is None:
            if isinstance(node.node, FuncDef):
                info = node.node.info
            elif isinstance(node.node, OverloadedFuncDef):
                info = node.node.items[0].info
            else:
                assert False, "'None' fullname for %s instance" % type(node.node)
            assert info is not None
            fullname = '%s.%s' % (info.fullname(), node.node.name())
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

    # Merge symbol tables to preserve identities of AST nodes. The file node will remain
    # the same, but other nodes may have been recreated with different identities, such as
    # NamedTuples defined using assignment statements.
    new_symbols = find_symbol_tables_recursive(file_node.fullname(), file_node.names)
    for name in old_symbols:
        if name in new_symbols:
            merge_asts(file_node, old_symbols[name], file_node, new_symbols[name])

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


def find_symbol_tables_recursive(prefix: str, symbols: SymbolTable) -> Dict[str, SymbolTable]:
    """Find all nested symbol tables.

    Args:
        prefix: Full name prefix (used for return value keys and to filter result so that
            cross references to other modules aren't included)
        symbols: Root symbol table

    Returns a dictionary from full name to corresponding symbol table.
    """
    result = {}
    result[prefix] = symbols
    for name, node in symbols.items():
        if isinstance(node.node, TypeInfo) and node.node.fullname().startswith(prefix + '.'):
            more = find_symbol_tables_recursive(prefix + '.' + name, node.node.names)
            result.update(more)
    return result


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
    items = split_target(modules, target)
    if items is None:
        # Deleted target
        return []
    module, rest = items
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
        if c not in node.names:
            # Deleted target
            return []
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
    assert isinstance(node, (FuncDef,
                             MypyFile,
                             OverloadedFuncDef)), 'unexpected type: %s' % type(node)
    return [DeferredNode(node, active_class_name, active_class)]


def extract_type_maps(graph: Graph) -> Dict[str, Dict[Expression, Type]]:
    return {id: state.type_map() for id, state in graph.items()}
