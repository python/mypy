import sys
from _typeshed import SupportsRichComparisonT
from typing import Callable, MutableSequence, Sequence, TypeVar, overload

_T = TypeVar("_T")

if sys.version_info >= (3, 10):
    @overload
    def bisect_left(
        a: Sequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ..., *, key: None = ...
    ) -> int: ...
    @overload
    def bisect_left(
        a: Sequence[_T],
        x: SupportsRichComparisonT,
        lo: int = ...,
        hi: int | None = ...,
        *,
        key: Callable[[_T], SupportsRichComparisonT] = ...,
    ) -> int: ...
    @overload
    def bisect_right(
        a: Sequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ..., *, key: None = ...
    ) -> int: ...
    @overload
    def bisect_right(
        a: Sequence[_T],
        x: SupportsRichComparisonT,
        lo: int = ...,
        hi: int | None = ...,
        *,
        key: Callable[[_T], SupportsRichComparisonT] = ...,
    ) -> int: ...
    @overload
    def insort_left(
        a: MutableSequence[SupportsRichComparisonT],
        x: SupportsRichComparisonT,
        lo: int = ...,
        hi: int | None = ...,
        *,
        key: None = ...,
    ) -> None: ...
    @overload
    def insort_left(
        a: MutableSequence[_T], x: _T, lo: int = ..., hi: int | None = ..., *, key: Callable[[_T], SupportsRichComparisonT] = ...
    ) -> None: ...
    @overload
    def insort_right(
        a: MutableSequence[SupportsRichComparisonT],
        x: SupportsRichComparisonT,
        lo: int = ...,
        hi: int | None = ...,
        *,
        key: None = ...,
    ) -> None: ...
    @overload
    def insort_right(
        a: MutableSequence[_T], x: _T, lo: int = ..., hi: int | None = ..., *, key: Callable[[_T], SupportsRichComparisonT] = ...
    ) -> None: ...

else:
    def bisect_left(
        a: Sequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ...
    ) -> int: ...
    def bisect_right(
        a: Sequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ...
    ) -> int: ...
    def insort_left(
        a: MutableSequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ...
    ) -> None: ...
    def insort_right(
        a: MutableSequence[SupportsRichComparisonT], x: SupportsRichComparisonT, lo: int = ..., hi: int | None = ...
    ) -> None: ...
