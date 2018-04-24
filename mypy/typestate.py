"""
A shared state for all TypeInfos that holds global cache and dependency information,
and potentially other mutable TypeInfo state. This module contains mutable global state.
"""

from typing import Dict, Set, Tuple

MYPY = False
if MYPY:
    from typing import ClassVar
from mypy.nodes import TypeInfo
from mypy.types import Instance


class TypeState:
    """
    This class provides subtype caching to improve performance of subtype checks.

    Note: to avoid leaking global state, 'reset_all_subtype_caches()' should be called
    after a build has finished and after a daemon shutdown. This class only exists for
    performance reasons, resetting subtype caches for a class has no semantic effect.
    """

    # 'caches' and 'caches_proper' are subtype caches, implemented as sets of pairs
    # of (subtype, supertype), where supertypes are instances of given TypeInfo.
    # We need the caches, since subtype checks for structural types are very slow.
    # _subtype_caches_proper is for caching proper subtype checks (i.e. not assuming that
    # Any is consistent with every type).
    _subtype_caches = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]
    _subtype_caches_proper = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]

    @classmethod
    def reset_all_subtype_caches(cls) -> None:
        """Completely reset all known subtype caches."""
        cls._subtype_caches = {}
        cls._subtype_caches_proper = {}

    @classmethod
    def reset_subtype_caches_for(cls, info: TypeInfo) -> None:
        """Reset subtype caches (if any) for a given supertype TypeInfo."""
        cls._subtype_caches.setdefault(info, set()).clear()
        cls._subtype_caches_proper.setdefault(info, set()).clear()

    @classmethod
    def reset_all_subtype_caches_for(cls, info: TypeInfo) -> None:
        """Reset subtype caches (if any) for a given supertype TypeInfo and its MRO."""
        for item in info.mro:
            cls.reset_subtype_caches_for(item)

    @classmethod
    def is_cached_subtype_check(cls, left: Instance, right: Instance) -> bool:
        return (left, right) in cls._subtype_caches.setdefault(right.type, set())

    @classmethod
    def is_cached_proper_subtype_check(cls, left: Instance, right: Instance) -> bool:
        return (left, right) in cls._subtype_caches_proper.setdefault(right.type, set())

    @classmethod
    def record_subtype_cache_entry(cls, left: Instance, right: Instance) -> None:
        cls._subtype_caches.setdefault(right.type, set()).add((left, right))

    @classmethod
    def record_proper_subtype_cache_entry(cls, left: Instance, right: Instance) -> None:
        cls._subtype_caches_proper.setdefault(right.type, set()).add((left, right))
