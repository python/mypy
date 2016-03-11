"""Dependency manager.

This will replace the dependency management in build.py.

Design
======

Ideally
-------

A. Collapse cycles (each SCC -- strongly connected component --
   becomes one "supernode").

B. Topologically sort nodes based on dependencies.

C. Process from leaves towards roots.

Wrinkles
--------

a. Need to parse source modules to determine dependencies.

b. Processing order for modules within an SCC.

c. Must order mtimes of files to decide whether to re-process; depends
   on clock never resetting.

d. from P import M; checks filesystem whether module P.M exists in
   filesystem.

e. Race conditions, where somebody modifies a file while we're
   processing.  I propose not to modify the algorithm to handle this,
   but to detect when this could lead to inconsistencies.  (For
   example, when we decide on the dependencies based on cache
   metadata, and then we decide to re-parse a file because of a stale
   dependency, if the re-parsing leads to a different list of
   dependencies we should warn the user or start over.)

Steps
-----

1. For each explicitly given module find the source file location.

2. For each such module load and check the cache metadata, and decide
   whether it's valid.

3. Now recursively (or iteratively) find dependencies and add those to
   the graph:

   - for cached nodes use the list of dependencies from the cache
     metadata (this will be valid even if we later end up re-parsing
     the same source);

   - for uncached nodes parse the file and process all imports found,
     taking care of (a) above.

Step 3 should also address (d) above.

Once step 3 terminates we have the entire dependency graph, and for
each module we've either loaded the cache metadata or parsed the
source code.  (However, we may still need to parse those modules for
which we have cache metadata but that depend, directly or indirectly,
on at least one module for which the cache metadata is stale.)

Now we can execute steps A-C from the first section.  Finding SCCs for
step A shouldn't be hard; there's a recipe here:
http://code.activestate.com/recipes/578507/.  There's also a plethora
of topsort recipes, e.g. http://code.activestate.com/recipes/577413/.

For single nodes, processing is simple.  If the node was cached, we
deserialize the cache data and fix up cross-references.  Otherwise, we
do semantic analysis followed by type checking.  We also handle (c)
above; if a module has valid cache data *but* any of its
dependendencies was processed from source, then the module should be
processed from source.

A relatively simple optimization (outside SCCs) we might do in the
future is as follows: if a node's cache data is valid, but one or more
of its dependencies are out of date so we have to re-parse the node
from source, once we have fully type-checked the node, we can decide
whether its symbol table actually changed compared to the cache data
(by reading the cache data and comparing it to the data we would be
writing).  If there is no change we can declare the node up to date,
and any node that depends (and for which we have cached data, and
whose other dependencies are up to date) on it won't need to be
re-parsed from source.

Import cycles
-------------

Finally we have to decide how to handle (c), import cycles.  Here
we'll need a modified version of the original state machine
(build.py), but we only need to do this per SCC, and we won't have to
deal with changes to the list of nodes while we're processing it.

If all nodes in the SCC have valid cache metadata and all dependencies
outside the SCC are still valid, we can proceed as follows:

  1. Load cache data for all nodes in the SCC.

  2. Fix up cross-references for all nodes in the SCC.

Otherwise, the simplest (but potentially slow) way to proceed is to
invalidate all cache data in the SCC and re-parse all nodes in the SCC
from source.  We can do this as follows:

  1. Parse source for all nodes in the SCC.

  2. Semantic analysis for all nodes in the SCC.

  3. Type check all nodes in the SCC.

(If there are more passes the process is the same -- each pass should
be done for all nodes before starting the next pass for any nodes in
the SCC.)

We could process the nodes in the SCC in any order.  We *might*
process them in the reverse order in which we encountered them when
originally constructing the graph (IIUC that's how the old build.py
deals with cycles).  For now we'll process them in alphabetical order.

Can we do better than re-parsing all nodes in the SCC when any of its
dependencies are out of date?  It's doubtful.  The optimization
mentioned at the end of the previous section would require re-parsing
and type-checking a node and then comparing its symbol table to the
cached data; but because the node is part of a cycle we can't
technically type-check it until the semantic analysis of all other
nodes in the cycle has completed.  (This is an important issue because
we have a cycle of over 500 modules in the server repo.  But I'd like
to deal with it later.)

"""

