# Stubs for unittest

# Based on http://docs.python.org/3.2/library/itertools.html

Iterator<int> count(int start=0, int step=1): pass # more general types?
Iterator<t> cycle<t>(Iterable<t> iter): pass
Iterator<t> repeat<t>(t object): pass
Iterator<t> repeat<t>(t object, int times): pass

Iterator<t> accumulate<t>(Iterable<t> iter): pass
Iterator<t> chain<t>(Iterable<t> *iterables): pass
# TODO chain.from_Iterable
Iterator<t> compress<t>(Iterable<t> data, Iterable<any> selectors): pass
Iterator<t> dropwhile<t>(func<t, any> predicate, Iterable<t> iter): pass
Iterator<t> filterfalse<t>(func<t, any> predicate, Iterable<t> iter): pass
Iterator<tuple<t, Iterator<t>>> \
                  groupby<t>(Iterable<t> iter): pass
Iterator<tuple<s, Iterator<t>>> \
                  groupby<t, s>(Iterable<t> iter, func<t, s> key): pass
Iterator<t> islice<t>(Iterable<t> iter, int stop): pass
Iterator<t> islice<t>(Iterable<t> iter, int start, int stop, int step=1): pass
Iterator<any> starmap(any func, Iterable<any> iter): pass
Iterator<t> takewhile<t>(func<t, any> predicate, Iterable<t> iter): pass
Iterator<any> tee(Iterable<any> iter, int n=2): pass
Iterator<any> zip_longest(Iterable<any> *p): pass # TODO fillvalue

Iterator<any> product(Iterable<any> *p): pass # TODO repeat
# TODO int with None default
Iterator<any> permutations(Iterable<any> iter, int r=None): pass
Iterable<any> combinations(Iterable<any> iter, int r): pass
Iterable<any> combinations_with_replacement(Iterable<any> iter, int r): pass
