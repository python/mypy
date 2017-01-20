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

- Support multiple rounds of change propagation
- Support multiple type checking passes
- Always reprocess targets with errors, even if they aren't explicitly
  stale
"""

from typing import Dict, List, Set

from mypy.build import BuildManager, State
from mypy.checker import DeferredNode
from mypy.errors import Errors
from mypy.nodes import MypyFile, FuncDef, TypeInfo, Expression, SymbolNode
from mypy.types import Type
from mypy.server.astdiff import compare_symbol_tables
from mypy.server.astmerge import merge_asts
from mypy.server.aststrip import strip_target
from mypy.server.deps import get_dependencies
from mypy.server.subexpr import get_subexpressions
from mypy.server.trigger import make_trigger


def get_all_dependencies(manager: BuildManager) -> Dict[str, Set[str]]:
    """Return the fine-grained dependency map for an entire build."""
    deps = {}  # type: Dict[str, Set[str]]
    update_dependencies(manager.modules, deps, manager.all_types)
    return deps


def update_build(manager: BuildManager,
                 graph: Dict[str, State],
                 deps: Dict[str, Set[str]],
                 changed_modules: List[str]) -> List[str]:
    """Update previous build result by processing changed modules.

    Also propagate changes to other modules as needed, but only process
    those parts of other modules that are affected by the changes. Retain
    the existing ASTs and symbol tables of unaffected modules.

    TODO: What about blocking errors?

    Args:
        manager: State of the build
        graph: Additional state of the build
        deps: Fine-grained dependcy map for the build (mutated by this function)
        changed_modules: Modules changed since the previous update/build (assume
            this is correct; not validated here)

    Returns:
        A list of errors.
    """
    old_modules = dict(manager.modules)
    manager.errors.reset()
    new_modules = build_incremental_step(manager, changed_modules)
    # TODO: What to do with stale dependencies?
    update_dependencies(new_modules, deps, manager.all_types)
    triggered = calculate_active_triggers(manager, old_modules, new_modules)
    replace_modules_with_new_variants(manager, old_modules, new_modules)
    propagate_changes_using_dependencies(manager, graph, deps, triggered, set(changed_modules))
    return manager.errors.messages()


def build_incremental_step(manager: BuildManager,
                           changed_modules: List[str]) -> Dict[str, MypyFile]:
    """Build new versions of changed modules only.

    Return the new ASTs for the changed modules. They will be totally
    separate from the existing ASTs and need to merged afterwards.
    """
    assert len(changed_modules) == 1
    id = changed_modules[0]
    path = manager.modules[id].path

    # TODO: what if file is missing?
    with open(path) as f:
        source = f.read()

    state = State(id=id,
                  path=path,
                  source=source,
                  manager=manager)  # TODO: more args?
    state.parse_file()
    # TODO: state.fix_suppressed_dependencies()?
    state.semantic_analysis()
    state.semantic_analysis_pass_three()
    state.type_check_first_pass()
    # TODO: state.type_check_second_pass()?
    state.finish_passes()
    # TODO: state.write_cache()?
    # TODO: state.mark_as_rechecked()?

    return {id: state.tree}


def update_dependencies(new_modules: Dict[str, MypyFile],
                        deps: Dict[str, Set[str]],
                        type_map: Dict[Expression, Type]) -> None:
    for id, node in new_modules.items():
        module_deps = get_dependencies(prefix=id,
                                       node=node,
                                       type_map=type_map)
        for trigger, targets in module_deps.items():
            deps.setdefault(trigger, set()).update(targets)


def calculate_active_triggers(manager: BuildManager,
                              old_modules: Dict[str, MypyFile],
                              new_modules: Dict[str, MypyFile]) -> Set[str]:
    """Determine activated triggers by comparing old and new symbol tables.

    For example, if only the signature of function m.f is different in the new
    symbol table, return {'<m.f>'}.
    """
    names = set()  # type: Set[str]
    for id in new_modules:
        names |= compare_symbol_tables(id, old_modules[id].names, new_modules[id].names)
    return {make_trigger(name) for name in names}


def replace_modules_with_new_variants(
        manager: BuildManager,
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
            # Remove nodes of old modules from the type map.
            all_types = manager.all_types
            for expr in get_subexpressions(old_modules[id]):
                if expr in all_types:
                    del all_types[expr]
        merge_asts(old_modules[id], old_modules[id].names,
                   new_modules[id], new_modules[id].names)
        manager.modules[id] = old_modules[id]


def propagate_changes_using_dependencies(
        manager: BuildManager,
        graph: Dict[str, State],
        deps: Dict[str, Set[str]],
        triggered: Set[str],
        up_to_date_modules: Set[str]) -> None:
    # TODO: Multiple propagation passes
    # TODO: Multiple type checking passes

    todo = find_targets_recursive(triggered, deps, manager.modules, up_to_date_modules)

    for id, nodes in todo.items():
        assert id not in up_to_date_modules
        file_node = manager.modules[id]
        for deferred in nodes:
            node = deferred.node
            # Strip semantic analysis information
            strip_target(node)
            # We don't redo the first pass, because it only does local things.
            semantic_analyzer = manager.semantic_analyzer
            with semantic_analyzer.file_context(
                    file_node=file_node,
                    fnam=file_node.path,
                    options=manager.options,
                    active_type=deferred.active_typeinfo):
                # Second pass
                manager.semantic_analyzer.refresh_partial(node)
                # Third pass
                manager.semantic_analyzer_pass3.refresh_partial(node)
        # Type check
        graph[id].type_checker.check_second_pass(list(nodes))  # TODO: check return value


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
                module_id = target.split('.', 1)[0]
                if module_id in up_to_date_modules:
                    # Already processed.
                    continue
                if module_id not in result:
                    result[module_id] = set()
                deferred = lookup_target(modules, target)
                result[module_id].add(deferred)

    return result


def lookup_target(modules: Dict[str, MypyFile], target: str) -> DeferredNode:
    """Look up a target by fully-qualified name."""
    components = target.split('.')
    node = modules[components[0]]  # type: SymbolNode
    active_class = None
    active_class_name = None
    for c in components[1:]:
        if isinstance(node, TypeInfo):
            active_class = node
            active_class_name = node.name()
        # TODO: Is it possible for the assertion to fail?
        assert isinstance(node, (MypyFile, TypeInfo))
        node = node.names[c].node
    assert isinstance(node, (FuncDef, MypyFile))
    return DeferredNode(node, active_class_name, active_class)
