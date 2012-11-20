# Stubs for heapq

# Based on http://docs.python.org/3.2/library/heapq.html

void heappush<t>(list<t> heap, t item): pass
t heappop<t>(list<t> heap): pass
t heappushpop<t>(list<t> heap, t item): pass
void heapify<t>(list<t> x): pass
t heapreplace<t>(list <t> heap, t item): pass
iterable<t> merge<t>(iterable<t> *iterables): pass
list<t> nlargest<t>(int n, iterable<t> iter, func<t, any> key=None): pass
list<t> nsmallest<t>(int n, iterable<t> iter, func<t, any> key=None): pass
