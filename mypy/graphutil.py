from typing import List, Dict, Iterable, Mapping, Collection, Iterator, Set, TypeVar


T = TypeVar('T')


def strongly_connected_components(vertices: Iterable[T],
                                  edges: Mapping[T, Collection[T]]) -> Iterator[Set[T]]:
    """Compute Strongly Connected Components of a directed graph.

    Args:
      vertices: the labels for the vertices
      edges: for each vertex, gives the target vertices of its outgoing edges

    Returns:
      An iterator yielding strongly connected components, each
      represented as a set of vertices.  Each input vertex will occur
      exactly once; vertices not part of a SCC are returned as
      singleton sets.
      The SCCs are yielded in topologically sorted order.

    From http://code.activestate.com/recipes/578507/.
    """
    identified: Set[T] = set()
    stack: List[T] = []
    index: Dict[T, int] = {}
    boundaries: List[int] = []

    def dfs(v: T) -> Iterator[Set[T]]:
        index[v] = len(stack)
        stack.append(v)
        boundaries.append(index[v])

        for w in edges.get(v, ()):
            if w not in index:
                yield from dfs(w)
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
            yield from dfs(v)


def toposort(edges: Mapping[T, Collection[T]]) -> Iterator[T]:
    """Topologically sort a dict from item to dependencies.

    This runs in O(V + E).
    """
    vertices = edges.keys()
    for scc in strongly_connected_components(vertices, edges):
        if len(scc) != 1:
            raise AssertionError("A cyclic dependency exists amongst %r" % scc)
        yield from scc
