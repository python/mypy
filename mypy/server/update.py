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

from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import Sequence
from typing import Callable, Final, NamedTuple, Union
from typing_extensions import TypeAlias as _TypeAlias

from mypy.build import (
    DEBUG_FINE_GRAINED,
    FAKE_ROOT_MODULE,
    BuildManager,
    BuildResult,
    Graph,
    State,
    load_graph,
    process_fresh_modules,
)
from mypy.checker import FineGrainedDeferredNode
from mypy.errors import CompileError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource
from mypy.nodes import (
    Decorator,
    FuncDef,
    ImportFrom,
    MypyFile,
    OverloadedFuncDef,
    SymbolNode,
    SymbolTable,
    TypeInfo,
)
from mypy.options import Options
from mypy.semanal_main import semantic_analysis_for_scc, semantic_analysis_for_targets
from mypy.server.astdiff import (
    SymbolSnapshot,
    compare_symbol_table_snapshots,
    snapshot_symbol_table,
)
from mypy.server.astmerge import merge_asts
from mypy.server.aststrip import SavedAttributes, strip_target
from mypy.server.deps import get_dependencies_of_target, merge_dependencies
from mypy.server.target import trigger_to_target
from mypy.server.trigger import WILDCARD_TAG, make_trigger
from mypy.typestate import type_state
from mypy.util import is_stdlib_file, module_prefix, split_target

MAX_ITER: Final = 1000

# These are modules beyond stdlib that have some special meaning for mypy.
SENSITIVE_INTERNAL_MODULES = ("mypy_extensions", "typing_extensions")


