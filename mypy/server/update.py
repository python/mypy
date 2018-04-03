"""Update build by processing changes using fine-grained dependencies.

Use fine-grained dependencies to update targets in other modules that
may be affected by externally-visible changes in the changed modules.

This forms the core of the fine-grained incremental daemon mode. This
module is not used at all by the 'classic' (non-daemon) incremental
mode.

Here is some motivation for this mode:

* By keeping program state in memory between incremental runs, we
  only have to process changed modules, not their dependencies. The
  classic incremental mode has to deserialize the symbol tables of
  all dependencies of changed modules, which can be slow for large
  programs.

* Fine-grained dependencies allow processing only the relevant parts
  of modules indirectly affected by a change. Say, if only one function
  in a large module is affected by a change in another module, only this
  function is processed. The classic incremental mode always processes
  an entire file as a unit, which is typically much slower.

* It's possible to independently process individual modules within an
  import cycle (SCC). Small incremental changes can be fast independent
  of the size of the related SCC. In classic incremental mode, any change
  within a SCC requires the entire SCC to be processed, which can slow
  things down considerably.

Some terms:

* A *target* is a function/method definition or the top level of a module.
  We refer to targets using their fully qualified name (e.g.
  'mod.Cls.method'). Targets are the smallest units of processing during
  fine-grained incremental checking.

* A *trigger* represents the properties of a part of a program, and it
  gets triggered/fired when these properties change. For example,
  '<mod.func>' refers to a module-level function. It gets triggered if
  the signature of the function changes, or if the function is removed,
  for example.

Some program state is maintained across multiple build increments in
memory:

* The full ASTs of all modules are stored in memory all the time (this
  includes the type map).

* A fine-grained dependency map is maintained, which maps triggers to
  affected program locations (these can be targets, triggers, or
  classes). The latter determine what other parts of a program need to
  be processed again due to a fired trigger.

Here's a summary of how a fine-grained incremental program update happens:

* Determine which modules have changes in their source code since the
  previous update.

* Process changed modules one at a time. Perform a separate full update
  for each changed module, but only report the errors after all modules
  have been processed, since the intermediate states can generate bogus
  errors due to only seeing a partial set of changes.

* Each changed module is processed in full. We parse the module, and
  run semantic analysis to create a new AST and symbol table for the
  module. Reuse the existing ASTs and symbol tables of modules that
  have no changes in their source code. At the end of this stage, we have
  two ASTs and symbol tables for the changed module (the old and the new
  versions). The latter AST has not yet been type checked.

* Take a snapshot of the old symbol table. This is used later to determine
  which properties of the module have changed and which triggers to fire.

* Merge the old AST with the new AST, preserving the identities of
  externally visible AST nodes for which we can find a corresponding node
  in the new AST. (Look at mypy.server.astmerge for the details.) This
  way all external references to AST nodes in the changed module will
  continue to point to the right nodes (assuming they still have a valid
  target).

* Type check the new module.

* Take another snapshot of the symbol table of the changed module.
  Look at the differences between the old and new snapshots to determine
  which parts of the changed modules have changed. The result is a set of
  fired triggers.

* Using the dependency map and the fired triggers, decide which other
  targets have become stale and need to be reprocessed.

* Create new fine-grained dependencies for the changed module. We don't
  garbage collect old dependencies, since extra dependencies are relatively
  harmless (they take some memory and can theoretically slow things down
  a bit by causing redundant work). This is implemented in
  mypy.server.deps.

* Strip the stale AST nodes that we found above. This returns them to a
  state resembling the end of semantic analysis pass 1. We'll run semantic
  analysis again on the existing AST nodes, and since semantic analysis
  is not idempotent, we need to revert some changes made during semantic
  analysis. This is implemented in mypy.server.aststrip.

* Run semantic analyzer passes 2 and 3 on the stale AST nodes, and type
  check them. We also need to do the symbol table snapshot comparison
  dance to find any changes, and we need to merge ASTs to preserve AST node
  identities.

* If some triggers haven been fired, continue processing and repeat the
  previous steps until no triggers are fired.

This is module is tested using end-to-end fine-grained incremental mode
test cases (test-data/unit/fine-grained*.test).
"""

import os
import time
import os.path
from typing import (
    Dict, List, Set, Tuple, Iterable, Union, Optional, Mapping, NamedTuple,
    Callable, overload
)