import json
import os

from typing import Any, Dict, List, Set, AbstractSet, Iterable, Iterator, Optional, TypeVar

from .build import (BuildManager, BuildSource, CacheMeta, FAST_PARSER,
                    find_cache_meta, find_module, read_with_python_encoding,
                    write_cache)
from .errors import CompileError
from .fixup import fixup_module_pass_one, fixup_module_pass_two
from .nodes import MypyFile, SymbolTableNode, MODULE_REF
from .parse import parse
from .semanal import FirstPass


class State:
    """The state for a module.

    It's a package if path ends in __init__.py[i].

    The source is only used for the -c command line option; in that
    case path is None.  Otherwise source is None and path isn't.
    """

    manager = None  # type: BuildManager
    id = None  # type: str  # Fully qualified module name
    path = None  # type: Optional[str]  # Path to module source
    xpath = None  # type: str  # Path or '<string>'
    source = None  # type: Optional[str]  # Module source code
    meta = None  # type: Optional[CacheMeta]
    data = None  # type: Optional[str]
    tree = None  # type: Optional[MypyFile]
    dependencies = None  # type: Optional[Set[str]]

    def __init__(self,
                 id: Optional[str],
                 path: Optional[str],
                 source: Optional[str],
                 manager: BuildManager,
                 ) -> None:
        assert id or path or source, "Neither id, path nor source given"
        self.manager = manager
        self.id = id or '__main__'
        if not path and not source:
            path = find_module(id, manager.lib_path)
            if not path:
                raise CompileError(["mypy: can't find module '%s'" % id])
        self.path = path
        self.xpath = path or '<string>'
        self.source = source
        if path:
            # TODO: Only if --incremental.
            self.meta = find_cache_meta(self.id, self.path, manager)
            # TODO: Get mtime if not cached.
        if self.meta:
            self.dependencies = set(self.meta.dependencies)
        else:
            # Parse the file (and then some) to get the dependencies.
            self.parse_file()

    def is_fresh(self) -> bool:
        return self.meta is not None

    def clear_fresh(self) -> None:
        self.meta = None

    # Methods for processing cached modules.

    def load_tree(self) -> None:
        with open(self.meta.data_json) as f:
            data = json.load(f)
        # TODO: Assert data file wasn't changed.
        self.tree = MypyFile.deserialize(data)
        self.manager.modules[self.id] = self.tree

    def fix_cross_refs(self) -> None:
        fixup_module_pass_one(self.tree, self.manager.modules)

    def calculate_mros(self) -> None:
        fixup_module_pass_two(self.tree, self.manager.modules)

    # Methods for processing modules from source code.

    def parse_file(self) -> None:
        if self.tree is not None:
            # The file was already parsed (in __init__()).
            return

        manager = self.manager
        modules = manager.modules

        if not self.source:
            self.source = read_with_python_encoding(self.path, manager.pyversion)
        self.tree = parse_file(self.id, self.path, self.source, manager)
        self.source = None  # We won't need it again.
        modules[self.id] = self.tree

        if self.tree and '.' in self.id:
            # Include module in the symbol table of the enclosing package.
            # TODO: This is weirdly optional; why is it needed?
            parent, child = self.id.rsplit('.', 1)
            if parent in modules:
                modules[parent].names[child] = SymbolTableNode(MODULE_REF, self.tree, parent)

        # Do the first pass of semantic analysis: add top-level
        # definitions in the file to the symbol table.  We must do
        # this before processing imports, since this may mark some
        # import statements as unreachable.
        first = FirstPass(manager.semantic_analyzer)
        first.analyze(self.tree, self.xpath, self.id)

        # Initialize module symbol table, which was populated by the
        # semantic analyzer.  TODO: can't FirstPass .analyze() do this?
        self.tree.names = manager.semantic_analyzer.globals

        # Compute dependencies.
        dependencies = set()
        # Start with parent packages.
        parent = self.id
        while '.' in parent:
            parent, _ = parent.rsplit('.', 1)
            dependencies.add(parent)
        # Every module implicitly depends on builtins.
        if self.id != 'builtins':
            dependencies.add('builtins')
        # Add all direct imports (this is why we needed the first pass).
        dependencies.update(id for id, _ in manager.all_imported_modules_in_file(self.tree))

        # If self.dependencies is already set, it was read from the
        # cache, but for some reason we're re-parsing the file.
        # Double-check that the dependencies still match (otherwise
        # the graph is out of date).
        if self.dependencies is not None and dependencies != self.dependencies:
            # TODO: Make this into a reasonable error message.
            print("HELP!! Dependencies changed!")  # Probably the file was edited.
            print("  Cached:", self.dependencies)
            print("  Source:", dependencies)
        self.dependencies = dependencies

    def semantic_analysis(self) -> None:
        self.manager.semantic_analyzer.visit_file(self.tree, self.xpath)

    def semantic_analysis_pass_three(self) -> None:
        self.manager.semantic_analyzer_pass3.visit_file(self.tree, self.xpath)
        # TODO: DUMP_TYPE_STATS

    def type_check(self) -> None:
        self.manager.type_checker.visit_file(self.tree, self.xpath)
        # TODO: DUMP_INFER_STATS, manager.reports.file()

    def write_cache(self) -> None:
        if self.path:
            write_cache(self.id, self.path, self.tree, list(self.dependencies), self.manager)


