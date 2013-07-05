# Stubs for itertools

# Based on http://docs.python.org/3.2/library/itertools.html

from typing import Iterator, typevar, Iterable, overload, Any, Function, Tuple

T = typevar('T')
S = typevar('S')

def count(start: int = 0,
          step: int = 1) -> Iterator[int]: pass # more general types?
def cycle(iterable: Iterable[T]) -> Iterator[T]: pass

@overload
def repeat(object: T) -> Iterator[T]: pass
@overload
def repeat(object: T, times: int) -> Iterator[T]: pass

def accumulate(iterable: Iterable[T]) -> Iterator[T]: pass
def chain( *iterables: Iterable[T]) -> Iterator[T]: pass
# TODO chain.from_Iterable
def compress(data: Iterable[T], selectors: Iterable[Any]) -> Iterator[T]: pass
def dropwhile(predicate: Function[[T], Any],
              iterable: Iterable[T]) -> Iterator[T]: pass
def filterfalse(predicate: Function[[T], Any],
                iterable: Iterable[T]) -> Iterator[T]: pass

@overload
def groupby(iterable: Iterable[T]) -> Iterator[Tuple[T, Iterator[T]]]: pass
@overload
def groupby(iterable: Iterable[T],
            key: Function[[T], S]) -> Iterator[Tuple[S, Iterator[T]]]: pass

@overload
def islice(iterable: Iterable[T], stop: int) -> Iterator[T]: pass
@overload
def islice(iterable: Iterable[T], start: int, stop: int,
           step: int = 1) -> Iterator[T]: pass

def starmap(func: Any, iterable: Iterable[Any]) -> Iterator[Any]: pass
def takewhile(predicate: Function[[T], Any],
              iterable: Iterable[T]) -> Iterator[T]: pass
def tee(iterable: Iterable[Any], n: int = 2) -> Iterator[Any]: pass
def zip_longest( *p: Iterable[Any]) -> Iterator[Any]: pass # TODO fillvalue

def product( *p: Iterable[Any]) -> Iterator[Any]: pass # TODO repeat
# TODO int with None default
def permutations(iterable: Iterable[Any], r: int = None) -> Iterator[Any]: pass
def combinations(iterable: Iterable[Any], r: int) -> Iterable[Any]: pass
def combinations_with_replacement(iterable: Iterable[Any],
                                  r: int) -> Iterable[Any]: pass