from mypy.build import (
    BuildManager, State, BuildSource, BuildResult, Graph, load_graph,
    PRI_INDIRECT, DEBUG_FINE_GRAINED, collect_protocol_deps
)
from mypy.checker import DeferredNode
from mypy.errors import Errors, CompileError
from mypy.nodes import (
    MypyFile, FuncDef, TypeInfo, Expression, SymbolNode, Var, FuncBase, ClassDef, Decorator,
    Import, ImportFrom, OverloadedFuncDef, SymbolTable, LambdaExpr
)
from mypy.options import Options
from mypy.types import Type
from mypy.fscache import FileSystemCache
from mypy.semanal import apply_semantic_analyzer_patches
from mypy.semanal_pass3 import add_protocol_members
from mypy.server.astdiff import (
    snapshot_symbol_table, compare_symbol_table_snapshots, SnapshotItem
)
from mypy.server.astmerge import merge_asts
from mypy.server.aststrip import strip_target
from mypy.server.deps import get_dependencies_of_target
from mypy.server.target import module_prefix, split_target
from mypy.server.trigger import make_trigger, WILDCARD_TAG


MAX_ITER = 1000


class FineGrainedBuildManager:
    def __init__(self, result: BuildResult) -> None:
        """Initialize fine-grained build based on a batch build.

        Args:
            result: Result from the initialized build.
                    The manager and graph will be taken over by this class.
            manager: State of the build (mutated by this class)
            graph: Additional state of the build (only read to initialize state)
        """
        manager = result.manager
        self.manager = manager
        self.graph = result.graph
        self.previous_modules = get_module_to_path_map(manager)
        self.deps = get_all_dependencies(manager, self.graph)
        self.previous_targets_with_errors = manager.errors.targets()
        self.previous_messages = result.errors[:]
        # Module, if any, that had blocking errors in the last run as (id, path) tuple.
        self.blocking_error = None  # type: Optional[Tuple[str, str]]
        # Module that we haven't processed yet but that are known to be stale.
        self.stale = []  # type: List[Tuple[str, str]]
        # Disable the cache so that load_graph doesn't try going back to disk
        # for the cache.
        self.manager.cache_enabled = False

        # Some hints to the test suite about what is going on:
        # Active triggers during the last update
        self.triggered = []  # type: List[str]
        # Modules passed to update during the last update
        self.changed_modules = []  # type: List[Tuple[str, str]]
        # Modules processed during the last update
        self.updated_modules = []  # type: List[str]
        self.prio_deps = {}  # type: Dict[str, Set[str]]
        self.update_protocol_deps()

    def update_protocol_deps(self) -> None:
        # TODO: fail gracefully if cache doesn't contain protocol deps data.
        assert self.manager.proto_deps is not None
        for trigger, targets in self.manager.proto_deps.low_prio.items():
            self.deps.setdefault(trigger, set()).update(targets)
        self.prio_deps = self.manager.proto_deps.high_prio.copy()

    def update(self,
               changed_modules: List[Tuple[str, str]],
               removed_modules: List[Tuple[str, str]]) -> List[str]:
        """Update previous build result by processing changed modules.

        Also propagate changes to other modules as needed, but only process
        those parts of other modules that are affected by the changes. Retain
        the existing ASTs and symbol tables of unaffected modules.

        Create new graph with new State objects, but reuse original BuildManager.

        Args:
            changed_modules: Modules changed since the previous update/build; each is
                a (module id, path) tuple. Includes modified and added modules.
                Assume this is correct; it's not validated here.
            removed_modules: Modules that have been deleted since the previous update
                or removed from the build.

        Returns:
            A list of errors.
        """
        changed_modules = changed_modules + removed_modules
        removed_set = {module for module, _ in removed_modules}
        self.changed_modules = changed_modules

        if not changed_modules:
            self.manager.fscache.flush()
            return self.previous_messages

        # Reset find_module's caches for the new build.
        self.manager.find_module_cache.clear()

        self.triggered = []
        self.updated_modules = []
        changed_modules = dedupe_modules(changed_modules + self.stale)
        initial_set = {id for id, _ in changed_modules}
        self.manager.log_fine_grained('==== update %s ====' % ', '.join(
            repr(id) for id, _ in changed_modules))
        if self.previous_targets_with_errors and is_verbose(self.manager):
            self.manager.log_fine_grained('previous targets with errors: %s' %
                             sorted(self.previous_targets_with_errors))

        if self.blocking_error:
            # Handle blocking errors first. We'll exit as soon as we find a
            # module that still has blocking errors.
            self.manager.log_fine_grained('existing blocker: %s' % self.blocking_error[0])
            changed_modules = dedupe_modules([self.blocking_error] + changed_modules)
            self.blocking_error = None

        while True:
            result = self.update_one(changed_modules, initial_set, removed_set)
            changed_modules, (next_id, next_path), blocker_messages = result

            if blocker_messages is not None:
                self.blocking_error = (next_id, next_path)
                self.stale = changed_modules
                messages = blocker_messages
                break

            # It looks like we are done processing everything, so now
            # reprocess all targets with errors. We are careful to
            # support the possibility that reprocessing an errored module
            # might trigger loading of a module, but I am not sure
            # if this can really happen.
            if not changed_modules:
                # N.B: We just checked next_id, so manager.errors contains
                # the errors from it. Thus we consider next_id up to date
                # when propagating changes from the errored targets,
                # which prevents us from reprocessing errors in it.
                changed_modules = propagate_changes_using_dependencies(
                    self.manager, self.graph, self.deps, self.prio_deps,
                    set(), {next_id}, self.previous_targets_with_errors)
                changed_modules = dedupe_modules(changed_modules)
                if not changed_modules:
                    # Preserve state needed for the next update.
                    self.previous_targets_with_errors = self.manager.errors.targets()
                    messages = self.manager.errors.new_messages()
                    break

        self.manager.fscache.flush()
        self.previous_messages = messages[:]
        self.manager.proto_deps.low_prio, self.manager.proto_deps.high_prio = collect_protocol_deps(self.graph)
        self.update_protocol_deps()
        return messages

    def update_one(self,
                   changed_modules: List[Tuple[str, str]],
                   initial_set: Set[str],
                   removed_set: Set[str]) -> Tuple[List[Tuple[str, str]],
                                                   Tuple[str, str],
                                                   Optional[List[str]]]:
        """Process a module from the list of changed modules.

        Returns:
            Tuple with these items:

            - Updated list of pending changed modules as (module id, path) tuples
            - Module which was actually processed as (id, path) tuple
            - If there was a blocking error, the error messages from it
        """
        t0 = time.time()
        next_id, next_path = changed_modules.pop(0)
        if next_id not in self.previous_modules and next_id not in initial_set:
            self.manager.log_fine_grained('skip %r (module not in import graph)' % next_id)
            return changed_modules, (next_id, next_path), None
        result = self.update_module(next_id, next_path, next_id in removed_set)
        remaining, (next_id, next_path), blocker_messages = result
        changed_modules = [(id, path) for id, path in changed_modules
                           if id != next_id]
        changed_modules = dedupe_modules(remaining + changed_modules)
        t1 = time.time()

        self.manager.log_fine_grained(
            "update once: {} in {:.3f}s - {} left".format(
                next_id, t1 - t0, len(changed_modules)))

        return changed_modules, (next_id, next_path), blocker_messages

    def update_module(self,
                      module: str,
                      path: str,
                      force_removed: bool) -> Tuple[List[Tuple[str, str]],
                                                    Tuple[str, str],
                                                    Optional[List[str]]]:
        """Update a single modified module.

        If the module contains imports of previously unseen modules, only process one of
        the new modules and return the remaining work to be done.

        Args:
            module: Id of the module
            path: File system path of the module
            force_removed: If True, consider module removed from the build even if path
                exists (used for removing an existing file from the build)

        Returns:
            Tuple with these items:

            - Remaining modules to process as (module id, path) tuples
            - Module which was actually processed as (id, path) tuple
            - If there was a blocking error, the error messages from it
        """
        self.manager.log_fine_grained('--- update single %r ---' % module)
        self.updated_modules.append(module)

        manager = self.manager
        previous_modules = self.previous_modules
        graph = self.graph

        # Record symbol table snaphot of old version the changed module.
        old_snapshots = {}  # type: Dict[str, Dict[str, SnapshotItem]]
        if module in manager.modules:
            snapshot = snapshot_symbol_table(module, manager.modules[module].names)
            old_snapshots[module] = snapshot

        manager.errors.reset()
        result = update_module_isolated(module, path, manager, previous_modules, graph,
                                        force_removed)
        if isinstance(result, BlockedUpdate):
            # Blocking error -- just give up
            module, path, remaining, errors = result
            self.previous_modules = get_module_to_path_map(manager)
            return remaining, (module, path), errors
        assert isinstance(result, NormalUpdate)  # Work around #4124
        module, path, remaining, tree = result

        # TODO: What to do with stale dependencies?
        triggered = calculate_active_triggers(manager, old_snapshots, {module: tree})
        if is_verbose(self.manager):
            filtered = [trigger for trigger in triggered
                        if not trigger.endswith('__>')]
            self.manager.log_fine_grained('triggered: %r' % sorted(filtered))
        self.triggered.extend(triggered | self.previous_targets_with_errors)
        collect_dependencies({module: tree}, self.deps, graph)
        remaining += propagate_changes_using_dependencies(
            manager, graph, self.deps, self.prio_deps, triggered,
            {module},
            targets_with_errors=set())

        # Preserve state needed for the next update.
        self.previous_targets_with_errors.update(manager.errors.targets())
        self.previous_modules = get_module_to_path_map(manager)

        return remaining, (module, path), None