class FineGrainedBuildManager:
    def __init__(self, result: BuildResult) -> None:
        """Initialize fine-grained build based on a batch build.

        Args:
            result: Result from the initialized build.
                    The manager and graph will be taken over by this class.
            manager: State of the build (mutated by this class)
            graph: Additional state of the build (mutated by this class)
        """
        manager = result.manager
        self.manager = manager
        self.graph = result.graph
        self.previous_modules = get_module_to_path_map(self.graph)
        self.deps = manager.fg_deps
        # Merge in any root dependencies that may not have been loaded
        merge_dependencies(manager.load_fine_grained_deps(FAKE_ROOT_MODULE), self.deps)
        self.previous_targets_with_errors = manager.errors.targets()
        self.previous_messages: list[str] = result.errors.copy()
        # Module, if any, that had blocking errors in the last run as (id, path) tuple.
        self.blocking_error: tuple[str, str] | None = None
        # Module that we haven't processed yet but that are known to be stale.
        self.stale: list[tuple[str, str]] = []
        # Disable the cache so that load_graph doesn't try going back to disk
        # for the cache.
        self.manager.cache_enabled = False

        # Some hints to the test suite about what is going on:
        # Active triggers during the last update
        self.triggered: list[str] = []
        # Modules passed to update during the last update
        self.changed_modules: list[tuple[str, str]] = []
        # Modules processed during the last update
        self.updated_modules: list[str] = []
        # Targets processed during last update (for testing only).
        self.processed_targets: list[str] = []

    def update(
        self,
        changed_modules: list[tuple[str, str]],
        removed_modules: list[tuple[str, str]],
        followed: bool = False,
    ) -> list[str]:
        """Update previous build result by processing changed modules.

        Also propagate changes to other modules as needed, but only process
        those parts of other modules that are affected by the changes. Retain
        the existing ASTs and symbol tables of unaffected modules.

        Reuses original BuildManager and Graph.

        Args:
            changed_modules: Modules changed since the previous update/build; each is
                a (module id, path) tuple. Includes modified and added modules.
                Assume this is correct; it's not validated here.
            removed_modules: Modules that have been deleted since the previous update
                or removed from the build.
            followed: If True, the modules were found through following imports

        Returns:
            A list of errors.
        """
        self.processed_targets.clear()
        changed_modules = changed_modules + removed_modules
        removed_set = {module for module, _ in removed_modules}
        self.changed_modules = changed_modules

        if not changed_modules:
            return self.previous_messages

        # Reset find_module's caches for the new build.
        self.manager.find_module_cache.clear()

        self.triggered = []
        self.updated_modules = []
        changed_modules = dedupe_modules(changed_modules + self.stale)
        initial_set = {id for id, _ in changed_modules}
        self.manager.log_fine_grained(
            "==== update %s ====" % ", ".join(repr(id) for id, _ in changed_modules)
        )
        if self.previous_targets_with_errors and is_verbose(self.manager):
            self.manager.log_fine_grained(
                "previous targets with errors: %s" % sorted(self.previous_targets_with_errors)
            )

        blocking_error = None
        if self.blocking_error:
            # Handle blocking errors first. We'll exit as soon as we find a
            # module that still has blocking errors.
            self.manager.log_fine_grained(f"existing blocker: {self.blocking_error[0]}")
            changed_modules = dedupe_modules([self.blocking_error] + changed_modules)
            blocking_error = self.blocking_error[0]
            self.blocking_error = None

        while True:
            result = self.update_one(
                changed_modules, initial_set, removed_set, blocking_error, followed
            )
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
                    self.manager,
                    self.graph,
                    self.deps,
                    set(),
                    {next_id},
                    self.previous_targets_with_errors,
                    self.processed_targets,
                )
                changed_modules = dedupe_modules(changed_modules)
                if not changed_modules:
                    # Preserve state needed for the next update.
                    self.previous_targets_with_errors = self.manager.errors.targets()
                    messages = self.manager.errors.new_messages()
                    break

        messages = sort_messages_preserving_file_order(messages, self.previous_messages)
        self.previous_messages = messages.copy()
        return messages

    def trigger(self, target: str) -> list[str]:
        """Trigger a specific target explicitly.

        This is intended for use by the suggestions engine.
        """
        self.manager.errors.reset()
        changed_modules = propagate_changes_using_dependencies(
            self.manager,
            self.graph,
            self.deps,
            set(),
            set(),
            self.previous_targets_with_errors | {target},
            [],
        )
        # Preserve state needed for the next update.
        self.previous_targets_with_errors = self.manager.errors.targets()
        self.previous_messages = self.manager.errors.new_messages().copy()
        return self.update(changed_modules, [])

    def flush_cache(self) -> None:
        """Flush AST cache.

        This needs to be called after each increment, or file changes won't
        be detected reliably.
        """
        self.manager.ast_cache.clear()

    def update_one(
        self,
        changed_modules: list[tuple[str, str]],
        initial_set: set[str],
        removed_set: set[str],
        blocking_error: str | None,
        followed: bool,
    ) -> tuple[list[tuple[str, str]], tuple[str, str], list[str] | None]:
        """Process a module from the list of changed modules.

        Returns:
            Tuple with these items:

            - Updated list of pending changed modules as (module id, path) tuples
            - Module which was actually processed as (id, path) tuple
            - If there was a blocking error, the error messages from it
        """
        t0 = time.time()
        next_id, next_path = changed_modules.pop(0)

        # If we have a module with a blocking error that is no longer
        # in the import graph, we must skip it as otherwise we'll be
        # stuck with the blocking error.
        if (
            next_id == blocking_error
            and next_id not in self.previous_modules
            and next_id not in initial_set
        ):
            self.manager.log_fine_grained(
                f"skip {next_id!r} (module with blocking error not in import graph)"
            )
            return changed_modules, (next_id, next_path), None

        result = self.update_module(next_id, next_path, next_id in removed_set, followed)
        remaining, (next_id, next_path), blocker_messages = result
        changed_modules = [(id, path) for id, path in changed_modules if id != next_id]
        changed_modules = dedupe_modules(remaining + changed_modules)
        t1 = time.time()

        self.manager.log_fine_grained(
            f"update once: {next_id} in {t1 - t0:.3f}s - {len(changed_modules)} left"
        )

        return changed_modules, (next_id, next_path), blocker_messages

    def update_module(
        self, module: str, path: str, force_removed: bool, followed: bool
    ) -> tuple[list[tuple[str, str]], tuple[str, str], list[str] | None]:
        """Update a single modified module.

        If the module contains imports of previously unseen modules, only process one of
        the new modules and return the remaining work to be done.

        Args:
            module: Id of the module
            path: File system path of the module
            force_removed: If True, consider module removed from the build even if path
                exists (used for removing an existing file from the build)
            followed: Was this found via import following?

        Returns:
            Tuple with these items:

            - Remaining modules to process as (module id, path) tuples
            - Module which was actually processed as (id, path) tuple
            - If there was a blocking error, the error messages from it
        """
        self.manager.log_fine_grained(f"--- update single {module!r} ---")
        self.updated_modules.append(module)

        # builtins and friends could potentially get triggered because
        # of protocol stuff, but nothing good could possibly come from
        # actually updating them.
        if (
            is_stdlib_file(self.manager.options.abs_custom_typeshed_dir, path)
            or module in SENSITIVE_INTERNAL_MODULES
        ):
            return [], (module, path), None

        manager = self.manager
        previous_modules = self.previous_modules
        graph = self.graph

        ensure_deps_loaded(module, self.deps, graph)

        # If this is an already existing module, make sure that we have
        # its tree loaded so that we can snapshot it for comparison.
        ensure_trees_loaded(manager, graph, [module])

        t0 = time.time()
        # Record symbol table snapshot of old version the changed module.
        old_snapshots: dict[str, dict[str, SymbolSnapshot]] = {}
        if module in manager.modules:
            snapshot = snapshot_symbol_table(module, manager.modules[module].names)
            old_snapshots[module] = snapshot

        manager.errors.reset()
        self.processed_targets.append(module)
        result = update_module_isolated(
            module, path, manager, previous_modules, graph, force_removed, followed
        )
        if isinstance(result, BlockedUpdate):
            # Blocking error -- just give up
            module, path, remaining, errors = result
            self.previous_modules = get_module_to_path_map(graph)
            return remaining, (module, path), errors
        assert isinstance(result, NormalUpdate)  # Work around #4124
        module, path, remaining, tree = result

        # TODO: What to do with stale dependencies?
        t1 = time.time()
        triggered = calculate_active_triggers(manager, old_snapshots, {module: tree})
        if is_verbose(self.manager):
            filtered = [trigger for trigger in triggered if not trigger.endswith("__>")]
            self.manager.log_fine_grained(f"triggered: {sorted(filtered)!r}")
        self.triggered.extend(triggered | self.previous_targets_with_errors)
        if module in graph:
            graph[module].update_fine_grained_deps(self.deps)
            graph[module].free_state()
        remaining += propagate_changes_using_dependencies(
            manager,
            graph,
            self.deps,
            triggered,
            {module},
            targets_with_errors=set(),
            processed_targets=self.processed_targets,
        )
        t2 = time.time()
        manager.add_stats(update_isolated_time=t1 - t0, propagate_time=t2 - t1)

        # Preserve state needed for the next update.
        self.previous_targets_with_errors.update(manager.errors.targets())
        self.previous_modules = get_module_to_path_map(graph)

        return remaining, (module, path), None


