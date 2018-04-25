"""
A shared state for all TypeInfos that holds global cache and dependency information,
and potentially other mutable TypeInfo state. This module contains mutable global state.
"""

from typing import Dict, Set, Tuple, Optional

MYPY = False
if MYPY:
    from typing import ClassVar
from mypy.nodes import TypeInfo
from mypy.types import Instance
from mypy.server.trigger import make_trigger


class TypeState:
    """
    This class provides subtype caching to improve performance of subtype checks.
    As well it holds protocol fine grained dependencies.

    Note: to avoid leaking global state, 'reset_all_subtype_caches()' should be called
    after a build has finished and after a daemon shutdown. This subtype cache only exists for
    performance reasons, resetting subtype caches for a class has no semantic effect.
    The protocol dependencies however are only stored here, and shouldn't be deleted unless
    no more needed (e.g. during daemon shutdown).
    """

    # 'caches' and 'caches_proper' are subtype caches, implemented as sets of pairs
    # of (subtype, supertype), where supertypes are instances of given TypeInfo.
    # We need the caches, since subtype checks for structural types are very slow.
    # _subtype_caches_proper is for caching proper subtype checks (i.e. not assuming that
    # Any is consistent with every type).
    _subtype_caches = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]
    _subtype_caches_proper = {}  # type: ClassVar[Dict[TypeInfo, Set[Tuple[Instance, Instance]]]]

    # This contains protocol dependencies generated after running a full build,
    # or after an update. These dependencies are special because:
    #   * They are a global property of the program; i.e. some dependencies for imported
    #     classes can be generated in the importing modules.
    #   * Because of the above, they are serialized separately, after a full run,
    #     or a full update.
    # `proto_deps` can be None if after deserialization it turns out that they are
    # inconsistent with the other cache files (or an error occurred during deserialization).
    # A blocking error will be generated in this case, since we can't proceed safely.
    proto_deps = {}  # type: Optional[Dict[str, Set[str]]]

    # Protocols (full names) a given class attempted to implement.
    # Used to calculate fine grained protocol dependencies and optimize protocol
    # subtype cache invalidation in fine grained mode.
    _attempted_protocols = {}  # type: Dict[TypeInfo, Set[str]]
    # We also snapshot protocol members of the above protocols.
    _checked_against_members = {}  # type: Dict[TypeInfo, Set[str]]
    # TypeInfos that has been type-checked since latest dependency snapshot update.
    # This is an optimisation for fine grained mode; during a full run we only take
    # a dependency snapshot at the very end, so this set will contain all type-checked
    # TypeInfos. After a fine grained update however, we can gather new dependencies only
    # from few TypeInfos that were type-checked during this update, because these are
    # the only that can generate new protocol dependencies.
    _rechecked_types = set()  # type: Set[TypeInfo]

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

    @classmethod
    def reset_protocol_deps(cls) -> None:
        cls.proto_deps = {}
        cls._attempted_protocols = {}
        cls._checked_against_members = {}
        cls._rechecked_types = set()

    @classmethod
    def record_protocol_subtype_check(cls, left_type: TypeInfo, right_type: TypeInfo) -> None:
        assert right_type.is_protocol
        cls._rechecked_types.add(left_type)
        cls._attempted_protocols.setdefault(left_type, set()).add(right_type.fullname())
        cls._checked_against_members.setdefault(left_type,
                                                set()).update(right_type.protocol_members)

    @classmethod
    def snapshot_protocol_deps(cls) -> Dict[str, Set[str]]:
        """Collect protocol attribute dependencies found so far from registered subtype checks.

        There are three kinds of protocol dependencies. For example, after a subtype check:

            x: Proto = C()

        the following dependencies will be generated:
            1. ..., <SuperProto[wildcard]>, <Proto[wildcard]> -> <Proto>
            2. ..., <B.attr>, <C.attr> -> <C> [for every attr in Proto members]
            3. <C> -> Proto  # this one to invalidate the subtype cache

        The first kind is generated immediately per-module in deps.py. While two other kinds are
        generated here after all modules are type checked anf we have recorded all the subtype
        checks.
        """
        deps = {}  # type: Dict[str, Set[str]]
        for info in cls._rechecked_types:
            for attr in cls._checked_against_members[info]:
                # The need for full MRO here is subtle, during an update, base classes of
                # a concrete class may not be reprocessed, so not all <B.x> -> <C.x> deps
                # are added.
                for base_info in info.mro[:-1]:
                    trigger = make_trigger('%s.%s' % (base_info.fullname(), attr))
                    if 'typing' in trigger or 'builtins' in trigger:
                        # TODO: avoid everything from typeshed
                        continue
                    deps.setdefault(trigger, set()).add(make_trigger(info.fullname()))
            for proto in cls._attempted_protocols[info]:
                trigger = make_trigger(info.fullname())
                if 'typing' in trigger or 'builtins' in trigger:
                    continue
                # If any class that was checked against a protocol changes,
                # we need to reset the subtype cache for the protocol.
                #
                # Note: strictly speaking, the protocol doesn't need to be
                # re-checked, we only need to reset the cache, and its uses
                # elsewhere are still valid (unless invalidated by other deps).
                deps.setdefault(trigger, set()).add(proto)
        return deps

    @classmethod
    def update_protocol_deps(cls, second_map: Optional[Dict[str, Set[str]]] = None) -> None:
        """Update global protocol dependency map.

        We update the global map incrementally, using a snapshot only from recently
        type checked types. If second_map is given, update it as well. This is currently used
        by FineGrainedBuildManager that maintains normal (non-protocol) dependencies.
        """
        if cls.proto_deps is None:
            # Unsuccesful cache loading, nothing to do.
            return
        new_deps = cls.snapshot_protocol_deps()
        for trigger, targets in new_deps.items():
            cls.proto_deps.setdefault(trigger, set()).update(targets)
        if second_map is not None:
            for trigger, targets in new_deps.items():
                second_map.setdefault(trigger, set()).update(targets)
        cls._rechecked_types.clear()


def reset_global_state() -> None:
    """Reset all existing global states. Currently they are all in this module."""
    TypeState.reset_all_subtype_caches()
    TypeState.reset_protocol_deps()