def get_all_dependencies(manager: BuildManager, graph: Dict[str, State]) -> Dict[str, Set[str]]:
    """Return the fine-grained dependency map for an entire build."""
    # Deps for each module were computed during build() or loaded from the cache.
    deps = {}  # type: Dict[str, Set[str]]
    collect_dependencies(manager.modules, deps, graph)
    return deps


# The result of update_module_isolated when no blockers, with these items:
#
# - Id of the changed module (can be different from the module argument)
# - Path of the changed module
# - New AST for the changed module (None if module was deleted)
# - Remaining changed modules that are not processed yet as (module id, path)
#   tuples (non-empty if the original changed module imported other new
#   modules)
NormalUpdate = NamedTuple('NormalUpdate', [('module', str),
                                           ('path', str),
                                           ('remaining', List[Tuple[str, str]]),
                                           ('tree', Optional[MypyFile])])

# The result of update_module_isolated when there is a blocking error. Items
# are similar to NormalUpdate (but there are fewer).
BlockedUpdate = NamedTuple('BlockedUpdate', [('module', str),
                                             ('path', str),
                                             ('remaining', List[Tuple[str, str]]),
                                             ('messages', List[str])])

UpdateResult = Union[NormalUpdate, BlockedUpdate]


def update_module_isolated(module: str,
                           path: str,
                           manager: BuildManager,
                           previous_modules: Dict[str, str],
                           graph: Graph,
                           force_removed: bool) -> UpdateResult:
    """Build a new version of one changed module only.

    Don't propagate changes to elsewhere in the program. Raise CompleError on
    encountering a blocking error.

    Args:
        module: Changed module (modified, created or deleted)
        path: Path of the changed module
        manager: Build manager
        graph: Build graph
        force_removed: If True, consider the module removed from the build even it the
            file exists

    Returns a named tuple describing the result (see above for details).
    """
    if module in manager.modules:
        assert_equivalent_paths(path, manager.modules[module].path)
    else:
        manager.log_fine_grained('new module %r' % module)

    if not manager.fscache.isfile(path) or force_removed:
        delete_module(module, graph, manager)
        return NormalUpdate(module, path, [], None)

    old_modules = dict(manager.modules)
    sources = get_sources(manager.fscache, previous_modules, [(module, path)])

    if module in manager.missing_modules:
        manager.missing_modules.remove(module)

    try:
        if module in graph:
            del graph[module]
        load_graph(sources, manager, graph)
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
        return BlockedUpdate(err.module_with_blocker, path, remaining_modules, err.messages)

    # Find any other modules brought in by imports.
    changed_modules = get_all_changed_modules(module, path, previous_modules, graph)
    # If there are multiple modules to process, only process one of them and return
    # the remaining ones to the caller.
    if len(changed_modules) > 1:
        # As an optimization, look for a module that imports no other changed modules.
        module, path = find_relative_leaf_module(changed_modules, graph)
        changed_modules.remove((module, path))
        remaining_modules = changed_modules
        # The remaining modules haven't been processed yet so drop them.
        for id, _ in remaining_modules:
            if id in old_modules:
                manager.modules[id] = old_modules[id]
            else:
                del manager.modules[id]
            del graph[id]
        manager.log_fine_grained('--> %r (newly imported)' % module)
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
        return BlockedUpdate(module, path, remaining_modules, err.messages)
    state.semantic_analysis_pass_three()
    state.semantic_analysis_apply_patches()

    # Merge old and new ASTs.
    assert state.tree is not None, "file must be at least parsed"
    new_modules = {module: state.tree}  # type: Dict[str, Optional[MypyFile]]
    replace_modules_with_new_variants(manager, graph, old_modules, new_modules)

    # Perform type checking.
    state.type_checker().reset()
    state.type_check_first_pass()
    state.type_check_second_pass()
    state.compute_fine_grained_deps()
    state.finish_passes()

    graph[module] = state

    return NormalUpdate(module, path, remaining_modules, state.tree)