# TODO: This would make a nice method on BuildManager.
def parse_file(id: str, path: str, source: str, manager: BuildManager) -> MypyFile:
    """Parse the source of a file with the given name.

    Raise CompileError if there is a parse error.
    """
    errors = manager.errors
    num_errs = errors.num_messages()
    tree = parse(source, path, errors,
                 pyversion=manager.pyversion,
                 custom_typing_module=manager.custom_typing_module,
                 implicit_any=manager.implicit_any,
                 fast_parser=FAST_PARSER in manager.flags)
    tree._fullname = id
    if errors.num_messages() != num_errs:
        errors.raise_error()
    return tree


Graph = Dict[str, State]


def dispatch(sources: List[BuildSource], manager: BuildManager) -> None:
    manager.log("Using new dependency manager")
    graph = load_graph(sources, manager)
    manager.log("Loaded graph with %d nodes" % len(graph))
    process_graph(graph, manager)


def load_graph(sources: List[BuildSource], manager: BuildManager) -> Graph:
    """Given some source files, load the full dependency graph."""
    graph = {}  # type: Graph
    # Seed graph with roots.
    for bs in sources:
        st = State(bs.module, bs.path, bs.text, manager)
        assert st.id not in graph, "TODO: Duplicate module %s" % st.id
        graph[st.id] = st
    # Collect dependencies.
    while True:
        new = {}  # type: Graph
        for st in graph.values():
            for dep in st.dependencies:
                if dep not in graph and dep not in new:
                    # TODO: Implement --silent-imports.
                    depst = State(dep, None, None, manager)
                    assert depst.id not in new, "TODO: This is bad %s" % depst.id
                    new[depst.id] = depst
        if not new:
            break
        graph.update(new)
    return graph


def process_graph(graph: Graph, manager: BuildManager) -> None:
    """Process everyhing in dependency order."""
    sccs = sorted_components(graph)
    manager.log("Found %d SCCs" % len(sccs))
    for scc in sccs:
        manager.trace("Processing SCC of size %d (%s)" % (len(scc), " ".join(sorted(scc))))
        # TODO: Do something about mtime ordering.
        fresh = all(graph[id].is_fresh() for id in scc)
        if fresh:
            manager.trace("  Looks fresh...")
            deps = set()
            for id in scc:
                deps.update(graph[id].dependencies)
            deps -= scc
            fresh = all(graph[id].is_fresh() for id in deps)
        if fresh:
            manager.trace("  Processing as fresh")
            process_fresh_scc(graph, scc)
        else:
            manager.trace("  *** Processing as stale ***")
            process_stale_scc(graph, scc)


