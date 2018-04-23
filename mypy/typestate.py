"""
A shared state for all TypeInfo's that holds global cache and dependency information,
and potentially other mutable TypeInfo state.
"""

from typing import Dict, Set, Tuple

MYPY = False
if MYPY:
    from typing import ClassVar
    from mypy.nodes import TypeInfo
    from mypy.types import Instance


class State:
    # 'caches' and 'caches_proper' are subtype caches, implemented as sets of pairs
    # of (subtype, supertype), where supertypes are instances of given TypeInfo.
    # We need the caches, since subtype checks for structural types are very slow.
    caches = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]
    caches_proper = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]

    @classmethod
    def add_caches(cls, info: 'TypeInfo') -> None:
        cls.caches[info] = set()
        cls.caches_proper[info] = set()

    @classmethod
    def reset_caches(cls, info: 'TypeInfo') -> None:
        cls.caches[info].clear()
        cls.caches_proper[info].clear()

    @classmethod
    def is_cached_subtype_check(cls, left: 'Instance', right: 'Instance',
                                proper_subtype: bool = False) -> bool:
        info = right.type
        if proper_subtype:
            cache = cls.caches_proper[info]
        else:
            cache = cls.caches[info]
        return (left, right) in cache

    @classmethod
    def record_subtype_cache_entry(cls, left: 'Instance', right: 'Instance',
                                   proper_subtype: bool = False) -> None:
        info = right.type
        if proper_subtype:
            cache = cls.caches_proper[info]
        else:
            cache = cls.caches[info]
        cache.add((left, right))