def find_relative_leaf_module(modules: List[Tuple[str, str]], graph: Graph) -> Tuple[str, str]:
    """Find a module in a list that directly imports no other module in the list.

    If no such module exists, return the lexicographically first module from the list.
    Always return one of the items in the modules list.

    NOTE: If both 'abc' and 'typing' have changed, an effect of the above rule is that
        we prefer 'abc', even if both are in the same SCC. This works around a false
        positive in 'typing', at least in tests.

    Args:
        modules: List of (module, path) tuples (non-empty)
        graph: Program import graph that contains all modules in the module list
    """
    assert modules
    # Sort for repeatable results.
    modules = sorted(modules)
    module_set = {module for module, _ in modules}
    for module, path in modules:
        state = graph[module]
        if len(set(state.dependencies) & module_set) == 0:
            # Found it!
            return module, path
    # Could not find any. Just return the first module (by lexicographic order).
    return modules[0]


def assert_equivalent_paths(path1: str, path2: str) -> None:
    path1 = os.path.normpath(os.path.abspath(path1))
    path2 = os.path.normpath(os.path.abspath(path2))
    assert path1 == path2, '%s != %s' % (path1, path2)


def delete_module(module_id: str,
                  graph: Graph,
                  manager: BuildManager) -> None:
    manager.log_fine_grained('delete module %r' % module_id)
    # TODO: Remove deps for the module (this only affects memory use, not correctness)
    if module_id in graph:
        del graph[module_id]
    if module_id in manager.modules:
        del manager.modules[module_id]
    components = module_id.split('.')
    if len(components) > 1:
        # Delete reference to module in parent module.
        parent_id = '.'.join(components[:-1])
        # If parent module is ignored, it won't be included in the modules dictionary.
        if parent_id in manager.modules:
            parent = manager.modules[parent_id]
            if components[-1] in parent.names:
                del parent.names[components[-1]]


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


