"""Type-annotated versions of the recipes from the itertools docs.

These are all meant to be examples of idiomatic itertools usage,
so they should all type-check without error.
"""

from __future__ import annotations

import collections
import math
import operator
import sys
from itertools import chain, combinations, count, cycle, filterfalse, groupby, islice, product, repeat, starmap, tee, zip_longest
from typing import (
    Any,
    Callable,
    Collection,
    Hashable,
    Iterable,
    Iterator,
    Literal,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import TypeAlias, TypeVarTuple, Unpack

_T = TypeVar("_T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_HashableT = TypeVar("_HashableT", bound=Hashable)
_Ts = TypeVarTuple("_Ts")


def take(n: int, iterable: Iterable[_T]) -> list[_T]:
    "Return first n items of the iterable as a list"
    return list(islice(iterable, n))


# Note: the itertools docs uses the parameter name "iterator",
# but the function actually accepts any iterable
# as its second argument
def prepend(value: _T1, iterator: Iterable[_T2]) -> Iterator[_T1 | _T2]:
    "Prepend a single value in front of an iterator"
    # prepend(1, [2, 3, 4]) --> 1 2 3 4
    return chain([value], iterator)


def tabulate(function: Callable[[int], _T], start: int = 0) -> Iterator[_T]:
    "Return function(0), function(1), ..."
    return map(function, count(start))


def repeatfunc(func: Callable[[Unpack[_Ts]], _T], times: int | None = None, *args: Unpack[_Ts]) -> Iterator[_T]:
    """Repeat calls to func with specified arguments.

    Example:  repeatfunc(random.random)
    """
    if times is None:
        return starmap(func, repeat(args))
    return starmap(func, repeat(args, times))


def flatten(list_of_lists: Iterable[Iterable[_T]]) -> Iterator[_T]:
    "Flatten one level of nesting"
    return chain.from_iterable(list_of_lists)


def ncycles(iterable: Iterable[_T], n: int) -> Iterator[_T]:
    "Returns the sequence elements n times"
    return chain.from_iterable(repeat(tuple(iterable), n))


def tail(n: int, iterable: Iterable[_T]) -> Iterator[_T]:
    "Return an iterator over the last n items"
    # tail(3, 'ABCDEFG') --> E F G
    return iter(collections.deque(iterable, maxlen=n))


# This function *accepts* any iterable,
# but it only *makes sense* to use it with an iterator
def consume(iterator: Iterator[object], n: int | None = None) -> None:
    "Advance the iterator n-steps ahead. If n is None, consume entirely."
    # Use functions that consume iterators at C speed.
    if n is None:
        # feed the entire iterator into a zero-length deque
        collections.deque(iterator, maxlen=0)
    else:
        # advance to the empty slice starting at position n
        next(islice(iterator, n, n), None)


@overload
def nth(iterable: Iterable[_T], n: int, default: None = None) -> _T | None: ...


@overload
def nth(iterable: Iterable[_T], n: int, default: _T1) -> _T | _T1: ...


def nth(iterable: Iterable[object], n: int, default: object = None) -> object:
    "Returns the nth item or a default value"
    return next(islice(iterable, n, None), default)


@overload
def quantify(iterable: Iterable[object]) -> int: ...


@overload
def quantify(iterable: Iterable[_T], pred: Callable[[_T], bool]) -> int: ...


def quantify(iterable: Iterable[object], pred: Callable[[Any], bool] = bool) -> int:
    "Given a predicate that returns True or False, count the True results."
    return sum(map(pred, iterable))


@overload
def first_true(
    iterable: Iterable[_T], default: Literal[False] = False, pred: Callable[[_T], bool] | None = None
) -> _T | Literal[False]: ...


@overload
def first_true(iterable: Iterable[_T], default: _T1, pred: Callable[[_T], bool] | None = None) -> _T | _T1: ...


def first_true(iterable: Iterable[object], default: object = False, pred: Callable[[Any], bool] | None = None) -> object:
    """Returns the first true value in the iterable.
    If no true value is found, returns *default*
    If *pred* is not None, returns the first item
    for which pred(item) is true.
    """
    # first_true([a,b,c], x) --> a or b or c or x
    # first_true([a,b], x, f) --> a if f(a) else b if f(b) else x
    return next(filter(pred, iterable), default)


_ExceptionOrExceptionTuple: TypeAlias = Union[Type[BaseException], Tuple[Type[BaseException], ...]]


@overload
def iter_except(func: Callable[[], _T], exception: _ExceptionOrExceptionTuple, first: None = None) -> Iterator[_T]: ...


@overload
def iter_except(
    func: Callable[[], _T], exception: _ExceptionOrExceptionTuple, first: Callable[[], _T1]
) -> Iterator[_T | _T1]: ...


def iter_except(
    func: Callable[[], object], exception: _ExceptionOrExceptionTuple, first: Callable[[], object] | None = None
) -> Iterator[object]:
    """Call a function repeatedly until an exception is raised.
    Converts a call-until-exception interface to an iterator interface.
    Like builtins.iter(func, sentinel) but uses an exception instead
    of a sentinel to end the loop.
    Examples:
        iter_except(functools.partial(heappop, h), IndexError)   # priority queue iterator
        iter_except(d.popitem, KeyError)                         # non-blocking dict iterator
        iter_except(d.popleft, IndexError)                       # non-blocking deque iterator
        iter_except(q.get_nowait, Queue.Empty)                   # loop over a producer Queue
        iter_except(s.pop, KeyError)                             # non-blocking set iterator
    """
    try:
        if first is not None:
            yield first()  # For database APIs needing an initial cast to db.first()
        while True:
            yield func()
    except exception:
        pass


def sliding_window(iterable: Iterable[_T], n: int) -> Iterator[tuple[_T, ...]]:
    # sliding_window('ABCDEFG', 4) --> ABCD BCDE CDEF DEFG
    it = iter(iterable)
    window = collections.deque(islice(it, n - 1), maxlen=n)
    for x in it:
        window.append(x)
        yield tuple(window)


def roundrobin(*iterables: Iterable[_T]) -> Iterator[_T]:
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
    # Recipe credited to George Sakkis
    num_active = len(iterables)
    nexts: Iterator[Callable[[], _T]] = cycle(iter(it).__next__ for it in iterables)
    while num_active:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            # Remove the iterator we just exhausted from the cycle.
            num_active -= 1
            nexts = cycle(islice(nexts, num_active))


def partition(pred: Callable[[_T], bool], iterable: Iterable[_T]) -> tuple[Iterator[_T], Iterator[_T]]:
    """Partition entries into false entries and true entries.
    If *pred* is slow, consider wrapping it with functools.lru_cache().
    """
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = tee(iterable)
    return filterfalse(pred, t1), filter(pred, t2)


def subslices(seq: Sequence[_T]) -> Iterator[Sequence[_T]]:
    "Return all contiguous non-empty subslices of a sequence"
    # subslices('ABCD') --> A AB ABC ABCD B BC BCD C CD D
    slices = starmap(slice, combinations(range(len(seq) + 1), 2))
    return map(operator.getitem, repeat(seq), slices)


def before_and_after(predicate: Callable[[_T], bool], it: Iterable[_T]) -> tuple[Iterator[_T], Iterator[_T]]:
    """Variant of takewhile() that allows complete
    access to the remainder of the iterator.
    >>> it = iter('ABCdEfGhI')
    >>> all_upper, remainder = before_and_after(str.isupper, it)
    >>> ''.join(all_upper)
    'ABC'
    >>> ''.join(remainder)     # takewhile() would lose the 'd'
    'dEfGhI'
    Note that the first iterator must be fully
    consumed before the second iterator can
    generate valid results.
    """
    it = iter(it)
    transition: list[_T] = []

    def true_iterator() -> Iterator[_T]:
        for elem in it:
            if predicate(elem):
                yield elem
            else:
                transition.append(elem)
                return

    def remainder_iterator() -> Iterator[_T]:
        yield from transition
        yield from it

    return true_iterator(), remainder_iterator()


@overload
def unique_everseen(iterable: Iterable[_HashableT], key: None = None) -> Iterator[_HashableT]: ...


@overload
def unique_everseen(iterable: Iterable[_T], key: Callable[[_T], Hashable]) -> Iterator[_T]: ...


def unique_everseen(iterable: Iterable[_T], key: Callable[[_T], Hashable] | None = None) -> Iterator[_T]:
    "List unique elements, preserving order. Remember all elements ever seen."
    # unique_everseen('AAAABBBCCDAABBB') --> A B C D
    # unique_everseen('ABBcCAD', str.lower) --> A B c D
    seen: set[Hashable] = set()
    if key is None:
        for element in filterfalse(seen.__contains__, iterable):
            seen.add(element)
            yield element
        # For order preserving deduplication,
        # a faster but non-lazy solution is:
        #     yield from dict.fromkeys(iterable)
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen.add(k)
                yield element
        # For use cases that allow the last matching element to be returned,
        # a faster but non-lazy solution is:
        #      t1, t2 = tee(iterable)
        #      yield from dict(zip(map(key, t1), t2)).values()


# Slightly adapted from the docs recipe; a one-liner was a bit much for pyright
def unique_justseen(iterable: Iterable[_T], key: Callable[[_T], bool] | None = None) -> Iterator[_T]:
    "List unique elements, preserving order. Remember only the element just seen."
    # unique_justseen('AAAABBBCCDAABBB') --> A B C D A B
    # unique_justseen('ABBcCAD', str.lower) --> A B c A D
    g: groupby[_T | bool, _T] = groupby(iterable, key)
    return map(next, map(operator.itemgetter(1), g))


def powerset(iterable: Iterable[_T]) -> Iterator[tuple[_T, ...]]:
    "powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


def polynomial_derivative(coefficients: Sequence[float]) -> list[float]:
    """Compute the first derivative of a polynomial.
    f(x)  =  x³ -4x² -17x + 60
    f'(x) = 3x² -8x  -17
    """
    # polynomial_derivative([1, -4, -17, 60]) -> [3, -8, -17]
    n = len(coefficients)
    powers = reversed(range(1, n))
    return list(map(operator.mul, coefficients, powers))


def nth_combination(iterable: Iterable[_T], r: int, index: int) -> tuple[_T, ...]:
    "Equivalent to list(combinations(iterable, r))[index]"
    pool = tuple(iterable)
    n = len(pool)
    c = math.comb(n, r)
    if index < 0:
        index += c
    if index < 0 or index >= c:
        raise IndexError
    result: list[_T] = []
    while r:
        c, n, r = c * r // n, n - 1, r - 1
        while index >= c:
            index -= c
            c, n = c * (n - r) // n, n - 1
        result.append(pool[-1 - n])
    return tuple(result)


if sys.version_info >= (3, 10):

    @overload
    def grouper(
        iterable: Iterable[_T], n: int, *, incomplete: Literal["fill"] = "fill", fillvalue: None = None
    ) -> Iterator[tuple[_T | None, ...]]: ...

    @overload
    def grouper(
        iterable: Iterable[_T], n: int, *, incomplete: Literal["fill"] = "fill", fillvalue: _T1
    ) -> Iterator[tuple[_T | _T1, ...]]: ...

    @overload
    def grouper(
        iterable: Iterable[_T], n: int, *, incomplete: Literal["strict", "ignore"], fillvalue: None = None
    ) -> Iterator[tuple[_T, ...]]: ...

    def grouper(
        iterable: Iterable[object], n: int, *, incomplete: Literal["fill", "strict", "ignore"] = "fill", fillvalue: object = None
    ) -> Iterator[tuple[object, ...]]:
        "Collect data into non-overlapping fixed-length chunks or blocks"
        # grouper('ABCDEFG', 3, fillvalue='x') --> ABC DEF Gxx
        # grouper('ABCDEFG', 3, incomplete='strict') --> ABC DEF ValueError
        # grouper('ABCDEFG', 3, incomplete='ignore') --> ABC DEF
        args = [iter(iterable)] * n
        if incomplete == "fill":
            return zip_longest(*args, fillvalue=fillvalue)
        if incomplete == "strict":
            return zip(*args, strict=True)
        if incomplete == "ignore":
            return zip(*args)
        else:
            raise ValueError("Expected fill, strict, or ignore")

    def transpose(it: Iterable[Iterable[_T]]) -> Iterator[tuple[_T, ...]]:
        "Swap the rows and columns of the input."
        # transpose([(1, 2, 3), (11, 22, 33)]) --> (1, 11) (2, 22) (3, 33)
        return zip(*it, strict=True)


if sys.version_info >= (3, 12):
    from itertools import batched

    def sum_of_squares(it: Iterable[float]) -> float:
        "Add up the squares of the input values."
        # sum_of_squares([10, 20, 30]) -> 1400
        return math.sumprod(*tee(it))

    def convolve(signal: Iterable[float], kernel: Iterable[float]) -> Iterator[float]:
        """Discrete linear convolution of two iterables.
        The kernel is fully consumed before the calculations begin.
        The signal is consumed lazily and can be infinite.
        Convolutions are mathematically commutative.
        If the signal and kernel are swapped,
        the output will be the same.
        Article:  https://betterexplained.com/articles/intuitive-convolution/
        Video:    https://www.youtube.com/watch?v=KuXjwB4LzSA
        """
        # convolve(data, [0.25, 0.25, 0.25, 0.25]) --> Moving average (blur)
        # convolve(data, [1/2, 0, -1/2]) --> 1st derivative estimate
        # convolve(data, [1, -2, 1]) --> 2nd derivative estimate
        kernel = tuple(kernel)[::-1]
        n = len(kernel)
        padded_signal = chain(repeat(0, n - 1), signal, repeat(0, n - 1))
        windowed_signal = sliding_window(padded_signal, n)
        return map(math.sumprod, repeat(kernel), windowed_signal)

    def polynomial_eval(coefficients: Sequence[float], x: float) -> float:
        """Evaluate a polynomial at a specific value.
        Computes with better numeric stability than Horner's method.
        """
        # Evaluate x³ -4x² -17x + 60 at x = 2.5
        # polynomial_eval([1, -4, -17, 60], x=2.5) --> 8.125
        n = len(coefficients)
        if not n:
            return type(x)(0)
        powers = map(pow, repeat(x), reversed(range(n)))
        return math.sumprod(coefficients, powers)

    def matmul(m1: Sequence[Collection[float]], m2: Sequence[Collection[float]]) -> Iterator[tuple[float, ...]]:
        "Multiply two matrices."
        # matmul([(7, 5), (3, 5)], [(2, 5), (7, 9)]) --> (49, 80), (41, 60)
        n = len(m2[0])
        return batched(starmap(math.sumprod, product(m1, transpose(m2))), n)
