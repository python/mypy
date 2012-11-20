# Stubs for unittest

# Based on http://docs.python.org/3.2/library/itertools.html

iterator<int> count(int start=0, int step=1): pass # more general types?
iterator<t> cycle<t>(iterable<t> iter): pass
iterator<t> repeat<t>(t object): pass
iterator<t> repeat<t>(t object, int times): pass

iterator<t> accumulate<t>(iterable<t> iter): pass
iterator<t> chain<t>(iterable<t> *iterables): pass
# TODO chain.from_iterable
iterator<t> compress<t>(iterable<t> data, iterable<any> selectors): pass
iterator<t> dropwhile<t>(func<t, any> predicate, iterable<t> iter): pass
iterator<t> filterfalse<t>(func<t, any> predicate, iterable<t> iter): pass
iterator<tuple<t, iterator<t>>> \
                  groupby<t>(iterable<t> iter): pass
iterator<tuple<s, iterator<t>>> \
                  groupby<t, s>(iterable<t> iter, func<t, s> key): pass
iterator<t> islice<t>(iterable<t> iter, int stop): pass
iterator<t> islice<t>(iterable<t> iter, int start, int stop, int step=1): pass
iterator<any> starmap(any func, iterable<any> iter): pass
iterator<t> takewhile<t>(func<t, any> predicate, iterable<t> iter): pass
iterator<any> tee(iterable<any> iter, int n=2): pass
iterator<any> zip_longest(iterable<any> *p): pass # TODO fillvalue

iterator<any> product(iterable<any> *p): pass # TODO repeat
# TODO int with None default
iterator<any> permutations(iterable<any> iter, int r=None): pass
iterable<any> combinations(iterable<any> iter, int r): pass
iterable<any> combinations_with_replacement(iterable<any> iter, int r): pass