def get_sources(fscache: FileSystemCache,
                modules: Dict[str, str],
                changed_modules: List[Tuple[str, str]]) -> List[BuildSource]:
    sources = []
    for id, path in changed_modules:
        if fscache.isfile(path):
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


def verify_dependencies(state: State, manager: BuildManager) -> None:
    """Report errors for import targets in module that don't exist."""
    # Strip out indirect dependencies. See comment in build.load_graph().
    dependencies = [dep for dep in state.dependencies if state.priorities.get(dep) != PRI_INDIRECT]
    for dep in dependencies + state.suppressed:  # TODO: ancestors?
        if dep not in manager.modules and not state.options.ignore_missing_imports:
            assert state.tree
            line = state.dep_line_map.get(dep, 1)
            assert state.path
            manager.module_not_found(state.path, state.id, line, dep)


def collect_dependencies(new_modules: Mapping[str, Optional[MypyFile]],
                         deps: Dict[str, Set[str]],
                         graph: Dict[str, State]) -> None:
    for id, node in new_modules.items():
        if node is None:
            continue
        for trigger, targets in graph[id].fine_grained_deps.items():
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
        diff = compare_symbol_table_snapshots(id, snapshot1, snapshot2)
        package_nesting_level = id.count('.')
        for item in diff.copy():
            if (item.count('.') <= package_nesting_level + 1
                    and item.split('.')[-1] not in ('__builtins__',
                                                    '__file__',
                                                    '__name__',
                                                    '__package__',
                                                    '__doc__')):
                # Activate catch-all wildcard trigger for top-level module changes (used for
                # "from m import *"). This also gets triggered by changes to module-private
                # entries, but as these unneeded dependencies only result in extra processing,
                # it's a minor problem. Also used by protocols.
                #
                # TODO: Some __* names cause mistriggers. Fix the underlying issue instead of
                #     special casing them here.
                diff.add(id + WILDCARD_TAG)
            if item.count('.') > package_nesting_level + 1:
                diff.add(item.rsplit('.', 1)[0] + WILDCARD_TAG)

        names |= diff
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
            preserved_module = old_modules[id]
            merge_asts(preserved_module, old_modules[id].names,
                       new_module, new_module.names)
            manager.modules[id] = preserved_module
            graph[id].tree = preserved_module