def process_fresh_scc(graph: Graph, scc: AbstractSet[str]) -> None:
    """Process the modules in one SCC from their cached data."""
    for id in scc:
        graph[id].load_tree()
    for id in scc:
        graph[id].fix_cross_refs()
    for id in scc:
        graph[id].calculate_mros()


def process_stale_scc(graph: Graph, ascc: AbstractSet[str]) -> None:
    """Process the modules in one SCC from source code."""
    if ascc == {'abc', 'typing', 'builtins'}:
        # Hack: typing must be processed before builtins.  TODO: Why?
        scc = ['abc', 'typing', 'builtins']
    else:
        scc = sorted(ascc)  # Sort for reproducibility.  TODO: Why?
    for id in scc:
        graph[id].clear_fresh()
    for id in scc:
        # We may already have parsed the module, or not.
        graph[id].parse_file()
    for id in scc:
        graph[id].semantic_analysis()
    for id in scc:
        graph[id].semantic_analysis_pass_three()
    for id in scc:
        graph[id].type_check()
        # TODO: Only if --incremental.
        graph[id].write_cache()


# TODO: Use TypeVar T instead of str.
def sorted_components(graph: Graph) -> List[AbstractSet[str]]:
    """Return the graph's SCCs, topologically sorted by dependencies."""
    # Compute SCCs.
    vertices = set(graph)
    edges = {id: st.dependencies for id, st in graph.items()}
    sccs = list(strongly_connected_components_path(vertices, edges))
    # Topsort.
    sccsmap = {id: frozenset(scc) for scc in sccs for id in scc}
    data = {}  # type: Dict[AbstractSet[str], Set[AbstractSet[str]]]
    for scc in sccs:
        deps = set()  # type: Set[AbstractSet[str]]
        for id in scc:
            deps.update(sccsmap[x] for x in graph[id].dependencies)
        data[frozenset(scc)] = deps
    return list(topsort(data))


# TODO: Use TypeVar T instead of str.
def strongly_connected_components_path(vertices: Set[str],
                                       edges: Dict[str, Set[str]]) -> Iterator[Set[str]]:
    """Compute Strongly Connected Components of a graph.

    From http://code.activestate.com/recipes/578507/.
    """
    identified = set()  # type: Set[str]
    stack = []  # type: List[str]
    index = {}  # type: Dict[str, int]
    boundaries = []  # type: List[int]

    def dfs(v: str) -> Iterator[Set[str]]:
        index[v] = len(stack)
        stack.append(v)
        boundaries.append(index[v])

        for w in edges[v]:
            if w not in index:
                # For Python >= 3.3, replace with "yield from dfs(w)"
                for scc in dfs(w):
                    yield scc
            elif w not in identified:
                while index[w] < boundaries[-1]:
                    boundaries.pop()

        if boundaries[-1] == index[v]:
            boundaries.pop()
            scc = set(stack[index[v]:])
            del stack[index[v]:]
            identified.update(scc)
            yield scc

    for v in vertices:
        if v not in index:
            # For Python >= 3.3, replace with "yield from dfs(v)"
            for scc in dfs(v):
                yield scc


# TODO: Use TypeVar T instead of str.
def topsort(data: Dict[AbstractSet[str], Set[AbstractSet[str]]]) -> Iterable[AbstractSet[str]]:
    """Topological sort.  Consumes its argument.

    From http://code.activestate.com/recipes/577413/.
    """
    # TODO: Use a faster algorithm?
    for k, v in data.items():
        v.discard(k)  # Ignore self dependencies.
    for item in set.union(*data.values()) - set(data.keys()):
        data[item] = set()
    while True:
        ready = {item for item, dep in data.items() if not dep}
        if not ready:
            break
        # TODO: Return the items in a reproducible order.
        for item in ready:
            yield item
        data = {item: (dep - ready)
                for item, dep in data.items()
                if item not in ready}
    assert not data, "A cyclic dependency exists amongst %r" % data
