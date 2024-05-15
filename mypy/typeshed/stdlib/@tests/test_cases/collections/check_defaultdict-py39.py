"""
Tests for `defaultdict.__or__` and `defaultdict.__ror__`.
These methods were only added in py39.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Mapping, TypeVar, Union
from typing_extensions import Self, assert_type

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


if sys.version_info >= (3, 9):

    class CustomDefaultDictSubclass(defaultdict[_KT, _VT]):
        pass

    class CustomMappingWithDunderOr(Mapping[_KT, _VT]):
        def __or__(self, other: Mapping[_KT, _VT]) -> dict[_KT, _VT]:
            return {}

        def __ror__(self, other: Mapping[_KT, _VT]) -> dict[_KT, _VT]:
            return {}

        def __ior__(self, other: Mapping[_KT, _VT]) -> Self:
            return self

    def test_defaultdict_dot_or(
        a: defaultdict[int, int],
        b: CustomDefaultDictSubclass[int, int],
        c: defaultdict[str, str],
        d: Mapping[int, int],
        e: CustomMappingWithDunderOr[str, str],
    ) -> None:
        assert_type(a | b, defaultdict[int, int])

        # In contrast to `dict.__or__`, `defaultdict.__or__` returns `Self` if called on a subclass of `defaultdict`:
        assert_type(b | a, CustomDefaultDictSubclass[int, int])

        assert_type(a | c, defaultdict[Union[int, str], Union[int, str]])

        # arbitrary mappings are not accepted by `defaultdict.__or__`;
        # it has to be a subclass of `dict`
        a | d  # type: ignore

        # but Mappings such as `os._Environ` or `CustomMappingWithDunderOr`,
        # which define `__ror__` methods that accept `dict`, are fine
        # (`os._Environ.__(r)or__` always returns `dict`, even if a `defaultdict` is passed):
        assert_type(a | os.environ, dict[Union[str, int], Union[str, int]])
        assert_type(os.environ | a, dict[Union[str, int], Union[str, int]])

        assert_type(c | os.environ, dict[str, str])
        assert_type(c | e, dict[str, str])

        assert_type(os.environ | c, dict[str, str])
        assert_type(e | c, dict[str, str])

        e |= c
        e |= a  # type: ignore

        # TODO: this test passes mypy, but fails pyright for some reason:
        # c |= e

        c |= a  # type: ignore