def propagate_changes_using_dependencies(
        manager: BuildManager,
        graph: Dict[str, State],
        deps: Dict[str, Set[str]],
        prio_deps: Dict[str, Set[str]],
        triggered: Set[str],
        up_to_date_modules: Set[str],
        targets_with_errors: Set[str]) -> List[Tuple[str, str]]:
    """Transitively rechecks targets based on triggers and the dependency map.

    Returns a list (module id, path) tuples representing modules that contain
    a target that needs to be reprocessed but that has not been parsed yet."""

    num_iter = 0
    remaining_modules = []

    # Propagate changes until nothing visible has changed during the last
    # iteration.
    while triggered or targets_with_errors:
        num_iter += 1
        if num_iter > MAX_ITER:
            raise RuntimeError('Max number of iterations (%d) reached (endless loop?)' % MAX_ITER)

        todo, stale_protos = find_targets_recursive(manager, triggered, deps,
                                                    prio_deps, up_to_date_modules)
        # Also process targets that used to have errors, as otherwise some
        # errors might be lost.
        for target in targets_with_errors:
            id = module_prefix(manager.modules, target)
            if id is not None and id not in up_to_date_modules:
                if id not in todo:
                    todo[id] = set()
                manager.log_fine_grained('process target with error: %s' % target)
                todo[id].update(lookup_target(manager, target))
        triggered = set()
        # TODO: Preserve order (set is not optimal)
        # First briefly reprocess high priority nodes, to invalidate
        # stale protocols.
        for info in stale_protos:
            if info.is_protocol:
                info.reset_subtype_cache()
                # Strictly speaking we need to do this only if super-protocol changes,
                # but the performance implications are negligible.
                add_protocol_members(info)
        for id, nodes in sorted(todo.items(), key=lambda x: x[0]):
            assert id not in up_to_date_modules
            if manager.modules[id].is_cache_skeleton:
                # We have only loaded the cache for this file, not the actual file,
                # so we can't access the nodes to reprocess.
                # Add it to the queue of files that need to be processed fully.
                remaining_modules.append((id, manager.modules[id].path))
            else:
                triggered |= reprocess_nodes(manager, graph, id, nodes, deps)
        # Changes elsewhere may require us to reprocess modules that were
        # previously considered up to date. For example, there may be a
        # dependency loop that loops back to an originally processed module.
        up_to_date_modules = set()
        targets_with_errors = set()
        if is_verbose(manager):
            manager.log_fine_grained('triggered: %r' % list(triggered))

    return remaining_modules


def find_targets_recursive(
        manager: BuildManager,
        triggers: Set[str],
        deps: Dict[str, Set[str]],
        prio_deps: Dict[str, Set[str]],
        up_to_date_modules: Set[str]) -> Tuple[Dict[str, Set[DeferredNode]], Set[TypeInfo]]:
    """Find names of all targets that need to reprocessed, given some triggers.

    Returns: Dictionary from module id to a set of stale targets.
    """
    result = {}  # type: Dict[str, Set[DeferredNode]]
    worklist = triggers
    processed = set()  # type: Set[str]
    stale_protos = set()  # type: Set[TypeInfo]

    # Find AST nodes corresponding to each target.
    #
    # TODO: Don't rely on a set, since the items are in an unpredictable order.
    while worklist:
        processed |= worklist
        current = worklist
        worklist = set()
        for target in current:
            if target.startswith('<'):
                if target in prio_deps:
                    # There are only leafs in high priority protocol dependencies.
                    for proto_name in prio_deps[target]:
                        info = lookup_typeinfo(manager, proto_name)
                        if info is not None:
                            stale_protos.add(info)
                worklist |= deps.get(target, set()) - processed
            else:
                module_id = module_prefix(manager.modules, target)
                if module_id is None:
                    # Deleted module.
                    continue
                if module_id in up_to_date_modules:
                    # Already processed.
                    continue
                if module_id not in result:
                    result[module_id] = set()
                manager.log_fine_grained('process: %s' % target)
                deferred = lookup_target(manager, target)
                result[module_id].update(deferred)

    return result, stale_protos