def find_unloaded_deps(
    manager: BuildManager, graph: dict[str, State], initial: Sequence[str]
) -> list[str]:
    """Find all the deps of the nodes in initial that haven't had their tree loaded.

    The key invariant here is that if a module is loaded, so are all
    of their dependencies. This means that when we encounter a loaded
    module, we don't need to explore its dependencies.  (This
    invariant is slightly violated when dependencies are added, which
    can be handled by calling find_unloaded_deps directly on the new
    dependencies.)
    """
    worklist = list(initial)
    seen: set[str] = set()
    unloaded = []
    while worklist:
        node = worklist.pop()
        if node in seen or node not in graph:
            continue
        seen.add(node)
        if node not in manager.modules:
            ancestors = graph[node].ancestors or []
            worklist.extend(graph[node].dependencies + ancestors)
            unloaded.append(node)

    return unloaded


def ensure_deps_loaded(module: str, deps: dict[str, set[str]], graph: dict[str, State]) -> None:
    """Ensure that the dependencies on a module are loaded.

    Dependencies are loaded into the 'deps' dictionary.

    This also requires loading dependencies from any parent modules,
    since dependencies will get stored with parent modules when a module
    doesn't exist.
    """
    if module in graph and graph[module].fine_grained_deps_loaded:
        return
    parts = module.split(".")
    for i in range(len(parts)):
        base = ".".join(parts[: i + 1])
        if base in graph and not graph[base].fine_grained_deps_loaded:
            merge_dependencies(graph[base].load_fine_grained_deps(), deps)
            graph[base].fine_grained_deps_loaded = True


def ensure_trees_loaded(
    manager: BuildManager, graph: dict[str, State], initial: Sequence[str]
) -> None:
    """Ensure that the modules in initial and their deps have loaded trees."""
    to_process = find_unloaded_deps(manager, graph, initial)
    if to_process:
        if is_verbose(manager):
            manager.log_fine_grained(
                "Calling process_fresh_modules on set of size {} ({})".format(
                    len(to_process), sorted(to_process)
                )
            )
        process_fresh_modules(graph, to_process, manager)


# The result of update_module_isolated when no blockers, with these items:
#
# - Id of the changed module (can be different from the module argument)
# - Path of the changed module
# - New AST for the changed module (None if module was deleted)
# - Remaining changed modules that are not processed yet as (module id, path)
#   tuples (non-empty if the original changed module imported other new
#   modules)
class NormalUpdate(NamedTuple):
    module: str
    path: str
    remaining: list[tuple[str, str]]
    tree: MypyFile | None


# The result of update_module_isolated when there is a blocking error. Items
# are similar to NormalUpdate (but there are fewer).
class BlockedUpdate(NamedTuple):
    module: str
    path: str
    remaining: list[tuple[str, str]]
    messages: list[str]


UpdateResult: _TypeAlias = Union[NormalUpdate, BlockedUpdate]


