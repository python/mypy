# Stubs for itertools

# Based on http://docs.python.org/3.2/library/itertools.html

from typing import (Iterator, typevar, Iterable, overload, Any, Function, Tuple,
                    Union, Sequence)

_T = typevar('_T')
_S = typevar('_S')

def count(start: int = 0,
          step: int = 1) -> Iterator[int]: pass # more general types?
def cycle(iterable: Iterable[_T]) -> Iterator[_T]: pass

@overload
def repeat(object: _T) -> Iterator[_T]: pass
@overload
def repeat(object: _T, times: int) -> Iterator[_T]: pass

def accumulate(iterable: Iterable[_T]) -> Iterator[_T]: pass
def chain(*iterables: Iterable[_T]) -> Iterator[_T]: pass
# TODO chain.from_Iterable
def compress(data: Iterable[_T], selectors: Iterable[Any]) -> Iterator[_T]: pass
def dropwhile(predicate: Function[[_T], Any],
              iterable: Iterable[_T]) -> Iterator[_T]: pass
def filterfalse(predicate: Function[[_T], Any],
                iterable: Iterable[_T]) -> Iterator[_T]: pass

@overload
def groupby(iterable: Iterable[_T]) -> Iterator[Tuple[_T, Iterator[_T]]]: pass
@overload
def groupby(iterable: Iterable[_T],
            key: Function[[_T], _S]) -> Iterator[Tuple[_S, Iterator[_T]]]: pass

@overload
def islice(iterable: Iterable[_T], stop: int) -> Iterator[_T]: pass
@overload
def islice(iterable: Iterable[_T], start: int, stop: int,
           step: int = 1) -> Iterator[_T]: pass

def starmap(func: Any, iterable: Iterable[Any]) -> Iterator[Any]: pass
def takewhile(predicate: Function[[_T], Any],
              iterable: Iterable[_T]) -> Iterator[_T]: pass
def tee(iterable: Iterable[Any], n: int = 2) -> Iterator[Any]: pass
def zip_longest(*p: Iterable[Any],
                fillvalue: Any = None) -> Iterator[Any]: pass

# TODO: Return type should be Iterator[Tuple[..]], but unknown tuple shape.
#       Iterator[Sequence[_T]] loses this type information.
def product(*p: Iterable[_T], repeat: int = 1) -> Iterator[Sequence[_T]]: pass

def permutations(iterable: Iterable[_T],
                 r: Union[int, None] = None) -> Iterator[Sequence[_T]]: pass
def combinations(iterable: Iterable[_T],
                 r: int) -> Iterable[Sequence[_T]]: pass
def combinations_with_replacement(iterable: Iterable[_T],
                                  r: int) -> Iterable[Sequence[_T]]: pass