def reprocess_nodes(manager: BuildManager,
                    graph: Dict[str, State],
                    module_id: str,
                    nodeset: Set[DeferredNode],
                    deps: Dict[str, Set[str]]) -> Set[str]:
    """Reprocess a set of nodes within a single module.

    Return fired triggers.
    """
    if module_id not in graph:
        manager.log_fine_grained('%s not in graph (blocking errors or deleted?)' %
                    module_id)
        return set()

    file_node = manager.modules[module_id]
    old_symbols = find_symbol_tables_recursive(file_node.fullname(), file_node.names)
    old_symbols = {name: names.copy() for name, names in old_symbols.items()}
    old_symbols_snapshot = snapshot_symbol_table(file_node.fullname(), file_node.names)

    def key(node: DeferredNode) -> int:
        # Unlike modules which are sorted by name within SCC,
        # nodes within the same module are sorted by line number, because
        # this is how they are processed in normal mode.
        return node.node.line

    nodes = sorted(nodeset, key=key)

    # TODO: ignore_all argument to set_file_ignored_lines
    manager.errors.set_file_ignored_lines(file_node.path, file_node.ignored_lines)

    targets = set()
    for node in nodes:
        target = target_from_node(module_id, node.node)
        if target is not None:
            targets.add(target)
    manager.errors.clear_errors_in_targets(file_node.path, targets)

    # Strip semantic analysis information.
    for deferred in nodes:
        strip_target(deferred.node)
    semantic_analyzer = manager.semantic_analyzer

    patches = []  # type: List[Tuple[int, Callable[[], None]]]

    # Second pass of semantic analysis. We don't redo the first pass, because it only
    # does local things that won't go stale.
    options = graph[module_id].options
    for deferred in nodes:
        with semantic_analyzer.file_context(
                file_node=file_node,
                fnam=file_node.path,
                options=options,
                active_type=deferred.active_typeinfo):
            manager.semantic_analyzer.refresh_partial(deferred.node, patches)

    # Third pass of semantic analysis.
    for deferred in nodes:
        with semantic_analyzer.file_context(
                file_node=file_node,
                fnam=file_node.path,
                options=options,
                active_type=deferred.active_typeinfo,
                scope=manager.semantic_analyzer_pass3.scope):
            manager.semantic_analyzer_pass3.refresh_partial(deferred.node, patches)

    with semantic_analyzer.file_context(
            file_node=file_node,
            fnam=file_node.path,
            options=options,
            active_type=None):
        apply_semantic_analyzer_patches(patches)

    # Merge symbol tables to preserve identities of AST nodes. The file node will remain
    # the same, but other nodes may have been recreated with different identities, such as
    # NamedTuples defined using assignment statements.
    new_symbols = find_symbol_tables_recursive(file_node.fullname(), file_node.names)
    for name in old_symbols:
        if name in new_symbols:
            merge_asts(file_node, old_symbols[name], file_node, new_symbols[name])

    # Type check.
    checker = graph[module_id].type_checker()
    checker.reset()
    # We seem to need additional passes in fine-grained incremental mode.
    checker.pass_num = 0
    checker.last_pass = 3
    more = checker.check_second_pass(nodes)
    while more:
        more = False
        if graph[module_id].type_checker().check_second_pass():
            more = True

    new_symbols_snapshot = snapshot_symbol_table(file_node.fullname(), file_node.names)
    # Check if any attribute types were changed and need to be propagated further.
    changed = compare_symbol_table_snapshots(file_node.fullname(),
                                             old_symbols_snapshot,
                                             new_symbols_snapshot)
    new_triggered = {make_trigger(name) for name in changed}

    # Dependencies may have changed.
    update_deps(module_id, nodes, graph, deps, options)

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