def update_module_isolated(
    module: str,
    path: str,
    manager: BuildManager,
    previous_modules: dict[str, str],
    graph: Graph,
    force_removed: bool,
    followed: bool,
) -> UpdateResult:
    """Build a new version of one changed module only.

    Don't propagate changes to elsewhere in the program. Raise CompileError on
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
    if module not in graph:
        manager.log_fine_grained(f"new module {module!r}")

    if not manager.fscache.isfile(path) or force_removed:
        delete_module(module, path, graph, manager)
        return NormalUpdate(module, path, [], None)

    sources = get_sources(manager.fscache, previous_modules, [(module, path)], followed)

    if module in manager.missing_modules:
        manager.missing_modules.remove(module)

    orig_module = module
    orig_state = graph.get(module)
    orig_tree = manager.modules.get(module)

    def restore(ids: list[str]) -> None:
        # For each of the modules in ids, restore that id's old
        # manager.modules and graphs entries. (Except for the original
        # module, this means deleting them.)
        for id in ids:
            if id == orig_module and orig_tree:
                manager.modules[id] = orig_tree
            elif id in manager.modules:
                del manager.modules[id]
            if id == orig_module and orig_state:
                graph[id] = orig_state
            elif id in graph:
                del graph[id]

    new_modules: list[State] = []
    try:
        if module in graph:
            del graph[module]
        load_graph(sources, manager, graph, new_modules)
    except CompileError as err:
        # Parse error somewhere in the program -- a blocker
        assert err.module_with_blocker
        restore([module] + [st.id for st in new_modules])
        return BlockedUpdate(err.module_with_blocker, path, [], err.messages)

    # Reparsing the file may have brought in dependencies that we
    # didn't have before. Make sure that they are loaded to restore
    # the invariant that a module having a loaded tree implies that
    # its dependencies do as well.
    ensure_trees_loaded(manager, graph, graph[module].dependencies)

    # Find any other modules brought in by imports.
    changed_modules = [(st.id, st.xpath) for st in new_modules]

    # If there are multiple modules to process, only process one of them and return
    # the remaining ones to the caller.
    if len(changed_modules) > 1:
        # As an optimization, look for a module that imports no other changed modules.
        module, path = find_relative_leaf_module(changed_modules, graph)
        changed_modules.remove((module, path))
        remaining_modules = changed_modules
        # The remaining modules haven't been processed yet so drop them.
        restore([id for id, _ in remaining_modules])
        manager.log_fine_grained(f"--> {module!r} (newly imported)")
    else:
        remaining_modules = []

    state = graph[module]

    # Process the changed file.
    state.parse_file()
    assert state.tree is not None, "file must be at least parsed"
    t0 = time.time()
    try:
        semantic_analysis_for_scc(graph, [state.id], manager.errors)
    except CompileError as err:
        # There was a blocking error, so module AST is incomplete. Restore old modules.
        restore([module])
        return BlockedUpdate(module, path, remaining_modules, err.messages)

    # Merge old and new ASTs.
    new_modules_dict: dict[str, MypyFile | None] = {module: state.tree}
    replace_modules_with_new_variants(manager, graph, {orig_module: orig_tree}, new_modules_dict)

    t1 = time.time()
    # Perform type checking.
    state.type_checker().reset()
    state.type_check_first_pass()
    state.type_check_second_pass()
    state.detect_possibly_undefined_vars()
    state.generate_unused_ignore_notes()
    state.generate_ignore_without_code_notes()
    t2 = time.time()
    state.finish_passes()
    t3 = time.time()
    manager.add_stats(semanal_time=t1 - t0, typecheck_time=t2 - t1, finish_passes_time=t3 - t2)

    graph[module] = state

    return NormalUpdate(module, path, remaining_modules, state.tree)


def find_relative_leaf_module(modules: list[tuple[str, str]], graph: Graph) -> tuple[str, str]:
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


def delete_module(module_id: str, path: str, graph: Graph, manager: BuildManager) -> None:
    manager.log_fine_grained(f"delete module {module_id!r}")
    # TODO: Remove deps for the module (this only affects memory use, not correctness)
    if module_id in graph:
        del graph[module_id]
    if module_id in manager.modules:
        del manager.modules[module_id]
    components = module_id.split(".")
    if len(components) > 1:
        # Delete reference to module in parent module.
        parent_id = ".".join(components[:-1])
        # If parent module is ignored, it won't be included in the modules dictionary.
        if parent_id in manager.modules:
            parent = manager.modules[parent_id]
            if components[-1] in parent.names:
                del parent.names[components[-1]]
    # If the module is removed from the build but still exists, then
    # we mark it as missing so that it will get picked up by import from still.
    if manager.fscache.isfile(path):
        manager.missing_modules.add(module_id)


def dedupe_modules(modules: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result = []
    for id, path in modules:
        if id not in seen:
            seen.add(id)
            result.append((id, path))
    return result


def get_module_to_path_map(graph: Graph) -> dict[str, str]:
    return {module: node.xpath for module, node in graph.items()}


def get_sources(
    fscache: FileSystemCache,
    modules: dict[str, str],
    changed_modules: list[tuple[str, str]],
    followed: bool,
) -> list[BuildSource]:
    sources = []
    for id, path in changed_modules:
        if fscache.isfile(path):
            sources.append(BuildSource(path, id, None, followed=followed))
    return sources


def calculate_active_triggers(
    manager: BuildManager,
    old_snapshots: dict[str, dict[str, SymbolSnapshot]],
    new_modules: dict[str, MypyFile | None],
) -> set[str]:
    """Determine activated triggers by comparing old and new symbol tables.

    For example, if only the signature of function m.f is different in the new
    symbol table, return {'<m.f>'}.
    """
    names: set[str] = set()
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
        package_nesting_level = id.count(".")
        for item in diff.copy():
            if item.count(".") <= package_nesting_level + 1 and item.split(".")[-1] not in (
                "__builtins__",
                "__file__",
                "__name__",
                "__package__",
                "__doc__",
            ):
                # Activate catch-all wildcard trigger for top-level module changes (used for
                # "from m import *"). This also gets triggered by changes to module-private
                # entries, but as these unneeded dependencies only result in extra processing,
                # it's a minor problem.
                #
                # TODO: Some __* names cause mistriggers. Fix the underlying issue instead of
                #     special casing them here.
                diff.add(id + WILDCARD_TAG)
            if item.count(".") > package_nesting_level + 1:
                # These are for changes within classes, used by protocols.
                diff.add(item.rsplit(".", 1)[0] + WILDCARD_TAG)

        names |= diff
    return {make_trigger(name) for name in names}


def replace_modules_with_new_variants(
    manager: BuildManager,
    graph: dict[str, State],
    old_modules: dict[str, MypyFile | None],
    new_modules: dict[str, MypyFile | None],
) -> None:
    """Replace modules with newly builds versions.

    Retain the identities of externally visible AST nodes in the
    old ASTs so that references to the affected modules from other
    modules will still be valid (unless something was deleted or
    replaced with an incompatible definition, in which case there
    will be dangling references that will be handled by
    propagate_changes_using_dependencies).
    """
    for id in new_modules:
        preserved_module = old_modules.get(id)
        new_module = new_modules[id]
        if preserved_module and new_module is not None:
            merge_asts(preserved_module, preserved_module.names, new_module, new_module.names)
            manager.modules[id] = preserved_module
            graph[id].tree = preserved_module


def propagate_changes_using_dependencies(
    manager: BuildManager,
    graph: dict[str, State],
    deps: dict[str, set[str]],
    triggered: set[str],
    up_to_date_modules: set[str],
    targets_with_errors: set[str],
    processed_targets: list[str],
) -> list[tuple[str, str]]:
    """Transitively rechecks targets based on triggers and the dependency map.

    Returns a list (module id, path) tuples representing modules that contain
    a target that needs to be reprocessed but that has not been parsed yet.

    Processed targets should be appended to processed_targets (used in tests only,
    to test the order of processing targets).
    """

    num_iter = 0
    remaining_modules: list[tuple[str, str]] = []

    # Propagate changes until nothing visible has changed during the last
    # iteration.
    while triggered or targets_with_errors:
        num_iter += 1
        if num_iter > MAX_ITER:
            raise RuntimeError("Max number of iterations (%d) reached (endless loop?)" % MAX_ITER)

        todo, unloaded, stale_protos = find_targets_recursive(
            manager, graph, triggered, deps, up_to_date_modules
        )
        # TODO: we sort to make it deterministic, but this is *incredibly* ad hoc
        remaining_modules.extend((id, graph[id].xpath) for id in sorted(unloaded))
        # Also process targets that used to have errors, as otherwise some
        # errors might be lost.
        for target in targets_with_errors:
            id = module_prefix(graph, target)
            if id is not None and id not in up_to_date_modules:
                if id not in todo:
                    todo[id] = set()
                manager.log_fine_grained(f"process target with error: {target}")
                more_nodes, _ = lookup_target(manager, target)
                todo[id].update(more_nodes)
        triggered = set()
        # First invalidate subtype caches in all stale protocols.
        # We need to do this to avoid false negatives if the protocol itself is
        # unchanged, but was marked stale because its sub- (or super-) type changed.
        for info in stale_protos:
            type_state.reset_subtype_caches_for(info)
        # Then fully reprocess all targets.
        # TODO: Preserve order (set is not optimal)
        for id, nodes in sorted(todo.items(), key=lambda x: x[0]):
            assert id not in up_to_date_modules
            triggered |= reprocess_nodes(manager, graph, id, nodes, deps, processed_targets)
        # Changes elsewhere may require us to reprocess modules that were
        # previously considered up to date. For example, there may be a
        # dependency loop that loops back to an originally processed module.
        up_to_date_modules = set()
        targets_with_errors = set()
        if is_verbose(manager):
            manager.log_fine_grained(f"triggered: {list(triggered)!r}")

    return remaining_modules


def find_targets_recursive(
    manager: BuildManager,
    graph: Graph,
    triggers: set[str],
    deps: dict[str, set[str]],
    up_to_date_modules: set[str],
) -> tuple[dict[str, set[FineGrainedDeferredNode]], set[str], set[TypeInfo]]:
    """Find names of all targets that need to reprocessed, given some triggers.

    Returns: A tuple containing a:
     * Dictionary from module id to a set of stale targets.
     * A set of module ids for unparsed modules with stale targets.
    """
    result: dict[str, set[FineGrainedDeferredNode]] = {}
    worklist = triggers
    processed: set[str] = set()
    stale_protos: set[TypeInfo] = set()
    unloaded_files: set[str] = set()

    # Find AST nodes corresponding to each target.
    #
    # TODO: Don't rely on a set, since the items are in an unpredictable order.
    while worklist:
        processed |= worklist
        current = worklist
        worklist = set()
        for target in current:
            if target.startswith("<"):
                module_id = module_prefix(graph, trigger_to_target(target))
                if module_id:
                    ensure_deps_loaded(module_id, deps, graph)

                worklist |= deps.get(target, set()) - processed
            else:
                module_id = module_prefix(graph, target)
                if module_id is None:
                    # Deleted module.
                    continue
                if module_id in up_to_date_modules:
                    # Already processed.
                    continue
                if (
                    module_id not in manager.modules
                    or manager.modules[module_id].is_cache_skeleton
                ):
                    # We haven't actually parsed and checked the module, so we don't have
                    # access to the actual nodes.
                    # Add it to the queue of files that need to be processed fully.
                    unloaded_files.add(module_id)
                    continue

                if module_id not in result:
                    result[module_id] = set()
                manager.log_fine_grained(f"process: {target}")
                deferred, stale_proto = lookup_target(manager, target)
                if stale_proto:
                    stale_protos.add(stale_proto)
                result[module_id].update(deferred)

    return result, unloaded_files, stale_protos


def reprocess_nodes(
    manager: BuildManager,
    graph: dict[str, State],
    module_id: str,
    nodeset: set[FineGrainedDeferredNode],
    deps: dict[str, set[str]],
    processed_targets: list[str],
) -> set[str]:
    """Reprocess a set of nodes within a single module.

    Return fired triggers.
    """
    if module_id not in graph:
        manager.log_fine_grained("%s not in graph (blocking errors or deleted?)" % module_id)
        return set()

    file_node = manager.modules[module_id]
    old_symbols = find_symbol_tables_recursive(file_node.fullname, file_node.names)
    old_symbols = {name: names.copy() for name, names in old_symbols.items()}
    old_symbols_snapshot = snapshot_symbol_table(file_node.fullname, file_node.names)

    def key(node: FineGrainedDeferredNode) -> int:
        # Unlike modules which are sorted by name within SCC,
        # nodes within the same module are sorted by line number, because
        # this is how they are processed in normal mode.
        return node.node.line

    nodes = sorted(nodeset, key=key)

    state = graph[module_id]
    options = state.options
    manager.errors.set_file_ignored_lines(
        file_node.path, file_node.ignored_lines, options.ignore_errors or state.ignore_all
    )
    manager.errors.set_skipped_lines(file_node.path, file_node.skipped_lines)

    targets = set()
    for node in nodes:
        target = target_from_node(module_id, node.node)
        if target is not None:
            targets.add(target)
    manager.errors.clear_errors_in_targets(file_node.path, targets)

    # If one of the nodes is the module itself, emit any errors that
    # happened before semantic analysis.
    for target in targets:
        if target == module_id:
            for info in graph[module_id].early_errors:
                manager.errors.add_error_info(info)

    # Strip semantic analysis information.
    saved_attrs: SavedAttributes = {}
    for deferred in nodes:
        processed_targets.append(deferred.node.fullname)
        strip_target(deferred.node, saved_attrs)
    semantic_analysis_for_targets(graph[module_id], nodes, graph, saved_attrs)
    # Merge symbol tables to preserve identities of AST nodes. The file node will remain
    # the same, but other nodes may have been recreated with different identities, such as
    # NamedTuples defined using assignment statements.
    new_symbols = find_symbol_tables_recursive(file_node.fullname, file_node.names)
    for name in old_symbols:
        if name in new_symbols:
            merge_asts(file_node, old_symbols[name], file_node, new_symbols[name])

    # Type check.
    checker = graph[module_id].type_checker()
    checker.reset()
    # We seem to need additional passes in fine-grained incremental mode.
    checker.pass_num = 0
    checker.last_pass = 3
    # It is tricky to reliably invalidate constructor cache in fine-grained increments.
    # See PR 19514 description for details.
    more = checker.check_second_pass(nodes, allow_constructor_cache=False)
    while more:
        more = False
        if graph[module_id].type_checker().check_second_pass(allow_constructor_cache=False):
            more = True

    if manager.options.export_types:
        manager.all_types.update(graph[module_id].type_map())

    new_symbols_snapshot = snapshot_symbol_table(file_node.fullname, file_node.names)
    # Check if any attribute types were changed and need to be propagated further.
    changed = compare_symbol_table_snapshots(
        file_node.fullname, old_symbols_snapshot, new_symbols_snapshot
    )
    new_triggered = {make_trigger(name) for name in changed}

    # Dependencies may have changed.
    update_deps(module_id, nodes, graph, deps, options)

    # Report missing imports.
    graph[module_id].verify_dependencies()

    graph[module_id].free_state()

    return new_triggered


def find_symbol_tables_recursive(prefix: str, symbols: SymbolTable) -> dict[str, SymbolTable]:
    """Find all nested symbol tables.

    Args:
        prefix: Full name prefix (used for return value keys and to filter result so that
            cross references to other modules aren't included)
        symbols: Root symbol table

    Returns a dictionary from full name to corresponding symbol table.
    """
    result = {prefix: symbols}
    for name, node in symbols.items():
        if isinstance(node.node, TypeInfo) and node.node.fullname.startswith(prefix + "."):
            more = find_symbol_tables_recursive(prefix + "." + name, node.node.names)
            result.update(more)
    return result


def update_deps(
    module_id: str,
    nodes: list[FineGrainedDeferredNode],
    graph: dict[str, State],
    deps: dict[str, set[str]],
    options: Options,
) -> None:
    for deferred in nodes:
        node = deferred.node
        type_map = graph[module_id].type_map()
        tree = graph[module_id].tree
        assert tree is not None, "Tree must be processed at this stage"
        new_deps = get_dependencies_of_target(
            module_id, tree, node, type_map, options.python_version
        )
        for trigger, targets in new_deps.items():
            deps.setdefault(trigger, set()).update(targets)
    # Merge also the newly added protocol deps (if any).
    type_state.update_protocol_deps(deps)


def lookup_target(
    manager: BuildManager, target: str
) -> tuple[list[FineGrainedDeferredNode], TypeInfo | None]:
    """Look up a target by fully-qualified name.

    The first item in the return tuple is a list of deferred nodes that
    needs to be reprocessed. If the target represents a TypeInfo corresponding
    to a protocol, return it as a second item in the return tuple, otherwise None.
    """

    def not_found() -> None:
        manager.log_fine_grained(f"Can't find matching target for {target} (stale dependency?)")

    modules = manager.modules
    items = split_target(modules, target)
    if items is None:
        not_found()  # Stale dependency
        return [], None
    module, rest = items
    if rest:
        components = rest.split(".")
    else:
        components = []
    node: SymbolNode | None = modules[module]
    file: MypyFile | None = None
    active_class = None
    for c in components:
        if isinstance(node, TypeInfo):
            active_class = node
        if isinstance(node, MypyFile):
            file = node
        if not isinstance(node, (MypyFile, TypeInfo)) or c not in node.names:
            not_found()  # Stale dependency
            return [], None
        # Don't reprocess plugin generated targets. They should get
        # stripped and regenerated when the containing target is
        # reprocessed.
        if node.names[c].plugin_generated:
            return [], None
        node = node.names[c].node
    if isinstance(node, TypeInfo):
        # A ClassDef target covers the body of the class and everything defined
        # within it.  To get the body we include the entire surrounding target,
        # typically a module top-level, since we don't support processing class
        # bodies as separate entities for simplicity.
        assert file is not None
        if node.fullname != target:
            # This is a reference to a different TypeInfo, likely due to a stale dependency.
            # Processing them would spell trouble -- for example, we could be refreshing
            # a deserialized TypeInfo with missing attributes.
            not_found()
            return [], None
        result = [FineGrainedDeferredNode(file, None)]
        stale_info: TypeInfo | None = None
        if node.is_protocol:
            stale_info = node
        for name, symnode in node.names.items():
            node = symnode.node
            if isinstance(node, FuncDef):
                method, _ = lookup_target(manager, target + "." + name)
                result.extend(method)
        return result, stale_info
    if isinstance(node, Decorator):
        # Decorator targets actually refer to the function definition only.
        node = node.func
    if not isinstance(node, (FuncDef, MypyFile, OverloadedFuncDef)):
        # The target can't be refreshed. It's possible that the target was
        # changed to another type and we have a stale dependency pointing to it.
        not_found()
        return [], None
    if node.fullname != target:
        # Stale reference points to something unexpected. We shouldn't process since the
        # context will be wrong and it could be a partially initialized deserialized node.
        not_found()
        return [], None
    return [FineGrainedDeferredNode(node, active_class)], None


def is_verbose(manager: BuildManager) -> bool:
    return manager.options.verbosity >= 1 or DEBUG_FINE_GRAINED


def target_from_node(module: str, node: FuncDef | MypyFile | OverloadedFuncDef) -> str | None:
    """Return the target name corresponding to a deferred node.

    Args:
        module: Must be module id of the module that defines 'node'

    Returns the target name, or None if the node is not a valid target in the given
    module (for example, if it's actually defined in another module).
    """
    if isinstance(node, MypyFile):
        if module != node.fullname:
            # Actually a reference to another module -- likely a stale dependency.
            return None
        return module
    else:  # OverloadedFuncDef or FuncDef
        if node.info:
            return f"{node.info.fullname}.{node.name}"
        else:
            return f"{module}.{node.name}"


if sys.platform != "win32":
    INIT_SUFFIXES: Final = ("/__init__.py", "/__init__.pyi")
else:
    INIT_SUFFIXES: Final = (
        os.sep + "__init__.py",
        os.sep + "__init__.pyi",
        os.altsep + "__init__.py",
        os.altsep + "__init__.pyi",
    )


def refresh_suppressed_submodules(
    module: str,
    path: str | None,
    deps: dict[str, set[str]],
    graph: Graph,
    fscache: FileSystemCache,
    refresh_file: Callable[[str, str], list[str]],
) -> list[str] | None:
    """Look for submodules that are now suppressed in target package.

    If a submodule a.b gets added, we need to mark it as suppressed
    in modules that contain "from a import b". Previously we assumed
    that 'a.b' is not a module but a regular name.

    This is only relevant when following imports normally.

    Args:
        module: target package in which to look for submodules
        path: path of the module
        refresh_file: function that reads the AST of a module (returns error messages)

    Return a list of errors from refresh_file() if it was called. If the
    return value is None, we didn't call refresh_file().
    """
    messages = None
    if path is None or not path.endswith(INIT_SUFFIXES):
        # Only packages have submodules.
        return None
    # Find any submodules present in the directory.
    pkgdir = os.path.dirname(path)
    try:
        entries = fscache.listdir(pkgdir)
    except FileNotFoundError:
        entries = []
    for fnam in entries:
        if (
            not fnam.endswith((".py", ".pyi"))
            or fnam.startswith("__init__.")
            or fnam.count(".") != 1
        ):
            continue
        shortname = fnam.split(".")[0]
        submodule = module + "." + shortname
        trigger = make_trigger(submodule)

        # We may be missing the required fine-grained deps.
        ensure_deps_loaded(module, deps, graph)

        if trigger in deps:
            for dep in deps[trigger]:
                # We can ignore <...> deps since a submodule can't trigger any.
                state = graph.get(dep)
                if not state:
                    # Maybe it's a non-top-level target. We only care about the module.
                    dep_module = module_prefix(graph, dep)
                    if dep_module is not None:
                        state = graph.get(dep_module)
                if state:
                    # Is the file may missing an AST in case it's read from cache?
                    if state.tree is None:
                        # Create AST for the file. This may produce some new errors
                        # that we need to propagate.
                        assert state.path is not None
                        messages = refresh_file(state.id, state.path)
                    tree = state.tree
                    assert tree  # Will be fine, due to refresh_file() above
                    for imp in tree.imports:
                        if isinstance(imp, ImportFrom):
                            if (
                                imp.id == module
                                and any(name == shortname for name, _ in imp.names)
                                and submodule not in state.suppressed_set
                            ):
                                state.suppressed.append(submodule)
                                state.suppressed_set.add(submodule)
    return messages


def extract_fnam_from_message(message: str) -> str | None:
    m = re.match(r"([^:]+):[0-9]+: (error|note): ", message)
    if m:
        return m.group(1)
    return None


def extract_possible_fnam_from_message(message: str) -> str:
    # This may return non-path things if there is some random colon on the line
    return message.split(":", 1)[0]


def sort_messages_preserving_file_order(
    messages: list[str], prev_messages: list[str]
) -> list[str]:
    """Sort messages so that the order of files is preserved.

    An update generates messages so that the files can be in a fairly
    arbitrary order.  Preserve the order of files to avoid messages
    getting reshuffled continuously.  If there are messages in
    additional files, sort them towards the end.
    """
    # Calculate file order from the previous messages
    n = 0
    order = {}
    for msg in prev_messages:
        fnam = extract_fnam_from_message(msg)
        if fnam and fnam not in order:
            order[fnam] = n
            n += 1

    # Related messages must be sorted as a group of successive lines
    groups = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        maybe_fnam = extract_possible_fnam_from_message(msg)
        group = [msg]
        if maybe_fnam in order:
            # This looks like a file name. Collect all lines related to this message.
            while (
                i + 1 < len(messages)
                and extract_possible_fnam_from_message(messages[i + 1]) not in order
                and extract_fnam_from_message(messages[i + 1]) is None
                and not messages[i + 1].startswith("mypy: ")
            ):
                i += 1
                group.append(messages[i])
        groups.append((order.get(maybe_fnam, n), group))
        i += 1

    groups = sorted(groups, key=lambda g: g[0])
    result = []
    for key, group in groups:
        result.extend(group)
    return result
