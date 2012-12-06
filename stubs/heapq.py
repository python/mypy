# Stubs for heapq

# Based on http://docs.python.org/3.2/library/heapq.html

void heappush<t>(t[] heap, t item): pass
t heappop<t>(t[] heap): pass
t heappushpop<t>(t[] heap, t item): pass
void heapify<t>(t[] x): pass
t heapreplace<t>(list <t> heap, t item): pass
Iterable<t> merge<t>(Iterable<t> *iterables): pass
t[] nlargest<t>(int n, Iterable<t> iterable, func<any(t)> key=None): pass
t[] nsmallest<t>(int n, Iterable<t> iterable, func<any(t)> key=None): pass