def update_deps(module_id: str,
                nodes: List[DeferredNode],
                graph: Dict[str, State],
                deps: Dict[str, Set[str]],
                options: Options) -> None:
    for deferred in nodes:
        node = deferred.node
        type_map = graph[module_id].type_map()
        tree = graph[module_id].tree
        assert tree is not None, "Tree must be processed at this stage"
        new_deps = get_dependencies_of_target(module_id, tree, node, type_map,
                                              options.python_version)
        for trigger, targets in new_deps.items():
            deps.setdefault(trigger, set()).update(targets)


def lookup_typeinfo(manager: BuildManager, target: str) -> Optional[TypeInfo]:
    """Lookup TypeInfo in symbol tables by its full name.

    If the name is stale (not found, refers to another node kind, etc.)
    return None.
    """
    # TODO: there is code/logic duplication with lookup_target.
    # Factor out common parts.
    modules = manager.modules
    items = split_target(modules, target)
    if items is None:
        return None
    module, rest = items
    if rest:
        components = rest.split('.')
    else:
        components = []
    node = modules[module]  # type: Optional[SymbolNode]
    for c in components:
        if (not isinstance(node, (MypyFile, TypeInfo))
                or c not in node.names):
            return None  # Stale dependency
        node = node.names[c].node
    if isinstance(node, TypeInfo):
        if node.fullname() != target:
            return None
        return node
    return None


def lookup_target(manager: BuildManager, target: str) -> List[DeferredNode]:
    """Look up a target by fully-qualified name."""

    def not_found() -> None:
        manager.log_fine_grained(
            "Can't find matching target for %s (stale dependency?)" % target)

    modules = manager.modules
    items = split_target(modules, target)
    if items is None:
        not_found()  # Stale dependency
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
        if isinstance(node, MypyFile):
            file = node
        if (not isinstance(node, (MypyFile, TypeInfo))
                or c not in node.names):
            not_found()  # Stale dependency
            return []
        node = node.names[c].node
    if isinstance(node, TypeInfo):
        # A ClassDef target covers the body of the class and everything defined
        # within it.  To get the body we include the entire surrounding target,
        # typically a module top-level, since we don't support processing class
        # bodies as separate entitites for simplicity.
        assert file is not None
        if node.fullname() != target:
            # This is a reference to a different TypeInfo, likely due to a stale dependency.
            # Processing them would spell trouble -- for example, we could be refreshing
            # a deserialized TypeInfo with missing attributes.
            not_found()
            return []
        result = [DeferredNode(file, None, None)]
        for name, symnode in node.names.items():
            node = symnode.node
            if isinstance(node, FuncDef):
                result.extend(lookup_target(manager, target + '.' + name))
        return result
    if isinstance(node, Decorator):
        # Decorator targets actually refer to the function definition only.
        node = node.func
    if not isinstance(node, (FuncDef,
                             MypyFile,
                             OverloadedFuncDef)):
        # The target can't be refreshed. It's possible that the target was
        # changed to another type and we have a stale dependency pointing to it.
        not_found()
        return []
    if node.fullname() != target:
        # Stale reference points to something unexpected. We shouldn't process since the
        # context will be wrong and it could be a partially initialized deserialized node.
        not_found()
        return []
    return [DeferredNode(node, active_class_name, active_class)]


def is_verbose(manager: BuildManager) -> bool:
    return manager.options.verbosity >= 1 or DEBUG_FINE_GRAINED


def target_from_node(module: str,
                     node: Union[FuncDef, MypyFile, OverloadedFuncDef, LambdaExpr]
                     ) -> Optional[str]:
    """Return the target name corresponding to a deferred node.

    Args:
        module: Must be module id of the module that defines 'node'

    Returns the target name, or None if the node is not a valid target in the given
    module (for example, if it's actually defined in another module).
    """
    if isinstance(node, MypyFile):
        if module != node.fullname():
            # Actually a reference to another module -- likely a stale dependency.
            return None
        return module
    elif isinstance(node, (OverloadedFuncDef, FuncDef)):
        if node.info is not None:
            return '%s.%s' % (node.info.fullname(), node.name())
        else:
            return '%s.%s' % (module, node.name())
    else:
        assert False, "Lambda expressions can't be deferred in fine-grained incremental mode"
